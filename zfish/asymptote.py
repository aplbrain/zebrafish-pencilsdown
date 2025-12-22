from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, Iterable, Literal, Mapping, Sequence

import numpy as np

# Common configuration for the asymptote fitting notebooks
PROGRESS_LEVELS: tuple[float, ...] = (0.50, 0.80, 0.90, 0.95, 0.99)
PLOT_EXCLUDE: frozenset[str] = frozenset({"density"})
BIC_TOLERANCE = 1.5
LIMIT_PREFERENCE_DELTA = 3


@dataclass
class ModelSpec:
    name: str
    feature_fns: tuple[Callable[[np.ndarray], np.ndarray], ...]
    description: str
    has_limit: bool


def make_inv_power(power: float) -> Callable[[np.ndarray], np.ndarray]:
    def transform(n: np.ndarray) -> np.ndarray:
        return n.astype(float) ** (-power)

    return transform


def make_exp_decay(tau: float) -> Callable[[np.ndarray], np.ndarray]:
    def transform(n: np.ndarray) -> np.ndarray:
        return np.exp(-(n.astype(float)) / tau)

    return transform


def make_monomial(power: float) -> Callable[[np.ndarray], np.ndarray]:
    def transform(n: np.ndarray) -> np.ndarray:
        return n.astype(float) ** power

    return transform


DEFAULT_MODEL_SPECS: tuple[ModelSpec, ...] = (
    ModelSpec(
        name="Constant",
        feature_fns=tuple(),
        description="y = L",
        has_limit=True,
    ),
    ModelSpec(
        name="Poly-Linear",
        feature_fns=(make_monomial(1.0),),
        description="y = a + b (n+delta)",
        has_limit=False,
    ),
    ModelSpec(
        name="Inverse-Linear",
        feature_fns=(make_inv_power(1.0),),
        description="y = L + a/(n+delta)",
        has_limit=True,
    ),
    ModelSpec(
        name="Inverse-Square",
        feature_fns=(make_inv_power(2.0),),
        description="y = L + a/(n+delta)^2",
        has_limit=True,
    ),
    ModelSpec(
        name="Inverse-Cubic",
        feature_fns=(make_inv_power(3.0),),
        description="y = L + a/(n+delta)^3",
        has_limit=True,
    ),
    ModelSpec(
        name="Inverse-Quartic",
        feature_fns=(make_inv_power(4.0),),
        description="y = L + a/(n+delta)^4",
        has_limit=True,
    ),
    *tuple(
        ModelSpec(
            name=f"Exp-{int(tau / 1000)}k",
            feature_fns=(make_exp_decay(tau),),
            description=f"y = L + a * exp(-(n+delta)/{int(tau)})",
            has_limit=True,
        )
        for tau in (5000.0, 10000.0, 20000.0)
    ),
)

SPEC_PRIORITY: dict[str, int] = {
    "Constant": 0,
    "Poly-Linear": 1,
    "Inverse-Linear": 2,
    "Inverse-Square": 3,
    "Inverse-Cubic": 4,
    "Inverse-Quartic": 5,
    "Exp-5k": 6,
    "Exp-10k": 7,
    "Exp-20k": 8,
}


def checkpoint_to_edits(label: str) -> int:
    """Convert a checkpoint label into an edit count.

    Args:
        label: Checkpoint label like "5k" or "5000".

    Returns:
        The edit count as an integer.
    """
    clean = label.strip().lower()
    if clean.endswith("k"):
        return int(clean[:-1]) * 1000
    return int(clean)


def compute_checkpoint_metadata(
    invariants_per_graph: Mapping[str, Mapping[str, float]],
) -> tuple[list[str], np.ndarray, dict[str, float], float]:
    """Derive checkpoint labels, numeric edits, lookup, and default shift.

    Args:
        invariants_per_graph: Mapping of invariant name to checkpoint values.

    Returns:
        A tuple containing the ordered checkpoint labels, the numeric edits
        array, a label-to-edits lookup, and the default shift value.
    """
    reference_invariant = next(iter(invariants_per_graph))
    checkpoint_labels = sorted(
        invariants_per_graph[reference_invariant].keys(),
        key=checkpoint_to_edits,
    )
    checkpoint_edits = np.array(
        [checkpoint_to_edits(label) for label in checkpoint_labels],
        dtype=float,
    )
    checkpoint_lookup = dict(zip(checkpoint_labels, checkpoint_edits))
    unique_edits = np.unique(checkpoint_edits)
    positive_gaps = np.diff(unique_edits)
    positive_gaps = positive_gaps[positive_gaps > 0]
    default_shift = float(positive_gaps.min() / 2) if positive_gaps.size else 1.0
    return checkpoint_labels, checkpoint_edits, checkpoint_lookup, default_shift


def build_design_matrix(
    x_edits: np.ndarray, spec: ModelSpec, shift: float
) -> np.ndarray:
    n_eff = x_edits.astype(float) + shift
    columns = [np.ones_like(n_eff)]
    for fn in spec.feature_fns:
        columns.append(fn(n_eff))
    return np.column_stack(columns)


def is_monotonic(values: np.ndarray, tol: float = 1e-9) -> bool:
    diffs = np.diff(values)
    return bool((diffs >= -tol).all()) or bool((diffs <= tol).all())


def fit_model(
    x_edits: np.ndarray,
    values: np.ndarray,
    spec: ModelSpec,
    shift: float,
) -> dict:
    """Fit a linearized model and compute diagnostics.

    Args:
        x_edits: Edit counts for the observations.
        values: Observed invariant values.
        spec: Model specification for the design matrix.
        shift: Positive shift added to edits for stability.

    Returns:
        A dict containing the fit parameters, predictions, residuals, and
        summary statistics like BIC/AIC.
    """
    X = build_design_matrix(x_edits, spec, shift)
    params, _, _, _ = np.linalg.lstsq(X, values, rcond=None)
    fitted = X @ params
    residuals = values - fitted
    sse = float(np.sum(residuals**2))
    n_obs = len(values)
    n_params = X.shape[1]
    dof = max(n_obs - n_params, 1)
    mse = sse / dof
    bic = n_obs * math.log(mse + 1e-12) + n_params * math.log(n_obs)
    aic = n_obs * math.log((sse / n_obs) + 1e-12) + 2 * n_params
    valid = is_monotonic(fitted)
    return {
        "spec": spec,
        "params": params,
        "fitted": fitted,
        "residuals": residuals,
        "sse": sse,
        "bic": bic,
        "aic": aic,
        "shift": shift,
        "n_obs": n_obs,
        "valid": valid,
    }


def select_best_fit(candidate_fits: list[dict]) -> dict:
    """Select the best fit using BIC and tie-breaker rules.

    Args:
        candidate_fits: Fits produced by ``fit_model`` for one invariant.

    Returns:
        The selected best-fit dict.
    """
    ordered = sorted(
        candidate_fits,
        key=lambda item: (
            item["bic"],
            SPEC_PRIORITY.get(item["spec"].name, 99),
        ),
    )
    best = ordered[0]
    if best["spec"].name.startswith("Exp-"):
        alternatives = [
            fit
            for fit in ordered
            if not fit["spec"].name.startswith("Exp-")
            and fit["bic"] - best["bic"] <= BIC_TOLERANCE
        ]
        if alternatives:
            best = alternatives[0]
    if not best["spec"].has_limit:
        limit_candidates = [
            fit
            for fit in ordered
            if fit["spec"].has_limit
            and fit["bic"] - best["bic"] <= LIMIT_PREFERENCE_DELTA
        ]
        if limit_candidates:
            best = limit_candidates[0]
    return best


def predict_from_fit(x_edits: np.ndarray, fit: dict) -> np.ndarray:
    """Predict invariant values from a fit dict.

    Args:
        x_edits: Edit counts to evaluate.
        fit: Fit dict returned by ``fit_model``.

    Returns:
        Predicted values for each edit count.
    """
    X = build_design_matrix(x_edits, fit["spec"], fit["shift"])
    return X @ fit["params"]


def get_limit_value(fit: dict) -> float | None:
    """Return the asymptote value for a fit, if defined.

    Args:
        fit: Fit dict returned by ``fit_model``.

    Returns:
        The limit value (L) if the model has a limit; otherwise ``None``.
    """
    if not fit["spec"].has_limit:
        return None
    return float(fit["params"][0])


def estimate_progress_edit(
    result: dict,
    fraction: float,
    limit_value: float | None,
    max_multiplier: float = 10.0,
    points: int = 2000,
) -> float | None:
    """Estimate the edit count at a given fraction of the asymptote.

    Args:
        result: One entry from ``fit_invariants`` results.
        fraction: Fraction of the asymptote to reach (0-1).
        limit_value: Asymptote value for the best fit.
        max_multiplier: Expansion factor when extending the search range.
        points: Number of grid points per search iteration.

    Returns:
        Estimated edit count where the fit reaches the target fraction, or
        ``None`` when it cannot be determined.
    """
    if limit_value is None:
        return None
    start_value = result["y"][0]
    if math.isclose(start_value, limit_value, rel_tol=1e-9, abs_tol=1e-9):
        return None
    target_value = start_value + (limit_value - start_value) * fraction
    direction = 1 if limit_value > start_value else -1
    x_data = result["x"]
    x_min = float(x_data.min())
    x_max = float(x_data.max())
    current_max = x_max
    for _ in range(12):
        x_grid = np.linspace(x_min, current_max, points)
        y_grid = predict_from_fit(x_grid, result["best_fit"])
        if direction > 0:
            mask = y_grid >= target_value - 1e-9
        else:
            mask = y_grid <= target_value + 1e-9
        if np.any(mask):
            idx = int(np.where(mask)[0][0])
            return float(x_grid[idx])
        current_max *= max_multiplier
    return None


def fit_invariants(
    invariants_per_graph: Mapping[str, Mapping[str, float]],
    checkpoint_labels: Sequence[str],
    checkpoint_lookup: Mapping[str, float],
    model_specs: Sequence[ModelSpec],
    shift: float,
) -> tuple[list[dict], list[str]]:
    """Fit models for each invariant across checkpoints.

    Args:
        invariants_per_graph: Invariant values by checkpoint label.
        checkpoint_labels: Ordered checkpoint labels to consider.
        checkpoint_lookup: Mapping from label to numeric edit count.
        model_specs: Candidate model specifications.
        shift: Positive shift added to edits for stability.

    Returns:
        A tuple of (fit_results, skipped_invariants).
    """
    fit_results: list[dict] = []
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
        candidate_fits: list[dict] = []
        for spec in model_specs:
            fit = fit_model(x_arr, y_arr, spec, shift)
            if not fit["valid"]:
                continue
            candidate_fits.append(fit)
        if not candidate_fits:
            skipped.append(invariant_name)
            continue
        best_fit = select_best_fit(candidate_fits)
        fit_results.append(
            {
                "invariant": invariant_name,
                "x": x_arr,
                "y": y_arr,
                "best_fit": best_fit,
                "candidate_fits": candidate_fits,
            }
        )
    return fit_results, skipped


def format_progress(
    value: float | None,
    italic: bool = False,
    lang: Literal["markdown", "latex"] = "markdown",
) -> str:
    """Format a progress milestone for table output.

    Args:
        value: Numeric edit count or ``None``.
        italic: Whether to italicize the output (markdown/latex only).
        lang: Output format, either "markdown" or "latex".

    Returns:
        A formatted string for the milestone cell.

    Raises:
        ValueError: If ``lang`` is not supported.
    """
    if value is None or math.isinf(value) or math.isnan(value):
        return "—"
    text = f"{value:,.0f}"
    if lang == "markdown":
        return f"_{text}_" if italic else text
    elif lang == "latex":
        return f"\\textit{{{text}}}" if italic else text
    else:
        raise ValueError(f"Unknown language: {lang}")


def build_summary_lines(
    fit_results: Sequence[dict],
    progress_levels: Iterable[float] = PROGRESS_LEVELS,
    lang: Literal["markdown", "latex"] = "markdown",
) -> list[str]:
    """Build summary table lines for fitted invariants.

    Args:
        fit_results: Results returned by ``fit_invariants``.
        progress_levels: Fractions of the asymptote to report.
        lang: Output format, either "markdown" or "latex".

    Returns:
        Table lines suitable for the chosen output format.

    Raises:
        ValueError: If ``lang`` is not supported.
    """
    if lang == "markdown":
        summary_lines = [
            "| Invariant | Best model | Asymptote (L) | 50% edits | 80% edits | 90% edits | 95% edits | 99% edits |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
        for result in sorted(fit_results, key=lambda item: item["invariant"]):
            best = result["best_fit"]
            limit_value = get_limit_value(best)
            asymptote_text = f"{limit_value:.6g}" if limit_value is not None else "—"
            milestones = []
            last_observed = result["x"].max()
            for level in progress_levels:
                edit_value = estimate_progress_edit(result, level, limit_value)
                italic = edit_value is not None and edit_value <= last_observed + 1e-9
                milestones.append(format_progress(edit_value, italic=italic, lang=lang))

            summary_lines.append(
                "| {inv} | {model} | {asym} | {p50} | {p80} | {p90} | {p95} | {p99} |".format(
                    inv=result["invariant"],
                    model=best["spec"].name,
                    asym=asymptote_text,
                    p50=milestones[0],
                    p80=milestones[1],
                    p90=milestones[2],
                    p95=milestones[3],
                    p99=milestones[4],
                )
            )
        return summary_lines
    elif lang == "latex":
        summary_lines = [
            r"\begin{tabular}{l|l|r|rrrrr}",
            r"Invariant & Best model & Asymptote (L) & 50\% edits & 80\% edits & 90\% edits & 95\% edits & 99\% edits \\",
            r"\hline",
        ]
        for result in sorted(fit_results, key=lambda item: item["invariant"]):
            best = result["best_fit"]
            limit_value = get_limit_value(best)
            asymptote_text = f"{limit_value:.6g}" if limit_value is not None else "—"
            milestones = []
            last_observed = result["x"].max()
            for level in progress_levels:
                edit_value = estimate_progress_edit(result, level, limit_value)
                italic = edit_value is not None and edit_value <= last_observed + 1e-9
                milestones.append(format_progress(edit_value, italic=italic, lang=lang))

            summary_lines.append(
                r"{inv} & {model} & {asym} & {p50} & {p80} & {p90} & {p95} & {p99} \\".format(
                    inv=result["invariant"].replace("_", r"\_"),
                    model=best["spec"].name,
                    asym=asymptote_text,
                    p50=milestones[0],
                    p80=milestones[1],
                    p90=milestones[2],
                    p95=milestones[3],
                    p99=milestones[4],
                )
            )
        summary_lines.append(r"\end{tabular}")
        return summary_lines
    else:
        raise ValueError(f"Unknown language: {lang}")


def average_milestones(
    fit_results: Sequence[dict],
    progress_levels: Iterable[float] = PROGRESS_LEVELS,
) -> tuple[dict[float, float | None], dict[float, float | None], dict[float, str]]:
    """Compute mean and std of milestone edits across invariants.

    Args:
        fit_results: Results returned by ``fit_invariants``.
        progress_levels: Fractions of the asymptote to summarize.

    Returns:
        Tuple of (means, stds, formatted_strings) keyed by progress level.
    """
    milestone_values: dict[float, list[float]] = {
        level: [] for level in progress_levels
    }
    average_means: dict[float, float | None] = {}
    average_stds: dict[float, float | None] = {}
    for result in fit_results:
        best = result["best_fit"]
        limit_value = get_limit_value(best)
        for level in progress_levels:
            edit_value = estimate_progress_edit(result, level, limit_value)
            if edit_value is not None:
                milestone_values[level].append(edit_value)
    for level in progress_levels:
        values = milestone_values[level]
        if values:
            avg = float(np.mean(values))
            std = float(np.std(values))
            average_means[level] = avg
            average_stds[level] = std
        else:
            average_means[level] = None
            average_stds[level] = None
    average_milestones_formatted: dict[float, str] = {}
    for level in progress_levels:
        avg = average_means[level]
        std = average_stds[level]
        if avg is None:
            average_milestones_formatted[level] = "—"
        else:
            average_milestones_formatted[level] = f"{avg:,.0f} ± {std:,.0f}"
    return average_means, average_stds, average_milestones_formatted


def chunked(iterable: Iterable, size: int) -> Iterable[list]:
    """Yield lists of a fixed size from an iterable.

    Args:
        iterable: Input sequence or iterator.
        size: Number of items per chunk.

    Yields:
        Lists of up to ``size`` items, with the final chunk possibly shorter.
    """
    chunk = []
    for item in iterable:
        chunk.append(item)
        if len(chunk) == size:
            yield chunk
            chunk = []
    if chunk:
        yield chunk


__all__ = [
    "PROGRESS_LEVELS",
    "PLOT_EXCLUDE",
    "BIC_TOLERANCE",
    "LIMIT_PREFERENCE_DELTA",
    "ModelSpec",
    "DEFAULT_MODEL_SPECS",
    "checkpoint_to_edits",
    "compute_checkpoint_metadata",
    "fit_model",
    "select_best_fit",
    "predict_from_fit",
    "get_limit_value",
    "estimate_progress_edit",
    "fit_invariants",
    "format_progress",
    "build_summary_lines",
    "average_milestones",
    "chunked",
]
