from __future__ import annotations

import math
from datetime import datetime, timezone
from statistics import fmean, pstdev

from .schemas import FaultClassificationResponse, FaultClassProbability, PredictResponse
from .simulator import get_asset


FAULT_LABELS = {
    "00": "정상",
    "01": "베어링 불량",
    "02": "회전체 불평형",
    "03": "축정렬 불량",
    "04": "벨트 느슨함",
}


def predict_fault_class(
    asset_id: str | None = None,
    window: list[dict[str, float]] | None = None,
    rul_prediction: PredictResponse | None = None,
) -> FaultClassificationResponse:
    selected_asset_id = asset_id or "INJ-03"
    asset = get_asset(selected_asset_id)
    features = _factory_sensor_features(asset.sensors, window)
    risk_factor = (rul_prediction.risk_72h / 100.0) if rul_prediction else asset.risk_72h / 100.0
    anomaly = rul_prediction.anomaly_score if rul_prediction else asset.anomaly_score

    vibration = max(features["vibration_change"], features["vibration_volatility"])
    current = max(features["current_change"], features["current_volatility"])
    temp = features["temperature_change"]
    pressure_drop = features["pressure_drop"]
    drift = max(vibration, current, temp, pressure_drop, anomaly)

    scores = {
        "00": 1.25 - 1.45 * risk_factor - 1.10 * drift,
        "01": 0.10 + 0.52 * vibration + 0.27 * current + 0.16 * risk_factor,
        "02": 0.08 + 0.58 * vibration + 0.16 * features["vibration_volatility"] + 0.08 * risk_factor,
        "03": 0.06 + 0.36 * vibration + 0.24 * pressure_drop + 0.22 * temp + 0.10 * risk_factor,
        "04": 0.05 + 0.42 * current + 0.25 * pressure_drop + 0.10 * temp + 0.08 * risk_factor,
    }
    probabilities = _softmax(scores)
    ranked = sorted(probabilities.items(), key=lambda item: item[1], reverse=True)
    fault_code, fault_probability = ranked[0]

    return FaultClassificationResponse(
        asset_id=asset.asset_id,
        model_version="factory-sensor-fault-classifier-v0.1",
        fault_code=fault_code,
        fault_label=FAULT_LABELS[fault_code],
        fault_probability=round(fault_probability, 3),
        is_fault=fault_code != "00",
        top_classes=[
            FaultClassProbability(code=code, label=FAULT_LABELS[code], probability=round(probability, 3))
            for code, probability in ranked[:3]
        ],
        evidence=_evidence(features, risk_factor, anomaly),
        source="실시간 공장 센서 윈도우 기반 경량 분류 모델. AI-Hub 전류/진동 학습 모델로 교체 가능.",
        generated_at=datetime.now(timezone.utc),
    )


def _factory_sensor_features(sensors, window: list[dict[str, float]] | None) -> dict[str, float]:
    by_key = {sensor.key: sensor for sensor in sensors}
    features = {
        "vibration_change": _sensor_change(by_key, "vibration_rms"),
        "current_change": _sensor_change(by_key, "motor_current_cv"),
        "temperature_change": _sensor_change(by_key, "hydraulic_temp"),
        "pressure_drop": max(0.0, -_sensor_change(by_key, "oil_pressure")),
        "vibration_volatility": 0.0,
        "current_volatility": 0.0,
    }
    if window:
        features["vibration_change"] = max(features["vibration_change"], _window_change(window, "vibration_rms"))
        features["current_change"] = max(features["current_change"], _window_change(window, "motor_current_cv"))
        features["temperature_change"] = max(features["temperature_change"], _window_change(window, "hydraulic_temp"))
        features["pressure_drop"] = max(features["pressure_drop"], -_window_change(window, "oil_pressure"))
        features["vibration_volatility"] = _window_cv(window, "vibration_rms")
        features["current_volatility"] = _window_cv(window, "motor_current_cv")
    return {key: _clip(value) for key, value in features.items()}


def _sensor_change(by_key: dict, key: str) -> float:
    sensor = by_key.get(key)
    if sensor is None or not sensor.baseline:
        return 0.0
    return _clip((sensor.current - sensor.baseline) / abs(sensor.baseline))


def _window_change(window: list[dict[str, float]], key: str) -> float:
    values = [float(row[key]) for row in window if key in row]
    if len(values) < 2:
        return 0.0
    baseline = values[0] if abs(values[0]) > 1e-6 else 1.0
    return _clip((values[-1] - values[0]) / abs(baseline))


def _window_cv(window: list[dict[str, float]], key: str) -> float:
    values = [float(row[key]) for row in window if key in row]
    if len(values) < 3:
        return 0.0
    mean = abs(fmean(values)) or 1.0
    return _clip(pstdev(values) / mean)


def _softmax(scores: dict[str, float]) -> dict[str, float]:
    max_score = max(scores.values())
    exp_scores = {key: math.exp((value - max_score) * 3.0) for key, value in scores.items()}
    total = sum(exp_scores.values()) or 1.0
    return {key: value / total for key, value in exp_scores.items()}


def _evidence(features: dict[str, float], risk_factor: float, anomaly: float) -> list[str]:
    candidates = [
        ("진동 변화/변동성", max(features["vibration_change"], features["vibration_volatility"])),
        ("모터 전류 변동성", max(features["current_change"], features["current_volatility"])),
        ("유압 온도 상승", features["temperature_change"]),
        ("유압 압력 저하", features["pressure_drop"]),
        ("RUL 기반 위험도", risk_factor),
        ("이상 점수", anomaly),
    ]
    ranked = sorted(candidates, key=lambda item: item[1], reverse=True)
    return [f"{label}: {value * 100:.1f}%" for label, value in ranked[:4]]


def _clip(value: float) -> float:
    return max(0.0, min(1.0, float(value)))
