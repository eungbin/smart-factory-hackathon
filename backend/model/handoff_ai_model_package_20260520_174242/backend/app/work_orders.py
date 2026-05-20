from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from .predictor import predict_rul, risk_to_severity
from .rag import retrieve_manual_chunks
from .schemas import DispatchResponse, WorkOrder, WorkOrderCreate
from .simulator import get_asset


def generate_work_order(payload: WorkOrderCreate) -> WorkOrder:
    asset = get_asset(payload.asset_id)
    prediction = payload.prediction or predict_rul(payload.asset_id)
    chunks = retrieve_manual_chunks(
        f"{asset.primary_issue} {asset.name} 진동 전류 유압 펌프 베어링 커플링 그리스"
    )
    severity = risk_to_severity(prediction.risk_72h)
    estimated_minutes = 30 if severity == "critical" else 20
    order_id = f"WO-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{uuid4().hex[:6].upper()}"

    return WorkOrder(
        id=order_id,
        asset_id=asset.asset_id,
        asset_name=asset.name,
        severity=severity,  # type: ignore[arg-type]
        status="draft",
        generated_at=datetime.now(timezone.utc),
        requested_by=payload.requested_by,
        summary=(
            f"{asset.name}의 72시간 내 고장 위험도는 {prediction.risk_72h:.1f}%이고 "
            f"예상 잔여 가동시간은 {prediction.rul_hours}h입니다. 출근 직후 점검을 권장합니다."
        ),
        root_cause_hypothesis=(
            "진동 RMS 상승, 모터 전류 변동성 증가, 유압 온도 상승이 동시에 관측되어 "
            "유압 펌프 구동부 베어링 마모 또는 커플링 정렬 불량 가능성이 큽니다."
        ),
        inspection_points=[
            "유압 펌프 베어링 하우징 온도와 비정상 소음 확인",
            "모터-펌프 커플링 체결 상태와 축정렬 상태 확인",
            "그리스 보충 상태와 누유 흔적 확인",
            "점검 후 10분 무부하 운전으로 진동 RMS 재측정",
        ],
        tools=["절연 장갑", "토크렌치", "휴대용 진동계", "비접촉 온도계", "그리스 건"],
        consumables=["리튬계 그리스 NLGI #2", "청소용 와이퍼", "표준 케이블 타이"],
        estimated_minutes=estimated_minutes,
        safety_rules=[
            "점검 전 사출기 주전원 차단 및 LOTO 태그 부착",
            "유압 라인 잔압 제거 후 커버 개방",
            "회전체 주변 작업 시 장갑 말림 위험을 확인",
        ],
        checklist=[
            "작업 전 사진 1장 등록",
            "베어링 하우징 온도 65C 미만 확인",
            "진동 RMS 재측정값을 결과 입력 폼에 기록",
            "교체 부품이 없더라도 조치 내용을 코멘트에 남김",
        ],
        manual_sources=[
            {"source": chunk.source, "title": chunk.title, "excerpt": _excerpt(chunk.content)}
            for chunk in chunks
        ],
        dispatch_message=(
            f"[공장지기] 오늘 점검 권장: {asset.name}, RUL {prediction.rul_hours}h, "
            f"위험도 {prediction.risk_72h:.0f}%. 작업지시서 {order_id}가 준비되었습니다."
        ),
    )


def mark_dispatched(order: WorkOrder) -> DispatchResponse:
    return DispatchResponse(
        work_order_id=order.id,
        channel="카카오톡 데모 모달",
        recipient_group="A동 정비 담당자",
        preview=order.dispatch_message,
        dispatched_at=datetime.now(timezone.utc),
    )


def _excerpt(content: str) -> str:
    normalized = " ".join(line.strip("# -") for line in content.splitlines() if line.strip())
    return normalized[:180]

