from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

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
    STATUS_CONVERGING,
    STATUS_NOT_CONVERGED,
    STATUS_PROJECTED_PLATEAU,
    analyze_invariants,
    compute_checkpoint_metadata,
)
from zfish.invariants import DATASET_CONNECTOME, DATASET_CONTACTOME, DATASET_HEMIBRAIN
from zfish.reporting import (
    build_convergence_summary_lines,
    convergence_stats_payload,
    render_convergence_grids,
    summarize_behavior,
    write_json,
    write_text_lines,
)

DATASET_CHOICES = (DATASET_CONNECTOME, DATASET_CONTACTOME, DATASET_HEMIBRAIN)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build nonparametric convergence summaries for one invariant trajectory JSON."
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
        "--summary-md",
        type=Path,
        required=True,
        help="Markdown output path for the convergence summary.",
    )
    parser.add_argument(
        "--summary-tex",
        type=Path,
        required=True,
        help="LaTeX output path for the convergence summary.",
    )
    parser.add_argument(
        "--stats-json",
        type=Path,
        required=True,
        help="JSON output path for summary statistics.",
    )
    parser.add_argument(
        "--figure-dir",
        type=Path,
        required=True,
        help="Directory for convergence figure exports.",
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
        help=(
            "Minimum ratio between earlier deviation from a plateau center and the "
            "plateau tail's own noise level."
        ),
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


def _build_markdown_summary(
    dataset: str,
    results: list[dict[str, Any]],
    skipped: list[str],
) -> list[str]:
    behavior = summarize_behavior(results)
    lines = [
        f"# {dataset.title()} Convergence Summary",
        "",
        f"- Plateau-projecting invariants: {behavior[STATUS_PROJECTED_PLATEAU]['count']}/{behavior[STATUS_PROJECTED_PLATEAU]['total']}",
        f"- Mean plateau-signal edit: {behavior[STATUS_PROJECTED_PLATEAU]['formatted']}",
        f"- Monotone-converging invariants: {behavior[STATUS_CONVERGING]['count']}/{behavior[STATUS_CONVERGING]['total']}",
        f"- Mean monotone-convergence edit: {behavior[STATUS_CONVERGING]['formatted']}",
        f"- Not converged: {behavior[STATUS_NOT_CONVERGED]['count']}/{behavior[STATUS_NOT_CONVERGED]['total']}",
    ]
    if skipped:
        lines.append(f"- Skipped invariants (<3 checkpoints): {', '.join(sorted(skipped))}")
    lines.extend(["", "## Convergence Table", ""])
    lines.extend(build_convergence_summary_lines(results, lang="markdown"))
    return lines


def _build_latex_summary(
    dataset: str,
    results: list[dict[str, Any]],
    skipped: list[str],
) -> list[str]:
    behavior = summarize_behavior(results)
    lines = [
        f"% Auto-generated convergence summary for {dataset}",
        f"% Plateau-projecting invariants: {behavior[STATUS_PROJECTED_PLATEAU]['count']}/{behavior[STATUS_PROJECTED_PLATEAU]['total']}",
        f"% Mean plateau-signal edit: {behavior[STATUS_PROJECTED_PLATEAU]['formatted']}",
        f"% Monotone-converging invariants: {behavior[STATUS_CONVERGING]['count']}/{behavior[STATUS_CONVERGING]['total']}",
        f"% Mean monotone-convergence edit: {behavior[STATUS_CONVERGING]['formatted']}",
        f"% Not converged: {behavior[STATUS_NOT_CONVERGED]['count']}/{behavior[STATUS_NOT_CONVERGED]['total']}",
    ]
    if skipped:
        lines.append(f"% Skipped invariants (<3 checkpoints): {', '.join(sorted(skipped))}")
    lines.extend(["", r"\subsection*{Convergence Summary}"])
    lines.extend(build_convergence_summary_lines(results, lang="latex"))
    return lines


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    payload = _load_invariants_payload(args.input_json)
    invariants_per_graph = payload["invariants_per_graph"]
    # checkpoint_labels, _checkpoint_edits, checkpoint_lookup = compute_checkpoint_metadata(
    #     invariants_per_graph
    # )
    checkpoint_lookup = sorted(payload["checkpoints"], key=lambda x: x["edits"])
    checkpoint_labels, checkpoint_edits = zip(*((x["label"], x["edits"]) for x in checkpoint_lookup))
    checkpoint_lookup = dict(zip(checkpoint_labels, checkpoint_edits))
    results, skipped = analyze_invariants(
        invariants_per_graph,
        checkpoint_labels,
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

    write_text_lines(
        args.summary_md,
        _build_markdown_summary(args.dataset, results, skipped),
    )
    write_text_lines(
        args.summary_tex,
        _build_latex_summary(args.dataset, results, skipped),
    )

    figure_paths = render_convergence_grids(results, checkpoint_lookup, args.figure_dir, dataset=args.dataset)
    stats_payload = convergence_stats_payload(args.dataset, results)
    stats_payload["input_json"] = str(args.input_json)
    stats_payload["metric_profile"] = payload.get("metric_profile")
    stats_payload["skipped_invariants"] = sorted(skipped)
    stats_payload["figure_paths"] = [str(path) for path in figure_paths]
    write_json(args.stats_json, stats_payload)

    print(
        f"Wrote convergence summaries for {len(results)} invariants "
        f"and {len(figure_paths)} figure file(s)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
