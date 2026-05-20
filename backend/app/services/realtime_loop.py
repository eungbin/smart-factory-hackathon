from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select

from app.db.models import Equipment
from app.db.session import SessionLocal
from app.realtime.manager import RealtimeManager
from app.schemas.predictions import PredictionOut
from app.services.dashboard import get_dashboard
from app.services.predictions import create_prediction_run
from app.services.simulation import create_sensor_tick


SENSOR_INTERVAL_SECONDS = 2.0
PREDICTION_INTERVAL_SECONDS = 10.0
KST = timezone(timedelta(hours=9))


async def run_realtime_loop(
    manager: RealtimeManager,
    stop_event: asyncio.Event,
    *,
    factory_id: int = 1,
    sensor_interval_seconds: float = SENSOR_INTERVAL_SECONDS,
    prediction_interval_seconds: float = PREDICTION_INTERVAL_SECONDS,
) -> None:
    sensor_task = asyncio.create_task(_run_sensor_loop(manager, stop_event, factory_id, sensor_interval_seconds))
    prediction_task = asyncio.create_task(_run_prediction_loop(manager, stop_event, factory_id, prediction_interval_seconds))

    try:
        await stop_event.wait()
    finally:
        stop_event.set()
        await asyncio.gather(sensor_task, prediction_task, return_exceptions=True)


async def _run_sensor_loop(
    manager: RealtimeManager,
    stop_event: asyncio.Event,
    factory_id: int,
    sensor_interval_seconds: float,
) -> None:
    while not stop_event.is_set():
        payload = await asyncio.to_thread(_create_sensor_payload, factory_id)
        await manager.broadcast(payload)
        await _sleep_or_stop(stop_event, sensor_interval_seconds)


async def _run_prediction_loop(
    manager: RealtimeManager,
    stop_event: asyncio.Event,
    factory_id: int,
    prediction_interval_seconds: float,
) -> None:
    while not stop_event.is_set():
        await _sleep_or_stop(stop_event, prediction_interval_seconds)
        if stop_event.is_set():
            return
        payload = await asyncio.to_thread(_create_prediction_payload, factory_id)
        await manager.broadcast(payload)


async def _sleep_or_stop(stop_event: asyncio.Event, seconds: float) -> None:
    try:
        await asyncio.wait_for(stop_event.wait(), timeout=seconds)
    except TimeoutError:
        pass


def _create_sensor_payload(factory_id: int) -> dict[str, Any]:
    with SessionLocal() as db:
        tick = create_sensor_tick(
            db,
            factory_id=factory_id,
            include_predictions=False,
        )
        dashboard = get_dashboard(db, factory_id=factory_id)

    return {
        "type": "dashboard_updated",
        "generatedAt": datetime.now(KST).isoformat(),
        "includedPredictions": False,
        "tick": tick.model_dump(),
        "dashboard": dashboard.model_dump(),
    }


def _create_prediction_payload(factory_id: int) -> dict[str, Any]:
    with SessionLocal() as db:
        equipment_ids = list(
            db.scalars(
                select(Equipment.id)
                .where(Equipment.factory_id == factory_id)
                .where(Equipment.is_active.is_(True))
                .order_by(Equipment.id)
            )
        )
        predictions: list[PredictionOut] = []
        for equipment_id in equipment_ids:
            prediction = create_prediction_run(db, equipment_id, commit=False)
            if prediction is not None:
                predictions.append(prediction)
        db.commit()
        dashboard = get_dashboard(db, factory_id=factory_id)

    return {
        "type": "dashboard_updated",
        "generatedAt": datetime.now(KST).isoformat(),
        "includedPredictions": True,
        "tick": {
            "insertedReadings": 0,
            "predictions": [prediction.model_dump() for prediction in predictions],
        },
        "dashboard": dashboard.model_dump(),
    }
