# AI-Hub Raw Waveform Deep Model Benchmark

## Setting

- ZIP: `data\aihub238\downloads\125.기계시설물_고장_예지_센서\01.데이터\2._Validation\vibration.zip`
- Signal kind: `vibration`
- Loaded rows: `10000`
- Groups: `31`
- Target length: `1024`
- Epochs: `4`
- CV folds: `5`
- Models: `tcn`
- Tasks: `multiclass_fault_type`

## Label Distribution

| Label | Name | Count |
|---|---|---:|
| 00 | 정상 | 2000 |
| 01 | 베어링 불량 | 2000 |
| 02 | 회전체 불평형 | 2000 |
| 03 | 축정렬 불량 | 2000 |
| 04 | 벨트 느슨함 | 2000 |

## Results

| Fold | Task | Model | Accuracy | Macro F1 | Weighted F1 | Top-2 | Top-3 |
|---:|---|---|---:|---:|---:|---:|---:|
| 5 | multiclass_fault_type | tcn | 0.502 | 0.333 | 0.397 | 0.607 | 0.701 |
| 2 | multiclass_fault_type | tcn | 0.338 | 0.289 | 0.351 | 0.577 | 0.700 |
| 4 | multiclass_fault_type | tcn | 0.433 | 0.260 | 0.375 | 0.618 | 0.728 |
| 3 | multiclass_fault_type | tcn | 0.299 | 0.195 | 0.251 | 0.391 | 0.430 |
| 1 | multiclass_fault_type | tcn | 0.162 | 0.092 | 0.107 | 0.401 | 0.727 |

## Saved Models

| Task | Model | Path |
|---|---|---|
| multiclass_fault_type | tcn | `data\models\aihub_vibration_waveform_tcn_10k_cv\vibration_multiclass_fault_type_fold1_tcn.pt` |
| multiclass_fault_type | tcn | `data\models\aihub_vibration_waveform_tcn_10k_cv\vibration_multiclass_fault_type_fold2_tcn.pt` |
| multiclass_fault_type | tcn | `data\models\aihub_vibration_waveform_tcn_10k_cv\vibration_multiclass_fault_type_fold3_tcn.pt` |
| multiclass_fault_type | tcn | `data\models\aihub_vibration_waveform_tcn_10k_cv\vibration_multiclass_fault_type_fold4_tcn.pt` |
| multiclass_fault_type | tcn | `data\models\aihub_vibration_waveform_tcn_10k_cv\vibration_multiclass_fault_type_fold5_tcn.pt` |

## Notes

- This benchmark uses grouped holdout by asset group, not row split.
- Raw waveform models use per-window z-score normalization and light augmentation: scaling, Gaussian noise, and time shift.
- Compare against the tabular reference row in the same result table for this exact sample/split.
