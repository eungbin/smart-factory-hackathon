# RUL 회귀 모델 실험 보고서

작성일: 2026-05-19  
프로젝트: 공장지기 MVP  
대상 실험: NASA C-MAPSS 기반 RUL 회귀 모델 검증

## 1. 실험 목적

이번 RUL 실험의 목적은 실제 중소 제조 설비에 바로 적용 가능한 최종 모델을 완성하는 것이 아니라, **잔여수명 예측 파이프라인이 기술적으로 성립하는지 검증**하는 것이다.

즉, 아래 흐름을 검증했다.

```text
NASA C-MAPSS 시계열 데이터
→ RUL 라벨 생성
→ 운전조건별 정규화
→ 50 cycle sliding window 생성
→ RUL 회귀 모델 학습
→ 모델 후보 비교
→ GRU+TCN+PatchTST 앙상블
→ FastAPI inference 연동
→ 프론트엔드 대시보드 표시
```

중요한 점은 NASA C-MAPSS는 항공기 터보팬 엔진 시뮬레이션 데이터이므로, 이 모델을 그대로 실제 사출기나 전동기에 적용한다고 주장하면 안 된다. 이 데이터셋은 **RUL 회귀 모델 구조, 평가 방식, API/프론트 연동 구조를 검증하기 위한 benchmark 데이터**로 사용했다.

## 2. 사용 데이터셋

| 항목 | 내용 |
|---|---|
| 데이터셋 | NASA C-MAPSS Jet Engine Simulated Data |
| 목적 | 터보팬 엔진의 잔여수명, RUL 예측 |
| 데이터 형태 | train/test/RUL 텍스트 파일 |
| 입력 구조 | unit, cycle, operational setting 1~3, sensor 1~21 |
| 정답 구조 | train은 마지막 cycle 기준으로 RUL 계산, test는 `RUL_FD00x.txt` 사용 |
| 사용 subset | FD001, FD002, FD003, FD004 전체 |

## 3. 원본 컬럼 구조

NASA C-MAPSS 원본은 헤더 없는 공백 구분 텍스트이며, 총 26개 숫자 컬럼으로 해석했다.

| 구분 | 개수 | 컬럼 |
|---|---:|---|
| 장비 ID | 1 | `unit` |
| 시간 순서 | 1 | `cycle` |
| 운전조건 | 3 | `operational_setting_1`, `operational_setting_2`, `operational_setting_3` |
| 센서 | 21 | `T2`, `T24`, `T30`, `T50`, `P2`, `P15`, `P30`, `Nf`, `Nc`, `epr`, `Ps30`, `phi`, `NRf`, `NRc`, `BPR`, `farB`, `htBleed`, `Nf_dmd`, `PCNfR_dmd`, `W31`, `W32` |

센서 21개는 온도, 압력, 회전수, 유량, 제어값 계열이다. 프론트엔드에 보이는 진동, 전류, 유압 온도, 유압 압력은 NASA 원본 컬럼이 아니라 공장 데모용 센서 표현이다.

## 4. Subset 구성

| Subset | 운전조건 | 고장 모드 | 특징 |
|---|---:|---|---|
| FD001 | 1개 | HPC 고장 | 가장 단순한 기본 조건 |
| FD002 | 6개 | HPC 고장 | 운전조건 변화가 있어 정규화 중요 |
| FD003 | 1개 | HPC + Fan 고장 | 복합 고장 모드 |
| FD004 | 6개 | HPC + Fan 고장 | 가장 어려운 조건 |

주의: 다운로드한 ZIP에서는 FD004 train/test unit count가 NASA README 설명과 서로 바뀐 것처럼 보여 검증 스크립트에서 warning으로 남겼다. 데이터 로딩과 평가 자체는 실제 ZIP 기준으로 진행했다.

## 5. 전처리

### 5.1 RUL 라벨 생성

train 데이터에는 RUL 정답이 직접 들어 있지 않으므로, 각 unit의 마지막 cycle을 기준으로 RUL을 계산했다.

```text
RUL = 해당 unit의 마지막 cycle - 현재 cycle
```

예를 들어 어떤 unit이 200 cycle에서 고장난다면, 150 cycle 시점의 RUL은 50이다.

test 데이터는 고장 직전까지 가지 않고 중간 시점에서 끊겨 있으므로, NASA가 제공한 `RUL_FD00x.txt`를 정답으로 사용했다.

### 5.2 RUL Cap

RUL 상한은 125 cycle로 설정했다.

```text
RUL cap = 125
```

고장까지 너무 멀리 남은 시점은 센서 변화가 뚜렷하지 않다. 그래서 먼 미래 수명을 정밀하게 맞히기보다, 고장 위험 구간을 더 잘 구분하도록 RUL 값을 125로 제한했다.

### 5.3 Sliding Window

시계열 모델 입력은 최근 50 cycle을 하나의 sample로 구성했다.

```text
입력 1개 = 최근 50 cycle x feature 31개
```

| 항목 | 값 |
|---|---:|
| window size | 50 cycle |
| RUL cap | 125 |
| 통합 train window 수 | 125,618 |
| seed 42 기준 train window 수 | 99,714 |
| seed 42 기준 validation window 수 | 25,904 |

### 5.4 운전조건별 정규화

FD002와 FD004는 운전조건이 6개다. 같은 센서값이라도 운전조건이 다르면 정상 범위가 달라질 수 있다.

따라서 operational setting 1~3을 기준으로 운전조건을 나누고, 조건별로 센서 평균과 표준편차를 따로 계산했다.

| 단계 | 처리 |
|---|---|
| 1 | operational setting 1~3 표준화 |
| 2 | FD001/FD003은 단일 조건으로 처리 |
| 3 | FD002/FD004는 KMeans로 6개 조건 clustering |
| 4 | 조건별 sensor 평균/표준편차 계산 |
| 5 | sensor 값을 조건별 z-score로 정규화 |
| 6 | condition one-hot feature 추가 |

최종 모델 입력 feature는 다음과 같다.

| Feature | 개수 |
|---|---:|
| 정규화된 sensor | 21 |
| condition one-hot | 6 |
| subset one-hot | 4 |
| 합계 | 31 |

## 6. 평가 지표

| 지표 | 의미 | 낮을수록 좋은가 |
|---|---|---|
| RMSE | 예측 RUL과 실제 RUL의 평균 오차 | 예 |
| PHM Score | RUL 예측 대회식 점수. 위험한 과대 예측에 더 큰 벌점 | 예 |
| High-Risk Count | 예측 RUL이 72 이하인 test unit 수 | 상황에 따라 해석 |

PHM Score는 단순히 오차 크기만 보는 것이 아니라, 실제보다 RUL을 길게 예측해 고장을 놓칠 수 있는 경우에 더 큰 벌점을 준다.

## 7. 실험 1: 기본 통합 모델

초기에는 FD001~FD004를 단순 통합해 RUL 회귀를 수행했다.

| 모델 | ALL RMSE | PHM Score | 해석 |
|---|---:|---:|---|
| 기본 통합 모델 | 17.857 | 4847.0 | 운전조건 차이를 충분히 보정하지 못해 한계가 큼 |

이 결과를 통해 FD002/FD004처럼 운전조건이 여러 개인 subset에서는 조건 정규화가 필요하다는 점을 확인했다.

## 8. 실험 2: 운전조건별 정규화 모델

운전조건별 정규화를 적용한 뒤 성능이 크게 개선됐다.

| 모델 | ALL RMSE | PHM Score | 개선 |
|---|---:|---:|---:|
| 조건 정규화 전 통합 모델 | 17.857 | 4847.0 | 기준 |
| 조건 정규화 후 통합 모델 | 15.396 | 3253.4 | RMSE -2.461 |

이 단계에서 운전조건별 정규화가 통합 RUL 모델에 필수적이라는 것을 확인했다.

## 9. 실험 3: GRU 시계열 모델

이후 50 cycle window를 직접 입력받는 GRU 모델을 학습했다.

| Subset | Test Units | RMSE | PHM Score | High-Risk Count |
|---|---:|---:|---:|---:|
| FD001 | 100 | 12.915 | 282.1 | 43 |
| FD002 | 259 | 13.059 | 782.2 | 117 |
| FD003 | 100 | 12.296 | 271.8 | 50 |
| FD004 | 248 | 13.582 | 1001.3 | 103 |
| ALL | 707 | 13.121 | 2337.4 | 313 |

GRU는 조건 정규화 baseline 대비 큰 성능 개선을 보였고, 이후 모든 모델 비교의 기준 모델이 되었다.

## 10. 실험 4: Model Zoo 비교

GRU 외에도 LSTM, TCN, CNN-GRU를 같은 조건으로 비교했다.

| 모델 | ALL RMSE | PHM Score | High-Risk Count | 해석 |
|---|---:|---:|---:|---|
| GRU | 13.118 | 2336.3 | 313 / 707 | 가장 안정적인 단독 기준 모델 |
| TCN | 13.250 | 2644.8 | 303 / 707 | GRU와 유사하나 RMSE는 약간 높음 |
| LSTM | 13.994 | 2413.9 | 320 / 707 | GRU보다 낮은 성능 |
| CNN-GRU | 14.133 | 3092.2 | 307 / 707 | 이번 설정에서는 효과 제한적 |

GRU와 TCN은 서로 다른 방식으로 시계열을 해석한다.

| 모델 | 특징 |
|---|---|
| GRU | 시간 순서대로 열화 흐름을 누적해 읽음 |
| TCN | convolution으로 최근 구간의 패턴 변화를 읽음 |

두 모델이 보는 관점이 다르므로 앙상블 후보로 적합하다고 판단했다.

## 11. 실험 5: Transformer 계열 후보

더 발전된 시계열 모델 후보로 PatchTST와 iTransformer를 추가했다.

| 모델 | 핵심 아이디어 |
|---|---|
| PatchTST | 시계열을 작은 patch로 나누고 Transformer attention으로 중요한 구간을 학습 |
| iTransformer | 시간축 대신 feature 축을 token처럼 보고 변수 간 관계를 학습 |

| 모델 | FD001 RMSE | FD002 RMSE | FD003 RMSE | FD004 RMSE | ALL RMSE | PHM Score |
|---|---:|---:|---:|---:|---:|---:|
| PatchTST | 13.610 | 14.106 | 12.273 | 14.307 | 13.864 | 2157.9 |
| iTransformer | 12.657 | 17.452 | 12.024 | 18.240 | 16.474 | 4778.5 |

PatchTST는 단독 RMSE는 GRU보다 낮지 않았지만 PHM Score가 좋았다. iTransformer는 FD001/FD003에서는 괜찮았지만 FD002/FD004에서 크게 흔들려 현재 후보에서는 보류했다.

## 12. 실험 6: Test 기준 앙상블

먼저 모델 후보들의 예측값을 이용해 test 기준 grid ensemble을 실험했다.

| 모델 | ALL RMSE | PHM Score | High-Risk Count |
|---|---:|---:|---:|
| GRU 단독 | 13.118 | 2336.3 | 313 / 707 |
| GRU + PatchTST, grid | 12.858 | 2013.4 | 313 / 707 |
| GRU + TCN, grid | 12.784 | 2302.1 | 306 / 707 |
| GRU + TCN + PatchTST, equal | 12.589 | 2003.8 | 310 / 707 |
| GRU + TCN + PatchTST, grid | 12.576 | 2031.3 | 312 / 707 |

이 실험에서 `GRU+TCN+PatchTST`가 가장 낮은 RMSE를 보였다.

하지만 이 결과는 test label 기준으로 가중치를 찾은 upper-bound 실험이다. 따라서 최종 성능으로 주장하기에는 과대평가 위험이 있다.

## 13. 실험 7: Validation 기준 앙상블

test label을 보지 않고 validation set에서 가중치를 고른 뒤 test set에서 평가했다.

공식 후보는 다음과 같이 정의했다.

```text
official model = ensemble_grid_gru_tcn_patchtst_val
```

seed 42 기준 validation에서 선택된 가중치:

| 모델 | 가중치 |
|---|---:|
| GRU | 0.30 |
| TCN | 0.35 |
| PatchTST | 0.35 |

seed 42 official 결과:

| 모델 | ALL RMSE | PHM Score | High-Risk Count |
|---|---:|---:|---:|
| GRU 단독 | 13.018 | 2868.6 | 295 / 707 |
| TCN 단독 | 13.248 | 2643.3 | 302 / 707 |
| PatchTST 단독 | 13.368 | 2485.4 | 305 / 707 |
| GRU+TCN+PatchTST validation ensemble | 12.614 | 2280.1 | 300 / 707 |

test 기준으로 가중치를 찾은 12.576보다는 조금 높지만, validation 기준으로도 12.614가 나와서 앙상블 효과가 실제로 유지됨을 확인했다.

## 14. 실험 8: Seed 반복 검증

한 번의 random seed 결과가 우연인지 확인하기 위해 seed 7, 42, 123으로 반복 실험했다.

| Seed | Weights | Official RMSE | PHM Score | GRU RMSE | GRU 대비 개선 |
|---:|---|---:|---:|---:|---:|
| 7 | GRU 0.40 / TCN 0.30 / PatchTST 0.30 | 12.677 | 2170.6 | 12.901 | 0.224 |
| 42 | GRU 0.30 / TCN 0.35 / PatchTST 0.35 | 12.614 | 2280.1 | 13.018 | 0.405 |
| 123 | GRU 0.40 / TCN 0.30 / PatchTST 0.30 | 12.924 | 2318.6 | 13.434 | 0.509 |

요약:

| Metric | RMSE | PHM | GRU 대비 개선 |
|---|---:|---:|---:|
| mean | 12.738 | 2256.4 | 0.379 |
| std | 0.164 | 76.8 | 0.145 |
| min | 12.614 | 2170.6 | 0.224 |
| max | 12.924 | 2318.6 | 0.509 |

seed에 따라 성능 차이는 있었지만, 모든 seed에서 GRU 단독보다 앙상블이 낮은 RMSE를 보였다.

## 15. Subset별 최종 성능

seed 42 official model 기준 subset별 성능은 다음과 같다.

| Subset | Test Units | RMSE | PHM Score | High-Risk Count |
|---|---:|---:|---:|---:|
| FD001 | 100 | 12.674 | 290.4 | 42 |
| FD002 | 259 | 12.492 | 827.3 | 114 |
| FD003 | 100 | 12.231 | 260.9 | 46 |
| FD004 | 248 | 12.865 | 901.5 | 98 |

FD002와 FD004는 운전조건이 6개인 어려운 subset인데도 RMSE 13 미만을 유지했다. 따라서 조건별 정규화와 subset one-hot 입력이 통합 모델에 의미 있게 작동한다고 판단했다.

## 16. API Inference 속도

최종 앙상블 결과를 FastAPI runtime에 연결한 뒤 HTTP 요청 기준으로 속도를 측정했다.

| Metric | Value |
|---|---:|
| Iterations | 200 |
| Mean latency | 31.819 ms |
| Median latency | 31.026 ms |
| P95 latency | 48.232 ms |
| P99 latency | 74.401 ms |
| Max latency | 87.858 ms |

MVP 기준인 1초 이내 예측 응답은 충분히 만족했다.

## 17. 최종 회귀 모델

현재 서버에서 사용하는 RUL 회귀 모델 버전은 다음과 같다.

```text
cmapss-fd001-fd004-validated-gru-tcn-patchtst-ensemble-v0.5
```

모델 구성:

| 구성 | 역할 |
|---|---|
| GRU | 시간 순서에 따른 열화 흐름 학습 |
| TCN | 최근 50 cycle 안의 센서 패턴 변화 학습 |
| PatchTST | 시계열 patch 간 중요 구간 관계 학습 |
| Ensemble | 세 모델 예측값을 validation 기준 가중 평균 |

최종 대표 성능은 다음처럼 정리하는 것이 가장 정직하다.

| 기준 | 값 |
|---|---:|
| test-tuned best RMSE | 12.576 |
| validation 기준 seed 42 RMSE | 12.614 |
| validation 기준 3 seed 평균 RMSE | 12.738 |

발표나 보고서에서는 test-tuned 12.576보다 **validation 기준 3 seed 평균 RMSE 12.738**을 대표 수치로 사용하는 것이 안전하다.

## 18. 서버 연동 방식

현재 FastAPI에서는 RUL 회귀 예측이 다음 API로 제공된다.

```text
POST /api/predict/rul
POST /api/predict/health
```

`/api/predict/health`는 RUL 회귀 결과와 고장 분류 결과를 함께 반환한다.

예시:

```json
{
  "asset_id": "INJ-03",
  "rul": {
    "model_version": "cmapss-fd001-fd004-validated-gru-tcn-patchtst-ensemble-v0.5",
    "rul_hours": 68,
    "risk_72h": 66.7
  },
  "fault": {
    "fault_label": "베어링 불량",
    "fault_probability": 0.343
  }
}
```

## 19. 생성된 주요 산출물

| 파일 | 설명 |
|---|---|
| `data/cmapss/cmapss_rul_benchmark.csv` | 초기 RUL benchmark |
| `data/cmapss/cmapss_rul_condition_normalized_benchmark.csv` | 운전조건 정규화 benchmark |
| `data/cmapss/cmapss_rul_gru_benchmark.csv` | GRU sequence benchmark |
| `data/cmapss/cmapss_model_zoo_benchmark.csv` | PatchTST/iTransformer 후보 실험 |
| `data/cmapss/cmapss_validated_gru_tcn_patchtst_benchmark.csv` | seed 42 validation 앙상블 benchmark |
| `data/cmapss/cmapss_validated_gru_tcn_patchtst_predictions.csv` | seed 42 validation 앙상블 예측값 |
| `data/cmapss/cmapss_rul_validated_ensemble_predictions.csv` | API runtime용 최종 RUL 예측 CSV |
| `data/cmapss/cmapss_seed_stability_summary.csv` | seed 반복 검증 요약 |
| `data/cmapss/cmapss_remaining_validation_report.md` | 남은 검증 보고서 |
| `data/models/validated_gru_tcn_patchtst_seed42` | seed 42 모델 checkpoint |
| `data/models/validated_gru_tcn_patchtst_seed7` | seed 7 모델 checkpoint |
| `data/models/validated_gru_tcn_patchtst_seed123` | seed 123 모델 checkpoint |

## 20. 재현 명령

seed 42 validation 앙상블:

```powershell
python backend\scripts\benchmark_cmapss_validated_ensemble.py --models gru tcn patchtst --epochs 6 --batch-size 1024 --hidden-size 64 --weight-step 0.05 --seed 42 --output data\cmapss\cmapss_validated_gru_tcn_patchtst_benchmark.csv --predictions-output data\cmapss\cmapss_validated_gru_tcn_patchtst_predictions.csv --models-dir data\models\validated_gru_tcn_patchtst_seed42
```

API latency:

```powershell
python backend\scripts\benchmark_api_latency.py --iterations 200 --warmup 20 --output data\cmapss\api_latency_validated_ensemble_benchmark.csv --report-output data\cmapss\api_latency_validated_ensemble_benchmark.md
```

데이터 검증:

```powershell
python backend\scripts\validate_cmapss_dataset.py --window-size 50 --benchmark-path data\cmapss\cmapss_validated_gru_tcn_patchtst_benchmark.csv --report-json data\cmapss\cmapss_validated_ensemble_validation_report.json --report-md data\cmapss\cmapss_validated_ensemble_validation_report.md
```

## 21. 한계와 주의점

| 항목 | 내용 |
|---|---|
| 도메인 차이 | NASA C-MAPSS는 항공기 터보팬 엔진 데이터이며, 실제 사출기/전동기 데이터가 아니다. |
| 실제 적용 | 실제 제조 설비에 적용하려면 해당 설비의 센서와 정비 이력으로 재학습 또는 보정이 필요하다. |
| 프론트 센서명 | 진동, 전류, 유압 온도, 유압 압력은 NASA 원본 컬럼이 아니라 공장 사용자가 이해하기 쉬운 데모용 센서 표현이다. |
| 대표 성능 | test-tuned 12.576보다 validation 기준 seed 평균 12.738을 대표 성능으로 쓰는 것이 정직하다. |

## 22. 최종 결론

NASA C-MAPSS 기반 RUL 회귀 실험에서 `GRU+TCN+PatchTST` validation 앙상블이 가장 타당한 최종 후보로 확인됐다.

핵심 결론은 다음과 같다.

1. 운전조건별 정규화가 통합 RUL 모델 성능에 중요하다.
2. GRU 단독 모델은 강한 기준선이다.
3. TCN과 PatchTST를 함께 앙상블하면 단독 GRU보다 안정적으로 RMSE가 개선된다.
4. test label을 보지 않고 validation 기준으로 가중치를 골라도 앙상블 효과가 유지된다.
5. FastAPI inference 속도는 MVP 대시보드 요구사항을 충분히 만족한다.

따라서 현재 공장지기 MVP의 RUL 회귀 엔진은 다음과 같이 정의한다.

```text
RUL regression engine = NASA C-MAPSS로 검증한 GRU+TCN+PatchTST validation 앙상블
```

단, 실제 제조 현장 적용 단계에서는 NASA 모델을 그대로 쓰는 것이 아니라, 실제 설비 센서와 정비 이력으로 도메인 모델을 다시 학습해야 한다.
