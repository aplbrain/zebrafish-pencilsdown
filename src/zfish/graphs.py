from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Iterable

import pandas as pd
import rustworkx as rx

from .invariants import DATASET_CONNECTOME, DATASET_CONTACTOME

GraphBundle = dict[str, rx.PyDiGraph | rx.PyGraph | tuple[int, ...]]
CheckpointGraphs = dict[str, rx.PyDiGraph]

_K_CHECKPOINT_RE = re.compile(r"(?P<thousands>\d+)k", re.IGNORECASE)
_C_CHECKPOINT_RE = re.compile(r"(?:^|[_-])c(?P<thousands>\d+)(?:[_-]|$)", re.IGNORECASE)


def checkpoint_to_edits(label: str) -> int:
    clean = label.strip().lower()
    if clean.startswith("c") and clean[1:].isdigit():
        return int(clean[1:]) * 1000
    if clean.endswith("k"):
        return int(clean[:-1]) * 1000
    return int(clean)


def edits_to_checkpoint_label(edit_count: int) -> str:
    if edit_count % 1000 == 0:
        return f"{edit_count // 1000}k"
    return str(edit_count)


def infer_checkpoint_label(path: Path) -> str:
    stem = path.stem.lower()
    for pattern in (_K_CHECKPOINT_RE, _C_CHECKPOINT_RE):
        match = pattern.search(stem)
        if match is not None:
            return edits_to_checkpoint_label(int(match.group("thousands")) * 1000)
    raise ValueError(f"Could not infer checkpoint label from {path.name}")


def make_undirected_graph(graph: rx.PyDiGraph | rx.PyGraph) -> rx.PyGraph:
    if isinstance(graph, rx.PyGraph):
        return graph
    return graph.to_undirected(multigraph=graph.multigraph)


def largest_strong_component_nodes(graph: rx.PyDiGraph) -> tuple[int, ...]:
    if graph.num_nodes() == 0:
        return tuple()
    return tuple(max(rx.strongly_connected_components(graph), key=len))


def largest_strong_component_graph(graph: rx.PyDiGraph) -> rx.PyDiGraph:
    nodes = largest_strong_component_nodes(graph)
    if not nodes:
        return rx.PyDiGraph(multigraph=graph.multigraph)
    return graph.subgraph(nodes).copy()


def build_graph_bundle(graph: rx.PyDiGraph) -> GraphBundle:
    strong_nodes = largest_strong_component_nodes(graph)
    return {
        "graph": graph,
        "undirected_graph": make_undirected_graph(graph),
        "largest_strong_component_graph": largest_strong_component_graph(graph),
        "largest_strong_component_nodes": strong_nodes,
    }


def _build_weighted_digraph(
    weighted_edges: Iterable[tuple[str, str, int | float]],
    *,
    remove_zero: bool = False,
) -> rx.PyDiGraph:
    graph = rx.PyDiGraph(multigraph=False)
    node_to_index: dict[str, int] = {}

    def index_for(node_id: str) -> int:
        existing = node_to_index.get(node_id)
        if existing is not None:
            return existing
        index = graph.add_node(node_id)
        node_to_index[node_id] = index
        return index

    edge_weights: dict[tuple[str, str], float] = {}
    for src_id, dst_id, weight in weighted_edges:
        if remove_zero and (src_id == "0" or dst_id == "0"):
            continue
        edge_weights[(src_id, dst_id)] = edge_weights.get((src_id, dst_id), 0.0) + float(
            weight
        )

    for (src_id, dst_id), weight in edge_weights.items():
        graph.add_edge(index_for(src_id), index_for(dst_id), weight)

    return graph


def load_connectome_graph(path: Path, *, remove_zero: bool = True) -> rx.PyDiGraph:
    weighted_edges: list[tuple[str, str, int]] = []
    with path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            synapse_id = row["synapse_id"]
            parts = synapse_id.split("_")
            if len(parts) == 7:
                _, _x, _y, _z, pre, post, _ = parts
            elif len(parts) == 6:
                _, _x, _y, _z, pre, post = parts
            else:
                raise ValueError(f"Unexpected synapse_id format: {synapse_id}")
            weighted_edges.append((pre[3:], post[4:], 1))
    return _build_weighted_digraph(weighted_edges, remove_zero=remove_zero)


def load_contactome_graph(path: Path, *, remove_zero: bool = False) -> rx.PyDiGraph:
    frame = pd.read_csv(path)
    columns = set(frame.columns)
    if {"pre", "post", "weight"} <= columns:
        frame = frame.rename(columns={"pre": "src", "post": "dst", "weight": "weight"})
    elif {"id1", "id2", "nm^2"} <= columns:
        frame = frame.rename(columns={"id1": "src", "id2": "dst", "nm^2": "weight"})
    else:
        raise ValueError(
            f"Unsupported contactome columns in {path.name}: {sorted(columns)}"
        )

    frame = frame.loc[:, ["src", "dst", "weight"]]
    if remove_zero:
        frame = frame[(frame["src"] != 0) & (frame["dst"] != 0)]
    grouped = frame.groupby(["src", "dst"], as_index=False, sort=False)["weight"].sum()
    weighted_edges = [
        (str(src), str(dst), float(weight))
        for src, dst, weight in grouped.itertuples(index=False, name=None)
    ]
    return _build_weighted_digraph(weighted_edges, remove_zero=remove_zero)


def _load_graphs(
    input_dir: Path,
    loader,
    *,
    remove_zero: bool = False,
) -> CheckpointGraphs:
    graphs: CheckpointGraphs = {}
    sources_by_checkpoint: dict[str, Path] = {}
    path = Path(input_dir)
    csv_paths = [path] if path.is_file() else sorted(path.rglob("*.csv"))
    for csv_path in csv_paths:
        if csv_path.name.startswith("."):
            continue
        checkpoint = infer_checkpoint_label(csv_path)
        if checkpoint in graphs:
            original = sources_by_checkpoint[checkpoint]
            raise ValueError(
                "Duplicate checkpoint label "
                f"{checkpoint} from {original} and {csv_path}. "
                "Point analysis at one ordered series at a time."
            )
        graphs[checkpoint] = loader(csv_path, remove_zero=remove_zero)
        sources_by_checkpoint[checkpoint] = csv_path
    return dict(sorted(graphs.items(), key=lambda item: checkpoint_to_edits(item[0])))


def load_connectome_graphs(
    input_dir: Path,
    *,
    remove_zero: bool = True,
) -> CheckpointGraphs:
    return _load_graphs(input_dir, load_connectome_graph, remove_zero=remove_zero)


def load_contactome_graphs(
    input_dir: Path,
    *,
    remove_zero: bool = False,
) -> CheckpointGraphs:
    return _load_graphs(input_dir, load_contactome_graph, remove_zero=remove_zero)


def load_checkpoint_graphs(
    dataset: str,
    input_dir: Path,
) -> CheckpointGraphs:
    if dataset == DATASET_CONNECTOME:
        return load_connectome_graphs(input_dir)
    if dataset == DATASET_CONTACTOME:
        return load_contactome_graphs(input_dir)
    raise ValueError(f"Unknown dataset: {dataset}")


def build_graph_bundles(graphs: CheckpointGraphs) -> dict[str, GraphBundle]:
    return {checkpoint: build_graph_bundle(graph) for checkpoint, graph in graphs.items()}


__all__ = [
    "GraphBundle",
    "CheckpointGraphs",
    "checkpoint_to_edits",
    "edits_to_checkpoint_label",
    "infer_checkpoint_label",
    "make_undirected_graph",
    "largest_strong_component_nodes",
    "largest_strong_component_graph",
    "build_graph_bundle",
    "build_graph_bundles",
    "load_connectome_graph",
    "load_contactome_graph",
    "load_connectome_graphs",
    "load_contactome_graphs",
    "load_checkpoint_graphs",
]
