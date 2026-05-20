# API Inference Latency Benchmark

| Metric | Value |
|---|---:|
| Iterations | 200 |
| Success Count | 200 |
| Mode | http |
| Mean latency ms | 31.819 |
| Median latency ms | 31.026 |
| P95 latency ms | 48.232 |
| P99 latency ms | 74.401 |
| Max latency ms | 87.858 |
| Min latency ms | 16.798 |

CSV: `data\cmapss\api_latency_validated_ensemble_benchmark.csv`

Note: Mode `http` measures the running local FastAPI server over localhost. If the server is unavailable, the script falls back to direct predictor calls.
