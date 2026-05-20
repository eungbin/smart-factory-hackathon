from __future__ import annotations

from datetime import datetime, timezone

from .cmapss_runtime import cmapss_risk_percent, get_cmapss_prediction_for_asset
from .fault_classifier import predict_fault_class
from .schemas import FaultClassificationResponse, HealthPredictionResponse, PredictResponse, SensorReading
from .simulator import DATASET_ROLES, get_asset


def predict_rul(asset_id: str | None = None, window: list[dict[str, float]] | None = None) -> PredictResponse:
    selected_asset_id = asset_id or "INJ-03"
    asset = get_asset(selected_asset_id)
    sensors = sorted(asset.sensors, key=lambda sensor: sensor.contribution, reverse=True)[:3]

    if window:
        anomaly = _window_anomaly(window)
        adjusted_rul = max(24, int(asset.rul_hours * (1.05 - anomaly * 0.18)))
        adjusted_risk = min(99.0, max(asset.risk_72h, anomaly * 100))
    else:
        adjusted_rul = asset.rul_hours
        adjusted_risk = asset.risk_72h

    cmapss_prediction = get_cmapss_prediction_for_asset(asset.asset_id)
    if cmapss_prediction is not None:
        adjusted_rul = int(round(cmapss_prediction.predicted_rul))
        adjusted_risk = cmapss_risk_percent(cmapss_prediction.predicted_rul)
        confidence_spread = 18
        confidence_interval = (
            max(0, adjusted_rul - confidence_spread),
            adjusted_rul + confidence_spread,
        )
        model_version = "cmapss-fd001-fd004-validated-gru-tcn-patchtst-ensemble-v0.5"
        anomaly_score = round(max(0.0, min(1.0, 1.0 - cmapss_prediction.predicted_rul / 125.0)), 2)
        rul_source = "NASA C-MAPSS validation-tuned GRU+TCN+PatchTST ensemble"
        cmapss_subset = cmapss_prediction.subset
        cmapss_unit = cmapss_prediction.unit
        cmapss_last_cycle = cmapss_prediction.last_cycle
        cmapss_actual_rul_reference = cmapss_prediction.actual_rul
    else:
        confidence_interval = asset.confidence_interval
        model_version = asset.model_version
        anomaly_score = asset.anomaly_score
        rul_source = "factory simulator fallback"
        cmapss_subset = None
        cmapss_unit = None
        cmapss_last_cycle = None
        cmapss_actual_rul_reference = None

    return PredictResponse(
        asset_id=asset.asset_id,
        model_version=model_version,
        rul_hours=adjusted_rul,
        risk_72h=round(adjusted_risk, 1),
        confidence_interval=confidence_interval,
        anomaly_score=anomaly_score,
        contributing_sensors=sensors,
        dataset_roles=DATASET_ROLES,
        generated_at=datetime.now(timezone.utc),
        rul_source=rul_source,
        rul_unit="cycle mapped to demo hours",
        cmapss_subset=cmapss_subset,
        cmapss_unit=cmapss_unit,
        cmapss_last_cycle=cmapss_last_cycle,
        cmapss_actual_rul_reference=cmapss_actual_rul_reference,
    )


def predict_fault(asset_id: str | None = None, window: list[dict[str, float]] | None = None) -> FaultClassificationResponse:
    rul_prediction = predict_rul(asset_id, window)
    return predict_fault_class(asset_id, window, rul_prediction)


def predict_health(asset_id: str | None = None, window: list[dict[str, float]] | None = None) -> HealthPredictionResponse:
    rul_prediction = predict_rul(asset_id, window)
    fault_prediction = predict_fault_class(asset_id, window, rul_prediction)
    return HealthPredictionResponse(
        asset_id=rul_prediction.asset_id,
        rul=rul_prediction,
        fault=fault_prediction,
        generated_at=datetime.now(timezone.utc),
    )


def _window_anomaly(window: list[dict[str, float]]) -> float:
    if not window:
        return 0.0
    keys = [key for key in window[-1].keys() if key not in {"cycle", "operational_setting_1", "operational_setting_2", "operational_setting_3"}]
    if not keys:
        return 0.0
    deltas: list[float] = []
    for key in keys:
        first = float(window[0].get(key, 0.0))
        last = float(window[-1].get(key, first))
        denom = abs(first) or 1.0
        deltas.append(abs(last - first) / denom)
    return max(0.0, min(1.0, sum(deltas) / len(deltas) * 5))


def risk_to_severity(risk_72h: float) -> str:
    if risk_72h >= 65:
        return "critical"
    if risk_72h >= 18:
        return "watch"
    return "normal"
