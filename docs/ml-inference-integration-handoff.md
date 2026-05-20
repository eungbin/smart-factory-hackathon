# ML 추론 결과 백엔드/프론트 반영 인수인계

작성일: 2026-05-19  
대상: 공장지기 FastAPI 백엔드 + React 프론트엔드  
목적: 이 문서 하나만 읽고 ML 모델 로딩, 추론 실행, DB 저장, API 응답, 프론트 반영까지 구현할 수 있게 한다.

## 1. 결론

우리 프로젝트에서 ML 추론 결과로 관리해야 하는 출력 데이터는 5개다.

1. RUL / 잔여수명
2. 72시간 내 고장 위험도
3. 대표 고장 유형 분류
4. 고장 유형별 확률
5. 근거 센서

모델 묶음으로 보면 보통 3개 축이다.

- RUL 회귀 모델: RUL, 신뢰구간
- 고장 위험/분류 모델: 위험도, 대표 고장 유형, 유형별 확률
- 설명 가능성 모듈: 근거 센서, feature importance 또는 attention

프론트는 이미 백엔드 API를 통해 데이터를 소비한다. 따라서 프론트 응답 shape는 유지하고, 백엔드에서 `equipment_state_latest`와 prediction 계열 테이블을 갱신하면 화면은 그대로 최신 추론 결과를 사용한다.

현재 MVP 구조는 프론트가 센서값을 생성하거나 백엔드로 전달하지 않는다. 백엔드 `POST /api/v1/simulation/tick`이 가상 센서값 생성, `sensor_readings` 저장, ML stub 추론, 최신 상태 갱신을 한 번에 처리한다.

## 2. 현재 구현 상태

현재 RUL, 위험도, 고장 유형은 실제 ML 모델 결과가 아니라 deterministic stub 결과다. 초기 seed 값은 데모 기본 상태로만 사용하고, 이후 `simulation/tick` 또는 `predictions/run` 호출 결과가 최신 상태를 덮어쓴다.

- 최신 화면용 값은 `equipment_state_latest`에 저장된다.
- 원시 센서 tick은 `sensor_readings`에 저장된다.
- 추론 1회 결과는 `prediction_runs`에 저장된다.
- 고장 유형별 확률은 `prediction_fault_probabilities`에 저장된다.
- 근거 센서는 `prediction_root_causes`에 저장된다.
- `/api/v1/dashboard`, `/api/v1/equipment`, `/api/v1/equipment/{id}`는 이 값을 읽어 프론트 `Equipment` 타입으로 내려준다.
- `/api/v1/equipment/{id}/sensor-history`는 저장된 `sensor_readings`를 우선 사용하고 없으면 fallback 데이터를 만든다.
- `/api/v1/equipment/{id}/rul-history`는 저장된 `prediction_runs`를 우선 사용하고 없으면 fallback 데이터를 만든다.
- `/api/v1/work-orders/generate`는 최신 설비 상태와 최신 root causes를 바탕으로 작업지시서를 만든다.
- 프론트 대시보드는 로컬 `Math.random()` 센서 갱신을 사용하지 않고, API 재조회와 `simulation/tick` 버튼으로 갱신한다.

현재 프론트가 기대하는 핵심 타입은 `src/types/index.ts`의 `Equipment`다.

```ts
export type Equipment = {
  id: number;
  name: string;
  model: string;
  year: number;
  status: 'normal' | 'warn' | 'danger';
  rul: number;
  rulMin: number;
  rulMax: number;
  risk: number;
  lastMaint: string;
  nextPlan: string;
  sensors: {
    vibration: number;
    temp: number;
    current: number;
    pressure: number;
  };
  faultType: string | null;
  faultConf: number | null;
};
```

이 타입은 바꾸지 않는 것을 기본 원칙으로 한다.

## 3. ML 출력 5개 정의

### 3.1 RUL / 잔여수명

저장 필드:

- `prediction_runs.rul_hours`
- `prediction_runs.rul_lower_hours`
- `prediction_runs.rul_upper_hours`
- `equipment_state_latest.rul_hours`
- `equipment_state_latest.rul_lower_hours`
- `equipment_state_latest.rul_upper_hours`

프론트 매핑:

- `Equipment.rul`
- `Equipment.rulMin`
- `Equipment.rulMax`
- 작업지시서 문구: `${rul}h (±${spread}h)`

예시:

```json
{
  "rul": 72,
  "rulMin": 48,
  "rulMax": 96
}
```

### 3.2 72시간 내 고장 위험도

저장 필드:

- `prediction_runs.risk_pct`
- `equipment_state_latest.risk_pct`

프론트 매핑:

- `Equipment.risk`
- 대시보드 위험도 바
- 설비 상세 고장 위험도 게이지
- 작업지시서 위험도

예시:

```json
{
  "risk": 78
}
```

### 3.3 대표 고장 유형 분류

저장 필드:

- `prediction_runs.fault_type_code`
- `equipment_state_latest.fault_type_code`

허용 코드:

- `normal`
- `bearing_fault`
- `belt_loose`
- `rotor_unbalance`
- `shaft_misalignment`
- `hydraulic_seal`
- `other`

프론트 매핑:

- `Equipment.faultType`

표시명 매핑은 백엔드 서비스에서 처리한다.

```py
FAULT_TYPE_LABELS = {
    "normal": "정상",
    "bearing_fault": "베어링 불량",
    "belt_loose": "벨트 장력 이상",
    "rotor_unbalance": "회전체 불균형",
    "shaft_misalignment": "축정렬 불량",
    "hydraulic_seal": "유압 씰 이상",
    "other": "기타",
}
```

### 3.4 고장 유형별 확률

저장 필드:

- `prediction_fault_probabilities.prediction_run_id`
- `prediction_fault_probabilities.fault_type_code`
- `prediction_fault_probabilities.probability_pct`

대표 고장 confidence 매핑:

- `equipment_state_latest.fault_confidence_pct`
- `Equipment.faultConf`

예시:

```json
[
  { "faultTypeCode": "bearing_fault", "probabilityPct": 78 },
  { "faultTypeCode": "belt_loose", "probabilityPct": 12 },
  { "faultTypeCode": "rotor_unbalance", "probabilityPct": 6 },
  { "faultTypeCode": "shaft_misalignment", "probabilityPct": 3 },
  { "faultTypeCode": "hydraulic_seal", "probabilityPct": 1 }
]
```

### 3.5 근거 센서

저장 필드:

- `prediction_root_causes.prediction_run_id`
- `prediction_root_causes.sensor_name`
- `prediction_root_causes.importance_pct`
- `prediction_root_causes.direction`
- `prediction_root_causes.display_text`
- `prediction_root_causes.rank_no`

프론트 매핑:

- 작업지시서 `rootSensors`
- 설비 상세의 feature importance 영역

예시:

```json
[
  { "sensor": "진동 RMS", "importance": 31, "display": "진동 RMS 31%↑" },
  { "sensor": "모터 전류 변동성", "importance": 18, "display": "모터 전류 변동성↑" },
  { "sensor": "유압 온도", "importance": 12, "display": "유압 온도↑" }
]
```

## 4. 입력 데이터

ML 추론 입력은 설비의 최근 센서 시계열 window다.

MVP 입력 센서:

- 진동 RMS: `vibration_rms_g`
- 유압 온도: `hydraulic_temp_c`
- 모터 전류: `motor_current_a`
- 유압 압력: `hydraulic_pressure_bar`

확장 입력:

- C-MAPSS/AI Hub 21변수 입력은 `features` JSONB에 넣는다.

현재 구현 순서:

1. `POST /api/v1/simulation/tick`이 백엔드에서 가상 센서값을 생성한다.
2. 생성된 값은 `sensor_readings`에 저장되고 `equipment_state_latest` 최신 센서값으로 반영된다.
3. 같은 요청 안에서 deterministic stub이 최근 sensor window를 읽어 추론한다.
4. 추론 결과는 `prediction_runs.input_window_start`, `input_window_end`, `input_readings_count`를 포함해 저장된다.
5. 실제 IoT/CSV 연동이 필요해지면 `POST /api/v1/sensor-readings/bulk`를 추가한다.

## 5. DB 구현 목표

다음 테이블을 Alembic revision으로 추가한다. 이미 일부 명세는 `docs/backend-db-api-spec.md`에 있으나, 구현 시 이 문서의 필드를 기준으로 맞춘다.

### 5.1 model_versions

모델 파일과 버전 추적용이다.

현재 MVP 코드에는 아직 구현하지 않았다. 실제 모델 파일을 도입할 때 추가한다.

필수 컬럼:

- `id`
- `model_key`: 예 `rul_lstm_fd001`, `fault_1dcnn_aihub238`
- `version`
- `model_type`: `rul_regression`, `fault_classification`, `integrated`
- `dataset_name`
- `artifact_uri`
- `is_active`
- `trained_at`
- `created_at`

### 5.2 prediction_runs

AI #1 추론 1회 결과의 헤더다.

필수 컬럼:

- `id`
- `equipment_id`
- `model_version_id`: 실제 모델 버전 테이블 도입 후 추가
- `input_window_start`
- `input_window_end`
- `input_readings_count`
- `status`
- `rul_hours`
- `rul_lower_hours`
- `rul_upper_hours`
- `risk_pct`
- `fault_type_code`
- `fault_confidence_pct`
- `summary`
- `raw_output`
- `created_at`

### 5.3 prediction_fault_probabilities

고장 유형별 확률 분포 저장용이다.

필수 컬럼:

- `id`
- `prediction_run_id`
- `fault_type_code`
- `probability_pct`

유니크 제약:

- `(prediction_run_id, fault_type_code)`

### 5.4 prediction_root_causes

근거 센서 저장용이다.

필수 컬럼:

- `id`
- `prediction_run_id`
- `sensor_name`
- `importance_pct`
- `direction`: `increase`, `decrease`, `variance`, `high`, `low`
- `display_text`
- `rank_no`

### 5.5 equipment_state_latest 보강

현재 구현에 없다면 다음 컬럼을 추가한다.

- `latest_prediction_run_id`

이 컬럼은 최신 추론 run과 화면용 캐시를 연결한다.

## 6. 백엔드 파일 구조 제안

다음 구조로 구현한다.

```text
backend/app/
  api/
    predictions.py
  ml/
    __init__.py
    contracts.py
    loader.py
    preprocess.py
    deterministic_stub.py
    infer.py
  schemas/
    predictions.py
  services/
    predictions.py
```

역할:

- `ml/contracts.py`: 모델 입력/출력 dataclass 또는 Pydantic 모델
- `ml/loader.py`: 모델 파일 lazy loading, singleton cache
- `ml/preprocess.py`: DB 센서값을 모델 입력 tensor/array로 변환
- `ml/deterministic_stub.py`: 모델 파일이 없을 때 같은 입력이면 같은 결과를 내는 stub
- `ml/infer.py`: 실제 모델 또는 stub을 호출하는 단일 진입점
- `services/predictions.py`: 트랜잭션, DB 저장, 최신 상태 갱신
- `api/predictions.py`: HTTP endpoint

## 7. ML 계약 코드 형태

`backend/app/ml/contracts.py`는 다음 형태를 목표로 한다.

```py
from dataclasses import dataclass


@dataclass(frozen=True)
class SensorWindow:
    equipment_id: int
    vibration: list[float]
    temperature: list[float]
    current: list[float]
    pressure: list[float]
    features: list[dict] | None = None


@dataclass(frozen=True)
class FaultProbability:
    fault_type_code: str
    probability_pct: float


@dataclass(frozen=True)
class RootSensor:
    sensor_name: str
    importance_pct: float
    direction: str
    display_text: str
    rank_no: int


@dataclass(frozen=True)
class InferenceResult:
    status: str
    rul_hours: int
    rul_lower_hours: int
    rul_upper_hours: int
    risk_pct: float
    fault_type_code: str | None
    fault_confidence_pct: float | None
    fault_probabilities: list[FaultProbability]
    root_causes: list[RootSensor]
    raw_output: dict
```

이 계약은 실제 PyTorch 모델, ONNX 모델, deterministic stub 모두 동일하게 사용한다.

## 8. 모델 로딩 방식

환경변수:

- `RUL_MODEL_PATH`
- `FAULT_MODEL_PATH`
- `ML_DEVICE`: 기본 `cpu`
- `ML_USE_STUB`: 기본 `true`

우선순위:

1. `ML_USE_STUB=true`면 무조건 deterministic stub 사용
2. `ML_USE_STUB=false`이고 모델 파일이 존재하면 실제 모델 로딩
3. 모델 파일이 없으면 서버 부팅 실패보다 stub fallback을 사용하되 로그를 남긴다

예상 `loader.py` 동작:

```py
def get_inference_engine() -> InferenceEngine:
    # lru_cache 또는 module-level singleton
    # 실제 모델 또는 stub 엔진 반환
```

실제 모델 교체 시에도 서비스 계층은 `run_inference(window)`만 호출한다.

## 9. 추론 실행 흐름

`POST /api/v1/predictions/run` 호출 시 다음 순서로 처리한다.

1. `equipment_id` 유효성 확인
2. 최근 센서 window 조회
3. window가 부족하면 `equipment_state_latest` 최신값으로 최소 입력 생성
4. `ml.infer.run_inference(window)` 호출
5. `prediction_runs` insert
6. `prediction_fault_probabilities` bulk insert
7. `prediction_root_causes` bulk insert
8. `equipment_state_latest` update
9. 위험도와 RUL 기준으로 `status` 확정
10. 결과를 프론트가 바로 쓸 수 있는 shape로 응답

트랜잭션은 하나로 묶는다. 5~8 중 하나라도 실패하면 rollback한다.

## 10. 상태 결정 규칙

ML이 `status`를 직접 내더라도 백엔드에서 최종 보정한다.

추천 규칙:

```py
if risk_pct >= 70 or rul_hours <= 96:
    status = "danger"
elif risk_pct >= 30 or rul_hours <= 240:
    status = "warn"
else:
    status = "normal"
```

이 규칙은 운영 기준에 맞춰 나중에 조정 가능하다.

중요: 프론트 색상과 알림은 `status`를 기준으로 움직인다.

## 11. API 명세

### 11.1 POST /api/v1/simulation/tick

백엔드 내장 센서 시뮬레이터를 한 번 실행하고, 생성된 센서값으로 추론까지 실행한다.

요청:

```json
{
  "factoryId": 1,
  "equipmentId": 3,
  "windowHours": 24
}
```

`equipmentId`를 생략하면 공장 전체 활성 설비에 대해 tick을 실행한다.

응답:

```json
{
  "data": {
    "insertedReadings": 1,
    "predictions": [
      {
        "predictionRunId": 9001,
        "equipmentId": 3,
        "status": "danger",
        "rul": 72,
        "rulMin": 48,
        "rulMax": 96,
        "risk": 78,
        "faultTypeCode": "bearing_fault",
        "faultType": "베어링 불량",
        "faultConfidence": 78,
        "faultProbabilities": [
          { "faultTypeCode": "bearing_fault", "faultType": "베어링 불량", "probability": 78 }
        ],
        "rootSensors": [
          { "sensorName": "vibration_rms_g", "importance": 31, "direction": "up", "displayText": "진동 RMS 상승" }
        ],
        "createdAt": "2026-05-19T09:00:00+09:00"
      }
    ]
  }
}
```

### 11.2 POST /api/v1/predictions/run

요청:

```json
{
  "equipmentId": 3,
  "windowHours": 24
}
```

응답:

```json
{
  "data": {
    "predictionRunId": 9001,
    "equipmentId": 3,
    "status": "danger",
    "rul": 72,
    "rulMin": 48,
    "rulMax": 96,
    "risk": 78,
    "faultTypeCode": "bearing_fault",
    "faultType": "베어링 불량",
    "faultConfidence": 78,
    "faultProbabilities": [
      { "faultTypeCode": "bearing_fault", "faultType": "베어링 불량", "probability": 78 },
      { "faultTypeCode": "belt_loose", "faultType": "벨트 장력 이상", "probability": 12 }
    ],
    "rootSensors": [
      { "sensorName": "vibration_rms_g", "importance": 31, "direction": "up", "displayText": "진동 RMS 상승" },
      { "sensorName": "motor_current_a", "importance": 18, "direction": "up", "displayText": "모터 전류 변동성" },
      { "sensorName": "hydraulic_temp_c", "importance": 12, "direction": "up", "displayText": "유압 온도 상승" }
    ]
  }
}
```

### 11.3 GET /api/v1/equipment/{equipmentId}/predictions/latest

최신 저장된 추론 결과를 반환한다. 응답 shape는 `/predictions/run`과 동일하다.

### 11.4 기존 API 반영

`POST /simulation/tick` 또는 `POST /predictions/run` 후 다음 기존 API가 자동으로 새 값을 내려줘야 한다.

- `GET /api/v1/dashboard`
- `GET /api/v1/equipment`
- `GET /api/v1/equipment/{equipmentId}`
- `GET /api/v1/equipment/{equipmentId}/rul-history`
- `POST /api/v1/work-orders/generate`

프론트는 대부분 기존 API를 다시 fetch하기만 하면 최신 추론 결과를 사용한다.

## 12. 프론트 반영 방식

프론트 기본 원칙:

- `Equipment` 타입은 유지한다.
- 대시보드/설비 상세/작업지시서 화면은 API 기반이므로, 백엔드가 `equipment_state_latest`를 갱신하면 기존 화면이 최신 값을 읽는다.
- 브라우저에서 `Math.random()`으로 센서값을 흔들지 않는다.
- 대시보드는 `POST /api/v1/simulation/tick` 버튼으로 백엔드 tick을 실행하고, 이후 `/dashboard`를 다시 조회한다.
- 설비 상세는 `/equipment`, `/sensor-history`, `/rul-history`를 주기적으로 다시 조회한다.

필요하면 추가할 수 있는 API 클라이언트:

```ts
export async function runPrediction(equipmentId: number) {
  const response = await fetch(`${baseUrl}/api/v1/predictions/run`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ equipmentId, windowHours: 24 }),
  });
  if (!response.ok) throw new Error(`Prediction API failed: ${response.status}`);
  return response.json();
}
```

사용 위치 후보:

- 설비 상세 화면에 "추론 실행" 버튼 추가
- 대시보드 진입 시 백그라운드 갱신
- 운영에서는 백엔드 스케줄러가 주기 실행하고 프론트는 조회만 수행

MVP 추천:

- 일반 화면은 기존 조회 API를 사용한다.
- 개발/시연용 갱신은 대시보드의 `센서 tick` 버튼이 담당한다.
- 실제 운영에서는 백엔드 스케줄러가 주기적으로 `simulation/tick` 또는 센서 수집 파이프라인을 실행한다.

## 13. 작업지시서 연결

`POST /api/v1/work-orders/generate`는 다음 값을 최신 추론 결과에서 가져와야 한다.

- RUL 문구: `rul`, `rulMin`, `rulMax`
- 위험도: `risk`
- 고장 유형: `faultType`, `faultConf`
- 근거 센서: 최신 `prediction_root_causes`

현재 작업지시서 서비스에 하드코딩된 `rootSensors`가 있다면, 최신 prediction root causes를 조회하도록 바꾼다.

우선순위:

1. 최신 prediction의 root causes 사용
2. 없으면 fault type과 센서값 기반 deterministic fallback 사용

## 14. RUL 히스토리 연결

현재 `/equipment/{id}/rul-history`는 데모 생성 방식이다. prediction 테이블 구현 후에는 다음 방식으로 바꾼다.

- `prediction_runs`에서 해당 설비의 최근 30일 추론 결과 조회
- 각 run의 `created_at`, `rul_hours`, `rul_lower_hours`, `rul_upper_hours`를 chart shape로 변환
- 데이터가 부족하면 부족한 만큼만 반환한다
- 완전히 없으면 현재처럼 deterministic fallback을 허용한다

프론트 shape:

```ts
export type RulHistoryPoint = {
  date: string;
  rul: number;
  upper: number;
  lower: number;
};
```

## 15. deterministic stub 기준

실제 모델이 없을 때도 API/DB/프론트 연결을 검증해야 한다. stub은 다음 규칙을 권장한다.

입력:

- vibration
- temperature
- current
- pressure

예시 계산:

```py
risk_pct = min(
    99,
    vibration_score * 35
    + temp_score * 25
    + current_score * 20
    + pressure_score * 10
)
rul_hours = max(24, int(600 - risk_pct * 6))
```

대표 고장 유형:

- vibration이 가장 크면 `bearing_fault`
- current가 가장 크면 `belt_loose`
- pressure/temp가 크면 `hydraulic_seal`
- 전체 낮으면 `normal`

stub이라도 같은 입력이면 같은 결과가 나와야 한다. 테스트 안정성을 위해 random을 쓰지 않는다.

## 16. 테스트 기준

반드시 추가할 테스트:

1. `POST /predictions/run`이 5개 출력 데이터를 모두 반환한다.
2. `POST /predictions/run` 후 `equipment_state_latest`가 갱신된다.
3. `prediction_fault_probabilities`에 고장 유형별 확률이 저장된다.
4. `prediction_root_causes`에 근거 센서가 rank 순서대로 저장된다.
5. `GET /equipment/{id}`가 갱신된 RUL/risk/fault 정보를 반환한다.
6. `GET /dashboard`의 alert/count가 갱신된 상태를 반영한다.
7. `GET /equipment/{id}/predictions/latest`가 최신 prediction을 반환한다.
8. 모델 파일이 없어도 `ML_USE_STUB=true`이면 API가 정상 동작한다.

권장 테스트 파일:

```text
backend/tests/test_predictions_api.py
backend/tests/test_prediction_service.py
backend/tests/test_ml_stub.py
```

## 17. 구현 순서

다음 순서대로 구현한다.

1. Alembic revision 추가
   - `sensor_readings`
   - `prediction_runs`
   - `prediction_fault_probabilities`
   - `prediction_root_causes`
   - `equipment_state_latest.latest_prediction_run_id`

2. schema 추가
   - `backend/app/schemas/predictions.py`

3. ML 계약 추가
   - `backend/app/ml/contracts.py`
   - `backend/app/ml/deterministic_stub.py`
   - `backend/app/ml/infer.py`
   - `backend/app/ml/loader.py`

4. 서비스 추가
   - `backend/app/services/predictions.py`
   - `backend/app/services/simulation.py`

5. API 추가
   - `backend/app/api/predictions.py`
   - `backend/app/api/simulation.py`
   - `app/main.py`에 router 등록

6. 기존 서비스 연결
   - `equipment_detail.list_sensor_history`를 sensor readings 기반으로 개선
   - `equipment_detail.list_rul_history`를 prediction 기반으로 개선
   - `work_orders.generate_work_order`의 `rootSensors`를 최신 root causes 기반으로 개선

7. 테스트 실행
   - `backend/.venv/Scripts/python.exe -m unittest discover -s tests`
   - `npm run lint`
   - `npm run build`

8. Docker 반영
   - `cd backend`
   - `docker compose up -d --build`
   - `GET /health`
   - `POST /api/v1/predictions/run`
   - `GET /api/v1/equipment/{id}`

## 18. 완료 조건

완료로 볼 수 있는 기준:

- `POST /api/v1/predictions/run` 한 번으로 5개 ML 출력이 생성된다.
- 생성된 결과가 prediction 계열 테이블에 저장된다.
- `equipment_state_latest`가 같은 트랜잭션에서 갱신된다.
- 기존 프론트 화면이 새 RUL, 위험도, 고장 유형을 표시한다.
- 작업지시서가 최신 근거 센서를 사용한다.
- 프론트 타입 변경 없이 `npm run build`가 통과한다.
- 백엔드 테스트가 통과한다.

## 19. 중요한 주의점

- 고장 유형별 확률과 대표 고장 유형은 분리해서 저장한다. 대표 유형 하나만 저장하면 나중에 설명/리포트가 약해진다.
- 근거 센서는 문자열 배열만 저장하지 말고 `sensor_name`, `importance_pct`, `direction`, `display_text`, `rank_no`로 구조화한다.
- 프론트 응답 shape는 가능하면 유지한다. 백엔드 내부 테이블이 늘어나도 화면 컴포넌트를 크게 바꾸지 않는다.
- 실제 모델 도입 전에는 deterministic stub으로 API, DB, 프론트 연결을 먼저 완성한다.
- random 기반 데모 데이터는 테스트를 불안정하게 만들기 때문에 ML 추론 stub에는 사용하지 않는다.
