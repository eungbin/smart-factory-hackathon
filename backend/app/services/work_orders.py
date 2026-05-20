from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import Equipment, PredictionRun, WorkOrder, WorkOrderPart, WorkOrderSource, WorkOrderStep
from app.schemas.work_orders import WorkOrderOut
from app.services.equipment import get_equipment
from app.services.knowledge import search_chunks
from app.services.predictions import get_latest_prediction, get_prediction_out
from app.work_orders.generators import (
    WorkOrderGenerationContext,
    WorkOrderGenerationError,
    get_work_order_generator,
)


KST = timezone(timedelta(hours=9))
DEFAULT_GENERATOR_PROVIDER = "template"
SOURCE_SUMMARY = "설비 운영 매뉴얼 §4.3 - 유압 펌프 베어링 정비 절차"


def generate_work_order(
    db: Session,
    equipment_id: int,
    prediction_run_id: int | None = None,
    generator_provider: str | None = None,
) -> WorkOrderOut | None:
    equipment = get_equipment(db, equipment_id)
    if equipment is None:
        return None

    prediction = _resolve_prediction(db, equipment_id, prediction_run_id)
    fault_type = equipment.faultType or "예방 점검"
    fault_conf = equipment.faultConf or equipment.risk
    generated_at = datetime.now(KST)
    rul_text = f"{equipment.rul}h (±{max(equipment.rul - equipment.rulMin, equipment.rulMax - equipment.rul)}h)"
    fault_type_text = f"{fault_type} ({fault_conf}%)"
    root_sensors = _root_sensor_texts(prediction) or ["진동 RMS 31%↑", "모터 전류 변동성↑", "유압 온도↑"]
    rag_sources = _search_rag_sources(db, equipment_id, equipment.name, equipment.model, fault_type, root_sensors)
    source_summary = _source_summary(rag_sources)
    generation = _generate_with_provider(
        _build_generation_context(equipment.name, fault_type_text, root_sensors, source_summary, rag_sources),
        generator_provider,
    )

    order = WorkOrder(
        equipment_id=equipment.id,
        prediction_run_id=prediction.predictionRunId if prediction is not None else None,
        status="generated",
        generated_at=generated_at,
        generator_provider=generation.provider,
        generator_model=generation.model,
        title=generation.title,
        fault_type_text=fault_type_text,
        risk_pct=Decimal(str(equipment.risk)),
        rul_text=rul_text,
        source_summary=generation.source_summary,
        total_minutes=generation.total_minutes,
        tech_level=generation.tech_level,
        caution=generation.caution,
        raw_prompt=generation.raw_prompt,
        raw_response=generation.raw_response,
    )
    db.add(order)
    db.flush()

    for source in rag_sources:
        db.add(
            WorkOrderSource(
                work_order_id=order.id,
                knowledge_chunk_id=source.chunkId,
                source_label=source.sourceLabel,
                relevance_score=Decimal(str(source.score)),
            )
        )

    for step in generation.steps:
        db.add(
            WorkOrderStep(
                work_order_id=order.id,
                step_no=step.no,
                category=step.category,
                action=step.action,
                tool=step.tool,
                estimated_minutes=_minutes_from_text(step.time),
                safety_required=step.safety,
            )
        )

    for part in generation.parts:
        db.add(
            WorkOrderPart(
                work_order_id=order.id,
                part_name=part.name,
                qty_text=part.qty,
                stock_text=part.stock,
                is_available=part.stock == "보유중" or "재고" in part.stock,
            )
        )

    db.commit()

    return WorkOrderOut(
        id=order.id,
        equipId=equipment.id,
        equipName=f"{equipment.name}({equipment.model}, {equipment.year})",
        generatedAt=order.generated_at.strftime("%Y-%m-%d %H:%M"),
        rul=order.rul_text,
        risk=equipment.risk,
        faultType=order.fault_type_text,
        rootSensors=root_sensors,
        source=order.source_summary,
        status=order.status,
        steps=generation.steps,
        parts=generation.parts,
        totalTime=generation.total_time_text,
        techLevel=order.tech_level,
        caution=order.caution,
    )


def _resolve_prediction(db: Session, equipment_id: int, prediction_run_id: int | None):
    if prediction_run_id is None:
        return get_latest_prediction(db, equipment_id)

    stmt = select(PredictionRun.id).where(
        PredictionRun.id == prediction_run_id,
        PredictionRun.equipment_id == equipment_id,
    )
    if db.execute(stmt).scalar_one_or_none() is None:
        return None
    return get_prediction_out(db, prediction_run_id)


def _search_rag_sources(
    db: Session,
    equipment_id: int,
    equipment_name: str,
    model_name: str,
    fault_type: str,
    root_sensors: list[str],
):
    model_id = db.execute(select(Equipment.model_id).where(Equipment.id == equipment_id)).scalar_one_or_none()
    query = " ".join([equipment_name, model_name, fault_type, *root_sensors, "정비 절차 안전 점검"])
    return search_chunks(db, query, model_id, limit=3)


def _build_generation_context(
    equipment_name: str,
    fault_type_text: str,
    root_sensors: list[str],
    source_summary: str,
    rag_sources,
) -> WorkOrderGenerationContext:
    return WorkOrderGenerationContext(
        equipment_name=equipment_name,
        fault_type_text=fault_type_text,
        root_sensors=root_sensors,
        source_summary=source_summary,
        rag_sources=[source.model_dump() for source in rag_sources],
    )


def _generate_with_provider(
    context: WorkOrderGenerationContext,
    generator_provider: str | None,
):
    settings = get_settings()
    provider = generator_provider or settings.work_order_generator_provider
    generator = get_work_order_generator(
        provider,
        gemini_api_key=settings.gemini_api_key,
        gemini_model=settings.gemini_model,
        openai_api_key=settings.openai_api_key,
        openai_model=settings.openai_model,
    )
    try:
        return generator.generate(context)
    except WorkOrderGenerationError as error:
        fallback_provider = settings.work_order_generator_fallback_provider
        fallback = get_work_order_generator(fallback_provider).generate(context)
        fallback.raw_response["fallbackFrom"] = provider
        fallback.raw_response["fallbackReasonCode"] = error.code
        fallback.raw_response["fallbackReason"] = str(error)
        return fallback


def _source_summary(rag_sources) -> str:
    if not rag_sources:
        return SOURCE_SUMMARY

    primary = rag_sources[0]
    if primary.heading:
        return f"{primary.sourceLabel} - {primary.heading}"
    return primary.sourceLabel


def _root_sensor_texts(prediction) -> list[str]:
    if prediction is None:
        return []
    return [sensor.displayText for sensor in prediction.rootSensors]


def _minutes_from_text(value: str) -> int:
    return int(value.replace("분", ""))
