from dataclasses import dataclass
import json
import urllib.request
from typing import Protocol

from app.schemas.work_orders import WorkOrderPartOut, WorkOrderStepOut


TEMPLATE_MODEL = "template-v1"
GEMINI_API_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
ALLOWED_STEP_CATEGORIES = ("안전", "진단", "윤활", "부품", "복구", "기록")


class WorkOrderGenerationError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class WorkOrderGenerationContext:
    equipment_name: str
    fault_type_text: str
    root_sensors: list[str]
    source_summary: str
    rag_sources: list[dict]


@dataclass(frozen=True)
class WorkOrderGenerationResult:
    provider: str
    model: str
    title: str
    source_summary: str
    steps: list[WorkOrderStepOut]
    parts: list[WorkOrderPartOut]
    total_minutes: int
    total_time_text: str
    tech_level: str
    caution: str
    raw_prompt: str | None
    raw_response: dict


class WorkOrderGenerator(Protocol):
    def generate(self, context: WorkOrderGenerationContext) -> WorkOrderGenerationResult:
        ...


class TemplateWorkOrderGenerator:
    provider = "template"
    model = TEMPLATE_MODEL

    def generate(self, context: WorkOrderGenerationContext) -> WorkOrderGenerationResult:
        return WorkOrderGenerationResult(
            provider=self.provider,
            model=self.model,
            title=f"{context.equipment_name} 예방 정비 작업지시서",
            source_summary=context.source_summary,
            steps=_template_steps(),
            parts=_template_parts(),
            total_minutes=65,
            total_time_text="약 65분",
            tech_level="정비 2급 이상",
            caution="유압 잔압을 반드시 해제한 뒤 작업하세요. 고온 부위 접촉에 주의하고 교체 부품 번호를 확인하세요.",
            raw_prompt=None,
            raw_response={
                "provider": self.provider,
                "model": self.model,
                "rootSensors": context.root_sensors,
                "ragSources": context.rag_sources,
            },
        )


class GeminiWorkOrderGenerator:
    provider = "gemini"

    def __init__(self, api_key: str | None, model: str, transport=None) -> None:
        self.api_key = api_key
        self.model = model
        self.transport = transport or _post_gemini_generate_content

    def generate(self, context: WorkOrderGenerationContext) -> WorkOrderGenerationResult:
        if not self.api_key:
            raise WorkOrderGenerationError("provider_not_configured", "GEMINI_API_KEY is not configured.")
        prompt = _build_work_order_prompt(context)
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseJsonSchema": _work_order_response_schema(),
            },
        }
        url = f"{GEMINI_API_BASE_URL}/models/{self.model}:generateContent"
        response = self.transport(url, self.api_key, payload)
        data = _parse_gemini_work_order_response(response)
        steps = [WorkOrderStepOut(**step) for step in data["steps"]]
        parts = [WorkOrderPartOut(**part) for part in data["parts"]]

        return WorkOrderGenerationResult(
            provider=self.provider,
            model=self.model,
            title=data["title"],
            source_summary=context.source_summary,
            steps=steps,
            parts=parts,
            total_minutes=_minutes_from_text(data["totalTime"]),
            total_time_text=data["totalTime"],
            tech_level=data["techLevel"],
            caution=data["caution"],
            raw_prompt=prompt,
            raw_response={
                "provider": self.provider,
                "model": self.model,
                "geminiResponse": response,
            },
        )


class OpenAIWorkOrderGenerator:
    provider = "openai"

    def __init__(self, api_key: str | None, model: str) -> None:
        self.api_key = api_key
        self.model = model

    def generate(self, context: WorkOrderGenerationContext) -> WorkOrderGenerationResult:
        if not self.api_key:
            raise WorkOrderGenerationError("provider_not_configured", "OPENAI_API_KEY is not configured.")
        raise WorkOrderGenerationError("provider_not_implemented", "OpenAI work order generation is not implemented yet.")


def get_work_order_generator(
    provider: str,
    gemini_api_key: str | None = None,
    gemini_model: str = "gemini-1.5-flash",
    openai_api_key: str | None = None,
    openai_model: str = "gpt-4.1-mini",
) -> WorkOrderGenerator:
    if provider == "template":
        return TemplateWorkOrderGenerator()
    if provider == "gemini":
        return GeminiWorkOrderGenerator(gemini_api_key, gemini_model)
    if provider == "openai":
        return OpenAIWorkOrderGenerator(openai_api_key, openai_model)
    raise ValueError(f"Unsupported work order generator provider: {provider}")


def _template_steps() -> list[WorkOrderStepOut]:
    return [
        WorkOrderStepOut(no=1, category="안전", action="전원 차단 후 잠금(LOTO) 및 주전원 차단기 태그 부착", tool="잠금 태그 세트", time="5분", safety=True),
        WorkOrderStepOut(no=2, category="진단", action="베어링 부위 육안 점검 및 이상음, 발열, 누유 여부 확인", tool="청음봉, 열화상 카메라", time="10분", safety=False),
        WorkOrderStepOut(no=3, category="윤활", action="베어링 그리스 보충 또는 교체 후 권장 그리스 적용", tool="그리스 건, 주입 노즐", time="15분", safety=False),
        WorkOrderStepOut(no=4, category="부품", action="마모 및 유격 확인 후 기준 초과 시 예비 베어링 교체", tool="버니어 캘리퍼스, 진동 측정기", time="20분", safety=False),
        WorkOrderStepOut(no=5, category="복구", action="전원 복구 후 시운전 5분 동안 진동, 온도, 전류 정상 범위 확인", tool="멀티미터, 진동 측정기", time="10분", safety=False),
        WorkOrderStepOut(no=6, category="기록", action="정비 결과와 교체 부품, 소요 시간, 특이사항을 시스템에 입력", tool="스마트폰 또는 PC", time="5분", safety=False),
    ]


def _template_parts() -> list[WorkOrderPartOut]:
    return [
        WorkOrderPartOut(name="Mobilux EP 2 그리스", qty="1통(100g)", stock="보유중"),
        WorkOrderPartOut(name="베어링 #6205-2RS", qty="1개", stock="재고 1개"),
        WorkOrderPartOut(name="그리스 주입 노즐 #3", qty="1개", stock="보유중"),
    ]


def _post_gemini_generate_content(url: str, api_key: str, payload: dict) -> dict:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        raise WorkOrderGenerationError("provider_call_failed", str(exc)) from exc


def _build_work_order_prompt(context: WorkOrderGenerationContext) -> str:
    rag_text = "\n".join(
        f"- {source.get('sourceLabel', '')} {source.get('heading', '')}: {source.get('body', '')}"
        for source in context.rag_sources
    )
    root_sensor_text = ", ".join(context.root_sensors)
    return (
        "공장 설비 정비 작업지시서를 JSON으로 생성하세요.\n"
        f"설비: {context.equipment_name}\n"
        f"AI 진단: {context.fault_type_text}\n"
        f"근거 센서: {root_sensor_text}\n"
        f"출처 요약: {context.source_summary}\n"
        f"RAG 근거:\n{rag_text}\n"
        "응답은 반드시 제공된 JSON schema를 따르고, 작업 단계 category는 안전, 진단, 윤활, 부품, 복구, 기록 중 하나만 사용하세요."
    )


def _work_order_response_schema() -> dict:
    step_schema = {
        "type": "object",
        "properties": {
            "no": {"type": "integer"},
            "category": {"type": "string", "enum": list(ALLOWED_STEP_CATEGORIES)},
            "action": {"type": "string"},
            "tool": {"type": "string"},
            "time": {"type": "string"},
            "safety": {"type": "boolean"},
        },
        "required": ["no", "category", "action", "tool", "time", "safety"],
    }
    part_schema = {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "qty": {"type": "string"},
            "stock": {"type": "string"},
        },
        "required": ["name", "qty", "stock"],
    }
    return {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "steps": {"type": "array", "items": step_schema},
            "parts": {"type": "array", "items": part_schema},
            "totalTime": {"type": "string"},
            "techLevel": {"type": "string"},
            "caution": {"type": "string"},
        },
        "required": ["title", "steps", "parts", "totalTime", "techLevel", "caution"],
    }


def _parse_gemini_work_order_response(response: dict) -> dict:
    try:
        text = response["candidates"][0]["content"]["parts"][0]["text"]
        data = json.loads(text)
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        raise WorkOrderGenerationError("provider_response_invalid", "Gemini response did not contain valid JSON.") from exc

    required = ["title", "steps", "parts", "totalTime", "techLevel", "caution"]
    if not all(key in data for key in required):
        raise WorkOrderGenerationError("provider_response_invalid", "Gemini response is missing required fields.")
    if not isinstance(data["steps"], list):
        raise WorkOrderGenerationError("provider_response_invalid", "Gemini response steps must be a list.")
    invalid_categories = [
        step.get("category") if isinstance(step, dict) else None
        for step in data["steps"]
        if not isinstance(step, dict) or step.get("category") not in ALLOWED_STEP_CATEGORIES
    ]
    if invalid_categories:
        raise WorkOrderGenerationError("provider_response_invalid", "Gemini response contains an unknown step category.")
    return data


def _minutes_from_text(value: str) -> int:
    digits = "".join(char for char in value if char.isdigit())
    if not digits:
        raise WorkOrderGenerationError("provider_response_invalid", "totalTime must include minutes.")
    return int(digits)
