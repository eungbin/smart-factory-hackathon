# NASA C-MAPSS 남은 검증 보고서

작성일: 2026-05-07

## 검증 요약

| 검증 항목 | 결과 | 판단 |
|---|---|---|
| validation 기준 GRU+TCN+PatchTST 가중치 탐색 | seed 42 기준 official RMSE 12.614 | test label 없이도 기존 test-tuned 12.576에 가까워 유효 |
| seed 변경 반복 실험 | seeds 7, 42, 123 official RMSE 평균 12.738, 표준편차 0.164 | seed에 따른 흔들림은 있으나 GRU 단독보다 계속 개선 |
| subset별 성능 확인 | FD001 12.674, FD002 12.492, FD003 12.231, FD004 12.865 | 어려운 FD002/FD004에서도 성능 붕괴 없음 |
| API inference 속도 측정 | 최종 앙상블 CSV 기준 HTTP mean 31.8ms, p95 48.2ms | 1초 응답 기준을 충분히 만족 |
| 모델 저장 및 재현 명령 고정 | seed별 `.pt`, benchmark, predictions 저장 | 데모와 발표 재현 가능 |
| 데이터/benchmark 무결성 검증 | errors 0, warnings 2, benchmark PASS | FD004 train/test count README 차이만 warning |

## Validation 기준 앙상블 결과

Official model은 validation set에서 grid search로 고른 `ensemble_grid_gru_tcn_patchtst_val`이다. 이 값은 test label을 보고 고른 가중치가 아니므로, 이전의 test-tuned ensemble보다 더 정직한 검증 수치다.

| Seed | Weights | Official RMSE | PHM Score | High-Risk | GRU RMSE | Improvement vs GRU | Best Row On Test |
|---:|---|---:|---:|---:|---:|---:|---|
| 7 | `{'gru': 0.40, 'tcn': 0.30, 'patchtst': 0.30}` | 12.677 | 2170.6 | 298 | 12.901 | 0.224 | `ensemble_constrained_ls_val` |
| 42 | `{'gru': 0.30, 'tcn': 0.35, 'patchtst': 0.35}` | 12.614 | 2280.1 | 300 | 13.018 | 0.405 | `ensemble_equal_all` |
| 123 | `{'gru': 0.40, 'tcn': 0.30, 'patchtst': 0.30}` | 12.924 | 2318.6 | 309 | 13.434 | 0.509 | `ensemble_equal_all` |

Seed별 official RMSE 요약:

| Metric | RMSE | PHM | Improvement vs GRU |
|---|---:|---:|---:|
| mean | 12.738 | 2256.4 | 0.379 |
| std | 0.164 | 76.8 | 0.145 |
| min | 12.614 | 2170.6 | 0.224 |
| max | 12.924 | 2318.6 | 0.509 |

## Subset별 성능

아래 표는 seed 42의 official model인 `ensemble_grid_gru_tcn_patchtst_val` 기준이다.

| Subset | Test Units | RMSE | PHM Score | High-Risk Count |
|---|---:|---:|---:|---:|
| FD001 | 100 | 12.674 | 290.4 | 42 |
| FD002 | 259 | 12.492 | 827.3 | 114 |
| FD003 | 100 | 12.231 | 260.9 | 46 |
| FD004 | 248 | 12.865 | 901.5 | 98 |

FD002와 FD004는 운전조건이 6개인 어려운 subset인데, 둘 다 13 미만 RMSE를 유지했다. 따라서 운전조건별 정규화와 subset one-hot 입력이 통합 모델에서 의미 있게 작동한다고 볼 수 있다.

## API Inference 속도

실행 중인 로컬 FastAPI 서버에 HTTP 요청을 보내 측정했다.

| Metric | Value |
|---|---:|
| Mode | http |
| Iterations | 200 |
| Mean ms | 31.819 |
| Median ms | 31.026 |
| P95 ms | 48.232 |
| P99 ms | 74.401 |
| Max ms | 87.858 |

MVP 성공 기준으로 잡았던 “예측 API 1초 이내 응답”은 충분히 만족한다.

## 저장된 모델과 산출물

| Seed | Model Directory | Benchmark CSV | Predictions CSV |
|---:|---|---|---|
| 42 | `data/models/validated_gru_tcn_patchtst_seed42` | `data/cmapss/cmapss_validated_gru_tcn_patchtst_benchmark.csv` | `data/cmapss/cmapss_validated_gru_tcn_patchtst_predictions.csv` |
| 7 | `data/models/validated_gru_tcn_patchtst_seed7` | `data/cmapss/cmapss_validated_gru_tcn_patchtst_seed7_benchmark.csv` | `data/cmapss/cmapss_validated_gru_tcn_patchtst_seed7_predictions.csv` |
| 123 | `data/models/validated_gru_tcn_patchtst_seed123` | `data/cmapss/cmapss_validated_gru_tcn_patchtst_seed123_benchmark.csv` | `data/cmapss/cmapss_validated_gru_tcn_patchtst_seed123_predictions.csv` |

Runtime용 최종 예측 CSV:

```text
data/cmapss/cmapss_rul_validated_ensemble_predictions.csv
```

이 파일은 `ensemble_grid_gru_tcn_patchtst_val` 컬럼을 API가 읽을 수 있는 `predicted_rul`, `risk_72h` 형식으로 변환한 것이다.

각 model directory에는 다음 파일이 저장되어 있다.

| 파일 | 설명 |
|---|---|
| `cmapss_gru_best.pt` | validation RMSE가 가장 낮았던 GRU checkpoint |
| `cmapss_tcn_best.pt` | validation RMSE가 가장 낮았던 TCN checkpoint |
| `cmapss_patchtst_best.pt` | validation RMSE가 가장 낮았던 PatchTST checkpoint |

## 재현 명령

Seed 42:

```powershell
python backend\scripts\benchmark_cmapss_validated_ensemble.py --models gru tcn patchtst --epochs 6 --batch-size 1024 --hidden-size 64 --weight-step 0.05 --seed 42 --output data\cmapss\cmapss_validated_gru_tcn_patchtst_benchmark.csv --predictions-output data\cmapss\cmapss_validated_gru_tcn_patchtst_predictions.csv --models-dir data\models\validated_gru_tcn_patchtst_seed42
```

Seed 7:

```powershell
python backend\scripts\benchmark_cmapss_validated_ensemble.py --models gru tcn patchtst --epochs 6 --batch-size 1024 --hidden-size 64 --weight-step 0.05 --seed 7 --output data\cmapss\cmapss_validated_gru_tcn_patchtst_seed7_benchmark.csv --predictions-output data\cmapss\cmapss_validated_gru_tcn_patchtst_seed7_predictions.csv --models-dir data\models\validated_gru_tcn_patchtst_seed7
```

Seed 123:

```powershell
python backend\scripts\benchmark_cmapss_validated_ensemble.py --models gru tcn patchtst --epochs 6 --batch-size 1024 --hidden-size 64 --weight-step 0.05 --seed 123 --output data\cmapss\cmapss_validated_gru_tcn_patchtst_seed123_benchmark.csv --predictions-output data\cmapss\cmapss_validated_gru_tcn_patchtst_seed123_predictions.csv --models-dir data\models\validated_gru_tcn_patchtst_seed123
```

API latency:

```powershell
python backend\scripts\benchmark_api_latency.py --iterations 200 --warmup 20 --output data\cmapss\api_latency_validated_ensemble_benchmark.csv --report-output data\cmapss\api_latency_validated_ensemble_benchmark.md
```

Dataset and benchmark validation:

```powershell
python backend\scripts\validate_cmapss_dataset.py --window-size 50 --benchmark-path data\cmapss\cmapss_validated_gru_tcn_patchtst_benchmark.csv --report-json data\cmapss\cmapss_validated_ensemble_validation_report.json --report-md data\cmapss\cmapss_validated_ensemble_validation_report.md
```

## 최종 판단

`GRU+TCN+PatchTST` validation 기반 앙상블은 test label을 직접 보고 고른 결과가 아니어도 GRU 단독보다 일관되게 낮은 RMSE를 보였다. seed 123에서 성능이 다소 떨어졌지만 여전히 GRU 단독 대비 개선됐다.

따라서 현재 NASA C-MAPSS 기반 운영 후보는 `GRU+TCN+PatchTST`로 유지하는 것이 타당하다. 발표나 보고서에서는 test-tuned 12.576보다 validation 기준 seed 평균 RMSE 약 12.738을 더 정직한 대표 수치로 사용하는 것이 좋다.
