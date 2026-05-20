# 공장지기 MVP

중소 제조사의 설비 고장 예측부터 작업지시서 생성, 정비 결과 기록, 재학습 큐 적재까지 연결하는 예지보전 데모입니다.

## 실행

### 백엔드

```powershell
cd backend
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### 프론트엔드

```powershell
cd frontend
npm install
npm run dev -- --host 127.0.0.1 --port 5173
```

브라우저에서 `http://127.0.0.1:5173`을 열면 됩니다.

## 데이터셋 스모크 테스트

NASA C-MAPSS는 실제 ZIP을 내려받아 `data/cmapss/CMAPSSData.zip`에 저장합니다.

```powershell
$env:PYTHONPATH="backend"
python backend/scripts/smoke_cmapss.py --subset FD001
```

NASA C-MAPSS 전체 검증 리포트를 생성하려면:

```powershell
python backend/scripts/validate_cmapss_dataset.py --window-size 50
```

운전조건별 정규화를 적용한 통합 RUL 벤치마크를 다시 생성하려면:

```powershell
python backend/scripts/benchmark_cmapss_condition_normalized.py --window-size 50 --rul-cap 125 --max-iter 180
```

조건 정규화 window를 직접 학습하는 GRU 시계열 모델을 다시 학습하려면:

```powershell
python backend/scripts/benchmark_cmapss_sequence_model.py --epochs 6 --batch-size 1024 --hidden-size 64
```

GRU, LSTM, TCN, CNN-GRU 후보군을 같은 조건으로 비교하려면:

```powershell
python backend/scripts/benchmark_cmapss_model_zoo.py --models gru lstm tcn cnn_gru --epochs 6 --batch-size 1024 --hidden-size 64
```

학습된 후보군 예측값으로 앙상블을 평가하려면:

```powershell
python backend/scripts/ensemble_cmapss_predictions.py --step 0.05
```

validation에서 epoch와 앙상블 가중치를 고른 뒤 test를 평가하려면:

```powershell
python backend/scripts/benchmark_cmapss_validated_ensemble.py --models gru tcn --epochs 8 --batch-size 1024 --hidden-size 64
```

AI-Hub는 승인 다운로드가 필요합니다. 파일이 없으면 내장 샘플로 annotation 정리, feature table 생성, 고장 유형 분류 파이프라인을 검증합니다.

```powershell
$env:PYTHONPATH="backend"
python backend/scripts/smoke_aihub.py
```

승인받은 AI-Hub annotation CSV/XLSX가 있으면 경로를 넘기면 됩니다.

```powershell
$env:PYTHONPATH="backend"
python backend/scripts/smoke_aihub.py --annotation-path "C:\path\to\aihub_annotation.csv"
```

둘을 한 번에 돌리려면:

```powershell
$env:PYTHONPATH="backend"
python backend/scripts/smoke_datasets.py
```

## AI-Hub 238 API 다운로드

이 데이터셋은 전체가 매우 큽니다. 먼저 파일 목록을 확인합니다.

```powershell
$env:PYTHONPATH="backend"
python backend/scripts/aihub238_download.py list
```

현재 확인된 묶음은 다음과 같습니다.

- `train_current`: `filekey=44889`, 약 21GB
- `train_vibration`: `filekey=44890`, 약 78GB
- `valid_current`: `filekey=44891`, 약 3GB
- `valid_vibration`: `filekey=44815`, 약 10GB

처음에는 가장 작은 `valid_current`만 받는 것을 권장합니다.

```powershell
$env:AIHUB_API_KEY="본인_API_KEY"
$env:PYTHONPATH="backend"
python backend/scripts/aihub238_download.py download --preset valid_current
```

다운로드가 끝나면 압축을 전부 풀지 말고 ZIP을 직접 샘플링해서 확인합니다.

```powershell
python backend/scripts/smoke_aihub_current_zip.py --max-files 250 --max-per-path-label 50
```

또는 프롬프트로 키를 입력하려면:

```powershell
.\scripts\download_aihub238_valid_current.ps1
```

## 구현 범위

- 8대 설비 가상 센서 시뮬레이터
- 3호 사출기 고위험 데모 시나리오
- RUL/72시간 위험도 예측 API
- C-MAPSS 로더, RUL 라벨러, sliding window 생성기, baseline LSTM 모델 클래스
- 매뉴얼 기반 RAG 검색과 작업지시서 JSON 생성
- 정비 결과 입력 및 재학습 큐 적재
- 대시보드, 설비 상세, 지시서, 결과 입력, 노하우 리포트 화면

## 데이터셋 역할

- NASA C-MAPSS: RUL 회귀 모델 검증용입니다. 항공 엔진 데이터라 국내 전동기/사출기 물리와 직접 동일하다고 보지 않습니다.
- AI-Hub 기계시설물 고장 예지 센서: 정상/고장 분류와 국내 전동기 도메인 보강용입니다. 공개 설명 기준 RUL 정답이 없어 RUL 주 학습 데이터로 사용하지 않습니다.

## API

- `GET /api/assets`
- `GET /api/assets/{asset_id}`
- `POST /api/predict/rul`
- `POST /api/work-orders`
- `POST /api/work-orders/{work_order_id}/dispatch`
- `POST /api/maintenance-events`
- `GET /api/reports/knowledge`
- `GET /api/datasets`
- `GET /api/cmapss/benchmark`
- `GET /api/cmapss/demo-predictions`

## Postgres/pgvector 확장

MVP는 로컬 실행성을 위해 SQLite를 기본 저장소로 사용합니다. 운영형 전환 시 `docker-compose.yml`의 Postgres/pgvector 서비스를 띄우고, `maintenance_events`, `training_queue`, `manual_chunks` 테이블을 Postgres로 이전하면 됩니다.
