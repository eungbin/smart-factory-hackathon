# C-MAPSS Validation Report

- Generated: `2026-05-07T12:29:45.926088+00:00`
- ZIP: `data\cmapss\CMAPSSData.zip`
- ZIP size: `12425978` bytes
- Window size: `50` cycle
- ZIP status: `PASS`

## Subset Summary

| subset | status | train rows | train units | test rows | test units | RUL rows | windows |
|---|---:|---:|---:|---:|---:|---:|---:|
| FD001 | PASS | 20631 | 100 | 13096 | 100 | 100 | 15731 |
| FD002 | PASS | 53759 | 260 | 33991 | 259 | 259 | 41019 |
| FD003 | PASS | 24720 | 100 | 16596 | 100 | 100 | 19820 |
| FD004 | WARN | 61249 | 249 | 41214 | 248 | 248 | 49048 |

## Benchmark

- Combined ALL capped RMSE: `13.018`
- Combined ALL PHM score: `2868.561`
- Combined high-risk count: `295`

## Issues

- `WARN` `FD004` `train_unit_count`: NASA expected 248 units, downloaded ZIP has 249. FD004 appears swapped against NASA README counts in the downloaded ZIP; keep this in loader logs.
- `WARN` `FD004` `test_unit_count`: NASA expected 249 units, downloaded ZIP has 248. FD004 appears swapped against NASA README counts in the downloaded ZIP; keep this in loader logs.
