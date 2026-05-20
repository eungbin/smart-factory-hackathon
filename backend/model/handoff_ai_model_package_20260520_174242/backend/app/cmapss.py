from __future__ import annotations

import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd
import requests

CMAPSS_URL = "https://data.nasa.gov/docs/legacy/CMAPSSData.zip"
SUBSETS = ("FD001", "FD002", "FD003", "FD004")
SENSOR_COLUMNS = [
    "T2",
    "T24",
    "T30",
    "T50",
    "P2",
    "P15",
    "P30",
    "Nf",
    "Nc",
    "epr",
    "Ps30",
    "phi",
    "NRf",
    "NRc",
    "BPR",
    "farB",
    "htBleed",
    "Nf_dmd",
    "PCNfR_dmd",
    "W31",
    "W32",
]
SETTING_COLUMNS = ["operational_setting_1", "operational_setting_2", "operational_setting_3"]
BASE_COLUMNS = ["unit", "cycle", *SETTING_COLUMNS, *SENSOR_COLUMNS]
NASA_EXPECTED_COUNTS = {
    "FD001": {"train": 100, "test": 100},
    "FD002": {"train": 260, "test": 259},
    "FD003": {"train": 100, "test": 100},
    "FD004": {"train": 248, "test": 249},
}


@dataclass(frozen=True)
class CountValidation:
    subset: str
    split: str
    expected_units: int
    actual_units: int
    matches_nasa_readme: bool
    note: str


def download_cmapss(data_dir: Path) -> Path:
    data_dir.mkdir(parents=True, exist_ok=True)
    zip_path = data_dir / "CMAPSSData.zip"
    if zip_path.exists():
        return zip_path
    response = requests.get(CMAPSS_URL, timeout=60)
    response.raise_for_status()
    zip_path.write_bytes(response.content)
    return zip_path


def load_split(
    data_dir: Path,
    subset: Literal["FD001", "FD002", "FD003", "FD004"] = "FD001",
    split: Literal["train", "test"] = "train",
) -> pd.DataFrame:
    zip_path = download_cmapss(data_dir)
    file_name = f"{split}_{subset}.txt"
    with zipfile.ZipFile(zip_path) as archive:
        with archive.open(file_name) as handle:
            frame = pd.read_csv(handle, sep=r"\s+", header=None, names=BASE_COLUMNS)
    return frame


def load_test_rul(
    data_dir: Path,
    subset: Literal["FD001", "FD002", "FD003", "FD004"] = "FD001",
) -> pd.Series:
    zip_path = download_cmapss(data_dir)
    with zipfile.ZipFile(zip_path) as archive:
        with archive.open(f"RUL_{subset}.txt") as handle:
            frame = pd.read_csv(handle, sep=r"\s+", header=None, names=["rul"])
    return frame["rul"]


def add_train_rul(frame: pd.DataFrame, cap: int | None = 125) -> pd.DataFrame:
    result = frame.copy()
    max_cycle = result.groupby("unit")["cycle"].transform("max")
    result["rul"] = max_cycle - result["cycle"]
    if cap is not None:
        result["rul"] = result["rul"].clip(upper=cap)
    return result


def validate_unit_leakage(train_frame: pd.DataFrame, test_frame: pd.DataFrame) -> bool:
    train_units = set(train_frame["unit"].astype(int).unique())
    test_units = set(test_frame["unit"].astype(int).unique())
    return train_units.isdisjoint(test_units)


def validate_subset_counts(data_dir: Path, subset: str) -> list[CountValidation]:
    validations: list[CountValidation] = []
    for split in ("train", "test"):
        frame = load_split(data_dir, subset=subset, split=split)  # type: ignore[arg-type]
        actual = int(frame["unit"].nunique())
        expected = NASA_EXPECTED_COUNTS[subset][split]
        matches = actual == expected
        note = "NASA README count matches the downloaded ZIP."
        if subset == "FD004" and not matches:
            note = "FD004 appears swapped against NASA README counts in the downloaded ZIP; keep this in loader logs."
        elif not matches:
            note = "Downloaded ZIP unit count differs from NASA README."
        validations.append(
            CountValidation(
                subset=subset,
                split=split,
                expected_units=expected,
                actual_units=actual,
                matches_nasa_readme=matches,
                note=note,
            )
        )
    return validations


def build_sliding_windows(
    frame: pd.DataFrame,
    window_size: int = 50,
    feature_columns: list[str] | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    features = feature_columns or [*SETTING_COLUMNS, *SENSOR_COLUMNS]
    if "rul" not in frame.columns:
        frame = add_train_rul(frame)
    windows: list[np.ndarray] = []
    labels: list[float] = []
    units: list[int] = []
    for unit, unit_frame in frame.groupby("unit"):
        unit_frame = unit_frame.sort_values("cycle")
        values = unit_frame[features].to_numpy(dtype=np.float32)
        rul_values = unit_frame["rul"].to_numpy(dtype=np.float32)
        for end in range(window_size, len(unit_frame) + 1):
            windows.append(values[end - window_size : end])
            labels.append(float(rul_values[end - 1]))
            units.append(int(unit))
    return np.stack(windows), np.asarray(labels, dtype=np.float32), np.asarray(units, dtype=np.int32)


def rmse(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.sqrt(np.mean((y_pred - y_true) ** 2)))


def phm_score(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    diff = y_pred - y_true
    score = 0.0
    for value in diff:
        if value < 0:
            score += np.exp(-value / 13.0) - 1.0
        else:
            score += np.exp(value / 10.0) - 1.0
    return float(score)
