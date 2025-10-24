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
        "--overwrite",
        action="store_true",
        help="Overwrite remap files when they already exist.",
    )
    generate.set_defaults(func=_run_generate)


def _run_generate(args: argparse.Namespace) -> int:
    generated = remap_mod.generate_remap_files(
        args.component_dir,
        overwrite=args.overwrite,
    )
    if generated:
        print(f"Generated {len(generated)} remap file(s).")
    else:
        print("No remap files created. Use --overwrite to regenerate existing files.")
    return 0

