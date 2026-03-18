from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from zfish.graphs import build_graph_bundles, checkpoint_to_edits, load_checkpoint_graphs
from zfish.invariants import (
    DATASET_CONNECTOME,
    DATASET_CONTACTOME,
    DATASET_HEMIBRAIN,
    METRIC_PROFILE_FAST,
    METRIC_PROFILE_FULL,
    compute_invariants,
)
from zfish.paths import ensure_parent

DATASET_CHOICES = (DATASET_CONNECTOME, DATASET_CONTACTOME, DATASET_HEMIBRAIN)
METRIC_PROFILE_CHOICES = (METRIC_PROFILE_FAST, METRIC_PROFILE_FULL)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compute invariant trajectories for one ordered graph series."
    )
    parser.add_argument(
        "--dataset",
        required=True,
        choices=DATASET_CHOICES,
        help="Dataset family to load.",
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        required=True,
        help="Directory containing one ordered series of edgelist CSVs.",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        required=True,
        help="Destination JSON path for computed invariant trajectories.",
    )
    parser.add_argument(
        "--metric-profile",
        choices=METRIC_PROFILE_CHOICES,
        default=METRIC_PROFILE_FAST,
        help="Metric set to compute. 'fast' favors scalable approximations.",
    )
    parser.add_argument(
        "--parallel",
        nargs="?",
        const=-1,
        type=int,
        default=0,
        help="Use threaded parallelism. Omit the value to use all cores.",
    )
    parser.add_argument(
        "--progress",
        action="store_true",
        help="Show progress bars while computing invariants.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    graphs = load_checkpoint_graphs(args.dataset, args.input_dir)
    if not graphs:
        raise FileNotFoundError(f"No CSV graphs found in {args.input_dir}")

    graph_bundles = build_graph_bundles(graphs)
    invariants_per_graph = compute_invariants(
        graph_bundles,
        args.dataset,
        metric_profile=args.metric_profile,
        parallel=args.parallel,
        progress=args.progress,
    )

    checkpoints = [
        {"label": label, "edits": checkpoint_to_edits(label)}
        for label in sorted(graphs, key=checkpoint_to_edits)
    ]
    payload = {
        "dataset": args.dataset,
        "input_dir": str(Path(args.input_dir)),
        "metric_profile": args.metric_profile,
        "checkpoints": checkpoints,
        "invariants_per_graph": invariants_per_graph,
    }

    output_path = ensure_parent(args.output_json)
    output_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(
        f"Wrote {len(invariants_per_graph)} invariant trajectories "
        f"across {len(checkpoints)} checkpoints to {output_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
