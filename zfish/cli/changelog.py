from __future__ import annotations

import argparse
from pathlib import Path

from zfish import changelog


def register_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("changelog", help="Work with Ariadne changelog files.")
    parser.set_defaults(func=lambda _: parser.print_help())

    changelog_subparsers = parser.add_subparsers(dest="changelog_command")
    changelog_subparsers.required = True

    subsample = changelog_subparsers.add_parser(
        "subsample", help="Generate NetworkX snapshots at fixed intervals."
    )
    subsample.add_argument(
        "--changes-file",
        type=Path,
        default=Path("changes.tsv"),
        help="Path to the Ariadne changelog TSV.",
    )
    subsample.add_argument(
        "--output-dir",
        type=Path,
        default=Path("component-graphs"),
        help="Directory where snapshot files are written.",
    )
    subsample.add_argument(
        "--step-size",
        type=_positive_int,
        default=5_000,
        help="Number of changelog entries per snapshot.",
    )
    subsample.add_argument(
        "--max-changes",
        type=_positive_int,
        default=None,
        help="Stop after processing this many changes.",
    )
    subsample.add_argument(
        "--skip-change-logs",
        action="store_true",
        help="Skip writing per-interval changelog excerpts.",
    )
    subsample.set_defaults(func=_run_subsample)


def _positive_int(value: str) -> int:
    intval = int(value)
    if intval <= 0:
        msg = "value must be greater than zero"
        raise argparse.ArgumentTypeError(msg)
    return intval


def _run_subsample(args: argparse.Namespace) -> int:
    summary = changelog.create_component_graph_snapshots(
        args.changes_file,
        args.output_dir,
        args.step_size,
        include_change_logs=not args.skip_change_logs,
        stop_after=args.max_changes,
    )
    print(
        f"Wrote {len(summary.graph_snapshots)} graph snapshots "
        f"from {summary.total_changes} changelog entries."
    )
    return 0

