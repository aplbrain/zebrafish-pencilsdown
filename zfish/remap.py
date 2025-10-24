from __future__ import annotations

from pathlib import Path
import json

import networkx as nx


def build_remap_dict(graph: nx.Graph) -> dict[str, str]:
    """
    Map each segment id to the smallest segment id within its component.
    """
    remap_dict: dict[str, str] = {}
    for component in nx.connected_components(graph):
        min_seg = min(component)
        for seg in component:
            remap_dict[str(seg)] = str(min_seg)
    return remap_dict


def write_remap_dict(remap_dict: dict[str, str], destination: Path) -> None:
    destination.write_text(
        json.dumps({k: remap_dict[k] for k in sorted(remap_dict)}, indent=2),
        encoding="utf-8",
    )


def generate_remap_files(
    component_dir: Path,
    *,
    overwrite: bool = False,
    extension: str = ".remap.json",
) -> list[Path]:
    """
    Produce remap dictionaries for each GEXF graph in component_dir.
    """
    component_dir = Path(component_dir)
    remap_paths: list[Path] = []

    for gexf_path in sorted(component_dir.glob("*.gexf")):
        remap_dict = build_remap_dict(nx.read_gexf(gexf_path))
        output_path = gexf_path.with_suffix(gexf_path.suffix + extension)
        if output_path.exists() and not overwrite:
            continue
        write_remap_dict(remap_dict, output_path)
        remap_paths.append(output_path)

    return remap_paths

