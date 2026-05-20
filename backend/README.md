# Gongjangjigi Backend

FastAPI + PostgreSQL + pgvector 백엔드입니다.

## Docker 통합 실행

`backend` 폴더에서 아래 명령어 하나로 API와 DB를 같이 실행합니다.

```powershell
docker compose up -d --build
```

이 명령은 다음을 함께 처리합니다.

- `postgres`: PostgreSQL 16 + pgvector DB 실행
- `api`: FastAPI 백엔드 이미지 빌드 및 실행
- API 컨테이너 시작 시 `alembic upgrade head` 자동 실행
- API 컨테이너 시작 시 DB가 비어 있을 때만 demo seed 자동 실행
- API 컨테이너 시작 시 설비 모델별 RAG 매뉴얼 seed 자동 실행

실행 상태 확인:

```powershell
docker compose ps
```

로그 확인:

```powershell
docker compose logs -f api
```

중지:

```powershell
docker compose down
```

DB 볼륨까지 삭제하고 완전히 초기화:

```powershell
docker compose down -v
```

## 확인 주소

- Health: `http://127.0.0.1:8000/health`
- DB Health: `http://127.0.0.1:8000/api/v1/health/db`
- Dashboard API: `http://127.0.0.1:8000/api/v1/dashboard`
- Equipment API: `http://127.0.0.1:8000/api/v1/equipment`
- Simulation Tick: `POST http://127.0.0.1:8000/api/v1/simulation/tick`
- Prediction Run: `POST http://127.0.0.1:8000/api/v1/predictions/run`
- Swagger UI: `http://127.0.0.1:8000/docs`

시연용 센서/추론 갱신:

```powershell
curl.exe -X POST http://127.0.0.1:8000/api/v1/simulation/tick -H "Content-Type: application/json" -d "{}"
```

특정 설비만 갱신:

```powershell
curl.exe -X POST http://127.0.0.1:8000/api/v1/simulation/tick -H "Content-Type: application/json" -d "{\"equipmentId\":3}"
```

`simulation/tick`은 프론트에서 센서값을 보내지 않습니다. 백엔드가 가상 센서값을 만들고 `sensor_readings`, `prediction_runs`, `prediction_fault_probabilities`, `prediction_root_causes`, `equipment_state_latest`를 함께 갱신합니다.

시연용 RAG 매뉴얼 seed를 수동으로 다시 반영:

```powershell
.\.venv\Scripts\python.exe -m app.db.seed_manuals
```

현재 seed는 `LS350-A`, `LS240-B`, `LS500-C` 모델별 운영 매뉴얼 요약 청크를 `knowledge_documents`, `knowledge_chunks`에 중복 없이 저장합니다.
매뉴얼 원문은 `backend/docs/manuals/*.md`에 있으며, seed 스크립트가 이 Markdown 파일을 읽어 문서 metadata, chunk, embedding을 DB에 적재합니다.

## 프론트엔드 연결

프론트엔드는 기본으로 아래 백엔드 주소를 호출합니다.

```text
http://127.0.0.1:8000
```

다른 주소를 쓰려면 프로젝트 루트의 `.env`에 값을 지정합니다.

```powershell
VITE_API_BASE_URL=http://127.0.0.1:8000
```

## 작업지시서 LLM provider

기본 작업지시서 생성기는 외부 API를 쓰지 않는 `template`입니다. Gemini를 실제로 호출하려면 `backend/.env` 또는 실행 환경에 아래 값을 설정한 뒤 Docker를 다시 올립니다.

```powershell
WORK_ORDER_GENERATOR_PROVIDER=gemini
WORK_ORDER_GENERATOR_FALLBACK_PROVIDER=template
GEMINI_API_KEY=발급받은_키
GEMINI_MODEL=gemini-2.5-flash
```

Gemini 호출 실패, API key 누락, 응답 파싱 실패 시에는 `template`로 fallback되고, 실패 원인은 `work_orders.raw_response`에 기록됩니다.

## 로컬 Python 실행이 필요한 경우

Docker가 아니라 로컬 가상환경에서 API만 직접 실행하려면 아래를 사용합니다.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m app.db.seed
.\.venv\Scripts\uvicorn.exe app.main:app --reload --host 127.0.0.1 --port 8000
```

로컬 실행 시 DB는 여전히 Docker의 `postgres` 서비스를 사용할 수 있습니다.

## 테스트

로컬 가상환경 기준:

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s tests
```
