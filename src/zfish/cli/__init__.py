from __future__ import annotations

import argparse

from . import changelog, remap, checkpoint


def register_commands(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    changelog.register_parser(subparsers)
    remap.register_parser(subparsers)
    checkpoint.register_parser(subparsers)


__all__ = ["register_commands"]

