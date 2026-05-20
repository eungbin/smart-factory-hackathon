# AI 모델 연동 실행 Runbook for Codex

이 문서는 프론트엔드/백엔드 담당자의 Codex가 그대로 읽고 실행할 수 있도록 만든 작업 지시서입니다.

## 0. 당신의 역할

당신은 공장지기 MVP의 프론트엔드/백엔드 연동 담당 Codex입니다.

목표:

- 현재 FastAPI 서버와 React 프론트가 실행되도록 확인합니다.
- RUL 예측은 이미 연결된 C-MAPSS 검증 결과를 사용합니다.
- 고장 분류는 현재 데모 분류기 상태이므로, AI-Hub joblib 모델을 실제 API에 연결하는 작업을 진행합니다.
- UI에서는 고장 유형을 "확정 진단"이 아니라 "추정 원인 후보"로 표현합니다.

## 1. 먼저 확인할 핵심 사실

현재 모델 상태:

| 영역 | 현재 상태 | 다음 작업 |
|---|---|---|
| RUL 회귀 | `/api/predict/rul`, `/api/predict/health`에 연결됨 | 우선 그대로 사용 |
| 고장 분류 | `/api/predict/fault`, `/api/predict/health`에 데모 분류기 연결됨 | AI-Hub joblib 모델로 교체 또는 보강 |
| 프론트 | `predictHealth()`로 통합 API 호출 | fault 응답의 Top-3 후보 표시 유지 |

현재 RUL 런타임 파일:

```text
data/cmapss/cmapss_rul_validated_ensemble_predictions.csv
```

현재 AI-Hub 모델 레지스트리:

```text
data/models/aihub_model_registry.json
```

## 2. 로컬 실행

프로젝트 루트:

```powershell
cd C:\Users\taeyoon\Desktop\factory_pipeline
```

Python 가상환경 생성:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
```

백엔드 테스트:

```powershell
$env:PYTHONPATH = "backend"
python -m unittest backend.tests.test_aihub backend.tests.test_fault_classifier backend.tests.test_cmapss backend.tests.test_work_orders
```

백엔드 서버 실행:

```powershell
$env:PYTHONPATH = "backend"
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

프론트 실행:

```powershell
cd frontend
npm install
npm run dev -- --host 127.0.0.1 --port 5173
```

브라우저:

```text
http://127.0.0.1:5173
```

API 문서:

```text
http://127.0.0.1:8000/docs
```

## 3. API 스모크 테스트

백엔드 서버가 켜진 상태에서 PowerShell로 실행:

```powershell
$body = @{ asset_id = "INJ-03" } | ConvertTo-Json
Invoke-RestMethod `
  -Uri http://127.0.0.1:8000/api/predict/health `
  -Method Post `
  -ContentType "application/json" `
  -Body $body
```

센서 window를 함께 보내는 예시:

```powershell
$body = @{
  asset_id = "INJ-03"
  window = @(
    @{
      cycle = 1
      vibration_rms = 0.8
      motor_current_cv = 0.12
      hydraulic_temp = 58
      oil_pressure = 140
    },
    @{
      cycle = 2
      vibration_rms = 1.2
      motor_current_cv = 0.18
      hydraulic_temp = 62
      oil_pressure = 130
    }
  )
} | ConvertTo-Json -Depth 5

Invoke-RestMethod `
  -Uri http://127.0.0.1:8000/api/predict/health `
  -Method Post `
  -ContentType "application/json" `
  -Body $body
```

기대 응답 구조:

```json
{
  "asset_id": "INJ-03",
  "rul": {
    "model_version": "cmapss-fd001-fd004-validated-gru-tcn-patchtst-ensemble-v0.5",
    "rul_hours": 72,
    "risk_72h": 65.0,
    "rul_source": "NASA C-MAPSS validation-tuned GRU+TCN+PatchTST ensemble"
  },
  "fault": {
    "model_version": "factory-sensor-fault-classifier-v0.1",
    "fault_code": "03",
    "fault_label": "축정렬 불량",
    "fault_probability": 0.72,
    "is_fault": true,
    "top_classes": []
  }
}
```

주의:

- 위 예시는 구조 설명용입니다. 실제 값은 현재 데모 asset과 CSV 매핑에 따라 달라집니다.
- `fault.model_version`이 `factory-sensor-fault-classifier-v0.1`이면 아직 AI-Hub joblib 모델이 연결되지 않은 상태입니다.

## 3-1. 실시간 입력/출력 계약

프론트/백엔드 연동자는 이 섹션을 API 계약으로 보면 됩니다.

핵심 흐름은 반드시 두 모델을 모두 거치는 구조입니다.

```text
실시간 센서 데이터
  -> 공통 window/feature 생성
  -> RUL 회귀 모델
  -> RUL 출력
  -> 고장 분류 모델
  -> 분류 출력
  -> /api/predict/health 통합 응답
  -> 프론트 출력
```

현재 코드의 의도도 이 순서입니다.

```python
rul_prediction = predict_rul(asset_id, window)
fault_prediction = predict_fault_class(asset_id, window, rul_prediction)
```

따라서 구현자는 아래 3개 계약을 분리해서 생각해야 합니다.

1. `RULRegressionInput -> RULRegressionOutput`
2. `FaultClassificationInput -> FaultClassificationOutput`
3. `HealthPredictionOutput = RULRegressionOutput + FaultClassificationOutput`

중요:

- 분류 모델은 RUL 출력만으로 돌리면 안 됩니다.
- 분류 모델은 전류/진동 feature를 주 입력으로 받아야 합니다.
- RUL 출력은 분류 모델의 보조 context로 넣을 수 있습니다.
- 프론트에는 RUL 결과와 분류 결과가 함께 나가야 합니다.

### RUL 회귀 모델 입력 계약

실제 실시간 연동에서는 RUL 모델에 최근 N개 센서 window를 넣습니다. C-MAPSS 실험 기준은 50 cycle이므로 MVP도 우선 50개 시점 기준으로 맞춥니다.

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

| 필드 | 타입 | 설명 |
|---|---|---|
| `asset_id` | string | 설비 ID |
| `timestamp` | string | window 마지막 시각 |
| `schema_version` | string | 입력 스키마 버전 |
| `window_size` | number | RUL 모델이 보는 시계열 길이 |
| `rul_window` | array | 최근 센서 시계열 |
| `temperature/current/vibration/pressure` | number | 공장 센서 feature |
| `operating_mode` | number/string | 운전 조건 |

### RUL 회귀 모델 출력 계약

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

| 필드 | 표시 |
|---|---|
| `rul_hours` | 잔여 가동시간 |
| `risk_72h` | 72시간 내 위험도 |
| `confidence_interval` | 예측 범위 |
| `anomaly_score` | 이상도 |
| `contributing_sensors` | 근거 센서 |

### 고장 분류 모델 입력 계약

RUL 모델 출력 이후, 분류 모델은 전류/진동 feature와 RUL context를 함께 받을 수 있습니다.

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

| 필드 | 설명 |
|---|---|
| `current_features` | 전류 기반 정상/고장 이진분류 입력 |
| `vibration_features` | 진동 기반 고장 원인 후보 분류 입력 |
| `rul_context` | RUL 결과. 위험도/evidence 보정에 사용 |

### 고장 분류 모델 출력 계약

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

| 필드 | 표시 |
|---|---|
| `is_fault` | 정상/고장 상태 |
| `fault_probability` | 고장 가능성 |
| `top_classes` | 추정 원인 후보 Top-3 |
| `evidence` | 판단 근거 |
| `source` | 모델 출처 |

### 통합 프론트 출력 계약

프론트는 아래처럼 RUL 결과와 분류 결과를 한 번에 받는 것이 가장 단순합니다.

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

### 현재 구현된 입력

현재 `POST /api/predict/health`는 아래 입력을 받습니다.

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

현재 입력 필드:

| 필드 | 타입 | 설명 |
|---|---|---|
| `asset_id` | string 또는 null | 설비 ID. 생략하면 `INJ-03` |
| `window` | array 또는 null | 최근 실시간 센서 window |
| `window[].cycle` | number | window 내부 순서 |
| `window[].vibration_rms` | number | 진동 대표값 |
| `window[].motor_current_cv` | number | 전류 대표값 |
| `window[].hydraulic_temp` | number | 온도 대표값 |
| `window[].oil_pressure` | number | 압력 대표값 |

### 현재 구현된 출력

현재 `POST /api/predict/health`는 아래 구조를 반환합니다.

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

프론트에서 반드시 써야 하는 핵심 출력:

| 필드 | 프론트 표시 |
|---|---|
| `rul.rul_hours` | 잔여 가동시간 |
| `rul.risk_72h` | 72시간 내 위험도 |
| `rul.confidence_interval` | 예측 범위 |
| `fault.is_fault` | 정상/고장 상태 |
| `fault.fault_probability` | 고장 가능성 |
| `fault.top_classes` | 추정 원인 후보 Top-3 |
| `fault.evidence` | 판단 근거 |
| `fault.source` | 모델 출처 |

### 실제 센서 서버 연동 시 권장 입력

AI-Hub joblib 모델까지 연결하려면 현재 `window`만으로는 부족할 수 있습니다. 실제 연동에서는 다음 중 하나를 새 스키마로 추가하세요.

권장안 A: 센서 서버가 feature를 계산해서 전달

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

권장안 B: 센서 서버가 원시 window를 전달하고 모델 서버가 feature 추출

```json
{
  "asset_id": "MOTOR-01",
  "timestamp": "2026-05-20T10:00:00+09:00",
  "sample_rate": 25600,
  "current_window": [0.12, 0.18, 0.16, 0.20],
  "vibration_window": [0.02, 0.03, 0.08, 0.04]
}
```

MVP 권장:

- 먼저 권장안 A를 구현합니다.
- 이유는 feature column 순서를 고정하기 쉽고, joblib 모델 입력과 바로 맞출 수 있기 때문입니다.
- 원시 window 방식은 이후 고도화 단계에서 추가합니다.

### 실제 센서 서버 연동 시 권장 출력

최종적으로 프론트가 받으면 좋은 최소 출력은 다음입니다.

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

현재 스키마를 유지한다면 이 출력은 `HealthPredictionResponse`의 `rul`과 `fault` 안에 나누어 담으면 됩니다.

## 4. AI-Hub 모델 레지스트리 확인

다음 명령으로 권장 모델 경로를 확인합니다.

```powershell
@'
import json
from pathlib import Path

registry = json.loads(Path("data/models/aihub_model_registry.json").read_text(encoding="utf-8"))
for role, spec in registry["recommended_mvp_roles"].items():
    print(role)
    print("  task:", spec.get("task"))
    print("  model:", spec.get("model"))
    print("  artifact:", spec.get("artifact"))
    print("  product_use:", spec.get("product_use"))
'@ | python -
```

MVP에서 우선 사용할 모델:

| 역할 | Artifact |
|---|---|
| 정상/고장 | `data/models/aihub_generalization_10k/binary_normal_vs_fault_asset_baseline_random_forest.joblib` |
| 5-class 원인 후보 | `data/models/aihub_vibration_generalization_10k/multiclass_fault_type_asset_baseline_logistic_regression.joblib` |
| 고장 4종 후보 | `data/models/aihub_vibration_generalization_10k/fault_type_only_asset_baseline_random_forest.joblib` |

## 5. 백엔드 구현 작업

### 5.1 구현 목표

현재:

```text
backend/app/fault_classifier.py
```

는 데모용 rule 기반 분류기입니다.

목표:

- AI-Hub joblib 모델을 로딩하는 새 모듈을 추가합니다.
- 실시간 payload가 충분한 feature를 포함하면 AI-Hub 모델을 사용합니다.
- feature가 부족하면 기존 데모 분류기로 fallback합니다.

권장 새 파일:

```text
backend/app/aihub_inference.py
```

### 5.2 필요한 응답 형태

기존 `FaultClassificationResponse` 스키마를 유지합니다.

```json
{
  "asset_id": "INJ-03",
  "model_version": "aihub-238-current-vibration-v1",
  "fault_code": "01",
  "fault_label": "베어링 불량",
  "fault_probability": 0.73,
  "is_fault": true,
  "top_classes": [
    {"code": "01", "label": "베어링 불량", "probability": 0.73},
    {"code": "03", "label": "축정렬 불량", "probability": 0.18},
    {"code": "04", "label": "벨트 느슨함", "probability": 0.06}
  ],
  "evidence": [
    "전류 기반 정상/고장 모델에서 fault probability 0.81",
    "진동 기반 원인 후보 Top-3 산출"
  ],
  "source": "AI-Hub 238 current binary + vibration top-3 candidate policy"
}
```

### 5.3 실시간 payload 설계

joblib 모델은 학습 때 생성한 feature column 순서와 같은 입력이 필요합니다. 따라서 API는 둘 중 하나를 받아야 합니다.

방식 A: 백엔드가 원시 window를 받아 feature 추출

```json
{
  "asset_id": "MOTOR-01",
  "current_window": [0.12, 0.18, 0.16],
  "vibration_window": [0.02, 0.03, 0.08],
  "sample_rate": 25600,
  "timestamp": "2026-05-20T10:00:00+09:00"
}
```

방식 B: 센서 서버가 이미 계산한 feature를 전달

```json
{
  "asset_id": "MOTOR-01",
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
  "timestamp": "2026-05-20T10:00:00+09:00"
}
```

권장:

- MVP에서는 방식 B가 더 안정적입니다.
- 이유는 실시간 서버와 모델 서버 사이의 feature schema를 명확히 고정할 수 있기 때문입니다.
- 원시 파형까지 받는 방식 A는 추후 확장으로 두는 것이 좋습니다.

### 5.4 구현 체크리스트

1. `backend/app/aihub_inference.py`를 추가합니다.
2. `aihub_model_registry.json`를 로딩합니다.
3. joblib artifact를 lazy load 또는 startup load합니다.
4. 입력 feature가 모델의 `feature_columns`와 일치하는지 검사합니다.
5. current binary 모델로 `is_fault`, `fault_probability`를 계산합니다.
6. vibration multiclass 모델로 `top_classes`를 계산합니다.
7. confidence가 낮으면 `fault_code = "unknown"` 또는 `source`/`evidence`에 "점검 필요"를 명시합니다.
8. `backend/app/predictor.py` 또는 `fault_classifier.py`에서 새 inference 함수를 호출합니다.
9. 기존 데모 fallback을 삭제하지 말고 유지합니다.
10. `backend/tests/test_fault_classifier.py`에 AI-Hub artifact 로딩 테스트 또는 fallback 테스트를 추가합니다.

## 6. 프론트엔드 구현 작업

프론트에서 이미 호출하는 함수:

```text
frontend/src/api.js
predictHealth(assetId, window)
```

UI 위치:

```text
frontend/src/App.jsx
FaultView
Metric label="고장 분류"
```

프론트 표시 정책:

| API 필드 | 표시 방식 |
|---|---|
| `fault.is_fault` | 정상/주의/위험 배지 |
| `fault.fault_probability` | 고장 가능성 confidence |
| `fault.top_classes` | 추정 원인 후보 Top-3 막대 |
| `fault.evidence` | 근거 센서/모델 설명 |
| `fault.source` | 모델 출처 |

문구 주의:

- `고장 확정`이라고 쓰지 않습니다.
- `추정 원인 후보`, `점검 권장`, `미확인 이상`처럼 표현합니다.

## 7. 모델 성능 기준

RUL 공식 모델:

| 항목 | 값 |
|---|---:|
| 모델 | GRU + TCN + PatchTST ensemble |
| 가중치 | GRU 0.30, TCN 0.35, PatchTST 0.35 |
| test RMSE | 12.614 |
| PHM Score | 2280.1 |
| API p95 | 48.232 ms |

AI-Hub 권장 분류 정책:

| 역할 | 모델 | Macro F1 | Top-3 |
|---|---|---:|---:|
| current 정상/고장 | RandomForest | 0.721 | 1.000 |
| vibration 5-class 후보 | LogisticRegression | 0.420 | 0.885 |
| vibration 고장 4종 후보 | RandomForest | 0.318 | 0.881 |

해석:

- 정상/고장 알림은 MVP에 사용할 수 있습니다.
- 고장 유형은 Top-1 확정 진단이 아니라 Top-3 후보로 써야 합니다.
- 미지 설비 일반화 성능은 row split이 아니라 group-CV 성능을 기준으로 봐야 합니다.

## 8. 재현 실험은 선택

연동만 할 때는 재학습을 먼저 하지 마세요. 이미 저장된 artifact를 사용하세요.

재현이 필요할 때만 아래 명령을 실행합니다. 시간이 오래 걸릴 수 있습니다.

RUL 재현:

```powershell
$env:PYTHONPATH = "backend"
python backend\scripts\benchmark_cmapss_validated_ensemble.py `
  --models gru tcn patchtst `
  --epochs 6 `
  --batch-size 1024 `
  --hidden-size 64 `
  --weight-step 0.05 `
  --seed 42 `
  --output data\cmapss\cmapss_validated_gru_tcn_patchtst_benchmark.csv `
  --predictions-output data\cmapss\cmapss_validated_gru_tcn_patchtst_predictions.csv `
  --models-dir data\models\validated_gru_tcn_patchtst_seed42
```

RUL API latency:

```powershell
$env:PYTHONPATH = "backend"
python backend\scripts\benchmark_api_latency.py `
  --iterations 200 `
  --warmup 20 `
  --output data\cmapss\api_latency_validated_ensemble_benchmark.csv `
  --report-output data\cmapss\api_latency_validated_ensemble_benchmark.md
```

AI-Hub current/vibration late fusion 재현:

```powershell
$env:PYTHONPATH = "backend"
python backend\scripts\benchmark_aihub_late_fusion.py `
  --current-zip data\aihub238\downloads\125.기계시설물_고장_예지_센서\01.데이터\2._Validation\current.zip `
  --vibration-zip data\aihub238\downloads\125.기계시설물_고장_예지_센서\01.데이터\2._Validation\vibration.zip `
  --max-files 10000 `
  --max-per-label-path 2000 `
  --output data\aihub238\aihub_current_vibration_late_fusion_benchmark.csv `
  --report-output data\aihub238\aihub_current_vibration_late_fusion_report.md `
  --models-dir data\models\aihub_late_fusion
```

AI-Hub 원시 파형 TCN 재현:

```powershell
$env:PYTHONPATH = "backend"
python backend\scripts\benchmark_aihub_waveform_deep.py `
  --signal vibration `
  --task multiclass_fault_type `
  --max-files 10000 `
  --max-per-label-path 2000 `
  --models tcn `
  --epochs 4 `
  --batch-size 128 `
  --output data\aihub238\aihub_vibration_waveform_tcn_10k_cv_benchmark.csv `
  --report-output data\aihub238\aihub_vibration_waveform_tcn_10k_cv_report.md `
  --models-dir data\models\aihub_vibration_waveform_tcn_10k_cv
```

## 9. 전달받아야 하는 파일 체크리스트

최소 전달 패키지:

```text
AI_MODEL_HANDOFF.md
AI_MODEL_CODEX_RUNBOOK.md
RUL_TEST.MD
CLASSIFICATION_TEST.MD
README.md
backend/
frontend/
data/models/aihub_model_registry.json
data/models/validated_gru_tcn_patchtst_seed42/cmapss_gru_best.pt
data/models/validated_gru_tcn_patchtst_seed42/cmapss_tcn_best.pt
data/models/validated_gru_tcn_patchtst_seed42/cmapss_patchtst_best.pt
data/models/aihub_generalization_10k/binary_normal_vs_fault_asset_baseline_random_forest.joblib
data/models/aihub_vibration_generalization_10k/multiclass_fault_type_asset_baseline_logistic_regression.joblib
data/models/aihub_vibration_generalization_10k/fault_type_only_asset_baseline_random_forest.joblib
data/cmapss/cmapss_rul_validated_ensemble_predictions.csv
data/cmapss/cmapss_validated_gru_tcn_patchtst_benchmark.csv
data/cmapss/cmapss_remaining_validation_report.md
data/cmapss/cmapss_validated_ensemble_validation_report.md
data/cmapss/api_latency_validated_ensemble_benchmark.md
data/aihub238/aihub_priority1_2_test_comparison.csv
data/aihub238/aihub_current_vs_vibration_summary.csv
data/aihub238/aihub_current_vibration_late_fusion_report.md
data/aihub238/aihub_vibration_waveform_tcn_10k_cv_report.md
```

대용량 원본 데이터는 기본 전달 패키지에서 제외해도 됩니다.

```text
data/aihub238/downloads/.../current.zip
data/aihub238/downloads/.../vibration.zip
```

필요할 때만 다운로드 스크립트로 다시 받습니다.

## 10. 완료 기준

연동 완료로 볼 수 있는 기준:

1. `npm run dev` 프론트에서 대시보드가 열린다.
2. FastAPI `/api/predict/health`가 1초 이내 응답한다.
3. 응답에 RUL과 fault가 함께 들어온다.
4. fault 응답의 `model_version` 또는 `source`에서 AI-Hub 기반 모델 사용 여부가 확인된다.
5. UI에서 고장 유형이 Top-3 추정 후보로 표시된다.
6. feature가 부족한 경우에도 서버가 죽지 않고 fallback 또는 "점검 필요"를 반환한다.

## 11. 다음 개발자가 반드시 지켜야 할 원칙

- test label을 보고 모델 가중치나 threshold를 고르지 않습니다.
- row split 성능을 실제 미지 설비 성능처럼 말하지 않습니다.
- AI-Hub 고장 분류 결과를 확정 진단으로 표현하지 않습니다.
- NASA C-MAPSS RUL 모델을 실제 공장 설비에 바로 일반화된 모델처럼 표현하지 않습니다.
- 실제 공장 센서가 들어오면 feature schema, 정상 기준선, 라벨 정책을 먼저 고정합니다.
