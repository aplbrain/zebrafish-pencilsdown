from __future__ import annotations

import argparse
import random
from pathlib import Path

from zfish import changelog
from zfish.paths import default_changes_path, default_component_graph_dir


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
        default=default_changes_path(),
        help="Path to the Ariadne changelog TSV.",
    )
    subsample.add_argument(
        "--output-dir",
        type=Path,
        default=default_component_graph_dir(),
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
    subsample.add_argument(
        "--shuffle-count",
        type=_non_negative_int,
        default=0,
        help="Number of shuffled control permutations to generate.",
    )
    subsample.add_argument(
        "--shuffle",
        "--shuffle-mode",
        dest="shuffle_mode",
        choices=("default", "naive"),
        default="default",
        help=(
            "Shuffle strategy for control permutations: 'default' preserves per-pair "
            "merge/split ordering; 'naive' randomizes all lines independently."
        ),
    )
    subsample.add_argument(
        "--shuffle-seed",
        type=int,
        default=None,
        help="Optional base seed for shuffle permutations.",
    )
    subsample.set_defaults(func=_run_subsample)


def _positive_int(value: str) -> int:
    intval = int(value)
    if intval <= 0:
        msg = "value must be greater than zero"
        raise argparse.ArgumentTypeError(msg)
    return intval


def _non_negative_int(value: str) -> int:
    intval = int(value)
    if intval < 0:
        msg = "value must not be negative"
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

    if args.shuffle_count:
        base_lines = args.changes_file.read_text(encoding="utf-8").splitlines(
            keepends=True
        )
        for index in range(1, args.shuffle_count + 1):
            if args.shuffle_seed is not None:
                rng = random.Random(args.shuffle_seed + index)
            else:
                rng = random.Random()
            if args.shuffle_mode == "naive":
                shuffled_lines = base_lines[:]
                rng.shuffle(shuffled_lines)
            else:
                shuffled_lines = changelog.shuffle_changes_constrained(
                    base_lines, rng
                )
            shuffle_dir = args.output_dir / f"shuffle_{index}"
            shuffle_summary = changelog.create_component_graph_snapshots(
                args.changes_file,
                shuffle_dir,
                args.step_size,
                include_change_logs=not args.skip_change_logs,
                stop_after=args.max_changes,
                changes_sequence=shuffled_lines,
            )
            print(
                f"Shuffle {index}: wrote {len(shuffle_summary.graph_snapshots)} graph "
                f"snapshots from {shuffle_summary.total_changes} permuted entries."
            )

    return 0
