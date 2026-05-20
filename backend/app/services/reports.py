from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Equipment, KnowhowInsight, LearningQueue, MaintenanceRecord, MonthlyFaultDistribution, MonthlyReport
from app.schemas.reports import (
    FaultDistributionOut,
    LearnedKnowledgeOut,
    MonthlyReportOut,
    MonthlyStatOut,
    ReportInsightOut,
    ReportKpisOut,
    ReportMonthOut,
)


KST = timezone(timedelta(hours=9))
RECENT_MONTH_COUNT = 6
LIVE_REPORT_START_MONTH = date(2026, 5, 1)

FAULT_META = {
    "normal": ("정상", "#4ade80"),
    "bearing_fault": ("베어링 불량", "#f87171"),
    "belt_loose": ("벨트 장력 이상", "#fbbf24"),
    "rotor_unbalance": ("회전체 불균형", "#a78bfa"),
    "shaft_misalignment": ("축정렬 불량", "#60a5fa"),
    "hydraulic_seal": ("유압 씰 이상", "#38bdf8"),
    "other": ("기타", "#94a3b8"),
}


@dataclass(frozen=True)
class LiveMonthlyReport:
    kpis: ReportKpisOut
    stat: MonthlyStatOut
    fault_distribution: list[FaultDistributionOut]
    insights: list[ReportInsightOut]
    learned_knowledge: list[LearnedKnowledgeOut]


def get_monthly_report(
    db: Session,
    factory_id: int = 1,
    month: str | None = None,
    today: date | None = None,
) -> MonthlyReportOut:
    reports = list(
        db.execute(
            select(MonthlyReport)
            .where(MonthlyReport.factory_id == factory_id)
            .order_by(MonthlyReport.month)
        ).scalars()
    )

    if not reports:
        return MonthlyReportOut(
            month=month or "",
            availableMonths=[],
            kpis=ReportKpisOut(
                unplannedDowntimeHours=0,
                preventedCount=0,
                mttrMinutes=0,
                learningDataCount=0,
            ),
            monthlyStats=[],
            faultDistribution=[],
            insights=[],
            learnedKnowledge=[],
        )

    today = today or datetime.now(KST).date()
    current_month = _month_start(today)
    target_month = _parse_month_key(month) if month else current_month
    target_key = _month_key(target_month)
    available_months = _recent_months(current_month, RECENT_MONTH_COUNT)
    reports_by_month = {_month_key(report.month): report for report in reports}
    live_target = _build_live_month_report(db, factory_id, target_month) if _is_live_month(target_month) else None
    seed_target = _report_for_month(reports, reports_by_month, target_month)
    seed_fault_distribution = _load_seed_fault_distribution(db, seed_target)
    seed_insights = _load_seed_insights(db, seed_target)

    return MonthlyReportOut(
        month=target_key,
        availableMonths=[ReportMonthOut(month=_month_key(item), label=_month_label(item)) for item in available_months],
        kpis=live_target.kpis if live_target else _seed_kpis(seed_target),
        monthlyStats=[
            _build_monthly_stat(db, reports, reports_by_month, factory_id, item)
            for item in available_months
        ],
        faultDistribution=live_target.fault_distribution if live_target else _seed_fault_distribution(seed_fault_distribution),
        insights=live_target.insights if live_target else _seed_insights(seed_insights),
        learnedKnowledge=live_target.learned_knowledge if live_target else _seed_learned_knowledge(seed_insights),
    )


def _build_live_month_report(db: Session, factory_id: int, month: date) -> LiveMonthlyReport:
    records = _load_live_records(db, factory_id, month)
    queue_rows = _load_live_learning_rows(db, factory_id, month)
    queue_by_record_id = {row.maintenance_record_id: row for row in queue_rows}
    prevented_count = sum(1 for record, _equipment in records if _is_preventive(record.maintenance_type))
    unplanned_minutes = sum(
        record.duration_minutes
        for record, _equipment in records
        if not _is_preventive(record.maintenance_type)
    )
    mttr_minutes = round(sum(record.duration_minutes for record, _equipment in records) / len(records)) if records else 0

    kpis = ReportKpisOut(
        unplannedDowntimeHours=round(unplanned_minutes / 60),
        preventedCount=prevented_count,
        mttrMinutes=mttr_minutes,
        learningDataCount=len(queue_rows),
    )
    return LiveMonthlyReport(
        kpis=kpis,
        stat=MonthlyStatOut(
            month=_month_label(month),
            downtime=kpis.unplannedDowntimeHours,
            prevented=kpis.preventedCount,
            mttr=kpis.mttrMinutes,
        ),
        fault_distribution=_live_fault_distribution([record for record, _equipment in records]),
        insights=_live_insights(month, records, kpis),
        learned_knowledge=_live_learned_knowledge(records, queue_by_record_id),
    )


def _load_live_records(db: Session, factory_id: int, month: date) -> list[tuple[MaintenanceRecord, Equipment]]:
    start, end = _month_bounds(month)
    return list(
        db.execute(
            select(MaintenanceRecord, Equipment)
            .join(Equipment, Equipment.id == MaintenanceRecord.equipment_id)
            .where(Equipment.factory_id == factory_id)
            .where(MaintenanceRecord.performed_at >= start)
            .where(MaintenanceRecord.performed_at < end)
            .order_by(MaintenanceRecord.performed_at.desc(), MaintenanceRecord.id.desc())
        ).all()
    )


def _load_live_learning_rows(db: Session, factory_id: int, month: date) -> list[LearningQueue]:
    start, end = _month_bounds(month)
    return list(
        db.execute(
            select(LearningQueue)
            .join(MaintenanceRecord, MaintenanceRecord.id == LearningQueue.maintenance_record_id)
            .join(Equipment, Equipment.id == LearningQueue.equipment_id)
            .where(Equipment.factory_id == factory_id)
            .where(MaintenanceRecord.performed_at >= start)
            .where(MaintenanceRecord.performed_at < end)
            .order_by(LearningQueue.id.desc())
        ).scalars()
    )


def _live_fault_distribution(records: list[MaintenanceRecord]) -> list[FaultDistributionOut]:
    codes = [_fault_code_from_record(record) for record in records]
    counts = Counter(code for code in codes if code)
    total = sum(counts.values())
    if total == 0:
        return []

    items: list[FaultDistributionOut] = []
    for code, count in counts.most_common():
        name, color = FAULT_META.get(code, FAULT_META["other"])
        items.append(FaultDistributionOut(name=name, value=round(count / total * 100), color=color))
    return items


def _live_insights(
    month: date,
    records: list[tuple[MaintenanceRecord, Equipment]],
    kpis: ReportKpisOut,
) -> list[ReportInsightOut]:
    if not records:
        return [
            ReportInsightOut(
                icon="K",
                title=f"{_month_label(month)} 데이터 수집 대기",
                body="아직 해당 월에 저장된 정비 결과가 없습니다. 결과 입력이 쌓이면 KPI와 학습 큐가 자동 집계됩니다.",
                priority="info",
            )
        ]

    top_fault = _top_fault_label([record for record, _equipment in records])
    return [
        ReportInsightOut(
            icon="K",
            title=f"{_month_label(month)} 정비 결과 {len(records)}건 반영",
            body=f"이번 달 저장된 정비 결과 {len(records)}건과 학습 큐 {kpis.learningDataCount}건을 리포트에 반영했습니다.",
            priority="info",
        ),
        ReportInsightOut(
            icon="T",
            title=f"평균 정비 시간 {kpis.mttrMinutes}분",
            body="정비 결과 입력의 소요 시간을 기준으로 월간 평균 MTTR을 산출했습니다.",
            priority="low",
        ),
        ReportInsightOut(
            icon="!",
            title=f"주요 고장 유형: {top_fault}",
            body="실제 고장 유형 라벨 또는 AI 정확도 평가 값을 기준으로 고장 유형 분포를 구성했습니다.",
            priority="medium",
        ),
        ReportInsightOut(
            icon="N",
            title=f"예방 정비 {kpis.preventedCount}건",
            body="예방 정비로 입력된 작업은 비계획 정지 시간이 아닌 예방 완료 건수로 집계됩니다.",
            priority="info",
        ),
    ]


def _live_learned_knowledge(
    records: list[tuple[MaintenanceRecord, Equipment]],
    queue_by_record_id: dict[int, LearningQueue],
) -> list[LearnedKnowledgeOut]:
    learned: list[LearnedKnowledgeOut] = []
    for record, equipment in records:
        queue = queue_by_record_id.get(record.id)
        learned.append(
            LearnedKnowledgeOut(
                id=queue.queue_key if queue else f"K-LIVE-{record.id:03d}",
                equip=equipment.name,
                content=record.note or record.ai_accuracy_note or f"{record.maintenance_type} 결과가 학습 데이터로 적재되었습니다.",
                confidence=90 if _fault_code_from_record(record) else 75,
                date=record.performed_at.date().isoformat(),
            )
        )
    return learned


def _build_monthly_stat(
    db: Session,
    reports: list[MonthlyReport],
    reports_by_month: dict[str, MonthlyReport],
    factory_id: int,
    month: date,
) -> MonthlyStatOut:
    if _is_live_month(month):
        return _build_live_month_report(db, factory_id, month).stat

    report = _report_for_month(reports, reports_by_month, month)
    return MonthlyStatOut(
        month=_month_label(month),
        downtime=_int(report.unplanned_downtime_hours),
        prevented=report.prevented_count,
        mttr=_int(report.mttr_minutes),
    )


def _report_for_month(
    reports: list[MonthlyReport],
    reports_by_month: dict[str, MonthlyReport],
    month: date,
) -> MonthlyReport:
    exact = reports_by_month.get(_month_key(month))
    if exact is not None:
        return exact

    previous_reports = [report for report in reports if report.month <= month]
    if previous_reports:
        return previous_reports[-1]
    return reports[0]


def _seed_kpis(report: MonthlyReport) -> ReportKpisOut:
    return ReportKpisOut(
        unplannedDowntimeHours=_int(report.unplanned_downtime_hours),
        preventedCount=report.prevented_count,
        mttrMinutes=_int(report.mttr_minutes),
        learningDataCount=report.learning_data_count,
    )


def _load_seed_fault_distribution(db: Session, report: MonthlyReport) -> list[MonthlyFaultDistribution]:
    return list(
        db.execute(
            select(MonthlyFaultDistribution)
            .where(MonthlyFaultDistribution.monthly_report_id == report.id)
            .order_by(MonthlyFaultDistribution.sort_order)
        ).scalars()
    )


def _load_seed_insights(db: Session, report: MonthlyReport) -> list[KnowhowInsight]:
    return list(
        db.execute(
            select(KnowhowInsight)
            .where(KnowhowInsight.monthly_report_id == report.id)
            .order_by(KnowhowInsight.id)
        ).scalars()
    )


def _seed_fault_distribution(items: list[MonthlyFaultDistribution]) -> list[FaultDistributionOut]:
    return [
        FaultDistributionOut(
            name=item.display_name,
            value=_int(item.percentage),
            color=item.color,
        )
        for item in items
    ]


def _seed_insights(items: list[KnowhowInsight]) -> list[ReportInsightOut]:
    return [
        ReportInsightOut(
            icon=item.icon or "",
            title=item.title,
            body=item.body,
            priority=item.priority,
        )
        for item in items
        if item.insight_type == "monthly_insight"
    ]


def _seed_learned_knowledge(items: list[KnowhowInsight]) -> list[LearnedKnowledgeOut]:
    return [
        LearnedKnowledgeOut(
            id=item.knowledge_key or f"K-{item.id:03d}",
            equip=item.equipment_label or "전체",
            content=item.body,
            confidence=_int(item.confidence_pct),
            date=item.knowledge_date.isoformat() if item.knowledge_date else "",
        )
        for item in items
        if item.insight_type == "learned_knowledge"
    ]


def _is_live_month(value: date) -> bool:
    return value >= LIVE_REPORT_START_MONTH


def _month_bounds(value: date) -> tuple[datetime, datetime]:
    start_month = _month_start(value)
    end_month = _add_months(start_month, 1)
    return (
        datetime(start_month.year, start_month.month, 1, tzinfo=KST),
        datetime(end_month.year, end_month.month, 1, tzinfo=KST),
    )


def _is_preventive(value: str) -> bool:
    normalized = value.lower()
    return "preventive" in normalized or "예방" in value


def _fault_code_from_record(record: MaintenanceRecord) -> str | None:
    if record.actual_fault_type_code:
        return record.actual_fault_type_code
    text = record.ai_accuracy_note or ""
    if "베어링" in text:
        return "bearing_fault"
    if "벨트" in text:
        return "belt_loose"
    if "회전체" in text or "불평형" in text or "불균형" in text:
        return "rotor_unbalance"
    if "축정렬" in text:
        return "shaft_misalignment"
    if "씰" in text or "유압" in text:
        return "hydraulic_seal"
    if "이상 없음" in text or "정상" in text:
        return "normal"
    if "다른" in text or "기타" in text:
        return "other"
    return None


def _top_fault_label(records: list[MaintenanceRecord]) -> str:
    counts = Counter(code for code in (_fault_code_from_record(record) for record in records) if code)
    if not counts:
        return "미분류"
    top_code = counts.most_common(1)[0][0]
    return FAULT_META.get(top_code, FAULT_META["other"])[0]


def _recent_months(current_month: date, count: int) -> list[date]:
    start = _add_months(current_month, -(count - 1))
    return [_add_months(start, offset) for offset in range(count)]


def _add_months(value: date, months: int) -> date:
    year = value.year + (value.month - 1 + months) // 12
    month = (value.month - 1 + months) % 12 + 1
    return date(year, month, 1)


def _month_start(value: date) -> date:
    return date(value.year, value.month, 1)


def _parse_month_key(value: str | None) -> date:
    if value is None:
        raise ValueError("month is required")
    return date.fromisoformat(f"{value}-01")


def _month_key(value: date) -> str:
    return value.strftime("%Y-%m")


def _month_label(value: date) -> str:
    return f"{value.month}월"


def _int(value: Decimal | int | None) -> int:
    if value is None:
        return 0
    return int(round(float(value)))
