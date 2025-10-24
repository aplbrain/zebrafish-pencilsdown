from __future__ import annotations

import argparse
from pathlib import Path

from zfish import remap as remap_mod


def register_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("remap", help="Create remap dictionaries from component graphs.")
    parser.set_defaults(func=lambda _: parser.print_help())

    remap_subparsers = parser.add_subparsers(dest="remap_command")
    remap_subparsers.required = True

    generate = remap_subparsers.add_parser(
        "generate", help="Convert all GEXF component graphs to remap JSON files."
    )
    generate.add_argument(
        "--component-dir",
        type=Path,
        default=Path("component-graphs"),
        help="Directory containing component graph GEXF files.",
    )
    generate.add_argument(
        "--shuffle-id",
        type=_positive_int,
        default=None,
        help="Use component graphs from the shuffle_<id> subdirectory.",
    )
    generate.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite remap files when they already exist.",
    )
    generate.add_argument(
        "--recursive",
        action="store_true",
        help="Recurse into subdirectories (useful for shuffle outputs).",
    )
    generate.set_defaults(func=_run_generate)


def _positive_int(value: str) -> int:
    intval = int(value)
    if intval <= 0:
        msg = "value must be greater than zero"
        raise argparse.ArgumentTypeError(msg)
    return intval


def _run_generate(args: argparse.Namespace) -> int:
    component_dir = args.component_dir
    if args.shuffle_id is not None:
        component_dir = component_dir / f"shuffle_{args.shuffle_id}"

    generated = remap_mod.generate_remap_files(
        component_dir,
        overwrite=args.overwrite,
        recursive=args.recursive,
    )
    if generated:
        print(f"Generated {len(generated)} remap file(s).")
    else:
        print("No remap files created. Use --overwrite to regenerate existing files.")
    return 0
