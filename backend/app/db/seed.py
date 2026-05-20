from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import delete, text
from sqlalchemy.orm import Session

from app.db.models import (
    Equipment,
    EquipmentModel,
    EquipmentStateLatest,
    EquipmentStatus,
    Factory,
    FaultTypeCode,
    KnowhowInsight,
    KnowledgeChunk,
    KnowledgeDocument,
    LearningQueue,
    MaintenanceRecord,
    MonthlyFaultDistribution,
    MonthlyReport,
    PredictionFaultProbability,
    PredictionRootCause,
    PredictionRun,
    SensorReading,
    User,
    WorkOrder,
    WorkOrderPart,
    WorkOrderSource,
    WorkOrderStep,
)
from app.db.session import SessionLocal


DEMO_EQUIPMENT = [
    {
        "id": 1,
        "name": "1호 사출기",
        "model_id": 1,
        "year": 2015,
        "status": EquipmentStatus.normal,
        "rul": 312,
        "rul_min": 288,
        "rul_max": 336,
        "risk": 12,
        "last_maint": "2026-04-18",
        "next_plan": "2026-05-20",
        "sensors": {"vibration": Decimal("1.2"), "temp": Decimal("68"), "current": Decimal("22"), "pressure": Decimal("142")},
    },
    {
        "id": 2,
        "name": "2호 사출기",
        "model_id": 1,
        "year": 2018,
        "status": EquipmentStatus.normal,
        "rul": 480,
        "rul_min": 456,
        "rul_max": 504,
        "risk": 8,
        "last_maint": "2026-04-25",
        "next_plan": "2026-06-01",
        "sensors": {"vibration": Decimal("0.9"), "temp": Decimal("65"), "current": Decimal("21"), "pressure": Decimal("138")},
    },
    {
        "id": 3,
        "name": "3호 사출기",
        "model_id": 2,
        "year": 1996,
        "status": EquipmentStatus.danger,
        "rul": 72,
        "rul_min": 48,
        "rul_max": 96,
        "risk": 78,
        "last_maint": "2026-03-12",
        "next_plan": "즉시 점검 필요",
        "sensors": {"vibration": Decimal("4.1"), "temp": Decimal("91"), "current": Decimal("31"), "pressure": Decimal("158")},
        "fault": FaultTypeCode.bearing_fault,
        "fault_conf": 78,
    },
    {
        "id": 4,
        "name": "4호 사출기",
        "model_id": 3,
        "year": 2012,
        "status": EquipmentStatus.warn,
        "rul": 168,
        "rul_min": 144,
        "rul_max": 192,
        "risk": 41,
        "last_maint": "2026-04-01",
        "next_plan": "2026-05-07",
        "sensors": {"vibration": Decimal("2.8"), "temp": Decimal("79"), "current": Decimal("26"), "pressure": Decimal("151")},
        "fault": FaultTypeCode.rotor_unbalance,
        "fault_conf": 41,
    },
    {
        "id": 5,
        "name": "5호 사출기",
        "model_id": 1,
        "year": 2010,
        "status": EquipmentStatus.warn,
        "rul": 210,
        "rul_min": 186,
        "rul_max": 234,
        "risk": 33,
        "last_maint": "2026-04-10",
        "next_plan": "2026-05-10",
        "sensors": {"vibration": Decimal("2.2"), "temp": Decimal("76"), "current": Decimal("24"), "pressure": Decimal("147")},
        "fault": FaultTypeCode.belt_loose,
        "fault_conf": 33,
    },
    {
        "id": 6,
        "name": "6호 사출기",
        "model_id": 2,
        "year": 2008,
        "status": EquipmentStatus.normal,
        "rul": 390,
        "rul_min": 366,
        "rul_max": 414,
        "risk": 15,
        "last_maint": "2026-04-22",
        "next_plan": "2026-05-25",
        "sensors": {"vibration": Decimal("1.4"), "temp": Decimal("70"), "current": Decimal("23"), "pressure": Decimal("143")},
    },
    {
        "id": 7,
        "name": "7호 사출기",
        "model_id": 3,
        "year": 2014,
        "status": EquipmentStatus.normal,
        "rul": 528,
        "rul_min": 504,
        "rul_max": 552,
        "risk": 5,
        "last_maint": "2026-04-28",
        "next_plan": "2026-06-10",
        "sensors": {"vibration": Decimal("0.7"), "temp": Decimal("63"), "current": Decimal("20"), "pressure": Decimal("136")},
    },
    {
        "id": 8,
        "name": "8호 사출기",
        "model_id": 1,
        "year": 2016,
        "status": EquipmentStatus.normal,
        "rul": 445,
        "rul_min": 421,
        "rul_max": 469,
        "risk": 11,
        "last_maint": "2026-04-20",
        "next_plan": "2026-05-28",
        "sensors": {"vibration": Decimal("1.1"), "temp": Decimal("67"), "current": Decimal("22"), "pressure": Decimal("141")},
    },
]

KST = timezone(timedelta(hours=9))

DEMO_MAINTENANCE_RECORDS = [
    {
        "id": 1,
        "equipment_id": 3,
        "performed_at": datetime(2026, 3, 12, 9, 0, tzinfo=KST),
        "technician_name": "박영훈",
        "maintenance_type": "예방 정비",
        "result": "정상",
        "duration_minutes": 120,
        "parts_text": "유압 씰 교체",
        "note": "펌프 이상을 사전 감지, 씰 교체 후 정상",
    },
    {
        "id": 2,
        "equipment_id": 3,
        "performed_at": datetime(2026, 1, 8, 9, 0, tzinfo=KST),
        "technician_name": "박영훈",
        "maintenance_type": "긴급 정비",
        "result": "정상",
        "duration_minutes": 240,
        "parts_text": "베어링 교체",
        "note": "야간 고장 대응",
    },
    {
        "id": 3,
        "equipment_id": 4,
        "performed_at": datetime(2026, 4, 1, 9, 0, tzinfo=KST),
        "technician_name": "이민준",
        "maintenance_type": "예방 정비",
        "result": "정상",
        "duration_minutes": 45,
        "parts_text": "벨트 조정",
        "note": "진동 상승 감지 후 예방 조치",
    },
    {
        "id": 4,
        "equipment_id": 5,
        "performed_at": datetime(2026, 4, 10, 9, 0, tzinfo=KST),
        "technician_name": "이민준",
        "maintenance_type": "점검",
        "result": "정상",
        "duration_minutes": 30,
        "parts_text": "없음",
        "note": "정기 점검, 이상 없음",
    },
]

DEMO_MONTHLY_REPORTS = [
    {"id": 1, "month": date(2025, 11, 1), "downtime": 58, "prevented": 2, "mttr": 185, "learning": 7},
    {"id": 2, "month": date(2025, 12, 1), "downtime": 42, "prevented": 3, "mttr": 162, "learning": 9},
    {"id": 3, "month": date(2026, 1, 1), "downtime": 48, "prevented": 4, "mttr": 170, "learning": 11},
    {"id": 4, "month": date(2026, 2, 1), "downtime": 35, "prevented": 5, "mttr": 148, "learning": 13},
    {"id": 5, "month": date(2026, 3, 1), "downtime": 36, "prevented": 4, "mttr": 145, "learning": 13},
    {"id": 6, "month": date(2026, 4, 1), "downtime": 18, "prevented": 6, "mttr": 110, "learning": 21},
]

DEMO_FAULT_DISTRIBUTION = [
    {"display_name": "베어링 불량", "percentage": 38, "color": "#f87171"},
    {"display_name": "벨트 장력", "percentage": 24, "color": "#fbbf24"},
    {"display_name": "회전체 불균형", "percentage": 19, "color": "#a78bfa"},
    {"display_name": "축정렬 불량", "percentage": 11, "color": "#60a5fa"},
    {"display_name": "기타", "percentage": 8, "color": "#4ade80"},
]

DEMO_INSIGHTS = [
    {
        "insight_type": "monthly_insight",
        "priority": "high",
        "icon": "!",
        "title": "3호기 베어링 이슈 반복 발생",
        "body": "최근 90일간 베어링 불량 3건 중 2건이 3호기에 집중되었습니다. 베어링 교체 주기를 6개월에서 4개월로 단축하는 것을 권장합니다.",
    },
    {
        "insight_type": "monthly_insight",
        "priority": "medium",
        "icon": "N",
        "title": "야간 정지 패턴 감지",
        "body": "비계획 정지 8건 중 6건이 00:00~06:00 사이에 발생했습니다. 야간 자동 알림 강도와 사전 점검 루틴을 조정하세요.",
    },
    {
        "insight_type": "monthly_insight",
        "priority": "low",
        "icon": "T",
        "title": "예방 정비 효과 확인",
        "body": "예방 정비 실시 후 평균 MTTR이 145분에서 110분으로 단축되었습니다. 4월 기준 비계획 정지 18h로 목표를 달성했습니다.",
    },
    {
        "insight_type": "monthly_insight",
        "priority": "info",
        "icon": "K",
        "title": "정비 노하우 구조화",
        "body": "정비 이력 21건이 학습 큐에 적재되었습니다. 그리스 보충 패턴과 베어링 교체 조건에서 6개 지식 항목을 추출했습니다.",
    },
    {
        "insight_type": "learned_knowledge",
        "priority": "high",
        "equipment_label": "3호 사출기",
        "knowledge_key": "K-001",
        "knowledge_date": date(2026, 4, 8),
        "body": "유압 온도 88도 초과 시 베어링 이상 전조 신호로 확인되었습니다.",
        "confidence_pct": 92,
    },
    {
        "insight_type": "learned_knowledge",
        "priority": "medium",
        "equipment_label": "4호 사출기",
        "knowledge_key": "K-002",
        "knowledge_date": date(2026, 4, 1),
        "body": "회전체 불균형은 진동 2.5g 이상 지속 시 72시간 내 정비를 권장합니다.",
        "confidence_pct": 78,
    },
    {
        "insight_type": "learned_knowledge",
        "priority": "medium",
        "equipment_label": "전체",
        "knowledge_key": "K-003",
        "knowledge_date": date(2026, 3, 20),
        "body": "Mobilux EP 2 그리스는 온도 80도 이상 환경에서 보충 주기를 3개월에서 2개월로 단축합니다.",
        "confidence_pct": 85,
    },
]


def seed_demo_data() -> None:
    with SessionLocal() as session:
        seed_demo_data_with_session(session)
        session.commit()


def seed_demo_data_with_session(session: Session) -> None:
    session.execute(delete(WorkOrderPart))
    session.execute(delete(WorkOrderStep))
    session.execute(delete(WorkOrderSource))
    session.execute(delete(WorkOrder))
    session.execute(delete(KnowledgeChunk))
    session.execute(delete(KnowledgeDocument))
    session.execute(delete(PredictionRootCause))
    session.execute(delete(PredictionFaultProbability))
    session.execute(delete(PredictionRun))
    session.execute(delete(SensorReading))
    session.execute(delete(KnowhowInsight))
    session.execute(delete(MonthlyFaultDistribution))
    session.execute(delete(MonthlyReport))
    session.execute(delete(LearningQueue))
    session.execute(delete(MaintenanceRecord))

    session.merge(
        Factory(
            id=1,
            name="세종 사출 공장",
            address="세종특별자치시",
            industry="플라스틱 사출",
            target_uptime_pct=Decimal("95.00"),
            target_delay_pct=Decimal("2.00"),
        )
    )

    session.merge(User(id=1, factory_id=1, name="김민수", role="maintenance", phone="010-0000-0001", is_active=True))
    session.merge(User(id=2, factory_id=1, name="이지은", role="operator", phone="010-0000-0002", is_active=True))

    session.merge(
        EquipmentModel(
            id=1,
            maker="LS",
            model_name="LS350-A",
            category="injection_molding",
            default_thresholds={},
            manual_notes="350톤급 사출기",
        )
    )
    session.merge(
        EquipmentModel(
            id=2,
            maker="LS",
            model_name="LS240-B",
            category="injection_molding",
            default_thresholds={},
            manual_notes="240톤급 사출기",
        )
    )
    session.merge(
        EquipmentModel(
            id=3,
            maker="LS",
            model_name="LS500-C",
            category="injection_molding",
            default_thresholds={},
            manual_notes="500톤급 사출기",
        )
    )
    session.flush()

    for item in DEMO_EQUIPMENT:
        session.merge(
            Equipment(
                id=item["id"],
                factory_id=1,
                model_id=item["model_id"],
                name=item["name"],
                serial_no=f"IM-{item['id']:03d}",
                installed_year=item["year"],
                assigned_user_id=1,
                cumulative_runtime_hours=Decimal("0.0"),
                thresholds_override=None,
                is_active=True,
            )
        )
        session.merge(
            EquipmentStateLatest(
                equipment_id=item["id"],
                status=item["status"],
                rul_hours=item["rul"],
                rul_lower_hours=item["rul_min"],
                rul_upper_hours=item["rul_max"],
                risk_pct=Decimal(str(item["risk"])),
                fault_type_code=item.get("fault"),
                fault_confidence_pct=Decimal(str(item["fault_conf"])) if item.get("fault_conf") is not None else None,
                vibration_rms_g=item["sensors"]["vibration"],
                hydraulic_temp_c=item["sensors"]["temp"],
                motor_current_a=item["sensors"]["current"],
                hydraulic_pressure_bar=item["sensors"]["pressure"],
                last_maintenance_at=date.fromisoformat(item["last_maint"]),
                next_plan_text=item["next_plan"],
                latest_sensor_reading_at=None,
                latest_prediction_run_id=None,
            )
        )

    for item in DEMO_MAINTENANCE_RECORDS:
        session.merge(
            MaintenanceRecord(
                id=item["id"],
                equipment_id=item["equipment_id"],
                work_order_id=None,
                performed_at=item["performed_at"],
                technician_name=item["technician_name"],
                maintenance_type=item["maintenance_type"],
                result=item["result"],
                duration_minutes=item["duration_minutes"],
                parts_text=item["parts_text"],
                actions={},
                actual_fault_type_code=None,
                ai_accuracy_note=None,
                note=item["note"],
                next_plan_text=None,
            )
        )

    for item in DEMO_MONTHLY_REPORTS:
        session.merge(
            MonthlyReport(
                id=item["id"],
                factory_id=1,
                month=item["month"],
                unplanned_downtime_hours=Decimal(str(item["downtime"])),
                prevented_count=item["prevented"],
                mttr_minutes=Decimal(str(item["mttr"])),
                learning_data_count=item["learning"],
            )
        )
    session.flush()

    latest_report_id = DEMO_MONTHLY_REPORTS[-1]["id"]
    for index, item in enumerate(DEMO_FAULT_DISTRIBUTION, start=1):
        session.merge(
            MonthlyFaultDistribution(
                id=index,
                monthly_report_id=latest_report_id,
                display_name=item["display_name"],
                percentage=Decimal(str(item["percentage"])),
                color=item["color"],
                sort_order=index,
            )
        )

    for index, item in enumerate(DEMO_INSIGHTS, start=1):
        session.merge(
            KnowhowInsight(
                id=index,
                factory_id=1,
                monthly_report_id=latest_report_id,
                insight_type=item["insight_type"],
                priority=item["priority"],
                icon=item.get("icon"),
                equipment_label=item.get("equipment_label"),
                title=item.get("title", item.get("knowledge_key", f"K-{index:03d}")),
                body=item["body"],
                confidence_pct=Decimal(str(item["confidence_pct"])) if item.get("confidence_pct") is not None else None,
                knowledge_key=item.get("knowledge_key"),
                knowledge_date=item.get("knowledge_date"),
            )
        )

    _advance_identity(session, "factories", 1)
    _advance_identity(session, "users", 2)
    _advance_identity(session, "equipment_models", 3)
    _advance_identity(session, "equipment", 8)
    _advance_identity(session, "maintenance_records", len(DEMO_MAINTENANCE_RECORDS))
    _advance_identity(session, "monthly_reports", len(DEMO_MONTHLY_REPORTS))
    _advance_identity(session, "monthly_fault_distributions", len(DEMO_FAULT_DISTRIBUTION))
    _advance_identity(session, "knowhow_insights", len(DEMO_INSIGHTS))


def _advance_identity(session: Session, table_name: str, current_id: int) -> None:
    session.execute(
        text("select setval(pg_get_serial_sequence(:table_name, 'id'), :current_id, true)"),
        {"table_name": table_name, "current_id": current_id},
    )


if __name__ == "__main__":
    seed_demo_data()
    print(f"Seeded {len(DEMO_EQUIPMENT)} equipment records.")
