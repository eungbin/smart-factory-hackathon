from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .cmapss_runtime import list_cmapss_benchmark_rows, list_cmapss_demo_predictions
from .predictor import predict_fault, predict_health, predict_rul
from .schemas import (
    DispatchResponse,
    FaultClassificationResponse,
    HealthPredictionResponse,
    KnowledgeReport,
    MaintenanceEvent,
    MaintenanceEventCreate,
    PredictRequest,
    PredictResponse,
    WorkOrder,
    WorkOrderCreate,
)
from .simulator import DATASET_ROLES, get_asset, list_assets
from .storage import (
    get_work_order,
    list_maintenance_events,
    list_work_orders,
    save_maintenance_event,
    save_work_order,
    training_queue_count,
    update_work_order_status,
)
from .work_orders import generate_work_order, mark_dispatched

app = FastAPI(title="공장지기 MVP API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "factory-pipeline"}


@app.get("/api/assets")
@app.get("/assets")
def assets() -> list[dict[str, Any]]:
    return [asset.model_dump(mode="json") for asset in list_assets()]


@app.get("/api/assets/{asset_id}")
@app.get("/assets/{asset_id}")
def asset_detail(asset_id: str) -> dict[str, Any]:
    try:
        return get_asset(asset_id).model_dump(mode="json")
    except Exception as exc:
        raise HTTPException(status_code=404, detail="asset not found") from exc


@app.post("/api/predict/rul", response_model=PredictResponse)
@app.post("/predict/rul", response_model=PredictResponse)
def predict(payload: PredictRequest) -> PredictResponse:
    return predict_rul(payload.asset_id, payload.window)


@app.post("/api/predict/fault", response_model=FaultClassificationResponse)
@app.post("/predict/fault", response_model=FaultClassificationResponse)
def predict_fault_endpoint(payload: PredictRequest) -> FaultClassificationResponse:
    return predict_fault(payload.asset_id, payload.window)


@app.post("/api/predict/health", response_model=HealthPredictionResponse)
@app.post("/predict/health", response_model=HealthPredictionResponse)
def predict_health_endpoint(payload: PredictRequest) -> HealthPredictionResponse:
    return predict_health(payload.asset_id, payload.window)


@app.post("/api/work-orders", response_model=WorkOrder)
@app.post("/work-orders", response_model=WorkOrder)
def create_work_order(payload: WorkOrderCreate) -> WorkOrder:
    order = generate_work_order(payload)
    return save_work_order(order)


@app.get("/api/work-orders", response_model=list[WorkOrder])
def work_orders() -> list[WorkOrder]:
    return list_work_orders()


@app.get("/api/work-orders/{work_order_id}", response_model=WorkOrder)
def work_order(work_order_id: str) -> WorkOrder:
    order = get_work_order(work_order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="work order not found")
    return order


@app.post("/api/work-orders/{work_order_id}/dispatch", response_model=DispatchResponse)
@app.post("/work-orders/{work_order_id}/dispatch", response_model=DispatchResponse)
def dispatch(work_order_id: str) -> DispatchResponse:
    order = get_work_order(work_order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="work order not found")
    dispatched = update_work_order_status(work_order_id, "dispatched")
    return mark_dispatched(dispatched or order)


@app.post("/api/maintenance-events", response_model=MaintenanceEvent)
@app.post("/maintenance-events", response_model=MaintenanceEvent)
def create_maintenance_event(payload: MaintenanceEventCreate) -> MaintenanceEvent:
    return save_maintenance_event(payload)


@app.get("/api/maintenance-events", response_model=list[MaintenanceEvent])
def maintenance_events() -> list[MaintenanceEvent]:
    return list_maintenance_events()


@app.get("/api/reports/knowledge", response_model=KnowledgeReport)
def knowledge_report() -> KnowledgeReport:
    events = list_maintenance_events(limit=10)
    queue_count = training_queue_count()
    return KnowledgeReport(
        month=datetime.now().strftime("%Y-%m"),
        digitized_knowhow_count=max(queue_count, len(events)),
        training_queue_count=queue_count,
        estimated_downtime_prevented_hours=18.0 + queue_count * 0.5,
        work_order_time_saved_minutes=20 * max(1, len(list_work_orders())),
        top_failure_modes=[
            {"label": "베어링/윤활 이상", "count": max(1, queue_count), "share": 0.42},
            {"label": "축정렬/커플링", "count": 1, "share": 0.24},
            {"label": "유압 온도 상승", "count": 1, "share": 0.18},
        ],
        recent_events=events,
        dataset_notes=DATASET_ROLES,
    )


@app.get("/api/datasets")
def datasets() -> dict[str, Any]:
    return {
        "aihub": {
            "name": "기계시설물 고장 예지 센서",
            "role": "정상/고장 분류와 국내 전동기 도메인 보강",
            "label_policy": "RUL 정답 없음. RUL 주 학습 데이터로 사용하지 않음.",
            "labels": {
                "00": "정상",
                "01": "베어링 불량",
                "02": "회전체 불평형",
                "03": "축정렬 불량",
                "04": "벨트 느슨함",
            },
            "total_records": 2333172,
        },
        "cmapss": {
            "name": "NASA C-MAPSS Jet Engine Simulated Data",
            "role": "RUL 회귀 검증용",
            "columns": ["unit", "cycle", "operational_setting_1..3", "sensor_1..21"],
            "subsets": ["FD001", "FD002", "FD003", "FD004"],
            "window_size": 50,
        },
    }


@app.get("/api/cmapss/benchmark")
def cmapss_benchmark() -> dict[str, Any]:
    rows = list_cmapss_benchmark_rows()
    return {"rows": rows, "count": len(rows)}


@app.get("/api/cmapss/demo-predictions")
def cmapss_demo_predictions() -> dict[str, Any]:
    rows = list_cmapss_demo_predictions()
    return {"rows": rows, "count": len(rows)}
