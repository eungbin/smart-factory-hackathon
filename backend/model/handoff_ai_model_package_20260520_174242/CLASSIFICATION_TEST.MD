# AI-Hub 전류 데이터 분류모델 개선 결과

## 목적

공장지기 MVP에서 분류모델은 RUL 회귀모델 다음 단계에서 다음 질문에 답한다.

```text
이 설비가 고장 상태인가?
고장이라면 어떤 유형인가?
```

AI-Hub 238 `기계시설물 고장 예지 센서` 데이터 중 현재 확보된 `Validation/current.zip`을 사용했다. 이 데이터는 RUL 정답이 아니라 상태 라벨 데이터이므로, 회귀가 아니라 분류 실험에 사용한다.

## 라벨 체계

| 코드 | 의미 |
|---|---|
| 00 | 정상 |
| 01 | 베어링 불량 |
| 02 | 회전체 불평형 |
| 03 | 축정렬 불량 |
| 04 | 벨트 느슨함 |

## 최종 실험 설정

| 항목 | 값 |
|---|---|
| 데이터 | `data/aihub238/downloads/.../Validation/current.zip` |
| 원본 CSV 수 | 144,730개 |
| 사용 샘플 | 10,000개 |
| 라벨별 최대 샘플 | 2,000개 |
| random seed | 42 |
| 최종 feature 수 | 260개 |
| 검증 task | 정상/고장 이진분류, 5-class 다중분류, fault-only 고장유형 분류 |
| 모델 후보 | Logistic Regression, RandomForest, ExtraTrees, HistGradientBoosting, Soft Voting |

## 개선한 점

초기 실험은 metadata와 기본 전류 통계만 사용했다.

이번 개선에서는 전류 파형에서 다음 feature를 추가했다.

| Feature 그룹 | 예시 | 이유 |
|---|---|---|
| 시간영역 통계 | mean, std, RMS, peak-to-peak, quantile, IQR | 전류 크기와 변동폭을 설명 |
| 파형 형상 | crest factor, form factor, impulse factor, skew, kurtosis | 충격성/비대칭/피크성 이상 포착 |
| 변화율 | diff mean, diff std, max diff | 급격한 전류 흔들림 포착 |
| 주파수영역 | spectral centroid, spread, entropy, dominant frequency, band ratio | 회전 불균형/벨트/축정렬 관련 주파수 패턴 포착 |
| 3상 관계 | R/S/T correlation, phase diff RMS, phase imbalance | 3상 전류 불균형과 위상 관계 반영 |
| 설비별 정상 baseline | asset_rel_* | 설비마다 전류 스케일이 다른 문제 완화 |

특히 `asset_rel_*` feature가 중요하다. 실제 현장에서는 설비별 정상 운전 기준선을 먼저 확보할 수 있으므로, 현재 전류값 자체뿐 아니라 “해당 설비의 정상 상태 대비 얼마나 달라졌는가”를 넣었다.

## 검증 방식

두 가지 split을 사용했다.

| Split | 의미 | 해석 |
|---|---|---|
| row_stratified_upper_bound | 행 단위 stratified split | 같은 설비/유사 파일이 train/test에 함께 들어갈 수 있으므로 성능 상한선 |
| asset_group_stratified | 설비 그룹 단위 holdout | 처음 보는 설비에 대한 일반화 성능에 가까움 |

기존에는 group split의 첫 fold를 그대로 사용해 test set에 특정 라벨이 빠지는 문제가 있었다. 이번에는 모델 성능을 보지 않고, train/test 양쪽에 라벨이 최대한 균형 있게 들어가도록 split 선택 로직을 수정했다.

## 최종 결과 요약

### 1. 정상/고장 이진분류

| 기준 | 최고 모델 | Accuracy | Macro F1 |
|---|---|---:|---:|
| row split 성능 상한 | ExtraTrees Smooth | 0.994 | 0.991 |
| 미지 설비 group split | HistGradientBoosting | 0.827 | 0.827 |

이진분류는 MVP 알림 단계에서 사용할 수 있을 정도로 개선됐다. group split 기준 Macro F1이 기존 약 `0.346`에서 `0.827`까지 올라갔다.

### 2. 5-class 전체 다중분류

| 기준 | 최고 모델 | Accuracy | Macro F1 |
|---|---|---:|---:|
| row split 성능 상한 | Soft Voting | 0.995 | 0.995 |
| 미지 설비 group split | RandomForest Baseline | 0.330 | 0.224 |

5-class를 처음 보는 설비에 바로 일반화하는 것은 아직 어렵다. 이유는 AI-Hub current validation 데이터에서 고장 유형과 특정 설비/모터 조건이 강하게 엮여 있기 때문이다.

### 3. fault-only 고장유형 분류

정상/고장 이진분류를 먼저 수행한 뒤, 고장으로 판단된 샘플만 01~04로 분류하는 계층형 구조다.

| 기준 | 최고 모델 | Accuracy | Macro F1 |
|---|---|---:|---:|
| row split 성능 상한 | 여러 모델 동률 | 1.000 | 1.000 |
| 미지 설비 group split | Logistic Regression | 0.422 | 0.319 |

데모와 MVP에서는 이 계층형 구조가 가장 자연스럽다.

```text
1단계: 정상/고장 판단
2단계: 고장일 때만 베어링/불평형/축정렬/벨트 분류
```

## 저장된 모델

| 용도 | 파일 | 모델 | 기준 성능 |
|---|---|---|---|
| 5-class 데모용 분류모델 | `data/models/aihub_current_fault_classifier.joblib` | Soft Voting | row split Macro F1 0.995 |
| 정상/고장 운영 후보 | `data/models/aihub_current_binary_fault_classifier.joblib` | HistGradientBoosting | group split Macro F1 0.827 |

## 재현 명령

```powershell
$env:PYTHONPATH='backend'
python backend\scripts\benchmark_aihub_current.py --max-files 10000 --max-per-path-label 2000 --seed 42 --output data\aihub238\aihub_current_final_hier_10k_benchmark.csv --report-output data\aihub238\aihub_current_final_hier_10k_report.md --model-output data\models\aihub_current_fault_classifier.joblib
```

## 산출물

| 파일 | 설명 |
|---|---|
| `data/aihub238/aihub_current_final_hier_10k_benchmark.csv` | 최종 성능표 |
| `data/aihub238/aihub_current_final_hier_10k_report.md` | 상세 리포트 |
| `data/models/aihub_current_fault_classifier.joblib` | 5-class 데모용 모델 |
| `data/models/aihub_current_binary_fault_classifier.joblib` | 정상/고장 운영 후보 모델 |

## 현재 결론

회귀모델은 NASA C-MAPSS 기반 RUL 예측 파이프라인 검증용으로 고정해도 된다.

분류모델은 오늘 기준으로 다음 단계까지 도달했다.

```text
정상/고장 이진분류: MVP 적용 가능 수준
고장유형 row split: 데모 가능 수준
고장유형 미지 설비 일반화: 아직 추가 데이터/진동 데이터 필요
```

따라서 공장지기 MVP에서는 다음 구조로 사용하는 것이 가장 안전하다.

```text
RUL 회귀모델
→ 정상/고장 이진분류
→ 고장일 때만 fault-only 고장유형 분류
→ 작업지시서 생성
```

## 추가 검증: 미지 설비 Group-CV

위 결과 중 `asset_group_stratified`는 한 번의 group split 결과다. 한 번의 split은 어떤 설비가 test에 들어갔는지에 따라 흔들릴 수 있다. 그래서 미지 설비 일반화 성능을 더 보수적으로 보기 위해 `5-fold StratifiedGroupKFold`를 추가로 실행했다.

| Task | 최고 모델 | Accuracy mean | Macro F1 mean | Macro F1 std | Top-2 mean | Top-3 mean |
|---|---|---:|---:|---:|---:|---:|
| 정상/고장 이진분류 | RandomForest | 0.800 | 0.721 | 0.134 | - | - |
| 5-class 전체분류 | RandomForest | 0.305 | 0.199 | 0.075 | 0.357 | 0.490 |
| 5-class 전체분류 후보형 | Logistic Regression | 0.259 | 0.167 | 0.087 | 0.514 | 0.666 |
| fault-only 고장유형 | Logistic Regression | 0.185 | 0.199 | 0.209 | 0.506 | 0.854 |

Top-2/Top-3는 “정답 라벨이 모델이 제시한 상위 후보 2개 또는 3개 안에 들어갔는가”를 뜻한다. 이진분류는 class가 2개뿐이라 Top-2가 항상 1.0이 되므로 의미 있게 보지 않는다.

이 추가 검증으로 결론이 더 명확해졌다.

```text
정상/고장 판단은 미지 설비에서도 어느 정도 일반화 가능하다.
하지만 5-class 고장유형을 top-1로 확정하는 것은 아직 위험하다.
고장유형은 top-2/top-3 후보와 센서 근거를 함께 보여주는 방식이 더 현실적이다.
```

추가 산출물:

| 파일 | 설명 |
|---|---|
| `backend/scripts/benchmark_aihub_generalization.py` | 미지 설비 group-CV 실험 스크립트 |
| `data/aihub238/aihub_current_generalization_10k_cv.csv` | 10k group-CV fold별 결과 |
| `data/aihub238/aihub_current_generalization_10k_cv_report.md` | 10k group-CV 상세 리포트 |
| `data/models/aihub_generalization_10k/binary_normal_vs_fault_asset_baseline_random_forest.joblib` | group-CV 기준 정상/고장 후보 모델 |
| `data/models/aihub_generalization_10k/fault_type_only_asset_baseline_logistic_regression.joblib` | group-CV 기준 fault-only 후보 모델 |
| `data/models/aihub_generalization_10k/multiclass_fault_type_asset_baseline_random_forest.joblib` | group-CV 기준 5-class 후보 모델 |

## 남은 개선 포인트

1. `vibration.zip`까지 확보해 전류+진동 통합 모델로 확장한다.
2. Train/current.zip까지 추가해 validation current만 쓰는 한계를 줄인다.
3. 설비별 정상 baseline 수집 절차를 제품 플로우에 명시한다.
4. 미지 설비 5-class 성능은 현재 낮으므로, 발표에서는 row split 성능과 group split 성능을 구분해서 말한다.

## 데이터 확장 준비

전류 데이터만으로는 고장유형 일반화에 한계가 있어, 다음 확장 스크립트를 추가했다.

| 스크립트 | 용도 |
|---|---|
| `scripts/download_aihub238_valid_vibration.ps1` | AI-Hub 238 Validation vibration.zip 다운로드 |
| `scripts/run_aihub238_vibration_experiments.ps1` | vibration.zip 기준 benchmark + group-CV 실행 |
| `scripts/download_and_run_aihub238_valid_vibration.ps1` | 다운로드와 실험을 한 번에 실행 |
| `scripts/download_aihub238_train_current.ps1` | 추가 학습량 확보용 Training current.zip 다운로드 |

권장 다음 명령:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\scripts\download_and_run_aihub238_valid_vibration.ps1
```

`Validation/vibration.zip`은 약 10GB라 다운로드와 압축 해제에 시간이 걸릴 수 있다. 실행이 끝나면 다음 결과 파일이 생성된다.

| 파일 | 설명 |
|---|---|
| `data/aihub238/aihub_vibration_final_hier_10k_benchmark.csv` | 진동 데이터 row/group split 성능표 |
| `data/aihub238/aihub_vibration_final_hier_10k_report.md` | 진동 데이터 상세 리포트 |
| `data/aihub238/aihub_vibration_generalization_10k_cv.csv` | 진동 데이터 미지 설비 group-CV 결과 |
| `data/aihub238/aihub_vibration_generalization_10k_cv_report.md` | 진동 데이터 미지 설비 group-CV 리포트 |

## 데이터 확장 결과: Vibration 추가

`Validation/vibration.zip` 다운로드와 10k 샘플 실험을 완료했다.

| 항목 | 값 |
|---|---|
| 파일 | `data/aihub238/downloads/.../2._Validation/vibration.zip` |
| ZIP size | 약 9.69GB |
| CSV count | 126,712개 |
| 실험 샘플 | 10,000개 |
| 라벨별 샘플 | 2,000개 |
| feature 수 | 106개 |

진동 데이터 단독 group split 결과는 전류보다 고장유형 분류에서 크게 좋아졌다.

| Task | Split | 최고 모델 | Accuracy | Macro F1 |
|---|---|---|---:|---:|
| 정상/고장 이진분류 | group split | ExtraTrees Smooth | 0.682 | 0.639 |
| 5-class 전체분류 | group split | HistGradientBoosting | 0.649 | 0.600 |
| fault-only 고장유형 | group split | ExtraTrees Deep | 0.578 | 0.599 |

더 보수적인 5-fold group-CV 평균 결과는 다음과 같다.

| Signal | Task | 최고 모델 | Accuracy mean | Macro F1 mean | Top-2 mean | Top-3 mean |
|---|---|---|---:|---:|---:|---:|
| current | 정상/고장 이진분류 | RandomForest | 0.800 | 0.721 | - | - |
| vibration | 정상/고장 이진분류 | RandomForest | 0.750 | 0.701 | - | - |
| current | 5-class 전체분류 | RandomForest | 0.305 | 0.199 | 0.357 | 0.490 |
| vibration | 5-class 전체분류 | LogisticRegression | 0.499 | 0.420 | 0.685 | 0.885 |
| current | fault-only 고장유형 | LogisticRegression | 0.185 | 0.199 | 0.506 | 0.854 |
| vibration | fault-only 고장유형 | RandomForest | 0.411 | 0.318 | 0.695 | 0.881 |

결론:

```text
정상/고장 알림: current가 약간 우세
고장유형 분류: vibration이 확실히 우세
고장유형 top-1 확정: 아직 위험
고장유형 top-3 후보 제공: 제품적으로 쓸 만함
```

따라서 공장지기 MVP의 분류모델 역할은 다음처럼 나누는 것이 좋다.

```text
전류 모델(current): 정상/고장 알림 신뢰도 강화
진동 모델(vibration): 베어링/불평형/축정렬/벨트 원인 후보 제시
RUL 회귀모델(C-MAPSS): 잔여수명/위험도 산출
```

추가 산출물:

| 파일 | 설명 |
|---|---|
| `data/aihub238/aihub_vibration_final_hier_10k_benchmark.csv` | 진동 데이터 row/group split 결과 |
| `data/aihub238/aihub_vibration_final_hier_10k_report.md` | 진동 데이터 상세 리포트 |
| `data/aihub238/aihub_vibration_generalization_10k_cv.csv` | 진동 데이터 group-CV 결과 |
| `data/aihub238/aihub_vibration_generalization_10k_cv_report.md` | 진동 데이터 group-CV 리포트 |
| `data/aihub238/aihub_current_vs_vibration_summary.csv` | 전류 vs 진동 비교 요약 |
| `data/models/aihub_vibration_generalization_10k/binary_normal_vs_fault_asset_baseline_random_forest.joblib` | 진동 정상/고장 후보 모델 |
| `data/models/aihub_vibration_generalization_10k/fault_type_only_asset_baseline_random_forest.joblib` | 진동 fault-only 후보 모델 |
| `data/models/aihub_vibration_generalization_10k/multiclass_fault_type_asset_baseline_logistic_regression.joblib` | 진동 5-class 후보 모델 |

## 원시 파형 딥러닝 실험: 1D-CNN / TCN

기존 분류모델은 원시 파형을 바로 학습한 것이 아니라, 전류/진동 파형에서 통계 feature를 추출한 뒤 tabular 모델을 학습했다.

이번 추가 실험에서는 `Validation/vibration.zip`에서 원시 진동 파형을 직접 읽어 1D-CNN과 TCN을 학습했다.

| 설정 | 값 |
|---|---|
| 데이터 | AI-Hub Validation vibration.zip |
| 샘플 | 3,000개 |
| 라벨별 최대 | 600개 |
| 입력 길이 | 1,024 point |
| 채널 | 1채널 진동 파형 |
| 모델 | 1D-CNN, TCN |
| Epoch | 6 |
| Split | 설비 그룹 holdout |
| 적용 장치 | amplitude normalization, random noise, scaling, time shift augmentation |

### 장치별 의미

| 장치 | 적용 의미 | 목적 |
|---|---|---|
| group holdout / group-CV | 설비 ID 기준으로 train/test 분리 | 같은 설비 암기 방지, 미지 설비 평가 |
| per-asset baseline normalization | 설비별 정상 기준선 대비 변화량 사용 | 모터 용량/설비별 스케일 차이 완화 |
| amplitude normalization | 파형별 평균 제거, 표준편차 정규화 | 센서 크기와 진폭 차이 완화 |
| random crop/windowing | 긴 파형 일부 구간을 학습 window로 사용 | 특정 파일 전체 패턴 암기 완화 |
| augmentation | noise, scaling, time shift | 센서 노이즈와 시작 위치 변화에 대한 견고성 |
| top-k 평가 | 정답이 상위 k개 후보 안에 있는지 평가 | 고장유형은 확정보다 후보 제시가 현실적 |
| current+vibration late fusion | 전류/진동 모델의 출력을 나중에 결합 | 전류의 고장 감지력과 진동의 유형 분류력 결합 |

### 원시 파형 실험 결과

| Task | Model | Accuracy | Macro F1 | Top-2 | Top-3 |
|---|---|---:|---:|---:|---:|
| 5-class 전체분류 | TCN | 0.547 | 0.459 | 0.575 | 0.738 |
| 5-class 전체분류 | CNN | 0.280 | 0.268 | 0.444 | 0.738 |
| 5-class 전체분류 | 같은 split tabular RF | 0.175 | 0.138 | 0.221 | 0.356 |
| fault-only 고장유형 | 같은 split tabular RF | 0.417 | 0.366 | 0.588 | 0.719 |
| fault-only 고장유형 | CNN | 0.472 | 0.308 | 0.533 | 0.616 |
| fault-only 고장유형 | TCN | 0.296 | 0.299 | 0.480 | 0.575 |

### 기존 실험과 비교

| 실험 | Task | 모델 | Macro F1 | Top-3 | 해석 |
|---|---|---|---:|---:|---|
| current tabular 10k group-CV | 정상/고장 | RandomForest | 0.721 | - | 알림용 최선 후보 |
| vibration tabular 10k group-CV | 5-class | LogisticRegression | 0.420 | 0.885 | MVP 고장유형 후보 제시용 최선 |
| vibration raw waveform 3k holdout | 5-class | TCN | 0.459 | 0.738 | top-1 성능 가능성은 좋지만 top-3와 안정성은 아직 부족 |
| vibration tabular 10k group-CV | fault-only | RandomForest | 0.318 | 0.881 | 고장 후 원인 후보 제시용 안정 후보 |
| vibration raw waveform 3k holdout | fault-only | CNN | 0.308 | 0.616 | 정확도는 높지만 macro/top-3는 약함 |

결론:

```text
원시 파형 TCN은 5-class top-1 성능을 올릴 가능성이 있다.
하지만 현재 3k 단일 holdout 기준이라, 10k 5-fold group-CV를 통과한 안정 후보는 아니다.
MVP 즉시 사용은 vibration tabular top-3 후보 모델이 더 안전하다.
원시 파형 모델은 다음 성능 개선 후보로 유지한다.
```

산출물:

| 파일 | 설명 |
|---|---|
| `backend/scripts/benchmark_aihub_waveform_deep.py` | 원시 파형 CNN/TCN 실험 스크립트 |
| `data/aihub238/aihub_vibration_waveform_deep_3k_benchmark.csv` | 원시 파형 3k 성능표 |
| `data/aihub238/aihub_vibration_waveform_deep_3k_report.md` | 원시 파형 실험 리포트 |
| `data/aihub238/aihub_classification_model_comparison.csv` | 기존 feature 모델과 원시 파형 모델 비교표 |

## 우선순위 1, 2 추가 실험

다음 우선순위로 두 가지를 실행했다.

```text
1. current + vibration late fusion
2. raw TCN 10k group-CV
```

### 1. Current + Vibration Late Fusion

목적은 전류와 진동의 역할을 나눠 결합하는 것이다.

```text
current 모델: 정상/고장 여부 판단
vibration 모델: 고장유형 후보 판단
late fusion: 두 모델의 출력을 마지막 의사결정 단계에서 결합
```

주의할 점은 AI-Hub `current.zip`과 `vibration.zip`이 완전히 같은 시각에 동시 계측된 1:1 샘플이라고 보장되지는 않는다는 것이다. 그래서 이번 실험에서는 같은 `asset_group`과 같은 `label`을 가진 전류/진동 샘플을 짝지은 pseudo-pair 방식으로 평가했다. 즉 이 실험은 실제 동시 센서 융합의 완전한 검증이라기보다, MVP 의사결정 정책 검증에 가깝다.

| Model | Task | Accuracy | Macro F1 | Top-2 | Top-3 |
|---|---|---:|---:|---:|---:|
| current binary RF | 정상/고장 | 0.842 | 0.780 | - | - |
| vibration multiclass RF | 5-class | 0.617 | 0.599 | 0.782 | 0.855 |
| late fusion hard gate | 5-class | 0.501 | 0.424 | 0.680 | 0.785 |
| late fusion soft gate | 5-class | 0.502 | 0.422 | 0.549 | 0.707 |
| vibration multiclass LogisticRegression | 5-class | 0.421 | 0.351 | 0.702 | 0.707 |
| current multiclass RF | 5-class | 0.184 | 0.099 | 0.260 | 0.555 |

해석:

```text
current는 정상/고장 이진 판단에 좋다.
vibration RF 단독이 5-class에서는 late fusion보다 더 좋았다.
late fusion은 제품 정책으로는 유용하지만, 현재 수치상 5-class 최강 모델은 아니다.
```

따라서 MVP에서는 late fusion을 “하나의 5-class 성능 개선 모델”로 쓰기보다, 아래처럼 역할 분리에 사용하는 것이 좋다.

```text
current binary RF: 알림 여부 판단
vibration multiclass RF/LogisticRegression: 원인 후보 top-3 제시
```

### 2. Raw TCN 10k Group-CV

3k 단일 group holdout에서 TCN은 5-class Macro F1 `0.459`로 가능성을 보였다. 그러나 단일 split은 우연히 쉬운 설비 조합이 test로 들어갔을 가능성이 있으므로, 10k 샘플과 5-fold group-CV로 다시 검증했다.

| Fold | Accuracy | Macro F1 | Top-2 | Top-3 |
|---:|---:|---:|---:|---:|
| 1 | 0.162 | 0.092 | 0.401 | 0.727 |
| 2 | 0.338 | 0.289 | 0.577 | 0.700 |
| 3 | 0.299 | 0.195 | 0.391 | 0.430 |
| 4 | 0.433 | 0.260 | 0.618 | 0.728 |
| 5 | 0.502 | 0.333 | 0.607 | 0.701 |
| 평균 | 0.347 | 0.234 | 0.519 | 0.657 |

결론:

```text
raw TCN은 3k 단일 split에서는 좋아 보였지만,
10k 5-fold group-CV에서는 안정적으로 일반화되지 않았다.
현재 MVP 기본 모델로 쓰기에는 tabular vibration 모델보다 위험하다.
```

### 전체 비교

| 실험 | Task | Model | Macro F1 | Top-3 | 판단 |
|---|---|---|---:|---:|---|
| current tabular 10k group-CV | 정상/고장 | RandomForest | 0.721 | - | 알림용 안정 후보 |
| late fusion paired holdout | 정상/고장 | current binary RF | 0.780 | - | pseudo-pair 기준 더 좋음 |
| vibration tabular 10k group-CV | 5-class | LogisticRegression | 0.420 | 0.885 | MVP top-3 후보 제시용 안정 후보 |
| late fusion paired holdout | 5-class | vibration RF | 0.599 | 0.855 | pseudo-pair 기준 강함, 추가 검증 필요 |
| late fusion paired holdout | 5-class | hard gate | 0.424 | 0.785 | 정책상 유용하지만 단독 최고는 아님 |
| raw TCN 10k group-CV | 5-class | TCN | 0.234 | 0.657 | 현재는 보류 |

### 현재 MVP 권장안

```text
1. 정상/고장 알림:
   current tabular RandomForest를 기본 후보로 사용

2. 고장유형:
   vibration tabular 모델의 top-3 후보를 표시

3. late fusion:
   최종 5-class 모델이라기보다,
   current가 고장 가능성을 판단하고 vibration이 원인 후보를 제시하는 제품 정책으로 사용

4. raw TCN:
   성능 개선 연구 후보로 유지하되 MVP 기본 모델에서는 제외
```

추가 산출물:

| 파일 | 설명 |
|---|---|
| `backend/scripts/benchmark_aihub_late_fusion.py` | current+vibration late fusion 실험 스크립트 |
| `data/aihub238/aihub_current_vibration_late_fusion_benchmark.csv` | late fusion 결과 |
| `data/aihub238/aihub_current_vibration_late_fusion_report.md` | late fusion 리포트 |
| `data/aihub238/aihub_vibration_waveform_tcn_10k_cv_benchmark.csv` | raw TCN 10k group-CV 결과 |
| `data/aihub238/aihub_vibration_waveform_tcn_10k_cv_report.md` | raw TCN 10k group-CV 리포트 |
| `data/aihub238/aihub_priority1_2_test_comparison.csv` | 우선순위 1, 2 결과 통합 비교표 |
