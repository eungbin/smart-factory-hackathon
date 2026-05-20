from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path
from urllib import error, request

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.predictor import predict_rul  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Measure FastAPI inference endpoint latency with TestClient.")
    parser.add_argument("--iterations", type=int, default=200)
    parser.add_argument("--warmup", type=int, default=20)
    parser.add_argument("--url", default="http://127.0.0.1:8000/api/predict/rul")
    parser.add_argument("--output", default="data/cmapss/api_latency_benchmark.csv")
    parser.add_argument("--report-output", default="data/cmapss/api_latency_benchmark.md")
    args = parser.parse_args()

    asset_ids = [f"INJ-{index:02d}" for index in range(1, 9)]
    mode = "http"
    for index in range(args.warmup):
        try:
            _predict_http(args.url, asset_ids[index % len(asset_ids)])
        except OSError:
            mode = "direct_predictor_fallback"
            predict_rul(asset_ids[index % len(asset_ids)])

    rows = []
    for index in range(args.iterations):
        asset_id = asset_ids[index % len(asset_ids)]
        start = time.perf_counter()
        if mode == "http":
            payload = _predict_http(args.url, asset_id)
            status_code = 200
        else:
            payload = predict_rul(asset_id).model_dump(mode="json")
            status_code = 200
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        rows.append(
            {
                "iteration": index + 1,
                "asset_id": asset_id,
                "status_code": status_code,
                "latency_ms": elapsed_ms,
                "rul_hours": payload.get("rul_hours"),
                "risk_72h": payload.get("risk_72h"),
                "model_version": payload.get("model_version"),
                "rul_source": payload.get("rul_source"),
                "mode": mode,
            }
        )

    frame = pd.DataFrame(rows)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(output, index=False, encoding="utf-8-sig")

    latencies = frame["latency_ms"].tolist()
    summary = {
        "iterations": len(latencies),
        "mean_ms": statistics.fmean(latencies),
        "median_ms": statistics.median(latencies),
        "p95_ms": _percentile(latencies, 95),
        "p99_ms": _percentile(latencies, 99),
        "max_ms": max(latencies),
        "min_ms": min(latencies),
        "success_count": int((frame["status_code"] == 200).sum()),
        "mode": mode,
    }
    report = Path(args.report_output)
    report.write_text(_make_report(summary, output), encoding="utf-8")

    print("[API latency benchmark]")
    for key, value in summary.items():
        if key.endswith("_ms"):
            print(f"{key}={value:.3f}")
        else:
            print(f"{key}={value}")
    print(f"csv={output}")
    print(f"report={report}")


def _percentile(values: list[float], percentile: float) -> float:
    sorted_values = sorted(values)
    if not sorted_values:
        return 0.0
    index = (len(sorted_values) - 1) * percentile / 100.0
    lower = int(index)
    upper = min(lower + 1, len(sorted_values) - 1)
    fraction = index - lower
    return sorted_values[lower] * (1.0 - fraction) + sorted_values[upper] * fraction


def _predict_http(url: str, asset_id: str) -> dict[str, object]:
    data = json.dumps({"asset_id": asset_id}).encode("utf-8")
    req = request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with request.urlopen(req, timeout=10) as response:
            if response.status != 200:
                raise RuntimeError(f"HTTP {response.status}: {response.read().decode('utf-8', errors='replace')}")
            return json.loads(response.read().decode("utf-8"))
    except error.URLError as exc:
        raise OSError(str(exc)) from exc


def _make_report(summary: dict[str, float], csv_path: Path) -> str:
    return "\n".join(
        [
            "# API Inference Latency Benchmark",
            "",
            "| Metric | Value |",
            "|---|---:|",
            f"| Iterations | {int(summary['iterations'])} |",
            f"| Success Count | {int(summary['success_count'])} |",
            f"| Mode | {summary['mode']} |",
            f"| Mean latency ms | {summary['mean_ms']:.3f} |",
            f"| Median latency ms | {summary['median_ms']:.3f} |",
            f"| P95 latency ms | {summary['p95_ms']:.3f} |",
            f"| P99 latency ms | {summary['p99_ms']:.3f} |",
            f"| Max latency ms | {summary['max_ms']:.3f} |",
            f"| Min latency ms | {summary['min_ms']:.3f} |",
            "",
            f"CSV: `{csv_path}`",
            "",
            "Note: Mode `http` measures the running local FastAPI server over localhost. If the server is unavailable, the script falls back to direct predictor calls.",
            "",
        ]
    )


if __name__ == "__main__":
    main()
