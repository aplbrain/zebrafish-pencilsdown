from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any, Iterable, Literal, Sequence, Mapping

import matplotlib.pyplot as plt
import numpy as np

from .convergence import (
    PLOT_EXCLUDE,
    STATUS_CONVERGING,
    STATUS_NOT_CONVERGED,
    STATUS_PROJECTED_PLATEAU,
    sort_results,
)
from .projections import (
    BASIS_MONOTONE_TAIL,
    BASIS_PLATEAU_SIGNAL,
    milestone_label,
    sort_projection_results,
)


def configure_matplotlib() -> None:
    plt.rcParams["svg.fonttype"] = "none"
    plt.rcParams["pdf.fonttype"] = 42
    plt.rcParams["ps.fonttype"] = 42
    # plt.rcParams["font.family"] = "Roboto"
    plt.rcParams["font.size"] = 10
    plt.rcParams["figure.dpi"] = 150


def chunked(iterable: Iterable[Any], size: int) -> Iterable[list[Any]]:
    chunk: list[Any] = []
    for item in iterable:
        chunk.append(item)
        if len(chunk) == size:
            yield chunk
            chunk = []
    if chunk:
        yield chunk


def _format_scalar(value: float | None) -> str:
    if value is None or math.isinf(value) or math.isnan(value):
        return "--"
    return f"{value:.6g}"


def format_edit(
    value: float | None,
    *,
    lang: Literal["markdown", "latex"] = "markdown",
) -> str:
    if value is None or math.isinf(value) or math.isnan(value):
        return "--"
    text = f"{value:,.0f}"
    if lang == "markdown":
        return text
    if lang == "latex":
        return text
    raise ValueError(f"Unknown language: {lang}")


def _status_label(status: str) -> str:
    if status == STATUS_PROJECTED_PLATEAU:
        return "projects plateau"
    if status == STATUS_CONVERGING:
        return "converging"
    if status == STATUS_NOT_CONVERGED:
        return "not converged"
    raise ValueError(f"Unknown status: {status}")


def _basis_label(basis: str | None) -> str:
    if basis == BASIS_PLATEAU_SIGNAL:
        return "plateau signal"
    if basis == BASIS_MONOTONE_TAIL:
        return "monotone tail"
    return "--"


def summarize_behavior(
    results: Sequence[dict[str, Any]],
) -> dict[str, dict[str, float | int | None | str]]:
    total = len(results)
    summary: dict[str, dict[str, float | int | None | str]] = {}
    for status in (STATUS_PROJECTED_PLATEAU, STATUS_CONVERGING, STATUS_NOT_CONVERGED):
        edits = [
            float(result["behavior_edit"])
            for result in results
            if result["status"] == status and result["behavior_edit"] is not None
        ]
        count = sum(1 for result in results if result["status"] == status)
        if edits:
            mean = float(np.mean(edits))
            std = float(np.std(edits))
            formatted = f"{mean:,.0f} ± {std:,.0f}"
        else:
            mean = None
            std = None
            formatted = "--"
        summary[status] = {
            "count": count,
            "total": total,
            "mean_edit": mean,
            "std_edit": std,
            "formatted": formatted,
        }
    return summary


def build_convergence_summary_lines(
    results: Sequence[dict[str, Any]],
    *,
    lang: Literal["markdown", "latex"] = "markdown",
) -> list[str]:
    if lang == "markdown":
        lines = [
            "| Invariant | Status | Since | Direction | Tail band | Tail drift | Tail step | Step decay | Sign consistency |",
            "| --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: |",
        ]
        for result in sort_results(results):
            plateau = result["plateau"]
            monotone = result["monotone"]
            lines.append(
                "| {inv} | {status} | {since} | {direction} | {band} | {drift} | {step} | {ratio} | {sign} |".format(
                    inv=result["invariant"],
                    status=_status_label(result["status"]),
                    since=format_edit(result["behavior_edit"], lang=lang),
                    direction=result["direction"] or "--",
                    band=_format_scalar(plateau["band"]),
                    drift=_format_scalar(plateau["drift"]),
                    step=_format_scalar(monotone["mean_abs_step"]),
                    ratio=_format_scalar(monotone["step_ratio"]),
                    sign=_format_scalar(monotone["sign_fraction"]),
                )
            )
        return lines

    if lang == "latex":
        lines = [
            r"\begin{tabular}{l|l|r|l|rrrrr}",
            r"Invariant & Status & Since & Direction & Tail band & Tail drift & Tail step & Step decay & Sign consistency \\",
            r"\hline",
        ]
        for result in sort_results(results):
            plateau = result["plateau"]
            monotone = result["monotone"]
            lines.append(
                r"{inv} & {status} & {since} & {direction} & {band} & {drift} & {step} & {ratio} & {sign} \\".format(
                    inv=result["invariant"].replace("_", r"\_"),
                    status=_status_label(result["status"]).replace("_", r"\_"),
                    since=format_edit(result["behavior_edit"], lang=lang),
                    direction=(result["direction"] or "--").replace("_", r"\_"),
                    band=_format_scalar(plateau["band"]),
                    drift=_format_scalar(plateau["drift"]),
                    step=_format_scalar(monotone["mean_abs_step"]),
                    ratio=_format_scalar(monotone["step_ratio"]),
                    sign=_format_scalar(monotone["sign_fraction"]),
                )
            )
        lines.append(r"\end{tabular}")
        return lines

    raise ValueError(f"Unknown language: {lang}")


def convergence_stats_payload(
    dataset: str,
    results: Sequence[dict[str, Any]],
) -> dict[str, Any]:
    summary = summarize_behavior(results)
    return {
        "dataset": dataset,
        "behavior_summary": summary,
        "invariants": [
            {
                "invariant": result["invariant"],
                "status": result["status"],
                "behavior_edit": result["behavior_edit"],
                "direction": result["direction"],
                "plateau_edit": result["plateau"]["edit"],
                "tail_center": result["plateau"]["center"],
                "tail_band": result["plateau"]["band"],
                "tail_drift": result["plateau"]["drift"],
                "tail_step": result["monotone"]["mean_abs_step"],
                "step_decay": result["monotone"]["step_ratio"],
                "step_relative": result["monotone"]["step_relative"],
                "sign_consistency": result["monotone"]["sign_fraction"],
            }
            for result in sort_results(results)
        ],
    }


def summarize_projection_results(
    results: Sequence[dict[str, Any]],
) -> dict[str, dict[str, float | int | None | str]]:
    total = len(results)
    summary: dict[str, dict[str, float | int | None | str]] = {}
    for basis in (BASIS_PLATEAU_SIGNAL, BASIS_MONOTONE_TAIL, None):
        finals = [
            float(result["predicted_final"])
            for result in results
            if result["basis"] == basis and result["predicted_final"] is not None
        ]
        count = sum(1 for result in results if result["basis"] == basis)
        if finals:
            mean = float(np.mean(finals))
            std = float(np.std(finals))
            formatted = f"{mean:.6g} ± {std:.3g}"
        else:
            mean = None
            std = None
            formatted = "--"
        key = "unprojected" if basis is None else basis
        summary[key] = {
            "count": count,
            "total": total,
            "mean_final": mean,
            "std_final": std,
            "formatted": formatted,
        }
    return summary


def summarize_projection_milestones(
    results: Sequence[dict[str, Any]],
    milestones: Sequence[float],
) -> dict[str, dict[str, float | int | None | str]]:
    summary: dict[str, dict[str, float | int | None | str]] = {}
    for fraction in milestones:
        label = milestone_label(fraction)
        values = [
            float(result["milestone_edits"][label])
            for result in results
            if result["milestone_edits"].get(label) is not None
        ]
        if values:
            mean = float(np.mean(values))
            std = float(np.std(values))
            count = len(values)
        else:
            mean = None
            std = None
            count = 0
        summary[label] = {
            "count": count,
            "mean_edit": mean,
            "std_edit": std,
        }
    return summary


def _projection_table_rows(
    results: Sequence[dict[str, Any]],
    milestones: Sequence[float],
    *,
    lang: Literal["markdown", "latex"] = "markdown",
) -> list[list[str]]:
    rows = [
        [
            result["invariant"],
            _basis_label(result["basis"]),
            _format_scalar(result["predicted_final"]),
            *[
                format_edit(
                    result["milestone_edits"][milestone_label(fraction)],
                    lang=lang,
                )
                for fraction in milestones
            ],
        ]
        for result in sort_projection_results(results)
    ]

    milestone_summary = summarize_projection_milestones(results, milestones)
    rows.append(
        [
            "Mean edits",
            "--",
            "--",
            *[
                format_edit(milestone_summary[milestone_label(fraction)]["mean_edit"], lang=lang)
                for fraction in milestones
            ],
        ]
    )
    rows.append(
        [
            "Std edits",
            "--",
            "--",
            *[
                format_edit(milestone_summary[milestone_label(fraction)]["std_edit"], lang=lang)
                for fraction in milestones
            ],
        ]
    )
    return rows


def build_projection_summary_lines(
    results: Sequence[dict[str, Any]],
    milestones: Sequence[float],
    *,
    lang: Literal["markdown", "latex"] = "markdown",
) -> list[str]:
    milestone_headers = [f"{milestone_label(fraction)} edits" for fraction in milestones]
    if lang == "markdown":
        header = ["Invariant", "Projection basis", "Final value", *milestone_headers]
        lines = [
            "| " + " | ".join(header) + " |",
            "| " + " | ".join(["---", "---", "---:"] + ["---:"] * len(milestones)) + " |",
        ]
        for row in _projection_table_rows(results, milestones, lang=lang):
            lines.append("| " + " | ".join(row) + " |")
        return lines

    if lang == "latex":
        columns = "l|l|r|" + "r" * len(milestones)
        lines = [
            rf"\begin{{tabular}}{{{columns}}}",
            " & ".join(
                ["Invariant", "Projection basis", "Final value", *milestone_headers]
            )
            + r" \\",
            r"\hline",
        ]
        rows = _projection_table_rows(results, milestones, lang=lang)
        for row_index, row in enumerate(rows):
            if row_index == len(rows) - 2:
                lines.append(r"\hline")
            row = [
                cell.replace("_", r"\_") if idx < 2 else cell
                for idx, cell in enumerate(row)
            ]
            lines.append(" & ".join(row) + r" \\")
        lines.append(r"\end{tabular}")
        return lines

    raise ValueError(f"Unknown language: {lang}")


def build_projection_summary_csv_rows(
    results: Sequence[dict[str, Any]],
    milestones: Sequence[float],
) -> list[list[str]]:
    header = ["Invariant", "Projection basis", "Final value"] + [
        f"{milestone_label(fraction)} edits" for fraction in milestones
    ]
    return [header, *_projection_table_rows(results, milestones, lang="markdown")]


def _format_k_edits(value: float) -> str:
    if not math.isfinite(value):
        return "--"
    if abs(value) >= 1000.0:
        return f"{value / 1000.0:.1f}K"
    return f"{value:.0f}"


def projection_stats_payload(
    dataset: str,
    results: Sequence[dict[str, Any]],
    milestones: Sequence[float],
) -> dict[str, Any]:
    summary = summarize_projection_results(results)
    return {
        "dataset": dataset,
        "milestones": [milestone_label(fraction) for fraction in milestones],
        "projection_summary": summary,
        "milestone_summary": summarize_projection_milestones(results, milestones),
        "invariants": [
            {
                "invariant": result["invariant"],
                "status": result["status"],
                "behavior_edit": result["behavior_edit"],
                "direction": result["direction"],
                "basis": result["basis"],
                "predicted_final": result["predicted_final"],
                "projection_decay_ratio": result["projection"]["decay_ratio"],
                "projection_tail_step": result["projection"]["tail_step"],
                "projection_step_spacing": result["projection"]["step_spacing"],
                "projection_residual": result["projection"]["residual"],
                "milestone_edits": result["milestone_edits"],
                "milestone_sources": result["milestone_sources"],
            }
            for result in sort_projection_results(results)
        ],
    }


def write_text_lines(path: Path, lines: Sequence[str]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def write_json(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def write_csv_rows(path: Path, rows: Sequence[Sequence[str]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerows(rows)
    return path


def render_projection_milestone_bands(
    dataset: str,
    results: Sequence[dict[str, Any]],
    output_dir: Path,
    *,
    milestones: Sequence[float],
    formats: Sequence[str] = ("svg", "pdf"),
) -> list[Path]:
    configure_matplotlib()
    output_dir.mkdir(parents=True, exist_ok=True)

    projected_results = [
        result
        for result in sort_projection_results(results)
        if result["basis"] is not None
    ]
    if not projected_results:
        return []

    milestone_labels = [milestone_label(fraction) for fraction in milestones]
    x_positions = np.array([fraction * 100.0 for fraction in milestones], dtype=float)
    milestone_summary = summarize_projection_milestones(projected_results, milestones)
    mean_values = np.array(
        [
            np.nan
            if milestone_summary[label]["mean_edit"] is None
            else float(milestone_summary[label]["mean_edit"])
            for label in milestone_labels
        ],
        dtype=float,
    )
    std_values = np.array(
        [
            0.0
            if milestone_summary[label]["std_edit"] is None
            else float(milestone_summary[label]["std_edit"])
            for label in milestone_labels
        ],
        dtype=float,
    )

    fig, ax = plt.subplots(figsize=(8.5, 5.0))

    basis_colors = {
        BASIS_MONOTONE_TAIL: "#2c7fb8",
        BASIS_PLATEAU_SIGNAL: "#d95f02",
    }
    for result in projected_results:
        y_values = np.array(
            [
                np.nan
                if result["milestone_edits"][label] is None
                else float(result["milestone_edits"][label])
                for label in milestone_labels
            ],
            dtype=float,
        )
        valid = np.isfinite(y_values)
        if not np.any(valid):
            continue
        ax.plot(
            x_positions[valid],
            y_values[valid],
            color=basis_colors[result["basis"]],
            linewidth=1.1,
            alpha=0.35,
            marker="o",
            markersize=3.5,
        )

    valid_mean = np.isfinite(mean_values)
    if not np.any(valid_mean):
        plt.close(fig)
        return []

    lower = np.maximum(mean_values - std_values, 0.0)
    upper = mean_values + std_values
    ax.fill_between(
        x_positions[valid_mean],
        lower[valid_mean],
        upper[valid_mean],
        color="#4daf4a",
        alpha=0.18,
        label="Mean ± 1 SD",
    )
    ax.errorbar(
        x_positions[valid_mean],
        mean_values[valid_mean],
        yerr=std_values[valid_mean],
        color="#1b1b1b",
        linewidth=2.0,
        marker="o",
        markersize=5.5,
        capsize=4,
        label="Mean edit",
    )

    for x_value, mean_value, std_value in zip(
        x_positions[valid_mean],
        mean_values[valid_mean],
        std_values[valid_mean],
    ):
        ax.annotate(
            _format_k_edits(mean_value),
            (x_value, mean_value + std_value),
            textcoords="offset points",
            xytext=(0, 10),
            ha="center",
            va="bottom",
            fontsize=8,
            color="#1b1b1b",
            bbox={
                "boxstyle": "round,pad=0.18",
                "facecolor": "white",
                "edgecolor": "none",
                "alpha": 0.9,
            },
        )

    ax.set_title(f"{dataset.title()} Projection Milestones")
    ax.set_xlabel("Percent of projected final value")
    ax.set_ylabel("Edits")
    ax.set_xticks(x_positions)
    ax.set_xticklabels([f"{int(value)}%" for value in x_positions])

    y_ticks = ax.get_yticks()
    ax.set_yticks(y_ticks)
    ax.set_yticklabels([_format_k_edits(value) for value in y_ticks])
    ax.grid(True, axis="y", linestyle=":", linewidth=0.7)
    ax.legend(frameon=False, loc="upper left")
    ax.text(
        0.98,
        0.02,
        f"Projected invariants: {len(projected_results)}",
        transform=ax.transAxes,
        ha="right",
        va="bottom",
        fontsize=8,
        color="#444444",
    )
    fig.tight_layout()

    stem = output_dir / "projection-milestone-bands"
    output_paths: list[Path] = []
    for fmt in formats:
        path = stem.with_suffix(f".{fmt}")
        fig.savefig(path, bbox_inches="tight")
        output_paths.append(path)
    plt.close(fig)
    return output_paths


def render_convergence_grids(
    results: Sequence[dict[str, Any]],
    checkpoints: Mapping[str, int],
    output_dir: Path,
    *,
    plot_exclude: frozenset[str] = PLOT_EXCLUDE,
    cols: int = 5,
    formats: Sequence[str] = ("svg", "pdf"),
) -> list[Path]:
    configure_matplotlib()
    output_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_labels, checkpoint_edits = zip(*checkpoints.items())

    sorted_results = [
        result
        for result in sort_results(results)
        if result["invariant"] not in plot_exclude
    ]
    if not sorted_results:
        return []

    max_observed = max(float(result["x"].max()) for result in sorted_results)
    # xtick_positions = np.arange(0.0, max_observed + 1e-9, 10_000.0)
    # if xtick_positions.size == 0 or xtick_positions[-1] != max_observed:
    #     xtick_positions = np.append(xtick_positions, max_observed)
    xtick_positions = checkpoint_edits
    # xtick_labels = [f"{int(pos / 1000)}K" for pos in xtick_positions]
    xtick_labels = checkpoint_edits
    plateau_color = "#1b9e77"
    converging_color = "#d95f02"
    neutral_color = "#666666"
    series_color = "#2c7fb8"

    group_size = cols * max(1, int(np.ceil(len(sorted_results) / cols)))
    output_paths: list[Path] = []

    for group_index, group in enumerate(chunked(sorted_results, group_size), start=1):
        rows = max(1, int(np.ceil(len(group) / cols)))
        fig, axes = plt.subplots(rows, cols, figsize=(10, 1.8 * rows), sharex=True)
        axes = np.array(axes).reshape(-1)

        for ax, result in zip(axes, group):
            x = result["x"]
            y = result["y"]
            plateau = result["plateau"]
            status = result["status"]
            behavior_edit = result["behavior_edit"]

            ax.plot(x, y, color=series_color, linewidth=1.2, marker="o", markersize=3.5)

            if status == STATUS_PROJECTED_PLATEAU and behavior_edit is not None:
                ax.axvspan(behavior_edit, float(x.max()), color=plateau_color, alpha=0.08)
                ax.axvline(behavior_edit, color=plateau_color, linewidth=1.5)
                center = plateau["center"]
                band = plateau["band"]
                if center is not None and band is not None:
                    ax.fill_between(
                        [behavior_edit, float(x.max())],
                        [center - band, center - band],
                        [center + band, center + band],
                        color=plateau_color,
                        alpha=0.12,
                    )
                    ax.plot(
                        [behavior_edit, float(x.max())],
                        [center, center],
                        color=plateau_color,
                        linewidth=1.2,
                    )
            elif status == STATUS_CONVERGING and behavior_edit is not None:
                tail_mask = x >= behavior_edit
                ax.axvspan(behavior_edit, float(x.max()), color=converging_color, alpha=0.08)
                ax.axvline(behavior_edit, color=converging_color, linewidth=1.5)
                ax.plot(
                    x[tail_mask],
                    y[tail_mask],
                    color=converging_color,
                    linewidth=1.6,
                    marker="o",
                    markersize=3.5,
                )

            ax.set_title(result["invariant"])
            ax.set_xlim(0, max_observed)
            ax.set_xticks(xtick_positions)
            ax.set_xticklabels(xtick_labels, rotation=90)
            ax.tick_params(axis="y", labelrotation=45)

            label = _status_label(status)
            if behavior_edit is not None:
                label = f"{label}: {int(behavior_edit / 1000)}K"
            color = (
                plateau_color
                if status == STATUS_PROJECTED_PLATEAU
                else converging_color
                if status == STATUS_CONVERGING
                else neutral_color
            )
            ax.text(
                0.02,
                0.98,
                label,
                transform=ax.transAxes,
                ha="left",
                va="top",
                fontsize=7,
                color=color,
            )

        for ax in axes:
            ax.grid(True, linestyle=":", linewidth=0.5)
        for ax in axes[len(group) :]:
            ax.axis("off")

        fig.tight_layout(rect=(0, 0, 1, 1))
        stem = output_dir / f"convergence-grid-{group_index:02d}"
        for fmt in formats:
            output_path = stem.with_suffix(f".{fmt}")
            fig.savefig(output_path, bbox_inches="tight")
            output_paths.append(output_path)
        plt.close(fig)

    return output_paths

__all__ = [
    "PLOT_EXCLUDE",
    "configure_matplotlib",
    "chunked",
    "format_edit",
    "summarize_behavior",
    "build_convergence_summary_lines",
    "convergence_stats_payload",
    "summarize_projection_results",
    "summarize_projection_milestones",
    "build_projection_summary_lines",
    "build_projection_summary_csv_rows",
    "projection_stats_payload",
    "write_text_lines",
    "write_json",
    "write_csv_rows",
    "render_convergence_grids",
    "render_projection_milestone_bands",
]
