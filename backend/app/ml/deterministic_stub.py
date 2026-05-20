from statistics import mean

from app.db.models import EquipmentStatus, FaultTypeCode
from app.ml.contracts import FaultProbability, InferenceResult, RootSensor, SensorWindow


def infer(window: SensorWindow) -> InferenceResult:
    latest = window.points[-1]
    vibration = mean(point.vibration_rms_g for point in window.points)
    temperature = mean(point.hydraulic_temp_c for point in window.points)
    current = mean(point.motor_current_a for point in window.points)
    pressure = mean(point.hydraulic_pressure_bar for point in window.points)

    scores = {
        "vibration_rms_g": _score(vibration, 1.5, 4.5),
        "hydraulic_temp_c": _score(temperature, 75.0, 95.0),
        "motor_current_a": _score(current, 24.0, 34.0),
        "hydraulic_pressure_bar": _score(abs(pressure - 145.0), 4.0, 22.0),
    }
    risk = _clamp(
        round(10 + scores["vibration_rms_g"] * 35 + scores["hydraulic_temp_c"] * 25 + scores["motor_current_a"] * 20 + scores["hydraulic_pressure_bar"] * 10),
        0,
        99,
    )
    rul = _clamp(round(620 - risk * 7), 24, 720)

    if risk >= 65 or rul <= 96:
        status = EquipmentStatus.danger
    elif risk >= 30 or rul <= 240:
        status = EquipmentStatus.warn
    else:
        status = EquipmentStatus.normal

    primary_sensor = max(scores, key=scores.get)
    fault_type = _fault_type_for(primary_sensor) if status != EquipmentStatus.normal else FaultTypeCode.normal
    confidence = _clamp(round(45 + risk * 0.55), 0, 95) if fault_type != FaultTypeCode.normal else None

    root_sensors = _root_sensors(scores)
    return InferenceResult(
        status=status,
        rul_hours=rul,
        rul_lower_hours=max(0, rul - 24),
        rul_upper_hours=rul + 24,
        risk_pct=risk,
        fault_type_code=fault_type,
        fault_confidence_pct=confidence,
        fault_probabilities=_fault_probabilities(fault_type, risk),
        root_sensors=root_sensors,
        summary=f"deterministic_stub latest={latest.measured_at.isoformat()} risk={risk}",
        raw_output={
            "model": "deterministic_stub",
            "scores": scores,
            "latest": {
                "vibration_rms_g": latest.vibration_rms_g,
                "hydraulic_temp_c": latest.hydraulic_temp_c,
                "motor_current_a": latest.motor_current_a,
                "hydraulic_pressure_bar": latest.hydraulic_pressure_bar,
            },
        },
    )


def _fault_type_for(sensor_name: str) -> FaultTypeCode:
    if sensor_name == "vibration_rms_g":
        return FaultTypeCode.bearing_fault
    if sensor_name == "motor_current_a":
        return FaultTypeCode.belt_loose
    if sensor_name == "hydraulic_pressure_bar":
        return FaultTypeCode.hydraulic_seal
    return FaultTypeCode.rotor_unbalance


def _fault_probabilities(primary: FaultTypeCode, risk: int) -> list[FaultProbability]:
    codes = [
        FaultTypeCode.bearing_fault,
        FaultTypeCode.belt_loose,
        FaultTypeCode.rotor_unbalance,
        FaultTypeCode.shaft_misalignment,
        FaultTypeCode.hydraulic_seal,
    ]
    if primary == FaultTypeCode.normal:
        return [
            FaultProbability(FaultTypeCode.normal, 70),
            FaultProbability(FaultTypeCode.bearing_fault, 8),
            FaultProbability(FaultTypeCode.belt_loose, 7),
            FaultProbability(FaultTypeCode.rotor_unbalance, 7),
            FaultProbability(FaultTypeCode.hydraulic_seal, 8),
        ]

    primary_pct = _clamp(round(40 + risk * 0.45), 45, 85)
    remaining = 100 - primary_pct
    others = [code for code in codes if code != primary]
    base = remaining // len(others)
    probabilities = [FaultProbability(primary, primary_pct)]
    probabilities.extend(FaultProbability(code, base) for code in others[:-1])
    probabilities.append(FaultProbability(others[-1], 100 - primary_pct - base * (len(others) - 1)))
    return probabilities


def _root_sensors(scores: dict[str, float]) -> list[RootSensor]:
    labels = {
        "vibration_rms_g": "진동 RMS 상승",
        "hydraulic_temp_c": "유압 온도 상승",
        "motor_current_a": "모터 전류 변동성",
        "hydraulic_pressure_bar": "유압 압력 변동",
    }
    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    return [
        RootSensor(
            sensor_name=sensor_name,
            importance_pct=_clamp(round(score * 45 + 12), 5, 60),
            direction="up",
            display_text=labels[sensor_name],
        )
        for sensor_name, score in ranked[:3]
    ]


def _score(value: float, normal: float, danger: float) -> float:
    return _clamp((value - normal) / (danger - normal), 0.0, 1.0)


def _clamp(value: float | int, low: float | int, high: float | int):
    return max(low, min(high, value))
