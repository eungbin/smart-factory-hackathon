# AI 모델 개발 및 검증 인수인계 문서

작성 목적: 공장지기 MVP에서 AI 모델 개발자가 프론트엔드/백엔드 담당자에게 넘겨야 할 결과물, 모델 해석, 연동 주의사항을 한 번에 전달하기 위한 문서입니다.

## 1. 전체 결론

공장지기 MVP의 AI는 하나의 만능 모델이 아니라 다음 두 축으로 나누어 연동해야 합니다.

| 역할 | 사용 데이터 | 현재 권장 방식 | 제품 내 표현 |
|---|---|---|---|
| RUL 회귀 | NASA C-MAPSS | GRU + TCN + PatchTST 앙상블 | 잔여 가동시간, 72시간 위험도 |
| 고장 분류 | AI-Hub 기계시설물 고장 예지 센서 | 전류 기반 정상/고장 + 진동 기반 원인 후보 Top-3 | 고장 알림, 추정 원인 후보 |

중요한 해석:

- NASA C-MAPSS는 RUL 회귀 파이프라인을 검증하기 위한 벤치마크 데이터입니다.
- AI-Hub는 전동기 전류/진동 기반 정상/고장 및 고장 유형 분류에 적합합니다.
- AI-Hub 공개 설명 기준으로 RUL 정답 라벨이 명확하지 않으므로, AI-Hub로 RUL을 학습했다고 말하면 안 됩니다.
- 실제 공장 데이터가 들어오면 NASA 모델을 그대로 적용하는 것이 아니라, 같은 구조와 검증 방식으로 재학습 또는 보정해야 합니다.

## 2. 현재 백엔드 연동 상태

현재 FastAPI에는 다음 엔드포인트가 있습니다.

| Endpoint | 역할 | 현재 상태 |
|---|---|---|
| `POST /api/predict/rul` | RUL 예측 | C-MAPSS 검증 결과 CSV를 데모 설비에 매핑 |
| `POST /api/predict/fault` | 고장 분류 | 아직 AI-Hub 학습 모델이 아니라 데모용 경량 분류기 |
| `POST /api/predict/health` | RUL + fault 통합 | 프론트에서 주로 호출하는 통합 엔드포인트 |
| `GET /api/cmapss/benchmark` | RUL 벤치마크 요약 | C-MAPSS 실험 결과 확인 |
| `GET /api/cmapss/demo-predictions` | 데모 예측 목록 | UI 데모용 예측값 확인 |

따라서 프론트/백엔드 담당자에게 넘길 때 반드시 알려야 할 점:

- RUL 쪽은 현재 데모 연동이 되어 있습니다.
- 고장 분류 쪽은 실험 산출물은 있지만, 운영 API에 joblib 모델 로딩이 아직 완전히 연결되지 않았습니다.
- 다음 담당자의 1순위 작업은 `data/models/aihub_model_registry.json`를 읽고 AI-Hub joblib 모델을 `/api/predict/fault` 또는 `/api/predict/health`에 연결하는 것입니다.

## 2-1. 실시간 서버 입력/출력 계약

프론트/백엔드 연동에서 가장 중요한 기준은 "서버로 어떤 센서 데이터가 들어오고, 모델 서버가 어떤 예측 결과를 돌려주는가"입니다.

정확한 실행 흐름은 아래처럼 두 모델이 모두 돌아가는 구조입니다.

```text
실시간 센서 입력
  -> 공통 전처리/window 생성
  -> 1단계 RUL 회귀 모델 입력
  -> 1단계 RUL 회귀 모델 출력
  -> 2단계 고장 분류 모델 입력
  -> 2단계 고장 분류 모델 출력
  -> /api/predict/health 통합 응답
  -> 프론트 대시보드 출력
```

현재 코드도 의도는 이 순서입니다.

```python
rul_prediction = predict_rul(asset_id, window)
fault_prediction = predict_fault_class(asset_id, window, rul_prediction)
```

즉 분류 모델은 센서 입력만 보는 것이 아니라, 필요하면 RUL 회귀 결과를 context로 같이 받을 수 있습니다. 다만 중요한 점은, 분류 모델 입력이 RUL 출력만이면 안 된다는 것입니다. 고장 원인 분류는 전류/진동 feature를 주 입력으로 쓰고, RUL 결과는 위험도 보정이나 evidence 문구에 보조로 쓰는 구조가 가장 안전합니다.

### 1단계: RUL 회귀 모델 입력

실제 실시간 연동에서 RUL 모델은 최근 N개 시점의 센서 window를 입력으로 받아야 합니다. C-MAPSS 실험에서는 `50 cycle window`를 사용했으므로, MVP도 우선 50개 시점 window를 기준으로 맞추는 것이 좋습니다.

```json
{
  "asset_id": "MOTOR-01",
  "timestamp": "2026-05-20T10:00:00+09:00",
  "schema_version": "factory-rul-window-v1",
  "window_size": 50,
  "rul_window": [
    {
      "t": 1,
      "temperature": 62.0,
      "current_rms": 0.18,
      "current_std": 0.05,
      "vibration_rms": 0.08,
      "vibration_peak": 0.20,
      "pressure": 130.0,
      "operating_mode": 0
    }
  ]
}
```

RUL 입력 필드:

| 필드 | 의미 |
|---|---|
| `asset_id` | 설비 ID |
| `timestamp` | 센서 window 마지막 시각 |
| `schema_version` | 입력 스키마 버전 |
| `window_size` | RUL 모델이 보는 시계열 길이 |
| `rul_window` | 최근 센서 시계열 |
| `temperature/current/vibration/pressure` | 공장 센서 feature |
| `operating_mode` | 운전 조건 또는 생산 조건 |

주의:

- 현재 C-MAPSS 모델은 원래 `operational_setting_1~3`, `sensor_1~21` 형태로 학습되었습니다.
- 공장 실시간 데이터에 적용하려면 공장 센서 컬럼을 고정하고 같은 구조로 재학습 또는 보정해야 합니다.
- 데모에서는 이미 계산된 C-MAPSS 예측 CSV를 설비에 매핑해 RUL을 보여주고 있습니다.

### 1단계: RUL 회귀 모델 출력

```json
{
  "model_type": "rul_regression",
  "asset_id": "MOTOR-01",
  "model_version": "cmapss-fd001-fd004-validated-gru-tcn-patchtst-ensemble-v0.5",
  "rul_hours": 72,
  "risk_72h": 65.0,
  "confidence_interval": [54, 90],
  "anomaly_score": 0.42,
  "contributing_sensors": [
    {"key": "vibration_rms", "label": "진동 RMS", "contribution": 0.38},
    {"key": "current_rms", "label": "전류 RMS", "contribution": 0.31}
  ],
  "generated_at": "2026-05-20T10:00:00Z"
}
```

프론트 표시:

| RUL 출력 | 프론트 표시 |
|---|---|
| `rul_hours` | 잔여 가동시간 |
| `risk_72h` | 72시간 내 위험도 |
| `confidence_interval` | 예측 범위 |
| `anomaly_score` | 이상도 |
| `contributing_sensors` | 위험도 근거 센서 |

### 2단계: 고장 분류 모델 입력

분류 모델은 전류/진동 feature를 주 입력으로 받고, 방금 나온 RUL 결과를 context로 함께 받을 수 있습니다.

```json
{
  "asset_id": "MOTOR-01",
  "timestamp": "2026-05-20T10:00:00+09:00",
  "schema_version": "factory-fault-features-v1",
  "current_features": {
    "rms": 0.18,
    "mean": 0.01,
    "std": 0.05,
    "peak_to_peak": 0.31
  },
  "vibration_features": {
    "rms": 0.08,
    "mean": 0.00,
    "std": 0.02,
    "peak_to_peak": 0.20
  },
  "rul_context": {
    "rul_hours": 72,
    "risk_72h": 65.0,
    "anomaly_score": 0.42
  }
}
```

분류 입력 필드:

| 필드 | 의미 |
|---|---|
| `current_features` | 전류 기반 정상/고장 이진분류 입력 |
| `vibration_features` | 진동 기반 고장 원인 후보 분류 입력 |
| `rul_context` | RUL 모델 출력값. 분류 confidence 보정 또는 evidence에 사용 |

### 2단계: 고장 분류 모델 출력

```json
{
  "model_type": "fault_classification",
  "asset_id": "MOTOR-01",
  "model_version": "aihub-238-current-vibration-v1",
  "is_fault": true,
  "fault_probability": 0.81,
  "fault_code": "01",
  "fault_label": "베어링 불량",
  "top_classes": [
    {"code": "01", "label": "베어링 불량", "probability": 0.62},
    {"code": "03", "label": "축정렬 불량", "probability": 0.24},
    {"code": "04", "label": "벨트 느슨함", "probability": 0.08}
  ],
  "evidence": [
    "전류 feature 기준 고장 가능성 0.81",
    "진동 feature 기준 베어링 불량 후보가 가장 높음",
    "RUL 72h로 단기 점검 필요"
  ],
  "source": "AI-Hub current binary + vibration top-3 candidate policy",
  "generated_at": "2026-05-20T10:00:00Z"
}
```

프론트 표시:

| 분류 출력 | 프론트 표시 |
|---|---|
| `is_fault` | 정상/주의/위험 상태 |
| `fault_probability` | 고장 가능성 |
| `top_classes` | 추정 원인 후보 Top-3 |
| `evidence` | 판단 근거 |
| `source` | 모델 출처 |

### 3단계: 프론트로 나가는 통합 출력

프론트는 회귀 출력과 분류 출력을 따로 받아도 되지만, MVP에서는 `/api/predict/health` 하나로 묶어서 받는 것이 좋습니다.

```json
{
  "asset_id": "MOTOR-01",
  "rul": {
    "rul_hours": 72,
    "risk_72h": 65.0,
    "confidence_interval": [54, 90],
    "model_version": "cmapss-fd001-fd004-validated-gru-tcn-patchtst-ensemble-v0.5"
  },
  "fault": {
    "is_fault": true,
    "fault_probability": 0.81,
    "fault_label": "베어링 불량",
    "top_classes": [
      {"code": "01", "label": "베어링 불량", "probability": 0.62},
      {"code": "03", "label": "축정렬 불량", "probability": 0.24},
      {"code": "04", "label": "벨트 느슨함", "probability": 0.08}
    ],
    "model_version": "aihub-238-current-vibration-v1"
  },
  "recommended_action": "72시간 내 베어링/축정렬 우선 점검",
  "generated_at": "2026-05-20T10:00:00Z"
}
```

### 현재 바로 동작하는 입력

현재 FastAPI의 `PredictRequest`는 다음 구조를 받습니다.

```json
{
  "asset_id": "INJ-03",
  "window": [
    {
      "cycle": 1,
      "vibration_rms": 0.8,
      "motor_current_cv": 0.12,
      "hydraulic_temp": 58.0,
      "oil_pressure": 140.0
    },
    {
      "cycle": 2,
      "vibration_rms": 1.2,
      "motor_current_cv": 0.18,
      "hydraulic_temp": 62.0,
      "oil_pressure": 130.0
    }
  ]
}
```

필드 의미:

| 필드 | 타입 | 필수 | 의미 |
|---|---|---|---|
| `asset_id` | string 또는 null | 선택 | 설비 ID. 없으면 데모 기본 설비 `INJ-03` 사용 |
| `window` | array 또는 null | 선택 | 최근 센서 시계열 window |
| `window[].cycle` | number | 선택 | window 내부 순서 또는 cycle |
| `window[].vibration_rms` | number | 선택 | 진동 RMS 또는 진동 대표값 |
| `window[].motor_current_cv` | number | 선택 | 전류 변동계수 또는 전류 대표값 |
| `window[].hydraulic_temp` | number | 선택 | 온도 대표값 |
| `window[].oil_pressure` | number | 선택 | 압력 대표값 |

현재 이 입력은 실시간 데모용 입력입니다. 실제 AI-Hub joblib 분류 모델까지 완전히 쓰려면 아래의 "최종 권장 입력"처럼 전류/진동 feature schema를 추가로 고정해야 합니다.

### 현재 바로 동작하는 출력

`POST /api/predict/health`는 RUL과 고장 분류를 한 번에 반환합니다.

```json
{
  "asset_id": "INJ-03",
  "rul": {
    "asset_id": "INJ-03",
    "model_version": "cmapss-fd001-fd004-validated-gru-tcn-patchtst-ensemble-v0.5",
    "rul_hours": 72,
    "risk_72h": 65.0,
    "confidence_interval": [54, 90],
    "anomaly_score": 0.42,
    "contributing_sensors": [],
    "dataset_roles": {},
    "generated_at": "2026-05-20T10:00:00Z",
    "rul_source": "NASA C-MAPSS validation-tuned GRU+TCN+PatchTST ensemble",
    "rul_unit": "cycle mapped to demo hours",
    "cmapss_subset": "FD004",
    "cmapss_unit": 12,
    "cmapss_last_cycle": 188,
    "cmapss_actual_rul_reference": 74.0
  },
  "fault": {
    "asset_id": "INJ-03",
    "model_version": "factory-sensor-fault-classifier-v0.1",
    "fault_code": "03",
    "fault_label": "축정렬 불량",
    "fault_probability": 0.72,
    "is_fault": true,
    "top_classes": [
      {"code": "03", "label": "축정렬 불량", "probability": 0.72},
      {"code": "01", "label": "베어링 불량", "probability": 0.18},
      {"code": "04", "label": "벨트 느슨함", "probability": 0.06}
    ],
    "evidence": ["위험도와 센서 변화량 기반 추정"],
    "source": "demo fallback classifier",
    "generated_at": "2026-05-20T10:00:00Z"
  },
  "generated_at": "2026-05-20T10:00:00Z"
}
```

출력 필드 의미:

| 출력 | 의미 | 프론트 표시 |
|---|---|---|
| `rul.rul_hours` | 예측 잔여 가동시간 | 잔여 가동시간 |
| `rul.risk_72h` | 72시간 내 위험도 | 위험도 게이지 |
| `rul.confidence_interval` | RUL 신뢰구간 | 예측 범위 |
| `rul.contributing_sensors` | 위험도에 기여한 센서 | 근거 센서 |
| `fault.is_fault` | 정상/고장 여부 | 정상/주의/위험 배지 |
| `fault.fault_probability` | 고장 가능성 | confidence |
| `fault.top_classes` | 고장 원인 후보 | 추정 원인 Top-3 |
| `fault.evidence` | 판단 근거 | 근거 설명 |
| `fault.source` | 모델 출처 | 모델 출처 표시 |

### 최종 권장 실시간 입력

실제 센서 서버와 붙일 때는 다음 중 하나로 입력 계약을 고정해야 합니다.

권장안 A: feature 기반 입력

```json
{
  "asset_id": "MOTOR-01",
  "timestamp": "2026-05-20T10:00:00+09:00",
  "current_features": {
    "rms": 0.18,
    "mean": 0.01,
    "std": 0.05,
    "peak_to_peak": 0.31
  },
  "vibration_features": {
    "rms": 0.08,
    "mean": 0.00,
    "std": 0.02,
    "peak_to_peak": 0.20
  }
}
```

권장안 B: 원시 파형 window 입력

```json
{
  "asset_id": "MOTOR-01",
  "timestamp": "2026-05-20T10:00:00+09:00",
  "sample_rate": 25600,
  "current_window": [0.12, 0.18, 0.16, 0.20],
  "vibration_window": [0.02, 0.03, 0.08, 0.04]
}
```

MVP에서는 권장안 A가 더 안전합니다. 이유는 실시간 수집 서버가 feature를 계산해서 넘기면 모델 서버는 같은 feature column 순서로 joblib 모델에 넣기 쉬워지고, API 계약도 명확해지기 때문입니다.

### 최종 권장 출력

최종 API는 최소한 아래 값을 항상 반환해야 합니다.

```json
{
  "asset_id": "MOTOR-01",
  "rul_hours": 72,
  "risk_72h": 65.0,
  "is_fault": true,
  "fault_probability": 0.81,
  "fault_candidates": [
    {"code": "01", "label": "베어링 불량", "probability": 0.62},
    {"code": "03", "label": "축정렬 불량", "probability": 0.24},
    {"code": "04", "label": "벨트 느슨함", "probability": 0.08}
  ],
  "recommended_action": "베어링/축정렬 우선 점검",
  "model_versions": {
    "rul": "cmapss-fd001-fd004-validated-gru-tcn-patchtst-ensemble-v0.5",
    "fault_binary": "aihub-current-rf-v1",
    "fault_type": "aihub-vibration-logreg-v1"
  },
  "generated_at": "2026-05-20T10:00:00Z"
}
```

이 최종 출력은 현재 `HealthPredictionResponse`와 거의 같은 의미입니다. 다만 프론트/백엔드 담당자가 실제 연동을 편하게 하려면 `fault_candidates` 같은 이름으로 Top-3 후보를 명확히 보여주는 것도 좋습니다.

## 3. RUL 회귀 모델 결과

### 3.1 데이터셋

사용 데이터셋: NASA C-MAPSS Jet Engine Simulated Data

컬럼 구조:

| 구분 | 개수 | 설명 |
|---|---:|---|
| unit number | 1 | 엔진 ID |
| cycle | 1 | 시간 순서 |
| operational setting | 3 | 운전 조건 |
| sensor | 21 | 센서 값 |
| 총 입력 컬럼 | 26 | 헤더 없는 공백 구분 텍스트 |

서브셋:

| Subset | 운전 조건 | 고장 모드 | 비고 |
|---|---|---|---|
| FD001 | 단일 조건 | 단일 고장 | 가장 단순 |
| FD002 | 6개 조건 | 단일 고장 | 운전 조건 변화 큼 |
| FD003 | 단일 조건 | 복합 고장 | 고장 모드 증가 |
| FD004 | 6개 조건 | 복합 고장 | 가장 어려운 조건 |

### 3.2 전처리 및 검증 방식

| 항목 | 적용 내용 | 이유 |
|---|---|---|
| 50 cycle sliding window | 최근 50 cycle을 하나의 시계열 입력으로 사용 | 순간값보다 추세를 보기 위해 |
| RUL cap 125 | 너무 먼 잔여수명은 125로 제한 | 초기 정상 구간의 과도한 영향 완화 |
| 운전조건별 정규화 | operational setting 기준 조건 차이를 보정 | FD002/FD004의 운전 조건 차이 완화 |
| subset 정보 입력 | FD001~FD004 출처를 모델에 알려줌 | 서로 다른 난이도와 조건 반영 |
| train/validation/test 분리 | validation에서 가중치 선택, test에서 최종 평가 | test label을 보고 튜닝하는 과대평가 방지 |
| unit 누수 방지 | 같은 unit이 train/test에 섞이지 않도록 검증 | 엔진 ID 암기 방지 |

### 3.3 최종 권장 모델

공식 모델명:

```text
cmapss-fd001-fd004-validated-gru-tcn-patchtst-ensemble-v0.5
```

선택 방식:

1. train set으로 GRU, TCN, PatchTST를 각각 학습
2. validation set에서 여러 앙상블 가중치 조합 실험
3. validation 성능이 가장 좋은 가중치 선택
4. 선택된 가중치를 고정
5. test set에서 최종 평가

seed 42 기준 validation에서 선택된 가중치:

| 모델 | 가중치 |
|---|---:|
| GRU | 0.30 |
| TCN | 0.35 |
| PatchTST | 0.35 |

최종 성능:

| 지표 | 값 |
|---|---:|
| 전체 test units | 707 |
| capped RMSE | 12.614 |
| PHM Score | 2280.1 |
| High-risk count | 300 |
| API 평균 응답속도 | 31.819 ms |
| API p95 응답속도 | 48.232 ms |

Subset별 성능:

| Subset | Test Units | RMSE | PHM Score | High-risk Count |
|---|---:|---:|---:|---:|
| FD001 | 100 | 12.674 | 290.4 | 42 |
| FD002 | 259 | 12.492 | 827.3 | 114 |
| FD003 | 100 | 12.231 | 260.9 | 46 |
| FD004 | 248 | 12.865 | 901.5 | 98 |

### 3.4 RUL 모델 해석 주의

이 모델은 C-MAPSS 기준 RUL 회귀 성능을 검증한 모델입니다. 실제 공장 설비에 바로 물리적으로 동일하게 맞는 모델이라는 뜻은 아닙니다.

실제 공장 데이터가 들어오면 다음 작업이 필요합니다.

- 공장 설비별 센서 컬럼 정의
- 설비별 정상 기준선 수집
- 동일한 window 생성
- RUL 또는 정비 이벤트 기반 라벨 생성
- 같은 GRU/TCN/PatchTST 구조로 재학습
- 공장 데이터 기준 validation/test 성능 재검증

## 4. AI-Hub 고장 분류 모델 결과

### 4.1 데이터셋

사용 데이터셋: AI-Hub 238 기계시설물 고장 예지 센서

데이터 특성:

| 항목 | 내용 |
|---|---|
| 주요 설비 | 도시철도 역사 전동기 |
| 센서 | 전류, 진동 |
| 목적 | 정상/고장 및 고장 유형 분류 |
| 라벨 수 | 5개 |

라벨:

| 코드 | 의미 |
|---|---|
| `00` | 정상 |
| `01` | 베어링 불량 |
| `02` | 회전체 불평형 |
| `03` | 축정렬 불량 |
| `04` | 벨트 느슨함 |

### 4.2 평가에서 가장 중요한 기준

row split 성능은 매우 높게 나올 수 있지만, 실제 미지 설비 일반화 성능으로 보기 어렵습니다.

| 분리 방식 | 의미 | 해석 |
|---|---|---|
| row split | 전체 row를 섞어서 train/test 분리 | 같은 설비의 비슷한 패턴이 양쪽에 들어갈 수 있어 점수가 과하게 높음 |
| group split 또는 group-CV | 설비 ID 또는 asset group 단위로 train/test 분리 | 처음 보는 설비에 대한 일반화 성능에 더 가까움 |

따라서 MVP 의사결정에는 row split 결과가 아니라 group-CV 결과를 기준으로 삼았습니다.

### 4.3 최종 권장 분류 정책

권장 정책:

1. 전류 모델로 정상/고장 여부를 먼저 판단합니다.
2. 고장 가능성이 있으면 진동 모델로 고장 원인 후보 Top-3를 제시합니다.
3. Top-1을 확정 진단처럼 보여주지 말고, "추정 원인 후보"로 표시합니다.
4. confidence가 낮거나 알려진 5개 라벨 밖의 패턴이면 "미확인 이상/점검 필요"로 보냅니다.

권장 모델:

| 역할 | 데이터 | 모델 | Accuracy | Macro F1 | Top-3 | Artifact |
|---|---|---|---:|---:|---:|---|
| 정상/고장 이진분류 | current | RandomForest | 0.800 | 0.721 | 1.000 | `data/models/aihub_generalization_10k/binary_normal_vs_fault_asset_baseline_random_forest.joblib` |
| 5-class 원인 후보 | vibration | LogisticRegression | 0.499 | 0.420 | 0.885 | `data/models/aihub_vibration_generalization_10k/multiclass_fault_type_asset_baseline_logistic_regression.joblib` |
| 고장 4종 후보 | vibration | RandomForest | 0.411 | 0.318 | 0.881 | `data/models/aihub_vibration_generalization_10k/fault_type_only_asset_baseline_random_forest.joblib` |

Late fusion 참고 결과:

| Task | Model | Accuracy | Macro F1 | Top-3 |
|---|---|---:|---:|---:|
| binary normal/fault | current binary RF | 0.842 | 0.780 | 1.000 |
| multiclass fault type | vibration multiclass RF | 0.617 | 0.599 | 0.855 |
| multiclass fault type | late fusion hard gate | 0.501 | 0.424 | 0.785 |
| multiclass fault type | late fusion soft gate | 0.502 | 0.422 | 0.707 |

해석:

- 전류는 정상/고장 감지에 강합니다.
- 진동은 고장 원인 후보 제시에 더 유리합니다.
- current + vibration hard/soft fusion은 아직 5-class 최종 모델로 쓰기에는 애매합니다.
- MVP에서는 "전류로 알림, 진동으로 원인 후보"가 가장 현실적인 정책입니다.

### 4.4 딥러닝 원시 파형 실험

진동 원시 파형 TCN도 실험했습니다.

| 모델 | Accuracy | Macro F1 | Top-3 |
|---|---:|---:|---:|
| vibration raw TCN 10k group-CV | 0.347 | 0.234 | 0.657 |

현재 결과로는 tabular feature 기반 모델보다 약합니다. 데이터 정리, 학습량, augmentation, 모델 튜닝을 더 하면 개선 가능성은 있지만, 오늘 기준 MVP 기본 모델로 쓰기에는 부적합합니다.

## 5. 넘겨야 할 파일

### 5.1 반드시 넘길 문서

| 파일 | 용도 |
|---|---|
| `AI_MODEL_HANDOFF.md` | 모델 개발 및 검증 인수인계 문서 |
| `AI_MODEL_CODEX_RUNBOOK.md` | 프론트/백엔드 Codex 실행 문서 |
| `RUL_TEST.MD` | NASA RUL 실험 전체 과정 |
| `CLASSIFICATION_TEST.MD` | AI-Hub 분류 실험 전체 과정 |
| `README.md` | 프로젝트 기본 실행 설명 |

### 5.2 반드시 넘길 모델/레지스트리

| 파일 | 용도 |
|---|---|
| `data/models/aihub_model_registry.json` | AI-Hub 권장 모델 레지스트리 |
| `data/models/validated_gru_tcn_patchtst_seed42/cmapss_gru_best.pt` | RUL GRU checkpoint |
| `data/models/validated_gru_tcn_patchtst_seed42/cmapss_tcn_best.pt` | RUL TCN checkpoint |
| `data/models/validated_gru_tcn_patchtst_seed42/cmapss_patchtst_best.pt` | RUL PatchTST checkpoint |
| `data/models/aihub_generalization_10k/binary_normal_vs_fault_asset_baseline_random_forest.joblib` | 전류 기반 정상/고장 모델 |
| `data/models/aihub_vibration_generalization_10k/multiclass_fault_type_asset_baseline_logistic_regression.joblib` | 진동 기반 5-class 후보 모델 |
| `data/models/aihub_vibration_generalization_10k/fault_type_only_asset_baseline_random_forest.joblib` | 진동 기반 고장 4종 후보 모델 |

### 5.3 반드시 넘길 검증 산출물

| 파일 | 용도 |
|---|---|
| `data/cmapss/cmapss_rul_validated_ensemble_predictions.csv` | 현재 백엔드 RUL 데모 런타임에서 읽는 최종 예측 CSV |
| `data/cmapss/cmapss_validated_gru_tcn_patchtst_benchmark.csv` | seed 42 RUL 벤치마크 |
| `data/cmapss/cmapss_remaining_validation_report.md` | RUL 남은 검증 요약 |
| `data/cmapss/cmapss_validated_ensemble_validation_report.md` | C-MAPSS 데이터 검증 보고서 |
| `data/cmapss/api_latency_validated_ensemble_benchmark.md` | API 응답속도 측정 결과 |
| `data/aihub238/aihub_priority1_2_test_comparison.csv` | AI-Hub 주요 실험 비교 |
| `data/aihub238/aihub_current_vs_vibration_summary.csv` | current/vibration 비교 요약 |
| `data/aihub238/aihub_current_vibration_late_fusion_report.md` | late fusion 정책 실험 |
| `data/aihub238/aihub_vibration_waveform_tcn_10k_cv_report.md` | 원시 파형 TCN 실험 |

### 5.4 코드 파일

| 파일/폴더 | 용도 |
|---|---|
| `backend/app/main.py` | FastAPI 엔드포인트 |
| `backend/app/schemas.py` | API 요청/응답 스키마 |
| `backend/app/predictor.py` | RUL + fault 통합 예측 로직 |
| `backend/app/fault_classifier.py` | 현재 데모 분류기 |
| `backend/app/aihub.py` | AI-Hub 로딩 및 feature table 생성 |
| `backend/app/cmapss.py` | C-MAPSS 로딩 및 window 생성 |
| `backend/app/cmapss_conditioning.py` | 운전조건 정규화 |
| `backend/app/cmapss_runtime.py` | RUL 데모 런타임 CSV 로딩 |
| `backend/scripts/*.py` | 실험 재현 스크립트 |
| `frontend/src/api.js` | 프론트 API 호출 |
| `frontend/src/App.jsx` | 현재 UI 연동 위치 |

### 5.5 원본 대용량 데이터는 선택

원본 AI-Hub validation 데이터는 매우 큽니다.

| 파일 | 대략적 성격 | 권장 |
|---|---|---|
| `data/aihub238/downloads/.../current.zip` | 전류 원본 데이터 | 재현이 꼭 필요할 때만 전달 |
| `data/aihub238/downloads/.../vibration.zip` | 진동 원본 데이터 | 재현이 꼭 필요할 때만 전달 |
| `data/cmapss/CMAPSSData.zip` | NASA 원본 ZIP | 작으므로 전달 가능 |

팀원에게는 원본 AI-Hub 전체를 바로 넘기기보다, 우선 모델 artifact와 검증 보고서를 넘기는 것을 권장합니다. 원본 데이터 재현이 필요하면 별도로 다운로드 스크립트를 실행하게 하면 됩니다.

## 6. 프론트 표시 정책

UI 문구는 다음처럼 표현하는 것을 권장합니다.

| 모델 출력 | UI 표현 |
|---|---|
| RUL | 잔여 가동시간 |
| risk_72h | 72시간 내 고장 위험도 |
| binary fault probability | 고장 가능성 |
| fault top classes | 추정 원인 후보 |
| low confidence | 미확인 이상, 점검 필요 |

피해야 할 표현:

- "AI가 고장 원인을 확정했다"
- "AI-Hub로 RUL을 학습했다"
- "NASA 모델을 실제 공장 설비에 바로 적용 가능하다"

권장 표현:

- "RUL 회귀 파이프라인은 C-MAPSS로 검증했다"
- "전류/진동 기반 고장 분류는 AI-Hub 전동기 데이터로 검증했다"
- "실제 공장 적용 시 설비별 정상 기준선과 정비 이력으로 재학습한다"

## 7. 다음 담당자의 핵심 작업

프론트/백엔드 담당자는 다음 순서로 진행하면 됩니다.

1. 현재 `/api/predict/health`가 프론트에서 정상 호출되는지 확인합니다.
2. `data/models/aihub_model_registry.json`를 읽어 권장 AI-Hub 모델 경로를 확인합니다.
3. joblib 모델을 로딩하는 `aihub_inference` 계층을 추가합니다.
4. 실시간 센서 payload를 모델 feature로 변환하는 인터페이스를 정합니다.
5. `/api/predict/fault` 응답을 데모 분류기에서 AI-Hub 모델 기반 응답으로 교체합니다.
6. 프론트에서는 Top-1 확정 진단이 아니라 Top-3 추정 후보로 보여줍니다.
7. 실제 공장 데이터가 들어오면 feature schema와 라벨 정책을 다시 고정합니다.
