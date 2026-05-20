from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from .schemas import MaintenanceEvent, MaintenanceEventCreate, WorkOrder

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "factory_pipeline.db"


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    initialize(connection)
    return connection


def initialize(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS work_orders (
            id TEXT PRIMARY KEY,
            payload TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS maintenance_events (
            id TEXT PRIMARY KEY,
            asset_id TEXT NOT NULL,
            work_order_id TEXT,
            worker TEXT NOT NULL,
            result TEXT NOT NULL,
            parts_replaced TEXT NOT NULL,
            downtime_minutes INTEGER NOT NULL,
            comments TEXT NOT NULL,
            follow_up_needed INTEGER NOT NULL,
            training_queue_id TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS training_queue (
            id TEXT PRIMARY KEY,
            asset_id TEXT NOT NULL,
            event_id TEXT NOT NULL,
            label TEXT NOT NULL,
            features_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        """
    )
    connection.commit()


def save_work_order(order: WorkOrder) -> WorkOrder:
    with connect() as connection:
        connection.execute(
            """
            INSERT OR REPLACE INTO work_orders (id, payload, status, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (
                order.id,
                order.model_dump_json(),
                order.status,
                order.generated_at.isoformat(),
            ),
        )
        connection.commit()
    return order


def update_work_order_status(work_order_id: str, status: str) -> WorkOrder | None:
    order = get_work_order(work_order_id)
    if order is None:
        return None
    updated = order.model_copy(update={"status": status})
    return save_work_order(updated)


def get_work_order(work_order_id: str) -> WorkOrder | None:
    with connect() as connection:
        row = connection.execute(
            "SELECT payload FROM work_orders WHERE id = ?", (work_order_id,)
        ).fetchone()
    if row is None:
        return None
    return WorkOrder.model_validate_json(row["payload"])


def list_work_orders() -> list[WorkOrder]:
    with connect() as connection:
        rows = connection.execute(
            "SELECT payload FROM work_orders ORDER BY created_at DESC"
        ).fetchall()
    return [WorkOrder.model_validate_json(row["payload"]) for row in rows]


def save_maintenance_event(payload: MaintenanceEventCreate) -> MaintenanceEvent:
    now = datetime.now(timezone.utc)
    event_id = f"ME-{uuid4().hex[:8].upper()}"
    training_queue_id = f"TQ-{uuid4().hex[:8].upper()}"
    event = MaintenanceEvent(
        **payload.model_dump(),
        id=event_id,
        created_at=now,
        training_queue_id=training_queue_id,
    )
    features = {
        "asset_id": payload.asset_id,
        "result": payload.result,
        "parts_replaced": payload.parts_replaced,
        "downtime_minutes": payload.downtime_minutes,
        "follow_up_needed": payload.follow_up_needed,
    }
    with connect() as connection:
        connection.execute(
            """
            INSERT INTO maintenance_events
            (id, asset_id, work_order_id, worker, result, parts_replaced, downtime_minutes, comments,
             follow_up_needed, training_queue_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event.id,
                event.asset_id,
                event.work_order_id,
                event.worker,
                event.result,
                event.parts_replaced,
                event.downtime_minutes,
                event.comments,
                1 if event.follow_up_needed else 0,
                event.training_queue_id,
                event.created_at.isoformat(),
            ),
        )
        connection.execute(
            """
            INSERT INTO training_queue (id, asset_id, event_id, label, features_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                training_queue_id,
                payload.asset_id,
                event_id,
                "maintenance_feedback",
                json.dumps(features, ensure_ascii=False),
                now.isoformat(),
            ),
        )
        connection.commit()
    if payload.work_order_id:
        update_work_order_status(payload.work_order_id, "closed")
    return event


def list_maintenance_events(limit: int = 20) -> list[MaintenanceEvent]:
    with connect() as connection:
        rows = connection.execute(
            "SELECT * FROM maintenance_events ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return [
        MaintenanceEvent(
            id=row["id"],
            asset_id=row["asset_id"],
            work_order_id=row["work_order_id"],
            worker=row["worker"],
            result=row["result"],
            parts_replaced=row["parts_replaced"],
            downtime_minutes=row["downtime_minutes"],
            comments=row["comments"],
            follow_up_needed=bool(row["follow_up_needed"]),
            training_queue_id=row["training_queue_id"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )
        for row in rows
    ]


def training_queue_count() -> int:
    with connect() as connection:
        row = connection.execute("SELECT COUNT(*) AS count FROM training_queue").fetchone()
    return int(row["count"])

