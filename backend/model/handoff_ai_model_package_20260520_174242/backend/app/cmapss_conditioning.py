from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans

from .cmapss import SENSOR_COLUMNS, SETTING_COLUMNS, SUBSETS


CONDITION_COUNTS = {
    "FD001": 1,
    "FD002": 6,
    "FD003": 1,
    "FD004": 6,
}
CONDITION_COLUMNS = [f"condition_{index}" for index in range(6)]
NORMALIZED_SENSOR_COLUMNS = [f"norm_{column}" for column in SENSOR_COLUMNS]


@dataclass(frozen=True)
class ConditionNormalizer:
    subset: str
    condition_count: int
    setting_mean: np.ndarray
    setting_scale: np.ndarray
    cluster_centers: np.ndarray
    sensor_means: dict[int, dict[str, float]]
    sensor_scales: dict[int, dict[str, float]]
    condition_counts: dict[int, int]


def fit_condition_normalizer(frame: pd.DataFrame, subset: str) -> ConditionNormalizer:
    if subset not in SUBSETS:
        raise ValueError(f"Unknown C-MAPSS subset: {subset}")
    condition_count = CONDITION_COUNTS[subset]
    settings = frame[SETTING_COLUMNS].to_numpy(dtype=np.float32)
    setting_mean = settings.mean(axis=0)
    setting_scale = settings.std(axis=0)
    setting_scale = np.where(setting_scale <= 1e-8, 1.0, setting_scale)
    scaled_settings = (settings - setting_mean) / setting_scale

    if condition_count == 1:
        condition_ids = np.zeros(len(frame), dtype=np.int32)
        cluster_centers = np.zeros((1, len(SETTING_COLUMNS)), dtype=np.float32)
    else:
        model = KMeans(n_clusters=condition_count, random_state=42, n_init=20)
        raw_ids = model.fit_predict(scaled_settings)
        order = np.lexsort(
            (
                model.cluster_centers_[:, 2],
                model.cluster_centers_[:, 1],
                model.cluster_centers_[:, 0],
            )
        )
        remap = {int(old): int(new) for new, old in enumerate(order.tolist())}
        condition_ids = np.asarray([remap[int(value)] for value in raw_ids], dtype=np.int32)
        cluster_centers = model.cluster_centers_[order].astype(np.float32)

    with_conditions = frame.copy()
    with_conditions["condition_id"] = condition_ids
    sensor_means: dict[int, dict[str, float]] = {}
    sensor_scales: dict[int, dict[str, float]] = {}
    condition_counts: dict[int, int] = {}
    global_mean = frame[SENSOR_COLUMNS].mean()
    global_scale = frame[SENSOR_COLUMNS].std().replace(0, 1.0).fillna(1.0)
    for condition in range(condition_count):
        condition_frame = with_conditions[with_conditions["condition_id"] == condition]
        condition_counts[condition] = int(len(condition_frame))
        if condition_frame.empty:
            mean = global_mean
            scale = global_scale
        else:
            mean = condition_frame[SENSOR_COLUMNS].mean()
            scale = condition_frame[SENSOR_COLUMNS].std().replace(0, 1.0).fillna(1.0)
        sensor_means[condition] = {column: float(mean[column]) for column in SENSOR_COLUMNS}
        sensor_scales[condition] = {
            column: float(scale[column]) if float(scale[column]) > 1e-8 else 1.0
            for column in SENSOR_COLUMNS
        }

    return ConditionNormalizer(
        subset=subset,
        condition_count=condition_count,
        setting_mean=setting_mean.astype(np.float32),
        setting_scale=setting_scale.astype(np.float32),
        cluster_centers=cluster_centers,
        sensor_means=sensor_means,
        sensor_scales=sensor_scales,
        condition_counts=condition_counts,
    )


def transform_with_condition_normalization(
    frame: pd.DataFrame,
    normalizer: ConditionNormalizer,
    include_raw_settings: bool = True,
) -> pd.DataFrame:
    result = frame.copy()
    condition_ids = assign_conditions(frame, normalizer)
    result["condition_id"] = condition_ids
    for column in CONDITION_COLUMNS:
        result[column] = 0.0
    for condition in range(normalizer.condition_count):
        result.loc[result["condition_id"] == condition, f"condition_{condition}"] = 1.0

    for sensor in SENSOR_COLUMNS:
        result[f"norm_{sensor}"] = 0.0
    for condition in range(normalizer.condition_count):
        mask = result["condition_id"] == condition
        means = normalizer.sensor_means.get(condition, normalizer.sensor_means[0])
        scales = normalizer.sensor_scales.get(condition, normalizer.sensor_scales[0])
        for sensor in SENSOR_COLUMNS:
            result.loc[mask, f"norm_{sensor}"] = (
                result.loc[mask, sensor] - means[sensor]
            ) / scales[sensor]

    if not include_raw_settings:
        return result
    return result


def assign_conditions(frame: pd.DataFrame, normalizer: ConditionNormalizer) -> np.ndarray:
    if normalizer.condition_count == 1:
        return np.zeros(len(frame), dtype=np.int32)
    settings = frame[SETTING_COLUMNS].to_numpy(dtype=np.float32)
    scaled_settings = (settings - normalizer.setting_mean) / normalizer.setting_scale
    distances = np.linalg.norm(
        scaled_settings[:, None, :] - normalizer.cluster_centers[None, :, :],
        axis=2,
    )
    return np.argmin(distances, axis=1).astype(np.int32)


def condition_feature_columns(include_raw_settings: bool = True) -> list[str]:
    columns = [*NORMALIZED_SENSOR_COLUMNS, *CONDITION_COLUMNS]
    if include_raw_settings:
        columns = [*SETTING_COLUMNS, *columns]
    return columns
