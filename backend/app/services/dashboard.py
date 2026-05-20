from sqlalchemy.orm import Session

from app.schemas.dashboard import DashboardAlertOut, DashboardOut, DashboardSummaryOut
from app.schemas.equipment import EquipmentOut
from app.services.equipment import list_equipment


MONTHLY_UPTIME_PCT = 96.2


def get_dashboard(db: Session, factory_id: int = 1) -> DashboardOut:
    equipment = list_equipment(db, factory_id=factory_id)
    return DashboardOut(
        summary=build_summary(equipment),
        alerts=build_alerts(equipment),
        equipment=equipment,
    )


def build_summary(equipment: list[EquipmentOut]) -> DashboardSummaryOut:
    danger_count = sum(1 for item in equipment if item.status == "danger")
    warn_count = sum(1 for item in equipment if item.status == "warn")
    normal_count = sum(1 for item in equipment if item.status == "normal")

    return DashboardSummaryOut(
        totalEquipment=len(equipment),
        dangerCount=danger_count,
        warnCount=warn_count,
        normalCount=normal_count,
        monthlyUptimePct=MONTHLY_UPTIME_PCT,
    )


def build_alerts(equipment: list[EquipmentOut]) -> list[DashboardAlertOut]:
    candidates = [item for item in equipment if item.status in {"danger", "warn"}]
    candidates.sort(key=lambda item: (0 if item.status == "danger" else 1, -item.risk, item.id))

    return [
        DashboardAlertOut(
            id=index,
            equipmentId=item.id,
            equipmentName=item.name,
            level=item.status,
            title=item.nextPlan,
            rulHours=item.rul,
            rulRangeText=build_rul_range_text(item),
            riskPct=item.risk,
            faultType=item.faultType,
        )
        for index, item in enumerate(candidates, start=101)
    ]


def build_rul_range_text(equipment: EquipmentOut) -> str:
    spread = max(abs(equipment.rul - equipment.rulMin), abs(equipment.rulMax - equipment.rul))
    return f"{equipment.rul}h (±{spread}h)"
