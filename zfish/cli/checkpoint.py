from __future__ import annotations

import argparse
from pathlib import Path

from zfish import checkpoint as checkpoint_mod

DEFAULT_SUPERVOXELS_PATH = (
    "precomputed://s3://cvdb-bossdb-boss/smith2024/zebrafish/supervoxels"
)
DEFAULT_CHECKPOINT_STEM = (
    "precomputed://s3://cvdb-bossdb-boss/smith2024/zebrafish/agglomeration_checkpoint_"
)


def register_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("checkpoint", help="Create agglomeration checkpoint volumes.")
    parser.set_defaults(func=lambda _: parser.print_help())

    checkpoint_subparsers = parser.add_subparsers(dest="checkpoint_command")
    checkpoint_subparsers.required = True

    upload = checkpoint_subparsers.add_parser(
        "upload", help="Upload checkpoint volumes for each remap dictionary."
    )
    upload.add_argument(
        "--component-dir",
        type=Path,
        default=Path("component-graphs"),
        help="Directory containing *.remap.json files.",
    )
    upload.add_argument(
        "--supervoxels-path",
        default=DEFAULT_SUPERVOXELS_PATH,
        help="CloudVolume path for the source supervoxels.",
    )
    upload.add_argument(
        "--checkpoint-stem",
        default=DEFAULT_CHECKPOINT_STEM,
        help="Prefix for destination checkpoint CloudVolume paths.",
    )
    upload.add_argument(
        "--jobs",
        type=int,
        default=16,
        help="Number of parallel jobs for block uploads.",
    )
    upload.add_argument(
        "--block-size",
        type=int,
        nargs=3,
        metavar=("X", "Y", "Z"),
        default=(256, 256, 256),
        help="Block dimensions used when traversing the source volume.",
    )
    upload.add_argument(
        "--no-randomize",
        action="store_true",
        help="Disable randomization of block upload order.",
    )
    upload.add_argument(
        "--skip",
        type=int,
        action="append",
        dest="skip",
        default=None,
        help="Edit counts to skip; may be provided multiple times.",
    )
    upload.add_argument(
        "--no-progress",
        action="store_true",
        help="Disable tqdm progress bars.",
    )
    upload.set_defaults(func=_run_upload)


def _run_upload(args: argparse.Namespace) -> int:
    block_size = tuple(int(dim) for dim in args.block_size)
    processed = checkpoint_mod.create_checkpoint_channels(
        args.component_dir,
        supervoxel_path=args.supervoxels_path,
        checkpoint_stem=args.checkpoint_stem,
        jobs=args.jobs,
        block_size=block_size,
        randomize=not args.no_randomize,
        skip_edit_counts=args.skip,
        progress=not args.no_progress,
    )
    if processed:
        processed_str = ", ".join(str(count) for count in processed)
        print(f"Uploaded checkpoints for edit counts: {processed_str}")
    else:
        print("No checkpoints uploaded.")
    return 0
