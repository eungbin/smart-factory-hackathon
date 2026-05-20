from __future__ import annotations

import csv
import io
import math
import random
import zipfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report
from sklearn.model_selection import GroupShuffleSplit, train_test_split

AIHUB_LABELS = {
    "00": "정상",
    "01": "베어링 불량",
    "02": "회전체 불평형",
    "03": "축정렬 불량",
    "04": "벨트 느슨함",
}

AIHUB_REQUIRED_COLUMNS = [
    "Date",
    "Filename",
    "Data Label",
    "Label_No",
    "Motor Spec",
    "Period",
    "Sample Rate",
    "RMS",
    "Data Length",
]


@dataclass(frozen=True)
class AIHubSummary:
    rows: int
    label_counts: dict[str, int]
    label_names: dict[str, str]
    motor_kw_values: list[float]
    sample_rate_values: list[int]
    missing_required_columns: list[str]


def load_aihub_annotations(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"AI-Hub annotation file not found: {path}")
    suffix = path.suffix.lower()
    if suffix in {".xlsx", ".xls"}:
        frame = pd.read_excel(path)
    elif suffix == ".json":
        frame = pd.read_json(path)
    elif suffix == ".jsonl":
        frame = pd.read_json(path, lines=True)
    else:
        frame = pd.read_csv(path, encoding="utf-8-sig")
    return normalize_aihub_frame(frame)


def normalize_aihub_frame(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    result.columns = [str(column).strip() for column in result.columns]
    if "Label_No" in result.columns:
        result["Label_No"] = result["Label_No"].astype(str).str.strip().str.zfill(2)
    if "RMS" in result.columns:
        result["RMS"] = pd.to_numeric(result["RMS"], errors="coerce")
    if "Data Length" in result.columns:
        result["Data Length"] = pd.to_numeric(result["Data Length"], errors="coerce")
    if "Sample Rate" in result.columns:
        result["Sample Rate"] = pd.to_numeric(result["Sample Rate"], errors="coerce")
    extracted_kw = result.get("Motor Spec", pd.Series([""] * len(result))).map(_extract_kw)
    if "motor_kw" in result.columns:
        result["motor_kw"] = pd.to_numeric(result["motor_kw"], errors="coerce").fillna(extracted_kw)
    else:
        result["motor_kw"] = extracted_kw
    extracted_asset = result.get("Filename", pd.Series(["unknown"] * len(result))).map(_asset_group)
    if "asset_group" in result.columns:
        result["asset_group"] = result["asset_group"].fillna(extracted_asset).replace("", "unknown")
    else:
        result["asset_group"] = extracted_asset
    return result


def summarize_aihub(frame: pd.DataFrame) -> AIHubSummary:
    missing = [column for column in AIHUB_REQUIRED_COLUMNS if column not in frame.columns]
    label_counts = (
        frame.get("Label_No", pd.Series(dtype=str))
        .astype(str)
        .value_counts()
        .sort_index()
        .to_dict()
    )
    motor_kw_values = sorted(
        float(value)
        for value in frame.get("motor_kw", pd.Series(dtype=float)).dropna().unique().tolist()
    )
    sample_rate_values = sorted(
        int(value)
        for value in frame.get("Sample Rate", pd.Series(dtype=float)).dropna().unique().tolist()
    )
    return AIHubSummary(
        rows=len(frame),
        label_counts={str(key): int(value) for key, value in label_counts.items()},
        label_names=AIHUB_LABELS,
        motor_kw_values=motor_kw_values,
        sample_rate_values=sample_rate_values,
        missing_required_columns=missing,
    )


def build_aihub_feature_table(
    frame: pd.DataFrame,
    include_asset_baseline_features: bool = False,
) -> tuple[pd.DataFrame, pd.Series, pd.Series]:
    required = {"RMS", "Data Length", "Sample Rate", "motor_kw", "Label_No", "asset_group"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"Missing required AI-Hub feature columns: {sorted(missing)}")
    base_columns = ["RMS", "Data Length", "Sample Rate", "motor_kw"]
    extra_columns = [
        column
        for column in frame.columns
        if column.startswith(("rms_", "current_", "vibration_", "phase_"))
        or column
        in {
            "motor_rpm",
            "motor_rated_current",
            "path_motor_kw",
            "rated_current_per_kw",
            "rms_to_rated_current",
        }
    ]
    feature_columns = list(dict.fromkeys(base_columns + extra_columns))
    features = frame[feature_columns].apply(pd.to_numeric, errors="coerce")
    features = features.dropna(axis=1, how="all")
    features = features.fillna(features.median(numeric_only=True))
    labels = frame["Label_No"].astype(str)
    groups = frame["asset_group"].astype(str)
    if include_asset_baseline_features:
        features = add_asset_baseline_features(features, labels, groups)
    return features, labels, groups


def add_asset_baseline_features(
    features: pd.DataFrame,
    labels: pd.Series,
    groups: pd.Series,
) -> pd.DataFrame:
    """Add per-asset normal-baseline deltas.

    In a factory deployment, each motor usually has a short normal-operation
    calibration period. These features express the current signal as a change
    from that asset's own normal baseline, reducing motor-size leakage.
    """
    normal_mask = labels.astype(str) == "00"
    if not normal_mask.any():
        return features
    global_baseline = features.loc[normal_mask].median(numeric_only=True)
    group_baselines = features.loc[normal_mask].groupby(groups.loc[normal_mask]).median(numeric_only=True)
    baseline = group_baselines.reindex(groups).reset_index(drop=True)
    baseline = baseline.fillna(global_baseline)
    baseline.index = features.index
    denominator = baseline.abs()
    fallback = features.abs().median(numeric_only=True).replace(0, 1.0)
    denominator = denominator.mask(denominator <= 1e-6, fallback, axis=1)
    relative = (features - baseline) / denominator
    relative = relative.replace([np.inf, -np.inf], 0.0).fillna(0.0)
    relative = relative.clip(lower=-25.0, upper=25.0)
    relative.columns = [f"asset_rel_{column}" for column in relative.columns]
    return pd.concat([features, relative], axis=1)


def find_default_aihub_current_zip(root: Path = Path("data/aihub238/downloads")) -> Path:
    matches = sorted(root.rglob("current.zip"))
    if not matches:
        raise FileNotFoundError(f"Could not find current.zip under {root}")
    return matches[0]


def find_default_aihub_vibration_zip(root: Path = Path("data/aihub238/downloads")) -> Path:
    matches = sorted(root.rglob("vibration.zip"))
    if not matches:
        raise FileNotFoundError(f"Could not find vibration.zip under {root}")
    return matches[0]


def inspect_aihub_current_zip(zip_path: Path) -> dict[str, object]:
    if not zip_path.exists():
        raise FileNotFoundError(f"AI-Hub current ZIP not found: {zip_path}")
    with zipfile.ZipFile(zip_path) as archive:
        csv_entries = [info for info in archive.infolist() if info.filename.lower().endswith(".csv")]
        path_motors: dict[str, int] = {}
        path_labels: dict[str, int] = {}
        assets: dict[str, int] = {}
        for info in csv_entries:
            parts = info.filename.split("/")
            if len(parts) >= 4:
                path_motors[parts[1]] = path_motors.get(parts[1], 0) + 1
                assets[parts[2]] = assets.get(parts[2], 0) + 1
                path_labels[parts[3]] = path_labels.get(parts[3], 0) + 1
        return {
            "zip_path": str(zip_path),
            "csv_count": len(csv_entries),
            "zip_size_bytes": zip_path.stat().st_size,
            "path_motor_counts": dict(sorted(path_motors.items())),
            "path_label_counts": path_labels,
            "asset_count": len(assets),
            "sample_members": [info.filename for info in csv_entries[:5]],
        }


def load_aihub_current_zip(
    zip_path: Path,
    max_files: int | None = 250,
    max_per_path_label: int | None = 50,
    seed: int = 42,
) -> pd.DataFrame:
    return load_aihub_signal_zip(zip_path, "current", max_files=max_files, max_per_path_label=max_per_path_label, seed=seed)


def load_aihub_vibration_zip(
    zip_path: Path,
    max_files: int | None = 250,
    max_per_path_label: int | None = 50,
    seed: int = 42,
) -> pd.DataFrame:
    return load_aihub_signal_zip(zip_path, "vibration", max_files=max_files, max_per_path_label=max_per_path_label, seed=seed)


def load_aihub_signal_zip(
    zip_path: Path,
    signal_kind: str,
    max_files: int | None = 250,
    max_per_path_label: int | None = 50,
    seed: int = 42,
) -> pd.DataFrame:
    if not zip_path.exists():
        raise FileNotFoundError(f"AI-Hub {signal_kind} ZIP not found: {zip_path}")
    with zipfile.ZipFile(zip_path) as archive:
        entries = sorted(
            [info for info in archive.infolist() if info.filename.lower().endswith(".csv")],
            key=lambda info: info.filename,
        )
        selected = _select_aihub_current_entries(entries, max_files, max_per_path_label, seed)
        records = [_read_aihub_signal_member(archive, info, signal_kind) for info in selected]
    return normalize_aihub_frame(pd.DataFrame(records))


def train_aihub_fault_classifier(frame: pd.DataFrame) -> dict:
    features, labels, groups = build_aihub_feature_table(frame)
    unique_groups = groups.nunique()
    unique_labels = labels.nunique()
    if unique_labels < 2:
        raise ValueError("Need at least two labels to train a classifier.")
    if unique_groups >= 3 and labels.value_counts().min() >= 2:
        splitter = GroupShuffleSplit(n_splits=1, test_size=0.35, random_state=42)
        train_index, test_index = next(splitter.split(features, labels, groups))
        split_name = "group"
    else:
        train_index, test_index = train_test_split(
            range(len(features)),
            test_size=0.35,
            random_state=42,
            stratify=labels if labels.value_counts().min() >= 2 else None,
        )
        split_name = "stratified"
    model = RandomForestClassifier(n_estimators=80, random_state=42, class_weight="balanced")
    model.fit(features.iloc[list(train_index)], labels.iloc[list(train_index)])
    predictions = model.predict(features.iloc[list(test_index)])
    return {
        "accuracy": float(accuracy_score(labels.iloc[list(test_index)], predictions)),
        "report": classification_report(
            labels.iloc[list(test_index)],
            predictions,
            zero_division=0,
            output_dict=True,
        ),
        "train_rows": int(len(train_index)),
        "test_rows": int(len(test_index)),
        "split": split_name,
    }


def make_sample_aihub_frame() -> pd.DataFrame:
    rows = []
    for idx, label in enumerate(["00", "01", "02", "03", "04"] * 12, start=1):
        motor_kw = [2.2, 3.7, 5.5, 7.5, 11.0][idx % 5]
        rms_base = {"00": 0.22, "01": 0.74, "02": 0.61, "03": 0.83, "04": 0.69}[label]
        rows.append(
            {
                "Date": f"2026-05-{(idx % 28) + 1:02d}",
                "Filename": f"{idx % 6:02d}_CITY Station A_Ch{idx % 10}_motor_{motor_kw}kW.csv",
                "Data Label": AIHUB_LABELS[label],
                "Label_No": label,
                "Motor Spec": f"rpm=1750, output={motor_kw}kW, current={motor_kw * 2.1:.1f}A",
                "Period": "10s",
                "Sample Rate": 25600,
                "RMS": round(rms_base + (idx % 4) * 0.015, 4),
                "Data Length": 256000,
            }
        )
    return normalize_aihub_frame(pd.DataFrame(rows))


def _select_aihub_current_entries(
    entries: list[zipfile.ZipInfo],
    max_files: int | None,
    max_per_path_label: int | None,
    seed: int,
) -> list[zipfile.ZipInfo]:
    rng = random.Random(seed)
    if max_per_path_label is None:
        selected = entries[:]
        rng.shuffle(selected)
    else:
        buckets: dict[str, list[zipfile.ZipInfo]] = {}
        for info in entries:
            parts = info.filename.split("/")
            path_label = parts[3] if len(parts) >= 4 else "unknown"
            buckets.setdefault(path_label, []).append(info)
        selected = []
        for path_label in sorted(buckets):
            members = buckets[path_label][:]
            rng.shuffle(members)
            selected.extend(members[:max_per_path_label])
        rng.shuffle(selected)
    if max_files is not None:
        selected = selected[:max_files]
    return selected


def _read_aihub_current_member(archive: zipfile.ZipFile, info: zipfile.ZipInfo) -> dict[str, object]:
    return _read_aihub_signal_member(archive, info, "current")


def _read_aihub_signal_member(archive: zipfile.ZipFile, info: zipfile.ZipInfo, signal_kind: str) -> dict[str, object]:
    metadata: dict[str, list[str]] = {}
    signal_rows: list[list[float]] = []
    with archive.open(info) as raw_file:
        text_file = io.TextIOWrapper(raw_file, encoding="utf-8-sig", newline="")
        reader = csv.reader(text_file)
        for row in reader:
            if not row:
                continue
            key = row[0].strip()
            if key in {
                "Date",
                "Filename",
                "Data Label",
                "Label No",
                "Label_No",
                "Motor Spec",
                "Period",
                "Sample Rate",
                "RMS",
                "Data Length",
            }:
                metadata[key] = [value.strip() for value in row[1:] if value.strip()]
                continue
            numeric_values = [_to_float(value) for value in row if value.strip()]
            clean_values = [float(value) for value in numeric_values if value is not None]
            if len(clean_values) >= 2:
                signal_rows.append(clean_values[:4])

    motor_values = metadata.get("Motor Spec", [])
    path_parts = info.filename.split("/")
    path_motor_kw = _extract_kw(path_parts[1]) if len(path_parts) >= 2 else None
    motor_id = motor_values[0] if motor_values else (path_parts[2] if len(path_parts) >= 3 else "unknown")
    motor_rpm = _to_float(motor_values[1]) if len(motor_values) >= 2 else None
    motor_kw = _to_float(motor_values[2]) if len(motor_values) >= 3 else path_motor_kw
    motor_current = _to_float(motor_values[3]) if len(motor_values) >= 4 else None
    data_length = _to_float(_first(metadata.get("Data Length"))) or len(signal_rows)
    sample_rate = _to_float(_first(metadata.get("Sample Rate")))
    rms_values = _numeric_values(metadata.get("RMS", []))
    signal_stats = _signal_stats(signal_rows, rms_values, sample_rate, signal_kind)
    label_no = _first(metadata.get("Label No")) or _first(metadata.get("Label_No")) or ""
    current_rms_mean = signal_stats.get("current_rms_mean") or signal_stats.get("RMS")

    return {
        "Date": _first(metadata.get("Date")),
        "Filename": _first(metadata.get("Filename")) or Path(info.filename).name,
        "Data Label": _first(metadata.get("Data Label")),
        "Label_No": str(label_no).zfill(2),
        "Motor Spec": ",".join(motor_values),
        "Period": _first(metadata.get("Period")),
        "Sample Rate": sample_rate,
        "RMS": float(np.mean(rms_values)) if rms_values else signal_stats.get("RMS"),
        "Data Length": data_length,
        "motor_id": motor_id,
        "motor_rpm": motor_rpm,
        "motor_kw": motor_kw,
        "path_motor_kw": path_motor_kw,
        "motor_rated_current": motor_current,
        "rated_current_per_kw": (
            float(motor_current) / float(motor_kw)
            if motor_current is not None and motor_kw not in {None, 0}
            else None
        ),
        "rms_to_rated_current": (
            float(current_rms_mean) / float(motor_current)
            if current_rms_mean is not None and motor_current not in {None, 0}
            else None
        ),
        "asset_group": motor_id,
        "zip_member": info.filename,
        **signal_stats,
    }


def _current_signal_stats(
    signal_rows: list[list[float]],
    metadata_rms: list[float],
    sample_rate: float | None = None,
) -> dict[str, float]:
    return _signal_stats(signal_rows, metadata_rms, sample_rate, "current")


def _signal_stats(
    signal_rows: list[list[float]],
    metadata_rms: list[float],
    sample_rate: float | None,
    signal_kind: str,
) -> dict[str, float]:
    stats: dict[str, float] = {}
    if signal_rows:
        min_width = min(len(row) for row in signal_rows)
        if min_width >= 2:
            signal = np.asarray([row[:min_width] for row in signal_rows], dtype=float)
            phases = signal[:, 1:min(min_width, 4)]
            phase_names = ["r", "s", "t"] if signal_kind == "current" else ["x", "y", "z"]
            computed_rms = []
            for index in range(phases.shape[1]):
                values = phases[:, index]
                name = phase_names[index]
                _add_signal_features(stats, f"{signal_kind}_{name}", values, sample_rate)
                rms = float(np.sqrt(np.mean(np.square(values))))
                stats[f"{signal_kind}_{name}_rms"] = rms
                computed_rms.append(rms)
            if computed_rms:
                rms_array = np.asarray(computed_rms, dtype=float)
                rms_mean = float(np.mean(rms_array))
                stats["RMS"] = rms_mean
                stats[f"{signal_kind}_rms_mean"] = rms_mean
                stats[f"{signal_kind}_rms_std"] = float(np.std(rms_array))
                stats[f"{signal_kind}_rms_min"] = float(np.min(rms_array))
                stats[f"{signal_kind}_rms_max"] = float(np.max(rms_array))
                stats[f"{signal_kind}_rms_cv"] = _safe_divide(float(np.std(rms_array)), abs(rms_mean))
                stats["phase_imbalance_rms"] = float(max(computed_rms) - min(computed_rms))
                stats["phase_imbalance_rms_pct"] = _safe_divide(stats["phase_imbalance_rms"], abs(rms_mean))
            _add_phase_relationship_features(stats, phases, signal_kind)
    if metadata_rms:
        phase_names = ["r", "s", "t"]
        for index, value in enumerate(metadata_rms[:3]):
            stats[f"rms_{phase_names[index]}"] = value
        rms_array = np.asarray(metadata_rms[:3], dtype=float)
        rms_mean = float(np.mean(rms_array))
        stats["rms_mean"] = rms_mean
        stats["rms_std"] = float(np.std(rms_array))
        stats["rms_cv"] = _safe_divide(float(np.std(rms_array)), abs(rms_mean))
        stats["phase_imbalance_rms"] = float(max(metadata_rms) - min(metadata_rms))
        stats["phase_imbalance_rms_pct"] = _safe_divide(stats["phase_imbalance_rms"], abs(rms_mean))
    return stats


def _add_signal_features(
    stats: dict[str, float],
    prefix: str,
    values: np.ndarray,
    sample_rate: float | None,
) -> None:
    clean = np.asarray(values, dtype=float)
    clean = clean[np.isfinite(clean)]
    if clean.size == 0:
        return
    mean = float(np.mean(clean))
    std = float(np.std(clean))
    abs_values = np.abs(clean)
    centered = clean - mean
    abs_mean = float(np.mean(abs_values))
    rms = float(np.sqrt(np.mean(np.square(clean))))
    q05, q25, q50, q75, q95 = np.quantile(clean, [0.05, 0.25, 0.50, 0.75, 0.95])
    peak = float(np.max(abs_values))
    diffs = np.diff(clean)
    stats[f"{prefix}_mean"] = mean
    stats[f"{prefix}_std"] = std
    stats[f"{prefix}_min"] = float(np.min(clean))
    stats[f"{prefix}_max"] = float(np.max(clean))
    stats[f"{prefix}_ptp"] = float(np.ptp(clean))
    stats[f"{prefix}_abs_mean"] = abs_mean
    stats[f"{prefix}_median"] = float(q50)
    stats[f"{prefix}_q05"] = float(q05)
    stats[f"{prefix}_q25"] = float(q25)
    stats[f"{prefix}_q75"] = float(q75)
    stats[f"{prefix}_q95"] = float(q95)
    stats[f"{prefix}_iqr"] = float(q75 - q25)
    stats[f"{prefix}_rms"] = rms
    stats[f"{prefix}_crest_factor"] = _safe_divide(peak, rms)
    stats[f"{prefix}_form_factor"] = _safe_divide(rms, abs_mean)
    stats[f"{prefix}_impulse_factor"] = _safe_divide(peak, abs_mean)
    if std > 1e-12:
        z = centered / std
        stats[f"{prefix}_skew"] = float(np.mean(np.power(z, 3)))
        stats[f"{prefix}_kurtosis"] = float(np.mean(np.power(z, 4)))
    else:
        stats[f"{prefix}_skew"] = 0.0
        stats[f"{prefix}_kurtosis"] = 0.0
    if clean.size > 1:
        stats[f"{prefix}_zero_crossing_rate"] = float(np.mean(clean[:-1] * clean[1:] < 0))
    if diffs.size:
        stats[f"{prefix}_diff_abs_mean"] = float(np.mean(np.abs(diffs)))
        stats[f"{prefix}_diff_std"] = float(np.std(diffs))
        stats[f"{prefix}_diff_max_abs"] = float(np.max(np.abs(diffs)))
    _add_frequency_features(stats, prefix, centered, sample_rate)


def _add_frequency_features(
    stats: dict[str, float],
    prefix: str,
    centered: np.ndarray,
    sample_rate: float | None,
) -> None:
    if centered.size < 8:
        return
    window = np.hanning(centered.size)
    spectrum = np.fft.rfft(centered * window)
    power = np.square(np.abs(spectrum))
    if power.size <= 1:
        return
    power = power[1:]
    total_power = float(np.sum(power))
    if total_power <= 1e-12:
        return
    if sample_rate and sample_rate > 0:
        freqs = np.fft.rfftfreq(centered.size, d=1.0 / sample_rate)[1:]
    else:
        freqs = np.linspace(0.0, 0.5, power.size, endpoint=True)
    centroid = float(np.sum(freqs * power) / total_power)
    spread = float(np.sqrt(np.sum(np.square(freqs - centroid) * power) / total_power))
    probs = power / total_power
    entropy = float(-np.sum(probs * np.log(probs + 1e-12)) / math.log(len(probs)))
    dominant_index = int(np.argmax(power))
    dominant_power = float(power[dominant_index])
    stats[f"{prefix}_spectral_centroid"] = centroid
    stats[f"{prefix}_spectral_spread"] = spread
    stats[f"{prefix}_spectral_entropy"] = entropy
    stats[f"{prefix}_dominant_freq"] = float(freqs[dominant_index])
    stats[f"{prefix}_dominant_power_ratio"] = dominant_power / total_power
    stats[f"{prefix}_low_band_ratio"] = _band_ratio(freqs, power, 0.0, 0.15, sample_rate)
    stats[f"{prefix}_mid_band_ratio"] = _band_ratio(freqs, power, 0.15, 0.35, sample_rate)
    stats[f"{prefix}_high_band_ratio"] = _band_ratio(freqs, power, 0.35, 1.0, sample_rate)
    if sample_rate and sample_rate > 0:
        stats[f"{prefix}_line_50_70hz_ratio"] = _absolute_band_ratio(freqs, power, 50.0, 70.0)
        stats[f"{prefix}_harmonic_100_140hz_ratio"] = _absolute_band_ratio(freqs, power, 100.0, 140.0)
        stats[f"{prefix}_harmonic_150_210hz_ratio"] = _absolute_band_ratio(freqs, power, 150.0, 210.0)


def _add_phase_relationship_features(stats: dict[str, float], phases: np.ndarray, signal_kind: str = "current") -> None:
    if phases.shape[1] < 2:
        return
    phase_names = ["r", "s", "t"] if signal_kind == "current" else ["x", "y", "z"]
    for left in range(phases.shape[1]):
        for right in range(left + 1, phases.shape[1]):
            a = phases[:, left]
            b = phases[:, right]
            corr = np.corrcoef(a, b)[0, 1] if np.std(a) > 1e-12 and np.std(b) > 1e-12 else 0.0
            if not np.isfinite(corr):
                corr = 0.0
            name = f"{signal_kind}_{phase_names[left]}{phase_names[right]}"
            stats[f"{name}_corr"] = float(corr)
            stats[f"{name}_diff_rms"] = float(np.sqrt(np.mean(np.square(a - b))))
            stats[f"{name}_sum_rms"] = float(np.sqrt(np.mean(np.square(a + b))))


def _band_ratio(
    freqs: np.ndarray,
    power: np.ndarray,
    low_fraction: float,
    high_fraction: float,
    sample_rate: float | None,
) -> float:
    if sample_rate and sample_rate > 0:
        nyquist = sample_rate / 2.0
        low = low_fraction * nyquist
        high = high_fraction * nyquist
    else:
        low = low_fraction * float(np.max(freqs))
        high = high_fraction * float(np.max(freqs))
    return _absolute_band_ratio(freqs, power, low, high)


def _absolute_band_ratio(freqs: np.ndarray, power: np.ndarray, low: float, high: float) -> float:
    mask = (freqs >= low) & (freqs < high)
    total = float(np.sum(power))
    if total <= 1e-12:
        return 0.0
    return float(np.sum(power[mask]) / total)


def _safe_divide(numerator: float, denominator: float) -> float:
    if abs(denominator) <= 1e-12:
        return 0.0
    return float(numerator / denominator)


def _first(values: list[str] | None) -> str:
    if not values:
        return ""
    return values[0]


def _numeric_values(values: list[str]) -> list[float]:
    return [float(value) for value in (_to_float(value) for value in values) if value is not None]


def _to_float(value: object) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _extract_kw(value: object) -> float | None:
    import re

    text = str(value)
    match = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*kW", text, re.IGNORECASE)
    if match:
        return float(match.group(1))
    match = re.search(r"output\s*=\s*([0-9]+(?:\.[0-9]+)?)", text, re.IGNORECASE)
    if match:
        return float(match.group(1))
    return None


def _asset_group(filename: object) -> str:
    text = str(filename)
    parts = text.split("_")
    if len(parts) >= 3:
        return "_".join(parts[:3])
    return text[:24] or "unknown"
