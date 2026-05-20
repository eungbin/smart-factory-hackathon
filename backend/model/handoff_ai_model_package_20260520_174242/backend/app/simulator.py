from __future__ import annotations

import math
from datetime import datetime, timezone
from random import Random

from .schemas import AssetDetail, AssetSummary, SensorReading

SENSOR_KEYS = [
    "T2",
    "T24",
    "T30",
    "T50",
    "P2",
    "P15",
    "P30",
    "Nf",
    "Nc",
    "epr",
    "Ps30",
    "phi",
    "NRf",
    "NRc",
    "BPR",
    "farB",
    "htBleed",
    "Nf_dmd",
    "PCNfR_dmd",
    "W31",
    "W32",
]

DATASET_ROLES = {
    "NASA C-MAPSS": "RUL 회귀 검증용. run-to-failure 구조와 테스트 RUL 정답을 제공한다.",
    "AI-Hub 기계시설물 고장 예지 센서": "국내 전동기 고장 유형/도메인 보강용. RUL 정답이 없어 RUL 주 학습 데이터로 사용하지 않는다.",
}


def _series(base: float, drift: float, noise: float, n: int, seed: int) -> list[float]:
    rng = Random(seed)
    values: list[float] = []
    for i in range(n):
        wave = math.sin(i / 5.0) * noise * 0.45
        values.append(round(base + drift * i + wave + rng.uniform(-noise, noise), 3))
    return values


def _sensor(
    key: str,
    label: str,
    unit: str,
    baseline: float,
    current: float,
    contribution: float,
    seed: int,
) -> SensorReading:
    change_pct = ((current - baseline) / baseline) * 100 if baseline else 0
    drift = (current - baseline) / 49
    return SensorReading(
        key=key,
        label=label,
        unit=unit,
        baseline=baseline,
        current=current,
        change_pct=round(change_pct, 1),
        contribution=contribution,
        series=_series(baseline, drift, max(abs(current - baseline) * 0.025, 0.05), 50, seed),
    )


def _asset_profile(index: int) -> dict:
    if index == 3:
        return {
            "status": "critical",
            "rul_hours": 72,
            "risk_72h": 78.0,
            "anomaly_score": 0.84,
            "primary_issue": "유압 펌프 구동부 진동 상승 및 전류 변동성 증가",
            "recommended_action": "출근 직후 유압 펌프 베어링, 커플링, 그리스 상태 점검",
            "confidence_interval": (48, 96),
            "sparkline": [24, 27, 31, 36, 42, 49, 57, 66, 72, 78],
            "sensors": [
                _sensor("vibration_rms", "진동 RMS", "mm/s", 3.1, 4.06, 0.39, 31),
                _sensor("motor_current_cv", "모터 전류 변동성", "%", 5.8, 8.1, 0.26, 32),
                _sensor("hydraulic_temp", "유압 온도", "C", 48.0, 61.4, 0.21, 33),
                _sensor("oil_pressure", "유압 압력", "bar", 126.0, 118.5, 0.08, 34),
            ],
        }
    if index in {5, 7}:
        return {
            "status": "watch",
            "rul_hours": 188 if index == 5 else 214,
            "risk_72h": 24.0 if index == 5 else 19.0,
            "anomaly_score": 0.39 if index == 5 else 0.32,
            "primary_issue": "서보 모터 온도와 압력 변동이 기준선보다 높음",
            "recommended_action": "다음 교대 전 온도 추세 재확인",
            "confidence_interval": (150, 230) if index == 5 else (170, 265),
            "sparkline": [9, 11, 12, 13, 15, 18, 20, 22, 24, 24] if index == 5 else [7, 8, 10, 12, 13, 15, 17, 18, 19, 19],
            "sensors": [
                _sensor("vibration_rms", "진동 RMS", "mm/s", 2.8, 3.15, 0.18, index * 10),
                _sensor("motor_current_cv", "모터 전류 변동성", "%", 5.5, 6.2, 0.14, index * 10 + 1),
                _sensor("hydraulic_temp", "유압 온도", "C", 47.0, 52.0, 0.12, index * 10 + 2),
            ],
        }
    return {
        "status": "normal",
        "rul_hours": 320 + index * 24,
        "risk_72h": max(4.0, 11.0 - index * 0.6),
        "anomaly_score": 0.12 + index * 0.01,
        "primary_issue": "정상 운전 범위",
        "recommended_action": "정기 점검 주기 유지",
        "confidence_interval": (270 + index * 18, 390 + index * 28),
        "sparkline": [5, 5, 6, 5, 7, 6, 7, 8, 7, max(4, int(11 - index * 0.6))],
        "sensors": [
            _sensor("vibration_rms", "진동 RMS", "mm/s", 2.7, 2.75 + index * 0.02, 0.05, index),
            _sensor("motor_current_cv", "모터 전류 변동성", "%", 5.2, 5.25 + index * 0.03, 0.04, index + 20),
            _sensor("hydraulic_temp", "유압 온도", "C", 46.0, 46.5 + index * 0.1, 0.03, index + 40),
        ],
    }


def list_assets() -> list[AssetSummary]:
    now = datetime.now(timezone.utc)
    assets: list[AssetSummary] = []
    for i in range(1, 9):
        profile = _asset_profile(i)
        assets.append(
            AssetSummary(
                asset_id=f"INJ-{i:02d}",
                name=f"{i}호 사출기",
                machine_type="유압식 사출성형기",
                location="A동 생산라인" if i <= 4 else "B동 생산라인",
                status=profile["status"],
                rul_hours=profile["rul_hours"],
                risk_72h=profile["risk_72h"],
                anomaly_score=profile["anomaly_score"],
                last_update=now,
                primary_issue=profile["primary_issue"],
                recommended_action=profile["recommended_action"],
                sparkline=profile["sparkline"],
            )
        )
    return assets


def get_asset(asset_id: str) -> AssetDetail:
    idx = int(asset_id.split("-")[-1]) if "-" in asset_id else 3
    profile = _asset_profile(idx)
    summary = next((asset for asset in list_assets() if asset.asset_id == asset_id), list_assets()[2])
    return AssetDetail(
        **summary.model_dump(),
        model_version="cmapss-lstm-baseline+factory-sim-v0.1",
        confidence_interval=profile["confidence_interval"],
        sensors=profile["sensors"],
        sensor_window=make_sensor_window(asset_id),
        recent_events=[
            {
                "date": "2026-05-02",
                "type": "정기점검",
                "note": "노즐 히터 저항값 정상, 그리스 보충 없음",
            },
            {
                "date": "2026-04-18",
                "type": "작업자 메모",
                "note": "야간 가동 중 유압 펌프음 평소보다 큼",
            },
        ],
    )


def make_sensor_window(asset_id: str, cycles: int = 50) -> list[dict[str, float]]:
    idx = int(asset_id.split("-")[-1]) if "-" in asset_id else 3
    profile = _asset_profile(idx)
    sensors = profile["sensors"]
    rng = Random(idx * 101)
    rows: list[dict[str, float]] = []
    for cycle in range(1, cycles + 1):
        row: dict[str, float] = {
            "cycle": float(cycle),
            "operational_setting_1": round(rng.uniform(-0.004, 0.004), 5),
            "operational_setting_2": round(rng.uniform(-0.0005, 0.0005), 5),
            "operational_setting_3": 100.0,
        }
        for sensor_index, key in enumerate(SENSOR_KEYS, start=1):
            anchor = 100 + sensor_index * 2.7
            risk_push = profile["anomaly_score"] * cycle * (sensor_index % 5) * 0.015
            row[key] = round(anchor + math.sin(cycle / (sensor_index + 4)) + risk_push + rng.uniform(-0.2, 0.2), 4)
        for sensor in sensors:
            row[sensor.key] = sensor.series[cycle - 1]
        rows.append(row)
    return rows

