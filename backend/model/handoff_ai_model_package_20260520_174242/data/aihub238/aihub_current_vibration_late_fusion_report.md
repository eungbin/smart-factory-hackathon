# AI-Hub Current + Vibration Late Fusion Benchmark

## Purpose

Evaluate an MVP decision-level fusion strategy: current detects normal/fault, vibration ranks fault-type candidates.

## Important Pairing Note

AI-Hub current.zip and vibration.zip are separate bundles and are not guaranteed to be simultaneous sensor captures.
For this benchmark, samples are paired by same asset_group and same label. This tests the decision strategy, not exact synchronized multimodal sensing.

## Setting

- Current rows loaded: `10000`
- Vibration rows loaded: `10000`
- Paired rows: `7770`
- Groups: `31`
- Max files per modality: `10000`
- Max per label path: `2000`

## Results

| Task | Model | Accuracy | Macro F1 | Weighted F1 | Top-2 | Top-3 |
|---|---|---:|---:|---:|---:|---:|
| binary_normal_vs_fault | current_binary_rf | 0.842 | 0.780 | 0.852 | 1.000 | 1.000 |
| multiclass_fault_type | vibration_multiclass_rf | 0.617 | 0.599 | 0.606 | 0.782 | 0.855 |
| multiclass_fault_type | late_fusion_hard_gate | 0.501 | 0.424 | 0.389 | 0.680 | 0.785 |
| multiclass_fault_type | late_fusion_soft_gate | 0.502 | 0.422 | 0.386 | 0.549 | 0.707 |
| multiclass_fault_type | vibration_multiclass_logreg | 0.421 | 0.351 | 0.319 | 0.702 | 0.707 |
| multiclass_fault_type | current_multiclass_rf | 0.184 | 0.099 | 0.095 | 0.260 | 0.555 |

## Saved Models

| Role | Path |
|---|---|
| current_binary | `data\models\aihub_late_fusion\current_binary_random_forest.joblib` |
| vibration_multiclass | `data\models\aihub_late_fusion\vibration_multiclass_logistic_regression.joblib` |
| current_multiclass | `data\models\aihub_late_fusion\current_multiclass_random_forest.joblib` |
| vibration_rf_multiclass | `data\models\aihub_late_fusion\vibration_multiclass_random_forest.joblib` |

## Interpretation

- Hard gate is conservative: if current predicts normal, final class is normal.
- Soft gate blends current normal/fault probability with vibration fault-type probabilities.
- For MVP, use this as a product decision policy, while still labeling fault type as ranked candidates.
