from __future__ import annotations

import argparse
from pathlib import Path

from zfish import checkpoint as checkpoint_mod
from zfish.paths import default_component_graph_dir

DEFAULT_SUPERVOXELS_PATH = (
    "precomputed://s3://cvdb-bossdb-boss/smith2024/zebrafish/supervoxels"
)
DEFAULT_CHECKPOINT_PREFIX = (
    "precomputed://s3://cvdb-bossdb-boss/smith2024/zebrafish/"
)
DEFAULT_CHECKPOINT_STEM = DEFAULT_CHECKPOINT_PREFIX + "agglomeration_checkpoint_"


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
        default=default_component_graph_dir(),
        help="Directory containing *.remap.json files.",
    )
    upload.add_argument(
        "--shuffle-id",
        type=_positive_int,
        default=None,
        help="Use remap files from the shuffle_<id> subdirectory and adjust defaults accordingly.",
    )
    upload.add_argument(
        "--mip",
        type=_nonnegative_int,
        default=0,
        help="Mipmap level to read from the source and write the destination checkpoints.",
    )
    upload.add_argument(
        "--supervoxels-path",
        default=DEFAULT_SUPERVOXELS_PATH,
        help="CloudVolume path for the source supervoxels.",
    )
    upload.add_argument(
        "--checkpoint-prefix",
        default=DEFAULT_CHECKPOINT_PREFIX,
        help="Base CloudVolume prefix for destination checkpoint paths.",
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
        "--chunk-size",
        type=_positive_int,
        nargs=3,
        metavar=("X", "Y", "Z"),
        default=None,
        help="Chunk size for the destination checkpoints at the requested mip.",
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


def _positive_int(value: str) -> int:
    intval = int(value)
    if intval <= 0:
        msg = "value must be greater than zero"
        raise argparse.ArgumentTypeError(msg)
    return intval


def _nonnegative_int(value: str) -> int:
    intval = int(value)
    if intval < 0:
        msg = "value must be zero or greater"
        raise argparse.ArgumentTypeError(msg)
    return intval


def _default_checkpoint_stem(prefix: str) -> str:
    return f"{prefix}agglomeration_checkpoint_"


def _shuffle_checkpoint_stem(shuffle_id: int, *, prefix: str = DEFAULT_CHECKPOINT_PREFIX) -> str:
    return f"{prefix}shuffle_{shuffle_id}_checkpoint_"


def _run_upload(args: argparse.Namespace) -> int:
    block_size = tuple(int(dim) for dim in args.block_size)
    chunk_size = tuple(int(dim) for dim in args.chunk_size) if args.chunk_size else None
    component_dir = args.component_dir
    checkpoint_stem = args.checkpoint_stem
    checkpoint_prefix = args.checkpoint_prefix
    using_default_stem = args.checkpoint_stem == DEFAULT_CHECKPOINT_STEM

    if using_default_stem:
        checkpoint_stem = _default_checkpoint_stem(checkpoint_prefix)

    if args.shuffle_id is not None:
        component_dir = component_dir / f"shuffle_{args.shuffle_id}"
        if using_default_stem:
            checkpoint_stem = _shuffle_checkpoint_stem(
                args.shuffle_id, prefix=checkpoint_prefix
            )

    processed = checkpoint_mod.create_checkpoint_channels(
        component_dir,
        supervoxel_path=args.supervoxels_path,
        checkpoint_stem=checkpoint_stem,
        jobs=args.jobs,
        block_size=block_size,
        chunk_size=chunk_size,
        mip=args.mip,
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
