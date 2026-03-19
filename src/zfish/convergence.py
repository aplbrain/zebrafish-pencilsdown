from __future__ import annotations

import math
from typing import Any, Mapping, Sequence

import numpy as np

from .graphs import checkpoint_to_edits


PLOT_EXCLUDE: frozenset[str] = frozenset({"density"})

PLATEAU_MIN_POINTS = 4
PLATEAU_BAND_REL = 0.03
PLATEAU_DRIFT_REL = 0.01
PLATEAU_CONTRAST_MIN = 4.0

MONOTONE_MIN_POINTS = 5
MONOTONE_STEP_RATIO_MAX = 0.65
MONOTONE_STEP_REL_MAX = 0.08
MONOTONE_SIGN_FRACTION_MIN = 1.0

STATUS_PROJECTED_PLATEAU = "projected_plateau"
STATUS_CONVERGING = "converging"
STATUS_NOT_CONVERGED = "not_converged"

STATUS_PRIORITY = {
    STATUS_PROJECTED_PLATEAU: 0,
    STATUS_CONVERGING: 1,
    STATUS_NOT_CONVERGED: 2,
}


def compute_checkpoint_metadata(
    invariants_per_graph: Mapping[str, Mapping[str, float]],
) -> tuple[list[str], np.ndarray, dict[str, float]]:
    checkpoint_labels = sorted(
        {
            checkpoint
            for values_by_checkpoint in invariants_per_graph.values()
            for checkpoint in values_by_checkpoint
        },
        key=checkpoint_to_edits,
    )
    checkpoint_edits = np.array(
        [checkpoint_to_edits(label) for label in checkpoint_labels], dtype=float
    )
    checkpoint_lookup = dict(zip(checkpoint_labels, checkpoint_edits))
    return checkpoint_labels, checkpoint_edits, checkpoint_lookup


def _series_scale(values: np.ndarray) -> float:
    if values.size == 0:
        return 1.0
    return max(float(np.ptp(values)), 1e-12)


def _tail_drift(x_edits: np.ndarray, values: np.ndarray) -> float:
    if x_edits.size <= 1 or np.allclose(x_edits, x_edits[0]):
        return 0.0
    slope, _ = np.polyfit(x_edits, values, deg=1)
    return float(abs(slope) * (x_edits[-1] - x_edits[0]))


def _mean_abs_diff(values: np.ndarray) -> float:
    if values.size <= 1:
        return 0.0
    return float(np.mean(np.abs(np.diff(values))))


def _direction_stats(
    diffs: np.ndarray,
    *,
    tol: float,
) -> tuple[str | None, float]:
    significant = diffs[np.abs(diffs) > tol]
    if significant.size == 0:
        return None, 0.0
    pos = int(np.sum(significant > 0))
    neg = int(np.sum(significant < 0))
    if pos >= neg:
        return "increasing", pos / significant.size
    return "decreasing", neg / significant.size


def estimate_plateau(
    x_edits: np.ndarray,
    values: np.ndarray,
    *,
    min_points: int = PLATEAU_MIN_POINTS,
    band_rel: float = PLATEAU_BAND_REL,
    band_abs: float = 0.0,
    drift_rel: float = PLATEAU_DRIFT_REL,
    drift_abs: float = 0.0,
    contrast_min: float = PLATEAU_CONTRAST_MIN,
    center: str = "median",
) -> dict[str, float | int | None]:
    if x_edits.shape != values.shape:
        raise ValueError("x_edits and values must have matching shapes")
    if min_points < 2:
        raise ValueError("min_points must be at least 2")
    if center not in {"mean", "median"}:
        raise ValueError(f"Unknown center method: {center}")
    if contrast_min <= 0:
        raise ValueError("contrast_min must be greater than zero")

    n_obs = int(values.size)
    scale = _series_scale(values)
    if n_obs < min_points:
        return {
            "edit": None,
            "center": None,
            "band": None,
            "drift": None,
            "prior_excursion": None,
            "contrast": None,
            "scale": scale,
            "band_threshold": None,
            "drift_threshold": None,
            "tail_points": 0,
        }

    band_threshold = max(float(band_abs), float(band_rel) * scale)
    drift_threshold = max(float(drift_abs), float(drift_rel) * scale)

    for start in range(1, n_obs - min_points + 1):
        tail_x = x_edits[start:].astype(float)
        tail_y = values[start:].astype(float)
        center_value = (
            float(np.mean(tail_y)) if center == "mean" else float(np.median(tail_y))
        )
        band_value = float(np.max(np.abs(tail_y - center_value)))
        drift_value = _tail_drift(tail_x, tail_y)
        prior_y = values[:start].astype(float)
        prior_excursion = float(np.max(np.abs(prior_y - center_value)))
        tail_noise = max(band_value, drift_value, 1e-12)
        contrast_value = prior_excursion / tail_noise
        if (
            band_value <= band_threshold
            and drift_value <= drift_threshold
            and contrast_value >= contrast_min
        ):
            return {
                "edit": float(tail_x[0]),
                "center": center_value,
                "band": band_value,
                "drift": drift_value,
                "prior_excursion": prior_excursion,
                "contrast": contrast_value,
                "scale": scale,
                "band_threshold": band_threshold,
                "drift_threshold": drift_threshold,
                "tail_points": int(tail_x.size),
            }

    tail_x = x_edits[-min_points:].astype(float)
    tail_y = values[-min_points:].astype(float)
    center_value = (
        float(np.mean(tail_y)) if center == "mean" else float(np.median(tail_y))
    )
    band_value = float(np.max(np.abs(tail_y - center_value)))
    drift_value = _tail_drift(tail_x, tail_y)
    prior_excursion = float(np.max(np.abs(values[:-min_points] - center_value))) if n_obs > min_points else 0.0
    tail_noise = max(band_value, drift_value, 1e-12)
    contrast_value = prior_excursion / tail_noise if prior_excursion > 0 else 0.0
    return {
        "edit": None,
        "center": center_value,
        "band": band_value,
        "drift": drift_value,
        "prior_excursion": prior_excursion,
        "contrast": contrast_value,
        "scale": scale,
        "band_threshold": band_threshold,
        "drift_threshold": drift_threshold,
        "tail_points": int(tail_x.size),
    }


def estimate_monotone_convergence(
    x_edits: np.ndarray,
    values: np.ndarray,
    *,
    min_points: int = MONOTONE_MIN_POINTS,
    step_ratio_max: float = MONOTONE_STEP_RATIO_MAX,
    step_rel_max: float = MONOTONE_STEP_REL_MAX,
    sign_fraction_min: float = MONOTONE_SIGN_FRACTION_MIN,
) -> dict[str, float | int | None | str]:
    if x_edits.shape != values.shape:
        raise ValueError("x_edits and values must have matching shapes")
    if min_points < 3:
        raise ValueError("min_points must be at least 3")
    if not 0 < sign_fraction_min <= 1:
        raise ValueError("sign_fraction_min must be in (0, 1]")
    if step_ratio_max <= 0 or step_rel_max <= 0:
        raise ValueError("step thresholds must be greater than zero")

    n_obs = int(values.size)
    scale = _series_scale(values)
    diffs = np.diff(values.astype(float))
    if n_obs < min_points or diffs.size == 0:
        return {
            "edit": None,
            "direction": None,
            "sign_fraction": None,
            "mean_abs_step": None,
            "early_step": None,
            "step_ratio": None,
            "step_relative": None,
            "tail_points": 0,
            "scale": scale,
            "step_ratio_threshold": step_ratio_max,
            "step_relative_threshold": step_rel_max,
            "sign_fraction_threshold": sign_fraction_min,
        }

    initial_count = min(max(min_points - 1, 1), diffs.size)
    early_step = float(np.mean(np.abs(diffs[:initial_count])))
    tol = max(scale * 1e-6, 1e-12)

    for start in range(1, n_obs - min_points + 1):
        tail_y = values[start:].astype(float)
        tail_diffs = np.diff(tail_y)
        direction, sign_fraction = _direction_stats(tail_diffs, tol=tol)
        mean_abs_step = _mean_abs_diff(tail_y)
        step_ratio = mean_abs_step / max(early_step, tol)
        step_relative = mean_abs_step / scale
        if (
            direction is not None
            and sign_fraction >= sign_fraction_min
            and step_ratio <= step_ratio_max
            and step_relative <= step_rel_max
        ):
            return {
                "edit": float(x_edits[start]),
                "direction": direction,
                "sign_fraction": sign_fraction,
                "mean_abs_step": mean_abs_step,
                "early_step": early_step,
                "step_ratio": step_ratio,
                "step_relative": step_relative,
                "tail_points": int(tail_y.size),
                "scale": scale,
                "step_ratio_threshold": step_ratio_max,
                "step_relative_threshold": step_rel_max,
                "sign_fraction_threshold": sign_fraction_min,
            }

    tail_y = values[-min_points:].astype(float)
    tail_diffs = np.diff(tail_y)
    direction, sign_fraction = _direction_stats(tail_diffs, tol=tol)
    mean_abs_step = _mean_abs_diff(tail_y)
    step_ratio = mean_abs_step / max(early_step, tol)
    step_relative = mean_abs_step / scale
    return {
        "edit": None,
        "direction": direction,
        "sign_fraction": sign_fraction,
        "mean_abs_step": mean_abs_step,
        "early_step": early_step,
        "step_ratio": step_ratio,
        "step_relative": step_relative,
        "tail_points": int(tail_y.size),
        "scale": scale,
        "step_ratio_threshold": step_ratio_max,
        "step_relative_threshold": step_rel_max,
        "sign_fraction_threshold": sign_fraction_min,
    }


def analyze_invariants(
    invariants_per_graph: Mapping[str, Mapping[str, float]],
    checkpoint_labels: Sequence[str],
    checkpoint_lookup: Mapping[str, float],
    *,
    plateau_kwargs: Mapping[str, Any] | None = None,
    monotone_kwargs: Mapping[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], list[str]]:
    results: list[dict[str, Any]] = []
    skipped: list[str] = []

    for invariant_name, values_by_checkpoint in invariants_per_graph.items():
        xs: list[float] = []
        ys: list[float] = []
        for label in checkpoint_labels:
            value = values_by_checkpoint.get(label)
            if value is None:
                continue
            xs.append(checkpoint_lookup[label])
            ys.append(value)

        x_arr = np.array(xs, dtype=float)
        y_arr = np.array(ys, dtype=float)
        if x_arr.size < 3:
            skipped.append(invariant_name)
            continue

        plateau = estimate_plateau(x_arr, y_arr, **dict(plateau_kwargs or {}))
        monotone = estimate_monotone_convergence(
            x_arr,
            y_arr,
            **dict(monotone_kwargs or {}),
        )

        if plateau["edit"] is not None:
            status = STATUS_PROJECTED_PLATEAU
            behavior_edit = plateau["edit"]
        elif monotone["edit"] is not None:
            status = STATUS_CONVERGING
            behavior_edit = monotone["edit"]
        else:
            status = STATUS_NOT_CONVERGED
            behavior_edit = None

        results.append(
            {
                "invariant": invariant_name,
                "x": x_arr,
                "y": y_arr,
                "status": status,
                "behavior_edit": behavior_edit,
                "direction": monotone["direction"],
                "plateau": plateau,
                "monotone": monotone,
            }
        )

    return results, skipped


def sort_results(results: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        results,
        key=lambda item: (
            STATUS_PRIORITY[item["status"]],
            math.inf if item["behavior_edit"] is None else float(item["behavior_edit"]),
            item["invariant"],
        ),
    )


__all__ = [
    "PLOT_EXCLUDE",
    "PLATEAU_MIN_POINTS",
    "PLATEAU_BAND_REL",
    "PLATEAU_DRIFT_REL",
    "PLATEAU_CONTRAST_MIN",
    "MONOTONE_MIN_POINTS",
    "MONOTONE_STEP_RATIO_MAX",
    "MONOTONE_STEP_REL_MAX",
    "MONOTONE_SIGN_FRACTION_MIN",
    "STATUS_PROJECTED_PLATEAU",
    "STATUS_CONVERGING",
    "STATUS_NOT_CONVERGED",
    "compute_checkpoint_metadata",
    "estimate_plateau",
    "estimate_monotone_convergence",
    "analyze_invariants",
    "sort_results",
]
