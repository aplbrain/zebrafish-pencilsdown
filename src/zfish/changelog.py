from __future__ import annotations

from contextlib import ExitStack
from pathlib import Path
from random import Random
from typing import Iterable, NamedTuple

import networkx as nx


class ChangeSummary(NamedTuple):
    graph_snapshots: list[Path]
    total_changes: int


def _apply_change(graph: nx.Graph, parts: Iterable[str]) -> None:
    op, *payload = parts
    if op == "+":
        graph.add_edge(payload[0], payload[1])
    elif op == "-":
        if graph.has_edge(payload[0], payload[1]):
            graph.remove_edge(payload[0], payload[1])
    elif op == "anchor_add":
        graph.add_node(payload[0], type="anchor")
    elif op == "anchor_del":
        if graph.has_node(payload[0]):
            graph.remove_node(payload[0])
    elif op == "note":
        if graph.has_node(payload[0]):
            graph.nodes[payload[0]]["note"] = payload[1]


def create_component_graph_snapshots(
    changes_file: Path,
    output_dir: Path,
    step_size: int,
    *,
    include_change_logs: bool = True,
    stop_after: int | None = None,
    changes_sequence: Iterable[str] | None = None,
) -> ChangeSummary:
    """
    Build incremental NetworkX component graphs from an Ariadne changelog.
    """
    if step_size <= 0:
        msg = "step_size must be a positive integer"
        raise ValueError(msg)

    output_dir.mkdir(parents=True, exist_ok=True)
    graph = nx.Graph()
    graph_paths: list[Path] = []
    lines_accumulator: list[str] | None = [] if include_change_logs else None
    changes_path = Path(changes_file)

    total_changes = 0

    def process_lines(iterator: Iterable[str]) -> None:
        nonlocal total_changes
        for line_number, line in enumerate(iterator, start=1):
            total_changes = line_number
            parts = line.rstrip("\n").split("\t")
            if not parts or not parts[0]:
                continue
            _apply_change(graph, parts)
            if lines_accumulator is not None:
                lines_accumulator.append(line)

            if line_number % step_size == 0:
                if include_change_logs and lines_accumulator is not None:
                    _write_change_log_snapshot(
                        output_dir, changes_path.name, line_number, lines_accumulator
                    )
                snapshot_path = _write_graph_snapshot(output_dir, graph, line_number)
                graph_paths.append(snapshot_path)

            if stop_after is not None and line_number >= stop_after:
                break
    with ExitStack() as stack:
        if changes_sequence is None:
            iterator = stack.enter_context(
                changes_path.open("r", encoding="utf-8")
            )
        else:
            iterator = iter(changes_sequence)
        process_lines(iterator)

    if include_change_logs and lines_accumulator is not None and total_changes:
        _write_change_log_snapshot(
            output_dir, changes_path.name, total_changes, lines_accumulator
        )

    return ChangeSummary(graph_paths, total_changes)


def _write_change_log_snapshot(
    output_dir: Path, stem: str, line_number: int, lines: list[str]
) -> Path:
    snapshot_path = output_dir / f"{stem}.{line_number}"
    snapshot_path.write_text("".join(lines), encoding="utf-8")
    return snapshot_path


def _write_graph_snapshot(output_dir: Path, graph: nx.Graph, line_number: int) -> Path:
    snapshot_path = output_dir / f"change_nx.{line_number}.gexf"
    nx.write_gexf(graph, snapshot_path)
    return snapshot_path


def shuffle_changes_constrained(lines: list[str], rng: Random) -> list[str]:
    """
    Generate a random permutation that preserves per-pair merge/split ordering.
    """
    count = len(lines)
    if count == 0:
        return []

    adjacency = [[] for _ in range(count)]
    indegree = [0] * count
    last_seen_by_pair: dict[tuple[str, str], int] = {}

    for idx, line in enumerate(lines):
        parts = line.rstrip("\n").split("\t")
        if parts and parts[0] in {"+", "-"} and len(parts) >= 3:
            pair = tuple(sorted((parts[1], parts[2])))
            previous_idx = last_seen_by_pair.get(pair)
            if previous_idx is not None:
                adjacency[previous_idx].append(idx)
                indegree[idx] += 1
            last_seen_by_pair[pair] = idx

    available = [i for i, deg in enumerate(indegree) if deg == 0]
    order: list[int] = []

    while available:
        choice_idx = rng.randrange(len(available))
        node = available.pop(choice_idx)
        order.append(node)
        for neighbor in adjacency[node]:
            indegree[neighbor] -= 1
            if indegree[neighbor] == 0:
                available.append(neighbor)

    if len(order) != count:
        msg = "Could not generate a valid constrained shuffle order"
        raise ValueError(msg)

    return [lines[i] for i in order]
