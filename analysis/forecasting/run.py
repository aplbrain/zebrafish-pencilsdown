from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Sequence

import matplotlib.pyplot as plt
import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from zfish.convergence import (
    MONOTONE_MIN_POINTS,
    MONOTONE_SIGN_FRACTION_MIN,
    MONOTONE_STEP_RATIO_MAX,
    MONOTONE_STEP_REL_MAX,
    PLATEAU_BAND_REL,
    PLATEAU_CONTRAST_MIN,
    PLATEAU_DRIFT_REL,
    PLATEAU_MIN_POINTS,
    analyze_invariants,
)
from zfish.invariants import DATASET_CONNECTOME, DATASET_CONTACTOME, DATASET_HEMIBRAIN
from zfish.projections import DEFAULT_MILESTONES, build_projection_results, milestone_label
from zfish.reporting import (
    build_convergence_summary_lines,
    build_projection_summary_csv_rows,
    build_projection_summary_lines,
    configure_matplotlib,
    convergence_stats_payload,
    projection_stats_payload,
    summarize_behavior,
    summarize_projection_results,
    write_csv_rows,
    write_json,
    write_text_lines,
)

DATASET_CHOICES = (DATASET_CONNECTOME, DATASET_CONTACTOME, DATASET_HEMIBRAIN)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Repeatedly trim checkpoints from the tail of one invariant trajectory JSON, "
            "rerun convergence/projection summaries, and aggregate milestone mean/std edits."
        )
    )
    parser.add_argument(
        "--dataset",
        required=True,
        choices=DATASET_CHOICES,
        help="Dataset family being summarized.",
    )
    parser.add_argument(
        "--input-json",
        type=Path,
        required=True,
        help="Invariant trajectory JSON produced by analysis/invariants/run.py.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Directory for per-iteration convergence and projection outputs.",
    )
    parser.add_argument(
        "--aggregate-csv",
        type=Path,
        required=True,
        help="CSV output path for the aggregated forecasting summary.",
    )
    parser.add_argument(
        "--aggregate-md",
        type=Path,
        required=True,
        help="Markdown output path for the aggregated forecasting summary.",
    )
    parser.add_argument(
        "--aggregate-json",
        type=Path,
        required=True,
        help="JSON output path for the aggregated forecasting summary.",
    )
    parser.add_argument(
        "--figure-dir",
        type=Path,
        required=True,
        help="Directory for forecasting figure exports.",
    )
    parser.add_argument(
        "--milestones",
        nargs="+",
        type=float,
        default=list(DEFAULT_MILESTONES),
        help="Progress milestones to report, expressed as fractions in (0, 1).",
    )
    parser.add_argument(
        "--plateau-min-points",
        type=int,
        default=PLATEAU_MIN_POINTS,
        help="Minimum number of checkpoints required in a plateau tail.",
    )
    parser.add_argument(
        "--plateau-band-rel",
        type=float,
        default=PLATEAU_BAND_REL,
        help="Relative width threshold for plateau tail banding.",
    )
    parser.add_argument(
        "--plateau-band-abs",
        type=float,
        default=0.0,
        help="Absolute width threshold for plateau tail banding.",
    )
    parser.add_argument(
        "--plateau-drift-rel",
        type=float,
        default=PLATEAU_DRIFT_REL,
        help="Relative drift threshold across the candidate plateau tail.",
    )
    parser.add_argument(
        "--plateau-drift-abs",
        type=float,
        default=0.0,
        help="Absolute drift threshold across the candidate plateau tail.",
    )
    parser.add_argument(
        "--plateau-contrast-min",
        type=float,
        default=PLATEAU_CONTRAST_MIN,
        help="Minimum early-vs-tail contrast required for plateau detection.",
    )
    parser.add_argument(
        "--plateau-center",
        choices=("mean", "median"),
        default="median",
        help="Tail center statistic used for plateau detection.",
    )
    parser.add_argument(
        "--monotone-min-points",
        type=int,
        default=MONOTONE_MIN_POINTS,
        help="Minimum number of checkpoints required in a monotone convergence tail.",
    )
    parser.add_argument(
        "--monotone-step-ratio-max",
        type=float,
        default=MONOTONE_STEP_RATIO_MAX,
        help="Maximum allowed tail-step / early-step ratio for monotone convergence.",
    )
    parser.add_argument(
        "--monotone-step-rel-max",
        type=float,
        default=MONOTONE_STEP_REL_MAX,
        help="Maximum allowed tail-step / full-range ratio for monotone convergence.",
    )
    parser.add_argument(
        "--monotone-sign-fraction-min",
        type=float,
        default=MONOTONE_SIGN_FRACTION_MIN,
        help="Minimum fraction of tail steps that must share one direction.",
    )
    return parser


def _load_invariants_payload(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if "invariants_per_graph" in payload:
        return payload
    return {
        "dataset": None,
        "metric_profile": None,
        "checkpoints": None,
        "invariants_per_graph": payload,
    }


def _validate_milestones(milestones: Sequence[float]) -> list[float]:
    clean = sorted(set(float(value) for value in milestones))
    if not clean:
        raise ValueError("At least one milestone is required.")
    for value in clean:
        if not 0.0 < value < 1.0:
            raise ValueError(f"Milestones must be in (0, 1), got {value}")
    return clean


def _build_convergence_markdown(
    dataset: str,
    results: list[dict[str, Any]],
    skipped: list[str],
) -> list[str]:
    behavior = summarize_behavior(results)
    lines = [
        f"# {dataset.title()} Convergence Summary",
        "",
        f"- Plateau-projecting invariants: {behavior['projected_plateau']['count']}/{behavior['projected_plateau']['total']}",
        f"- Mean plateau-signal edit: {behavior['projected_plateau']['formatted']}",
        f"- Monotone-converging invariants: {behavior['converging']['count']}/{behavior['converging']['total']}",
        f"- Mean monotone-convergence edit: {behavior['converging']['formatted']}",
        f"- Not converged: {behavior['not_converged']['count']}/{behavior['not_converged']['total']}",
    ]
    if skipped:
        lines.append(f"- Skipped invariants (<3 checkpoints): {', '.join(sorted(skipped))}")
    lines.extend(["", "## Convergence Table", ""])
    lines.extend(build_convergence_summary_lines(results, lang="markdown"))
    return lines


def _build_convergence_latex(
    dataset: str,
    results: list[dict[str, Any]],
    skipped: list[str],
) -> list[str]:
    behavior = summarize_behavior(results)
    lines = [
        f"% Auto-generated convergence summary for {dataset}",
        f"% Plateau-projecting invariants: {behavior['projected_plateau']['count']}/{behavior['projected_plateau']['total']}",
        f"% Mean plateau-signal edit: {behavior['projected_plateau']['formatted']}",
        f"% Monotone-converging invariants: {behavior['converging']['count']}/{behavior['converging']['total']}",
        f"% Mean monotone-convergence edit: {behavior['converging']['formatted']}",
        f"% Not converged: {behavior['not_converged']['count']}/{behavior['not_converged']['total']}",
    ]
    if skipped:
        lines.append(f"% Skipped invariants (<3 checkpoints): {', '.join(sorted(skipped))}")
    lines.extend(["", r"\subsection*{Convergence Summary}"])
    lines.extend(build_convergence_summary_lines(results, lang="latex"))
    return lines


def _build_projection_markdown(
    dataset: str,
    results: list[dict[str, Any]],
    milestones: list[float],
) -> list[str]:
    summary = summarize_projection_results(results)
    lines = [
        f"# {dataset.title()} Projection Summary",
        "",
        f"- Plateau-signal projections: {summary['plateau_signal']['count']}/{summary['plateau_signal']['total']}",
        f"- Monotone-tail projections: {summary['monotone_tail']['count']}/{summary['monotone_tail']['total']}",
        f"- Unprojected invariants: {summary['unprojected']['count']}/{summary['unprojected']['total']}",
        "",
        "## Projection Table",
        "",
    ]
    lines.extend(build_projection_summary_lines(results, milestones, lang="markdown"))
    return lines


def _build_projection_latex(
    dataset: str,
    results: list[dict[str, Any]],
    milestones: list[float],
) -> list[str]:
    summary = summarize_projection_results(results)
    lines = [
        f"% Auto-generated projection summary for {dataset}",
        f"% Plateau-signal projections: {summary['plateau_signal']['count']}/{summary['plateau_signal']['total']}",
        f"% Monotone-tail projections: {summary['monotone_tail']['count']}/{summary['monotone_tail']['total']}",
        f"% Unprojected invariants: {summary['unprojected']['count']}/{summary['unprojected']['total']}",
        "",
        r"\subsection*{Projection Summary}",
    ]
    lines.extend(build_projection_summary_lines(results, milestones, lang="latex"))
    return lines


def _trim_payload(
    payload: dict[str, Any],
    keep_labels: Sequence[str],
) -> dict[str, Any]:
    keep_set = set(keep_labels)
    return {
        **payload,
        "checkpoints": [
            checkpoint
            for checkpoint in payload["checkpoints"]
            if checkpoint["label"] in keep_set
        ],
        "invariants_per_graph": {
            invariant: {
                label: value
                for label, value in values_by_checkpoint.items()
                if label in keep_set
            }
            for invariant, values_by_checkpoint in payload["invariants_per_graph"].items()
        },
    }


def _iteration_dir(output_dir: Path, removed: int, total_removable: int) -> Path:
    return output_dir / f"remove-{removed:02d}-of-{total_removable:02d}"


def _aggregate_header(milestones: Sequence[float]) -> list[str]:
    header = [
        "iteration",
        "removed_checkpoints",
        "remaining_checkpoints",
        "last_checkpoint_label",
        "last_checkpoint_edits",
    ]
    for fraction in milestones:
        label = milestone_label(fraction)
        header.append(f"{label} mean edits")
        header.append(f"{label} std edits")
    return header


def _aggregate_row(
    iteration: int,
    removed: int,
    checkpoints: Sequence[dict[str, Any]],
    milestone_summary: dict[str, dict[str, float | int | None | str]],
    milestones: Sequence[float],
) -> list[str]:
    last_checkpoint = checkpoints[-1]
    row = [
        str(iteration),
        str(removed),
        str(len(checkpoints)),
        str(last_checkpoint["label"]),
        str(last_checkpoint["edits"]),
    ]
    for fraction in milestones:
        label = milestone_label(fraction)
        mean_edit = milestone_summary[label]["mean_edit"]
        std_edit = milestone_summary[label]["std_edit"]
        row.append("" if mean_edit is None else f"{float(mean_edit):.6g}")
        row.append("" if std_edit is None else f"{float(std_edit):.6g}")
    return row


def _aggregate_markdown(rows: Sequence[Sequence[str]]) -> list[str]:
    header = list(rows[0])
    lines = [
        "# Forecasting Summary",
        "",
        "| " + " | ".join(header) + " |",
        "| " + " | ".join(["---"] * len(header)) + " |",
    ]
    for row in rows[1:]:
        lines.append("| " + " | ".join(row) + " |")
    return lines


def _render_forecasting_summary_figure(
    dataset: str,
    iterations: Sequence[dict[str, Any]],
    milestones: Sequence[float],
    output_dir: Path,
    *,
    formats: Sequence[str] = ("svg", "pdf"),
) -> list[Path]:
    configure_matplotlib()
    output_dir.mkdir(parents=True, exist_ok=True)
    if not iterations:
        return []

    milestone_labels = [milestone_label(fraction) for fraction in milestones]
    x_positions = np.array([fraction * 100.0 for fraction in milestones], dtype=float)
    cmap = plt.get_cmap("viridis")
    colors = cmap(np.linspace(0.1, 0.9, len(iterations)))

    fig, ax = plt.subplots(figsize=(4.4, 3.2))

    for color, iteration in zip(colors, iterations):
        milestone_summary = iteration["milestone_summary"]
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
        valid = np.isfinite(mean_values)
        if not np.any(valid):
            continue

        ax.errorbar(
            x_positions[valid],
            mean_values[valid],
            yerr=std_values[valid],
            color=color,
            linewidth=1.2,
            elinewidth=0.8,
            capsize=2.0,
            marker="o",
            markersize=3.0,
            alpha=0.9,
        )
        last_valid_idx = int(np.where(valid)[0][-1])
        last_edit = iteration["last_checkpoint"]["edits"]
        ax.annotate(
            f"{last_edit:,.0f} edits",
            (x_positions[last_valid_idx], mean_values[last_valid_idx]),
            textcoords="offset points",
            xytext=(5, 0),
            ha="left",
            va="center",
            fontsize=6.5,
            color=color,
            alpha=0.95,
        )

    ax.set_title(f"{dataset.title()} Forecasting Summary", fontsize=9, pad=4)
    ax.set_xlabel("Projection milestone (%)", fontsize=8)
    ax.set_ylabel("Mean edits", fontsize=8)
    ax.set_xticks(x_positions, milestone_labels)
    ax.tick_params(axis="both", labelsize=7, length=3)
    ax.grid(True, axis="y", alpha=0.25, linewidth=0.5)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    fig.tight_layout()

    paths: list[Path] = []
    stem = output_dir / "forecasting-milestone-bands"
    for fmt in formats:
        path = stem.with_suffix(f".{fmt}")
        fig.savefig(path, bbox_inches="tight")
        paths.append(path)
    plt.close(fig)
    return paths


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    milestones = _validate_milestones(args.milestones)
    payload = _load_invariants_payload(args.input_json)
    checkpoints = sorted(payload["checkpoints"], key=lambda checkpoint: checkpoint["edits"])
    if len(checkpoints) < 3:
        raise ValueError("Forecasting requires at least 3 checkpoints.")

    total_removable = len(checkpoints) - 3
    aggregate_rows: list[list[str]] = [_aggregate_header(milestones)]
    iterations: list[dict[str, Any]] = []

    for removed in range(total_removable + 1):
        trimmed_checkpoints = checkpoints[: len(checkpoints) - removed]
        trimmed_labels = [checkpoint["label"] for checkpoint in trimmed_checkpoints]
        trimmed_payload = _trim_payload(payload, trimmed_labels)
        checkpoint_lookup = {
            checkpoint["label"]: checkpoint["edits"] for checkpoint in trimmed_checkpoints
        }

        convergence_results, skipped = analyze_invariants(
            trimmed_payload["invariants_per_graph"],
            trimmed_labels,
            checkpoint_lookup,
            plateau_kwargs={
                "min_points": args.plateau_min_points,
                "band_rel": args.plateau_band_rel,
                "band_abs": args.plateau_band_abs,
                "drift_rel": args.plateau_drift_rel,
                "drift_abs": args.plateau_drift_abs,
                "contrast_min": args.plateau_contrast_min,
                "center": args.plateau_center,
            },
            monotone_kwargs={
                "min_points": args.monotone_min_points,
                "step_ratio_max": args.monotone_step_ratio_max,
                "step_rel_max": args.monotone_step_rel_max,
                "sign_fraction_min": args.monotone_sign_fraction_min,
            },
        )

        convergence_payload = convergence_stats_payload(args.dataset, convergence_results)
        convergence_payload["input_json"] = str(args.input_json)
        convergence_payload["metric_profile"] = trimmed_payload.get("metric_profile")
        convergence_payload["skipped_invariants"] = sorted(skipped)
        convergence_payload["trimmed_checkpoints"] = trimmed_checkpoints
        convergence_payload["removed_checkpoints"] = removed
        convergence_payload["figure_paths"] = []

        projection_results = build_projection_results(
            trimmed_payload["invariants_per_graph"],
            convergence_payload,
            trimmed_checkpoints,
            milestones=milestones,
        )
        projection_payload = projection_stats_payload(
            args.dataset,
            projection_results,
            milestones,
        )
        projection_payload["input_json"] = str(args.input_json)
        projection_payload["metric_profile"] = trimmed_payload.get("metric_profile")
        projection_payload["removed_checkpoints"] = removed
        projection_payload["trimmed_checkpoints"] = trimmed_checkpoints
        projection_payload["figure_paths"] = []

        iteration_dir = _iteration_dir(args.output_dir, removed, total_removable)
        write_json(iteration_dir / "trimmed-invariants.json", trimmed_payload)
        write_text_lines(
            iteration_dir / "convergence-summary.md",
            _build_convergence_markdown(args.dataset, convergence_results, skipped),
        )
        write_text_lines(
            iteration_dir / "convergence-summary.tex",
            _build_convergence_latex(args.dataset, convergence_results, skipped),
        )
        write_json(iteration_dir / "convergence-stats.json", convergence_payload)
        write_text_lines(
            iteration_dir / "projection-summary.md",
            _build_projection_markdown(args.dataset, projection_results, milestones),
        )
        write_text_lines(
            iteration_dir / "projection-summary.tex",
            _build_projection_latex(args.dataset, projection_results, milestones),
        )
        write_csv_rows(
            iteration_dir / "projection-summary.csv",
            build_projection_summary_csv_rows(projection_results, milestones),
        )
        write_json(iteration_dir / "projection-stats.json", projection_payload)

        aggregate_rows.append(
            _aggregate_row(
                iteration=len(aggregate_rows) - 1,
                removed=removed,
                checkpoints=trimmed_checkpoints,
                milestone_summary=projection_payload["milestone_summary"],
                milestones=milestones,
            )
        )
        iterations.append(
            {
                "iteration": len(iterations),
                "removed_checkpoints": removed,
                "remaining_checkpoints": len(trimmed_checkpoints),
                "last_checkpoint": trimmed_checkpoints[-1],
                "iteration_dir": str(iteration_dir),
                "convergence_stats": str(iteration_dir / "convergence-stats.json"),
                "projection_stats": str(iteration_dir / "projection-stats.json"),
                "milestone_summary": projection_payload["milestone_summary"],
            }
        )

    write_csv_rows(args.aggregate_csv, aggregate_rows)
    write_text_lines(args.aggregate_md, _aggregate_markdown(aggregate_rows))
    figure_paths = _render_forecasting_summary_figure(
        args.dataset,
        iterations,
        milestones,
        args.figure_dir,
    )
    write_json(
        args.aggregate_json,
        {
            "dataset": args.dataset,
            "input_json": str(args.input_json),
            "milestones": [milestone_label(fraction) for fraction in milestones],
            "iterations": iterations,
            "aggregate_csv": str(args.aggregate_csv),
            "aggregate_md": str(args.aggregate_md),
            "output_dir": str(args.output_dir),
            "figure_paths": [str(path) for path in figure_paths],
        },
    )

    print(
        f"Wrote forecasting outputs for {len(iterations)} iterations "
        f"and {len(figure_paths)} figure file(s) to {args.output_dir}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
