from __future__ import annotations

import math
from typing import Any, Mapping, Sequence

import numpy as np

from .convergence import (
    STATUS_CONVERGING,
    STATUS_NOT_CONVERGED,
    STATUS_PROJECTED_PLATEAU,
    STATUS_PRIORITY,
)
from .graphs import checkpoint_to_edits


DEFAULT_MILESTONES: tuple[float, ...] = (0.50, 0.80, 0.90, 0.95, 0.99)

BASIS_PLATEAU_SIGNAL = "plateau_signal"
BASIS_MONOTONE_TAIL = "monotone_tail"


def milestone_label(fraction: float) -> str:
    return f"{int(round(fraction * 100))}%"


def _sort_key(item: dict[str, Any]) -> tuple[float, float, str]:
    return (
        STATUS_PRIORITY[item["status"]],
        math.inf if item["behavior_edit"] is None else float(item["behavior_edit"]),
        item["invariant"],
    )


def sort_projection_results(results: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(results, key=_sort_key)


def _build_series(checkpoints: Mapping[str, int], values_by_checkpoint: Mapping[str, float]) -> tuple[np.ndarray, np.ndarray]:
    checkpoint_lookup = sorted(checkpoints, key=lambda x: x["edits"])
    checkpoint_labels, checkpoint_edits = zip(*((x["label"], x["edits"]) for x in checkpoint_lookup))
    x = np.array(checkpoint_edits, dtype=float)
    y = np.array([float(values_by_checkpoint[label]) for label in list(checkpoint_labels)], dtype=float)
    return x, y


def _tail_mask(x: np.ndarray, behavior_edit: float | None, *, minimum_points: int = 4) -> np.ndarray:
    if x.size == 0:
        return np.zeros(0, dtype=bool)
    if behavior_edit is None:
        start = max(0, x.size - minimum_points)
        mask = np.zeros(x.size, dtype=bool)
        mask[start:] = True
        return mask
    mask = x >= float(behavior_edit) - 1e-9
    if int(mask.sum()) >= minimum_points:
        return mask
    start = max(0, x.size - minimum_points)
    fallback = np.zeros(x.size, dtype=bool)
    fallback[start:] = True
    return fallback


def _infer_direction_sign(direction: str | None, y: np.ndarray, final_hint: float | None = None) -> int:
    if direction == "increasing":
        return 1
    if direction == "decreasing":
        return -1
    if final_hint is not None:
        delta = float(final_hint) - float(y[0])
        if delta > 0:
            return 1
        if delta < 0:
            return -1
    delta = float(y[-1] - y[0])
    if delta > 0:
        return 1
    if delta < 0:
        return -1
    return 0


def _median_spacing(x: np.ndarray) -> float | None:
    if x.size <= 1:
        return None
    return float(np.median(np.diff(x)))


def _tail_center(y_tail: np.ndarray, center_hint: float | None) -> float | None:
    if center_hint is not None and math.isfinite(center_hint):
        return float(center_hint)
    if y_tail.size == 0:
        return None
    return float(np.median(y_tail))


def _estimate_decay_ratio(steps: np.ndarray, tol: float) -> float | None:
    if steps.size < 2:
        return None
    ratios = [
        float(next_step / prev_step)
        for prev_step, next_step in zip(steps[:-1], steps[1:])
        if prev_step > tol and 0.0 < next_step < prev_step * 4.0
    ]
    ratios = [ratio for ratio in ratios if 0.0 < ratio < 1.0]
    if not ratios:
        return None
    ratio = float(np.median(ratios[-min(4, len(ratios)) :]))
    return min(max(ratio, 0.05), 0.95)


def _aitken_limit_candidates(z_tail: np.ndarray, tol: float) -> list[float]:
    if z_tail.size < 3:
        return []
    step_scale = float(
        np.median(np.abs(np.diff(z_tail[-min(5, z_tail.size) :])))
    ) if z_tail.size > 1 else tol
    total_change = max(float(z_tail[-1] - z_tail[0]), tol)
    upper_bound = float(z_tail[-1] + max(12.0 * step_scale, 2.0 * total_change, tol))
    lower_bound = float(z_tail[-1] + tol)

    candidates: list[float] = []
    start = max(2, z_tail.size - 6)
    for idx in range(start, z_tail.size):
        a, b, c = (float(z_tail[idx - 2]), float(z_tail[idx - 1]), float(z_tail[idx]))
        delta = c - b
        curvature = c - 2.0 * b + a
        if abs(delta) <= tol or abs(curvature) <= tol:
            continue
        candidate = c - (delta * delta) / curvature
        if lower_bound <= candidate <= upper_bound:
            candidates.append(candidate)
    return candidates


def _estimate_monotone_limit(
    x: np.ndarray,
    y: np.ndarray,
    *,
    direction: str | None,
    behavior_edit: float | None,
) -> dict[str, float | None]:
    mask = _tail_mask(x, behavior_edit)
    x_tail = x[mask]
    y_tail = y[mask]
    sign = _infer_direction_sign(direction, y_tail if y_tail.size else y)
    if sign == 0 or y_tail.size < 3:
        return {
            "final_value": None,
            "decay_ratio": None,
            "residual": None,
            "tail_step": None,
            "step_spacing": _median_spacing(x),
            "tail_points": float(y_tail.size),
        }

    z_tail = sign * y_tail
    tol = max(float(np.ptp(z_tail)) * 1e-9, 1e-12)
    steps = np.diff(z_tail)
    positive_steps = steps[steps > tol]
    if positive_steps.size == 0:
        return {
            "final_value": None,
            "decay_ratio": None,
            "residual": None,
            "tail_step": None,
            "step_spacing": _median_spacing(x_tail),
            "tail_points": float(y_tail.size),
        }

    last_step = float(positive_steps[-1])
    step_scale = float(np.median(positive_steps[-min(4, positive_steps.size) :]))
    total_change = max(float(z_tail[-1] - z_tail[0]), tol)
    lower_bound = float(z_tail[-1] + max(0.5 * last_step, tol))
    upper_bound = float(z_tail[-1] + max(12.0 * step_scale, 2.0 * total_change, tol))

    decay_ratio = _estimate_decay_ratio(positive_steps, tol)
    candidates = _aitken_limit_candidates(z_tail, tol)
    if decay_ratio is not None:
        residual = last_step * decay_ratio / max(1.0 - decay_ratio, 1e-9)
        candidates.append(float(z_tail[-1] + residual))

    filtered = [candidate for candidate in candidates if lower_bound <= candidate <= upper_bound]
    if filtered:
        z_limit = float(np.median(filtered))
    elif candidates:
        z_limit = float(min(max(np.median(candidates), lower_bound), upper_bound))
    else:
        fallback_ratio = 0.5 if decay_ratio is None else decay_ratio
        z_limit = float(z_tail[-1] + last_step * fallback_ratio / max(1.0 - fallback_ratio, 1e-9))
        z_limit = min(max(z_limit, lower_bound), upper_bound)

    residual = float(max(z_limit - z_tail[-1], 0.0))
    effective_ratio = decay_ratio
    if effective_ratio is None and residual > 0.0:
        effective_ratio = float(min(max(residual / max(residual + last_step, tol), 0.05), 0.95))

    return {
        "final_value": float(sign * z_limit),
        "decay_ratio": effective_ratio,
        "residual": residual,
        "tail_step": last_step,
        "step_spacing": _median_spacing(x_tail),
        "tail_points": float(y_tail.size),
    }


def _progress_series(y: np.ndarray, final_value: float | None) -> tuple[np.ndarray, float]:
    if final_value is None:
        return np.full(y.shape, np.nan, dtype=float), 0.0
    total_delta = float(final_value - y[0])
    if abs(total_delta) <= 1e-12:
        return np.full(y.shape, np.nan, dtype=float), 0.0
    progress = (y - float(y[0])) / total_delta
    return progress.astype(float), total_delta


def _observed_milestone_edit(x: np.ndarray, progress: np.ndarray, milestone: float) -> float | None:
    clipped = np.clip(progress.astype(float), 0.0, 1.0)
    for idx, value in enumerate(clipped):
        if not math.isfinite(float(value)):
            continue
        if value + 1e-12 < milestone:
            continue
        if idx == 0:
            return float(x[0])
        prev_value = float(clipped[idx - 1])
        curr_value = float(value)
        if curr_value > prev_value + 1e-12:
            frac = (milestone - prev_value) / (curr_value - prev_value)
            return float(x[idx - 1] + frac * (x[idx] - x[idx - 1]))
        return float(x[idx])
    return None


def _project_future_milestone_edit(
    x: np.ndarray,
    y: np.ndarray,
    *,
    final_value: float | None,
    milestone: float,
    basis: str | None,
    decay_ratio: float | None,
    step_spacing: float | None,
) -> float | None:
    if final_value is None or step_spacing is None or step_spacing <= 0.0:
        return None
    progress, total_delta = _progress_series(y, final_value)
    if total_delta == 0.0 or basis != BASIS_MONOTONE_TAIL:
        return None

    current_progress = float(progress[-1])
    if current_progress >= milestone - 1e-12:
        return float(x[-1])

    current_residual = abs(float(final_value - y[-1]))
    target_residual = abs((1.0 - milestone) * total_delta)
    if current_residual <= target_residual + 1e-12:
        return float(x[-1])
    if target_residual <= 0.0:
        return float(x[-1])

    if decay_ratio is not None and 0.0 < decay_ratio < 1.0:
        steps_needed = math.log(target_residual / current_residual) / math.log(decay_ratio)
        return float(x[-1] + max(0.0, steps_needed) * step_spacing)

    tail_step = abs(float(y[-1] - y[-2])) if y.size > 1 else 0.0
    if tail_step <= 1e-12:
        return None
    edits_needed = (current_residual - target_residual) / tail_step
    return float(x[-1] + max(0.0, edits_needed) * step_spacing)


def _milestone_edits(
    x: np.ndarray,
    y: np.ndarray,
    *,
    final_value: float | None,
    basis: str | None,
    decay_ratio: float | None,
    step_spacing: float | None,
    milestones: Sequence[float],
) -> tuple[dict[str, float | None], dict[str, str]]:
    progress, _ = _progress_series(y, final_value)
    edits: dict[str, float | None] = {}
    sources: dict[str, str] = {}
    for milestone in milestones:
        label = milestone_label(milestone)
        observed = _observed_milestone_edit(x, progress, milestone)
        if observed is not None:
            edits[label] = observed
            sources[label] = "observed"
            continue
        projected = _project_future_milestone_edit(
            x,
            y,
            final_value=final_value,
            milestone=milestone,
            basis=basis,
            decay_ratio=decay_ratio,
            step_spacing=step_spacing,
        )
        edits[label] = projected
        sources[label] = "projected" if projected is not None else "unavailable"
    return edits, sources


def project_invariant_trajectory(
    invariant: str,
    values_by_checkpoint: Mapping[str, float],
    convergence_entry: Mapping[str, Any] | None,
    checkpoints: Mapping[str, int],
    *,
    milestones: Sequence[float] = DEFAULT_MILESTONES,
) -> dict[str, Any]:
    x, y = _build_series(checkpoints, values_by_checkpoint)
    if x.size < 2:
        return {
            "invariant": invariant,
            "x": x,
            "y": y,
            "status": STATUS_NOT_CONVERGED,
            "behavior_edit": None,
            "direction": None,
            "basis": None,
            "predicted_final": None,
            "milestone_edits": {milestone_label(fraction): None for fraction in milestones},
            "milestone_sources": {
                milestone_label(fraction): "unavailable" for fraction in milestones
            },
            "projection": {
                "decay_ratio": None,
                "tail_step": None,
                "step_spacing": _median_spacing(x),
                "residual": None,
            },
        }

    entry = dict(convergence_entry or {})
    status = entry.get("status", STATUS_NOT_CONVERGED)
    behavior_edit = entry.get("behavior_edit")
    direction = entry.get("direction")
    predicted_final: float | None = None
    basis: str | None = None
    projection = {
        "decay_ratio": None,
        "tail_step": None,
        "step_spacing": _median_spacing(x),
        "residual": None,
    }

    if status == STATUS_PROJECTED_PLATEAU:
        mask = _tail_mask(x, behavior_edit)
        predicted_final = _tail_center(y[mask], entry.get("tail_center"))
        basis = BASIS_PLATEAU_SIGNAL if predicted_final is not None else None
    elif status == STATUS_CONVERGING:
        estimate = _estimate_monotone_limit(
            x,
            y,
            direction=direction,
            behavior_edit=behavior_edit,
        )
        predicted_final = estimate["final_value"]
        if predicted_final is not None:
            basis = BASIS_MONOTONE_TAIL
        projection = {
            "decay_ratio": estimate["decay_ratio"],
            "tail_step": estimate["tail_step"],
            "step_spacing": estimate["step_spacing"],
            "residual": estimate["residual"],
        }

    milestone_edits, milestone_sources = _milestone_edits(
        x,
        y,
        final_value=predicted_final,
        basis=basis,
        decay_ratio=projection["decay_ratio"],
        step_spacing=projection["step_spacing"],
        milestones=milestones,
    )

    return {
        "invariant": invariant,
        "x": x,
        "y": y,
        "status": status,
        "behavior_edit": behavior_edit,
        "direction": direction,
        "basis": basis,
        "predicted_final": predicted_final,
        "milestone_edits": milestone_edits,
        "milestone_sources": milestone_sources,
        "projection": projection,
    }


def build_projection_results(
    invariants_per_graph: Mapping[str, Mapping[str, float]],
    convergence_payload: Mapping[str, Any],
    checkpoints: Mapping[str, int],
    *,
    milestones: Sequence[float] = DEFAULT_MILESTONES,
) -> list[dict[str, Any]]:
    entries = {
        entry["invariant"]: entry
        for entry in convergence_payload.get("invariants", [])
    }
    results = [
        project_invariant_trajectory(
            invariant,
            values_by_checkpoint,
            entries.get(invariant),
            checkpoints=checkpoints,
            milestones=milestones,
        )
        for invariant, values_by_checkpoint in invariants_per_graph.items()
    ]
    return sort_projection_results(results)


__all__ = [
    "DEFAULT_MILESTONES",
    "BASIS_PLATEAU_SIGNAL",
    "BASIS_MONOTONE_TAIL",
    "milestone_label",
    "sort_projection_results",
    "project_invariant_trajectory",
    "build_projection_results",
]
