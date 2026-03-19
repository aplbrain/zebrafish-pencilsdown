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

from zfish.invariants import DATASET_CONNECTOME, DATASET_CONTACTOME
from zfish.projections import DEFAULT_MILESTONES, build_projection_results
from zfish.reporting import (
    build_projection_summary_csv_rows,
    build_projection_summary_lines,
    projection_stats_payload,
    render_projection_milestone_bands,
    summarize_projection_results,
    write_csv_rows,
    write_json,
    write_text_lines,
)

DATASET_CHOICES = (DATASET_CONNECTOME, DATASET_CONTACTOME)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build projected invariant-limit summaries from existing invariants and convergence analyses."
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
        "--convergence-stats",
        type=Path,
        required=True,
        help="Convergence stats JSON produced by analysis/convergence/run.py.",
    )
    parser.add_argument(
        "--summary-md",
        type=Path,
        required=True,
        help="Markdown output path for the projection summary table.",
    )
    parser.add_argument(
        "--summary-tex",
        type=Path,
        required=True,
        help="LaTeX output path for the projection summary table.",
    )
    parser.add_argument(
        "--summary-csv",
        type=Path,
        required=True,
        help="CSV output path for the projection summary table.",
    )
    parser.add_argument(
        "--stats-json",
        type=Path,
        required=True,
        help="JSON output path for projection summary stats.",
    )
    parser.add_argument(
        "--figure-dir",
        type=Path,
        required=True,
        help="Directory for milestone-band figure exports.",
    )
    parser.add_argument(
        "--milestones",
        nargs="+",
        type=float,
        default=list(DEFAULT_MILESTONES),
        help="Progress milestones to report, expressed as fractions in (0, 1).",
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


def _validate_milestones(milestones: list[float]) -> list[float]:
    clean = sorted(set(float(value) for value in milestones))
    if not clean:
        raise ValueError("At least one milestone is required.")
    for value in clean:
        if not 0.0 < value < 1.0:
            raise ValueError(f"Milestones must be in (0, 1), got {value}")
    return clean


def _build_markdown_summary(
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


def _build_latex_summary(
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


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    milestones = _validate_milestones(args.milestones)
    invariants_payload = _load_invariants_payload(args.input_json)
    convergence_payload = json.loads(args.convergence_stats.read_text(encoding="utf-8"))

    results = build_projection_results(
        invariants_payload["invariants_per_graph"],
        convergence_payload,
        milestones=milestones,
    )

    write_text_lines(
        args.summary_md,
        _build_markdown_summary(args.dataset, results, milestones),
    )
    write_text_lines(
        args.summary_tex,
        _build_latex_summary(args.dataset, results, milestones),
    )
    write_csv_rows(
        args.summary_csv,
        build_projection_summary_csv_rows(results, milestones),
    )
    figure_paths = render_projection_milestone_bands(
        args.dataset,
        results,
        args.figure_dir,
        milestones=milestones,
    )

    stats_payload = projection_stats_payload(args.dataset, results, milestones)
    stats_payload["input_json"] = str(args.input_json)
    stats_payload["convergence_stats"] = str(args.convergence_stats)
    stats_payload["metric_profile"] = invariants_payload.get("metric_profile")
    stats_payload["figure_paths"] = [str(path) for path in figure_paths]
    write_json(args.stats_json, stats_payload)

    print(
        f"Wrote projection summaries for {len(results)} invariants "
        f"and {len(figure_paths)} figure file(s)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
