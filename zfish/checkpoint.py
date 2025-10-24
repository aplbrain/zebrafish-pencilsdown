from __future__ import annotations

import json
from pathlib import Path
from random import shuffle
from typing import Iterable

import fastremap
from cloudvolume import CloudVolume
from intern.utils.parallel import block_compute
from joblib import Parallel, delayed
from tqdm.auto import tqdm


def load_remap_dict(remap_path: Path) -> dict[int, int]:
    def int_keys_values(dct: dict[str, int]) -> dict[int, int]:
        return {int(k): int(v) for k, v in dct.items()}

    with Path(remap_path).open("r", encoding="utf-8") as fh:
        return json.load(fh, object_hook=int_keys_values)


def extract_edit_count(remap_path: Path) -> int:
    parts = remap_path.name.split(".")
    if len(parts) < 2:
        msg = f"Could not parse edit count from {remap_path}"
        raise ValueError(msg)
    return int(parts[1])


def create_checkpoint_channels(
    remap_dir: Path,
    *,
    supervoxel_path: str,
    checkpoint_stem: str,
    jobs: int = 16,
    block_size: tuple[int, int, int] = (256, 256, 256),
    randomize: bool = True,
    skip_edit_counts: Iterable[int] | None = None,
    progress: bool = True,
) -> list[int]:
    """
    Upload checkpoint volumes for each remap dictionary.
    """
    remap_dir = Path(remap_dir)
    skip = set(skip_edit_counts or [])
    src = CloudVolume(supervoxel_path, progress=False)

    processed: list[int] = []

    for remap_path in sorted(remap_dir.glob("*.remap.json")):
        edit_count = extract_edit_count(remap_path)
        if edit_count in skip:
            continue

        remap_dict = load_remap_dict(remap_path)
        dst_path = f"{checkpoint_stem}{edit_count}"
        dst = CloudVolume(dst_path, info=src.info, progress=False)
        dst.commit_info()

        blocks = list(
            block_compute(
                src.bounds.minpt[0],
                src.bounds.maxpt[0],
                src.bounds.minpt[1],
                src.bounds.maxpt[1],
                src.bounds.minpt[2],
                src.bounds.maxpt[2],
                block_size=block_size,
            )
        )
        if randomize:
            shuffle(blocks)

        iterator = blocks
        if progress:
            iterator = tqdm(blocks, desc=f"edit {edit_count}")

        Parallel(n_jobs=jobs)(
            delayed(_process_block)(block, src, dst, remap_dict) for block in iterator
        )

        processed.append(edit_count)

    return processed


def _process_block(
    block: tuple[tuple[int, int], tuple[int, int], tuple[int, int]],
    src: CloudVolume,
    dst: CloudVolume,
    remap_dict: dict[int, int],
) -> None:
    (x1, x2), (y1, y2), (z1, z2) = block
    src_data = src[x1:x2, y1:y2, z1:z2]
    remapped = fastremap.remap(
        src_data,
        remap_dict,
        preserve_missing_labels=True,
    )
    dst[x1:x2, y1:y2, z1:z2] = remapped

