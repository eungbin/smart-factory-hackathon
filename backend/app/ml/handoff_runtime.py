from __future__ import annotations

from functools import lru_cache
import importlib.util
import math
import warnings
from pathlib import Path
from statistics import mean, pstdev
from typing import Any

from app.db.models import EquipmentStatus, FaultTypeCode
from app.ml.contracts import FaultProbability, InferenceResult, RootSensor, SensorPoint, SensorWindow


MODEL_VERSION = "handoff_adapter_v1"
WINDOW_SIZE = 50
RUL_FEATURE_SIZE = 31
RUL_CAP = 125
ENSEMBLE_WEIGHTS = {"gru": 0.30, "tcn": 0.35, "patchtst": 0.35}
SENSOR_SCORE_WEIGHTS = {
    "vibration_rms_g": 0.35,
    "hydraulic_temp_c": 0.25,
    "motor_current_a": 0.25,
    "hydraulic_pressure_bar": 0.15,
}

FAULT_CODES = [
    FaultTypeCode.normal,
    FaultTypeCode.bearing_fault,
    FaultTypeCode.rotor_unbalance,
    FaultTypeCode.shaft_misalignment,
    FaultTypeCode.belt_loose,
]

AIHUB_CODE_MAP = {
    "00": FaultTypeCode.normal,
    "01": FaultTypeCode.bearing_fault,
    "02": FaultTypeCode.rotor_unbalance,
    "03": FaultTypeCode.shaft_misalignment,
    "04": FaultTypeCode.belt_loose,
}


def infer(window: SensorWindow) -> InferenceResult:
    points = _pad_points(window.points, WINDOW_SIZE)
    sensor_profile = _sensor_profile(points)
    synthetic_window = _synthetic_cmapss_window(points, sensor_profile)

    model_rul_hours, rul_detail = _predict_rul(synthetic_window, sensor_profile)
    rul_hours, calibration_detail = _calibrate_rul(model_rul_hours, sensor_profile)
    rul_detail = {**rul_detail, **calibration_detail}
    risk_pct, risk_detail = _combined_risk(rul_hours, sensor_profile)
    fault_probabilities, fault_detail = _predict_fault_probabilities(points, sensor_profile, risk_pct)
    fault_type, fault_confidence = _representative_fault(fault_probabilities, risk_pct)
    fault_detail = {
        **fault_detail,
        "representative_fault_type": fault_type.value,
        "representative_fault_confidence_pct": fault_confidence,
    }
    status = _status_from_risk(risk_pct, fault_type)
    root_sensors = _root_sensors(sensor_profile)

    return InferenceResult(
        status=status,
        rul_hours=rul_hours,
        rul_lower_hours=max(0, rul_hours - 18),
        rul_upper_hours=rul_hours + 18,
        risk_pct=risk_pct,
        fault_type_code=fault_type,
        fault_confidence_pct=fault_confidence,
        fault_probabilities=fault_probabilities,
        root_sensors=root_sensors,
        summary=f"{MODEL_VERSION} rul={rul_hours} risk={risk_pct}",
        raw_output={
            "model": MODEL_VERSION,
            "rul_source": "synthetic_cmapss_adapter",
            "fault_source": "aihub_feature_adapter",
            "visible_sensor_count": 4,
            "synthetic_rul_feature_shape": [WINDOW_SIZE, RUL_FEATURE_SIZE],
            "rul_detail": rul_detail,
            "fault_detail": fault_detail,
            "sensor_degradation_score": calibration_detail["sensor_degradation_score"],
            "risk_detail": risk_detail,
            "adapter_scores": sensor_profile["scores"],
            "warning": "RUL uses synthetic C-MAPSS-like features plus a four-sensor calibration layer.",
        },
    )


def _pad_points(points: list[SensorPoint], size: int) -> list[SensorPoint]:
    if not points:
        raise ValueError("SensorWindow must contain at least one point.")
    ordered = sorted(points, key=lambda point: point.measured_at)
    if len(ordered) >= size:
        return ordered[-size:]
    return [ordered[0]] * (size - len(ordered)) + ordered


def _sensor_profile(points: list[SensorPoint]) -> dict[str, Any]:
    vibration_values = [point.vibration_rms_g for point in points]
    temperature_values = [point.hydraulic_temp_c for point in points]
    current_values = [point.motor_current_a for point in points]
    pressure_values = [point.hydraulic_pressure_bar for point in points]

    scores = {
        "vibration_rms_g": _score(mean(vibration_values), 1.0, 4.5),
        "hydraulic_temp_c": _score(mean(temperature_values), 65.0, 95.0),
        "motor_current_a": _score(mean(current_values), 21.0, 35.0),
        "hydraulic_pressure_bar": _score(abs(mean(pressure_values) - 145.0), 3.0, 25.0),
    }
    trends = {
        "vibration_rms_g": _trend(vibration_values),
        "hydraulic_temp_c": _trend(temperature_values),
        "motor_current_a": _trend(current_values),
        "hydraulic_pressure_bar": -_trend(pressure_values),
    }
    volatility = {
        "vibration_rms_g": _cv(vibration_values),
        "hydraulic_temp_c": _cv(temperature_values),
        "motor_current_a": _cv(current_values),
        "hydraulic_pressure_bar": _cv(pressure_values),
    }
    degradation = _clamp(
        scores["vibration_rms_g"] * 0.35
        + scores["hydraulic_temp_c"] * 0.22
        + scores["motor_current_a"] * 0.28
        + scores["hydraulic_pressure_bar"] * 0.15
        + max(trends.values()) * 0.20,
        0.0,
        1.0,
    )
    return {
        "values": {
            "vibration_rms_g": vibration_values,
            "hydraulic_temp_c": temperature_values,
            "motor_current_a": current_values,
            "hydraulic_pressure_bar": pressure_values,
        },
        "scores": scores,
        "trends": trends,
        "volatility": volatility,
        "degradation": degradation,
    }


def _synthetic_cmapss_window(points: list[SensorPoint], profile: dict[str, Any]) -> list[list[float]]:
    sensor_weights = [
        0.55,
        0.35,
        0.42,
        0.65,
        0.20,
        0.30,
        0.45,
        0.62,
        0.58,
        0.25,
        0.48,
        0.38,
        0.52,
        0.50,
        0.33,
        0.28,
        0.44,
        0.22,
        0.24,
        0.40,
        0.47,
    ]
    degradation = float(profile["degradation"])
    trend = max(float(value) for value in profile["trends"].values())
    volatility = max(float(value) for value in profile["volatility"].values())
    condition_id = min(5, max(0, int(round(degradation * 5))))
    rows: list[list[float]] = []
    for index, point in enumerate(points):
        time_ratio = index / max(1, len(points) - 1)
        local = _local_degradation(point, profile)
        sensors = [
            (local * weight + trend * 0.25 * time_ratio + volatility * 0.10) * 2.0 - 0.7
            for weight in sensor_weights
        ]
        conditions = [1.0 if item == condition_id else 0.0 for item in range(6)]
        subset = [0.0, 0.0, 0.0, 1.0]
        rows.append([*sensors, *conditions, *subset])
    return rows


def _local_degradation(point: SensorPoint, profile: dict[str, Any]) -> float:
    return _clamp(
        _score(point.vibration_rms_g, 1.0, 4.5) * 0.35
        + _score(point.hydraulic_temp_c, 65.0, 95.0) * 0.22
        + _score(point.motor_current_a, 21.0, 35.0) * 0.28
        + _score(abs(point.hydraulic_pressure_bar - 145.0), 3.0, 25.0) * 0.15
        + float(profile["degradation"]) * 0.15,
        0.0,
        1.0,
    )


def _predict_rul(synthetic_window: list[list[float]], profile: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    model_prediction = _predict_rul_with_checkpoints(synthetic_window)
    if model_prediction is not None:
        return model_prediction, {"mode": "checkpoint_ensemble", "weights": ENSEMBLE_WEIGHTS}
    degradation = float(profile["degradation"])
    rul = int(round(_clamp(RUL_CAP - degradation * 101, 24, RUL_CAP)))
    return rul, {"mode": "surrogate", "reason": _cmapss_unavailable_reason()}


def _predict_rul_with_checkpoints(synthetic_window: list[list[float]]) -> int | None:
    loaded = _load_cmapss_models()
    if loaded is None:
        return None
    torch_module, models = loaded
    tensor = torch_module.tensor([synthetic_window], dtype=torch_module.float32)
    weighted = 0.0
    with torch_module.no_grad():
        for name, weight in ENSEMBLE_WEIGHTS.items():
            prediction = float(models[name](tensor).detach().cpu().numpy()[0]) * RUL_CAP
            weighted += prediction * weight
    return int(round(_clamp(weighted, 0, RUL_CAP)))


def _calibrate_rul(model_rul_hours: int, profile: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    sensor_score = _sensor_degradation_score(profile)
    penalty_hours = int(round(sensor_score * 58))
    sensor_based_rul = int(round(_clamp(RUL_CAP - sensor_score * 101, 12, RUL_CAP)))
    adjusted_rul = int(round(_clamp(min(model_rul_hours - penalty_hours, sensor_based_rul), 12, RUL_CAP)))
    return adjusted_rul, {
        "model_rul_hours": model_rul_hours,
        "sensor_degradation_score": round(sensor_score, 4),
        "sensor_penalty_hours": penalty_hours,
        "sensor_based_rul_hours": sensor_based_rul,
        "adjusted_rul_hours": adjusted_rul,
        "calibration_formula": "min(model_rul - sensor_penalty, sensor_based_rul)",
    }


def _sensor_degradation_score(profile: dict[str, Any]) -> float:
    scores = profile["scores"]
    trends = profile["trends"]
    volatility = profile["volatility"]
    weighted_score = sum(float(scores[name]) * weight for name, weight in SENSOR_SCORE_WEIGHTS.items())
    weighted_trend = sum(max(0.0, float(trends[name])) * weight for name, weight in SENSOR_SCORE_WEIGHTS.items())
    weighted_volatility = sum(float(volatility[name]) * weight for name, weight in SENSOR_SCORE_WEIGHTS.items())
    return float(_clamp(weighted_score * 0.75 + weighted_trend * 0.15 + weighted_volatility * 0.10, 0.0, 1.0))


@lru_cache(maxsize=1)
def _load_cmapss_models():
    try:
        import torch
    except Exception:
        return None
    model_module = _load_handoff_ml_model_module()
    if model_module is None:
        return None
    model_dir = _handoff_root() / "data" / "models" / "validated_gru_tcn_patchtst_seed42"
    specs = {
        "gru": ("cmapss_gru_best.pt", "GRURULRegressor"),
        "tcn": ("cmapss_tcn_best.pt", "TCNRULRegressor"),
        "patchtst": ("cmapss_patchtst_best.pt", "PatchTSTRULRegressor"),
    }
    models = {}
    try:
        for name, (file_name, class_name) in specs.items():
            checkpoint = torch.load(model_dir / file_name, map_location="cpu")
            factory = getattr(model_module, class_name)
            layers = int(checkpoint.get("layers", 1))
            if name == "tcn":
                layers = max(3, layers + 3)
            elif name == "patchtst":
                layers = max(2, layers + 1)
            with warnings.catch_warnings():
                warnings.filterwarnings(
                    "ignore",
                    message="enable_nested_tensor is True.*",
                    category=UserWarning,
                )
                model = factory(
                    input_size=int(checkpoint.get("input_size", RUL_FEATURE_SIZE)),
                    hidden_size=int(checkpoint.get("hidden_size", 64)),
                    layers=layers,
                )
            model.load_state_dict(checkpoint["model_state_dict"])
            model.eval()
            models[name] = model
    except Exception:
        return None
    return torch, models


def _load_handoff_ml_model_module():
    path = _handoff_root() / "backend" / "app" / "ml_model.py"
    if not path.exists():
        return None
    spec = importlib.util.spec_from_file_location("handoff_ml_model", path)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _cmapss_unavailable_reason() -> str:
    return "checkpoint inference unavailable; install torch and keep handoff RUL artifacts in backend/model"


def _predict_fault_probabilities(
    points: list[SensorPoint],
    profile: dict[str, Any],
    risk_pct: int,
) -> tuple[list[FaultProbability], dict[str, Any]]:
    model_result = _predict_fault_with_joblib(points, profile)
    if model_result is not None:
        return model_result
    return _surrogate_fault_probabilities(profile, risk_pct), {
        "mode": "surrogate",
        "reason": _aihub_unavailable_reason(),
    }


def _predict_fault_with_joblib(points: list[SensorPoint], profile: dict[str, Any]) -> tuple[list[FaultProbability], dict[str, Any]] | None:
    loaded = _load_aihub_payloads()
    if loaded is None:
        return None
    pd_module, payloads = loaded
    try:
        binary = _predict_payload_proba(pd_module, payloads["fault_detection_binary"], _feature_values(points, profile, "current"))
        multiclass = _predict_payload_proba(pd_module, payloads["fault_type_top3_candidates"], _feature_values(points, profile, "vibration"))
    except Exception:
        return None

    fault_pct = int(round(binary.get("fault", 0.0) * 100))
    normal_pct = max(0, 100 - fault_pct)
    class_probs = {
        AIHUB_CODE_MAP.get(str(code).zfill(2), FaultTypeCode.other): probability
        for code, probability in multiclass.items()
    }
    scaled_faults = _normalize_fault_distribution(class_probs, fault_pct)
    probabilities = [FaultProbability(FaultTypeCode.normal, normal_pct), *scaled_faults]
    return _complete_probabilities(probabilities), {
        "mode": "joblib",
        "binary_fault_probability_pct": fault_pct,
    }


def _representative_fault(
    probabilities: list[FaultProbability],
    risk_pct: int,
) -> tuple[FaultTypeCode, int | None]:
    primary = max(probabilities, key=lambda item: item.probability_pct)
    if primary.fault_type_code != FaultTypeCode.normal:
        return primary.fault_type_code, primary.probability_pct

    if risk_pct < 30:
        return FaultTypeCode.normal, None

    candidates = [item for item in probabilities if item.fault_type_code != FaultTypeCode.normal]
    if not candidates:
        return FaultTypeCode.normal, None

    likely_fault = max(candidates, key=lambda item: item.probability_pct)
    if likely_fault.probability_pct <= 0:
        return FaultTypeCode.normal, None
    return likely_fault.fault_type_code, likely_fault.probability_pct


@lru_cache(maxsize=1)
def _load_aihub_payloads():
    try:
        import joblib
        import pandas as pd
    except Exception:
        return None
    registry_path = _handoff_root() / "data" / "models" / "aihub_model_registry.json"
    if not registry_path.exists():
        return None
    try:
        import json

        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        roles = registry["recommended_mvp_roles"]
        payloads = {
            "fault_detection_binary": joblib.load(_handoff_root() / roles["fault_detection_binary"]["artifact"]),
            "fault_type_top3_candidates": joblib.load(_handoff_root() / roles["fault_type_top3_candidates"]["artifact"]),
        }
    except Exception:
        return None
    return pd, payloads


def _predict_payload_proba(pd_module, payload: dict[str, Any], features: dict[str, float]) -> dict[str, float]:
    model = payload["model"]
    columns = payload["feature_columns"]
    frame = pd_module.DataFrame([[features.get(column, _feature_default(column)) for column in columns]], columns=columns)
    probabilities = model.predict_proba(frame)[0]
    return {str(label): float(probability) for label, probability in zip(model.classes_, probabilities)}


def _feature_values(points: list[SensorPoint], profile: dict[str, Any], signal: str) -> dict[str, float]:
    values = profile["values"]["motor_current_a" if signal == "current" else "vibration_rms_g"]
    avg = float(mean(values))
    std = float(pstdev(values)) if len(values) > 1 else 0.0
    ptp = float(max(values) - min(values)) if values else 0.0
    score = float(profile["scores"]["motor_current_a" if signal == "current" else "vibration_rms_g"])
    common = {
        "RMS": avg,
        "Data Length": 256000.0,
        "Sample Rate": 25600.0,
        "motor_kw": 7.5,
        "motor_rpm": 1750.0,
        "motor_rated_current": 32.0,
        "path_motor_kw": 7.5,
        "rated_current_per_kw": 4.2,
        "rms_to_rated_current": avg / 32.0,
    }
    prefixes = ["current_r", "current_s", "current_t"] if signal == "current" else ["vibration_x", "vibration_y", "vibration_z"]
    for prefix in prefixes:
        common.update(
            {
                f"{prefix}_mean": avg,
                f"{prefix}_std": std,
                f"{prefix}_min": min(values),
                f"{prefix}_max": max(values),
                f"{prefix}_ptp": ptp,
                f"{prefix}_rms": avg,
                f"{prefix}_median": avg,
                f"{prefix}_q05": avg - std,
                f"{prefix}_q25": avg - std * 0.5,
                f"{prefix}_q75": avg + std * 0.5,
                f"{prefix}_q95": avg + std,
                f"{prefix}_iqr": std,
                f"{prefix}_abs_mean": abs(avg),
                f"{prefix}_crest_factor": 1.2 + score,
                f"{prefix}_form_factor": 1.0 + score * 0.2,
                f"{prefix}_impulse_factor": 1.1 + score,
                f"{prefix}_skew": score * 0.5,
                f"{prefix}_kurtosis": 3.0 + score,
                f"{prefix}_zero_crossing_rate": 0.05 + score * 0.1,
                f"{prefix}_diff_abs_mean": abs(float(profile["trends"]["motor_current_a" if signal == "current" else "vibration_rms_g"])),
                f"{prefix}_diff_std": std * 0.1,
                f"{prefix}_diff_max_abs": abs(float(profile["trends"]["motor_current_a" if signal == "current" else "vibration_rms_g"])) * 1.5,
                f"{prefix}_spectral_centroid": 60.0 + score * 120.0,
                f"{prefix}_spectral_spread": 20.0 + score * 80.0,
                f"{prefix}_spectral_entropy": 0.4 + score * 0.4,
                f"{prefix}_dominant_freq": 60.0 + score * 20.0,
                f"{prefix}_dominant_power_ratio": 0.2 + score * 0.4,
                f"{prefix}_low_band_ratio": 0.5 - score * 0.2,
                f"{prefix}_mid_band_ratio": 0.3 + score * 0.1,
                f"{prefix}_high_band_ratio": 0.2 + score * 0.2,
            }
        )
    for key, value in list(common.items()):
        if not key.startswith("asset_rel_") and isinstance(value, int | float):
            common[f"asset_rel_{key}"] = _clamp(float(value) * 0.01 * (score + 0.1), -25.0, 25.0)
    return common


def _feature_default(column: str) -> float:
    lower = column.lower()
    if "sample rate" in lower:
        return 25600.0
    if "data length" in lower:
        return 256000.0
    if "kw" in lower:
        return 7.5
    if "rpm" in lower:
        return 1750.0
    return 0.0


def _surrogate_fault_probabilities(profile: dict[str, Any], risk_pct: int) -> list[FaultProbability]:
    scores = profile["scores"]
    raw = {
        FaultTypeCode.normal: max(0.05, 1.0 - risk_pct / 100.0),
        FaultTypeCode.bearing_fault: 0.15 + scores["vibration_rms_g"] * 0.65,
        FaultTypeCode.belt_loose: 0.12 + scores["motor_current_a"] * 0.55,
        FaultTypeCode.rotor_unbalance: 0.10 + scores["vibration_rms_g"] * 0.35 + scores["motor_current_a"] * 0.15,
        FaultTypeCode.shaft_misalignment: 0.08 + scores["vibration_rms_g"] * 0.28 + scores["hydraulic_pressure_bar"] * 0.22,
    }
    total = sum(raw.values()) or 1.0
    probabilities = [
        FaultProbability(code, int(round(value / total * 100)))
        for code, value in sorted(raw.items(), key=lambda item: item[1], reverse=True)
    ]
    return _complete_probabilities(probabilities)


def _normalize_fault_distribution(class_probs: dict[FaultTypeCode, float], fault_pct: int) -> list[FaultProbability]:
    fault_items = [(code, probability) for code, probability in class_probs.items() if code != FaultTypeCode.normal]
    total = sum(probability for _, probability in fault_items) or 1.0
    return [
        FaultProbability(code, int(round(probability / total * fault_pct)))
        for code, probability in fault_items
    ]


def _complete_probabilities(probabilities: list[FaultProbability]) -> list[FaultProbability]:
    by_code = {item.fault_type_code: item.probability_pct for item in probabilities}
    for code in FAULT_CODES:
        by_code.setdefault(code, 0)
    total = sum(by_code.values())
    if total != 100:
        primary = max(by_code, key=by_code.get)
        by_code[primary] = max(0, by_code[primary] + 100 - total)
    return [
        FaultProbability(code, int(by_code[code]))
        for code in sorted(by_code, key=by_code.get, reverse=True)
    ]


def _aihub_unavailable_reason() -> str:
    return "joblib inference unavailable; install scikit-learn/joblib/pandas and keep handoff AI-Hub artifacts in backend/model"


def _root_sensors(profile: dict[str, Any]) -> list[RootSensor]:
    labels = {
        "vibration_rms_g": "진동 RMS 상승",
        "hydraulic_temp_c": "유압 온도 상승",
        "motor_current_a": "모터 전류 변동성",
        "hydraulic_pressure_bar": "유압 압력 변동",
    }
    ranked = sorted(profile["scores"].items(), key=lambda item: item[1], reverse=True)
    return [
        RootSensor(
            sensor_name=name,
            importance_pct=int(round(_clamp(score * 50 + 10, 5, 65))),
            direction="up",
            display_text=labels[name],
        )
        for name, score in ranked[:3]
    ]


def _risk_from_rul(rul_hours: int) -> int:
    if rul_hours <= 72:
        return int(round(_clamp(65 + (72 - rul_hours) / 72 * 31, 65, 96)))
    return int(round(_clamp(65 - (rul_hours - 72) / 53 * 45, 4, 65)))


def _combined_risk(rul_hours: int, profile: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    rul_risk = _risk_from_rul(rul_hours)
    sensor_score = _sensor_degradation_score(profile)
    sensor_risk = int(round(sensor_score * 100))
    combined = int(round(_clamp(rul_risk * 0.65 + sensor_risk * 0.35, 0, 99)))
    return combined, {
        "rul_risk": rul_risk,
        "sensor_risk": sensor_risk,
        "combined_risk": combined,
        "formula": "0.65*rul_risk + 0.35*sensor_risk",
    }


def _status_from_risk(risk_pct: int, fault_type: FaultTypeCode) -> EquipmentStatus:
    if risk_pct >= 65:
        return EquipmentStatus.danger
    if risk_pct >= 30 or fault_type != FaultTypeCode.normal:
        return EquipmentStatus.warn
    return EquipmentStatus.normal


def _score(value: float, normal: float, danger: float) -> float:
    return _clamp((value - normal) / (danger - normal), 0.0, 1.0)


def _trend(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    baseline = abs(values[0]) or 1.0
    return _clamp((values[-1] - values[0]) / baseline, -1.0, 1.0)


def _cv(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    avg = abs(mean(values)) or 1.0
    return _clamp(pstdev(values) / avg, 0.0, 1.0)


def _clamp(value: float | int, low: float | int, high: float | int):
    return max(low, min(high, value))


def _handoff_root() -> Path:
    backend_root = Path(__file__).resolve().parents[2]
    return backend_root / "model" / "handoff_ai_model_package_20260520_174242"
