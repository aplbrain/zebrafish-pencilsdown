from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Mapping

from joblib import Parallel, delayed
from tqdm import tqdm

import rustworkx as rx


DATASET_CONTACTOME = "contactome"
DATASET_CONNECTOME = "connectome"
DATASET_HEMIBRAIN = "hemibrain"
METRIC_PROFILE_FAST = "fast"
METRIC_PROFILE_FULL = "full"

AnyGraph = rx.PyGraph | rx.PyDiGraph


class RxInvariants:
    @staticmethod
    def _n_m(graph: AnyGraph) -> tuple[int, int]:
        return graph.num_nodes(), graph.num_edges()

    @staticmethod
    def _is_directed(graph: AnyGraph) -> bool:
        return isinstance(graph, rx.PyDiGraph)

    @staticmethod
    def _degree(graph: AnyGraph, index: int) -> int:
        if isinstance(graph, rx.PyDiGraph):
            return graph.in_degree(index) + graph.out_degree(index)
        return graph.degree(index)

    @staticmethod
    def _to_undirected_if_needed(graph: AnyGraph) -> rx.PyGraph:
        if isinstance(graph, rx.PyDiGraph):
            return graph.to_undirected(multigraph=graph.multigraph)
        return graph

    @staticmethod
    def _neighbors_undirected(graph: rx.PyGraph, source: int) -> Iterable[int]:
        return graph.neighbors(source)

    @staticmethod
    def _bfs_distances_undirected(graph: rx.PyGraph, source: int) -> dict[int, int]:
        distances: dict[int, int] = {source: 0}
        queue = [source]
        head = 0
        while head < len(queue):
            node = queue[head]
            head += 1
            dist = distances[node]
            for neighbor in RxInvariants._neighbors_undirected(graph, node):
                if neighbor in distances:
                    continue
                distances[neighbor] = dist + 1
                queue.append(neighbor)
        return distances

    @staticmethod
    def _pick_seeds(node_count: int, num_seeds: int) -> list[int]:
        if node_count <= 0:
            return []
        k = min(num_seeds, node_count)
        if k == node_count:
            return list(range(node_count))
        step = max(1, node_count // k)
        return list(range(0, node_count, step))[:k]

    @staticmethod
    def density(graph: AnyGraph) -> float:
        n, m = RxInvariants._n_m(graph)
        if n <= 1:
            return 0.0
        denom = n * (n - 1)
        if RxInvariants._is_directed(graph):
            return m / denom
        return (2 * m) / denom

    @staticmethod
    def average_degree(graph: AnyGraph) -> float:
        n, m = RxInvariants._n_m(graph)
        if n == 0:
            return 0.0
        return (2 * m) / n

    @staticmethod
    def transitivity(graph: AnyGraph) -> float:
        return rx.transitivity(graph)

    @staticmethod
    def diameter_dijkstra(
        graph: AnyGraph,
        *,
        disconnected_ok: bool = False,
        weak_for_directed: bool = True,
    ) -> float:
        node_count = graph.num_nodes()
        if node_count <= 1:
            return 0.0

        work = graph
        if isinstance(graph, rx.PyDiGraph) and weak_for_directed:
            work = graph.to_undirected(multigraph=graph.multigraph)

        if isinstance(work, rx.PyDiGraph):
            distances = rx.digraph_all_pairs_dijkstra_path_lengths(work, lambda _: 1.0)
        else:
            distances = rx.graph_all_pairs_dijkstra_path_lengths(work, lambda _: 1.0)

        max_distance = 0.0
        for _source, row in distances.items():
            if not disconnected_ok and len(row) < node_count - 1:
                return math.inf
            for _target, distance in row.items():
                if distance is None or math.isinf(distance):
                    if not disconnected_ok:
                        return math.inf
                    continue
                max_distance = max(max_distance, distance)
        return max_distance

    @staticmethod
    def diameter_approx(
        graph: AnyGraph,
        *,
        num_seeds: int = 64,
        weak_for_directed: bool = True,
        disconnected_ok: bool = True,
    ) -> float:
        node_count = graph.num_nodes()
        if node_count <= 1:
            return 0.0

        work: AnyGraph = graph
        if isinstance(graph, rx.PyDiGraph) and weak_for_directed:
            work = graph.to_undirected(multigraph=graph.multigraph)
        if isinstance(work, rx.PyDiGraph):
            work = work.to_undirected(multigraph=work.multigraph)

        seeds = RxInvariants._pick_seeds(node_count, num_seeds)
        max_distance = 0.0
        for seed in seeds:
            distances = RxInvariants._bfs_distances_undirected(work, seed)
            if not disconnected_ok and len(distances) < node_count:
                return math.inf
            max_distance = max(max_distance, max(distances.values(), default=0))
        return float(max_distance)

    @staticmethod
    def triangle_count_avg(graph: AnyGraph) -> float:
        undirected = RxInvariants._to_undirected_if_needed(graph)
        node_count = undirected.num_nodes()
        if node_count == 0:
            return 0.0

        tri_times_three = 0
        for node in undirected.node_indices():
            neighbors = list(undirected.neighbors(node))
            for i, neighbor in enumerate(neighbors):
                for other in neighbors[i + 1 :]:
                    if undirected.has_edge(neighbor, other):
                        tri_times_three += 1

        return (tri_times_three // 3) / node_count

    @staticmethod
    def giant_component_fraction(graph: AnyGraph) -> float:
        node_count = graph.num_nodes()
        if node_count == 0:
            return 0.0
        if isinstance(graph, rx.PyDiGraph):
            components = rx.connected_components(
                graph.to_undirected(multigraph=graph.multigraph)
            )
        else:
            components = rx.connected_components(graph)
        return len(max(components, key=len)) / node_count

    @staticmethod
    def num_components(graph: AnyGraph) -> float:
        if isinstance(graph, rx.PyDiGraph):
            components = rx.connected_components(
                graph.to_undirected(multigraph=graph.multigraph)
            )
        else:
            components = rx.connected_components(graph)
        return float(len(components))

    @staticmethod
    def component_size_cv(graph: AnyGraph) -> float:
        node_count = graph.num_nodes()
        if node_count == 0:
            return 0.0
        if isinstance(graph, rx.PyDiGraph):
            components = rx.connected_components(
                graph.to_undirected(multigraph=graph.multigraph)
            )
        else:
            components = rx.connected_components(graph)
        sizes = [len(component) for component in components]
        mean_size = sum(sizes) / len(sizes)
        if mean_size == 0:
            return 0.0
        variance = sum((size - mean_size) ** 2 for size in sizes) / len(sizes)
        return math.sqrt(variance) / mean_size

    @staticmethod
    def kcore_max(graph: AnyGraph) -> float:
        undirected = RxInvariants._to_undirected_if_needed(graph)
        if undirected.num_nodes() == 0:
            return 0.0

        adjacency = {node: set(undirected.neighbors(node)) for node in undirected.node_indices()}
        degrees = {node: len(neighbors) for node, neighbors in adjacency.items()}
        max_degree = max(degrees.values(), default=0)
        buckets: list[list[int]] = [[] for _ in range(max_degree + 1)]
        for node, degree in degrees.items():
            buckets[degree].append(node)

        removed: set[int] = set()
        core = 0
        for current_degree, bucket in enumerate(buckets):
            while bucket:
                node = bucket.pop()
                if node in removed:
                    continue
                removed.add(node)
                core = max(core, current_degree)
                for neighbor in list(adjacency[node]):
                    if neighbor in removed:
                        continue
                    degree = degrees[neighbor]
                    if degree <= current_degree:
                        continue
                    degrees[neighbor] = degree - 1
                    buckets[degree - 1].append(neighbor)
                    adjacency[neighbor].discard(node)
        return float(core)

    @staticmethod
    def top1pct_degree_mass(graph: AnyGraph, *, frac: float = 0.01) -> float:
        node_count = graph.num_nodes()
        if node_count == 0:
            return 0.0
        degrees = [RxInvariants._degree(graph, node) for node in graph.node_indices()]
        total = sum(degrees)
        if total == 0:
            return 0.0
        k = max(1, int(math.ceil(frac * node_count)))
        return sum(sorted(degrees, reverse=True)[:k]) / total

    @staticmethod
    def degree_entropy(graph: AnyGraph, *, base: float = math.e) -> float:
        node_count = graph.num_nodes()
        if node_count == 0:
            return 0.0
        degrees = [RxInvariants._degree(graph, node) for node in graph.node_indices()]
        total = sum(degrees)
        if total == 0:
            return 0.0
        log = math.log if base == math.e else (lambda x: math.log(x, base))
        return -sum((degree / total) * log(degree / total) for degree in degrees if degree > 0)

    @staticmethod
    def average_clustering(graph: AnyGraph) -> float:
        undirected = RxInvariants._to_undirected_if_needed(graph)
        node_count = undirected.num_nodes()
        if node_count == 0:
            return 0.0

        total = 0.0
        for node in undirected.node_indices():
            neighbors = list(undirected.neighbors(node))
            degree = len(neighbors)
            if degree < 2:
                continue
            links = 0
            for i, neighbor in enumerate(neighbors):
                for other in neighbors[i + 1 :]:
                    if undirected.has_edge(neighbor, other):
                        links += 1
            total += (2 * links) / (degree * (degree - 1))

        return total / node_count

    @staticmethod
    def average_clustering_sampled(
        graph: AnyGraph,
        *,
        max_nodes: int = 2048,
    ) -> float:
        undirected = RxInvariants._to_undirected_if_needed(graph)
        node_count = undirected.num_nodes()
        if node_count == 0:
            return 0.0

        sampled_nodes = RxInvariants._pick_seeds(node_count, max_nodes)
        if not sampled_nodes:
            return 0.0

        total = 0.0
        for node in sampled_nodes:
            neighbors = list(undirected.neighbors(node))
            degree = len(neighbors)
            if degree < 2:
                continue
            links = 0
            for i, neighbor in enumerate(neighbors):
                for other in neighbors[i + 1 :]:
                    if undirected.has_edge(neighbor, other):
                        links += 1
            total += (2 * links) / (degree * (degree - 1))

        return total / len(sampled_nodes)

    @staticmethod
    def transitivity_sampled(
        graph: AnyGraph,
        *,
        max_nodes: int = 2048,
    ) -> float:
        undirected = RxInvariants._to_undirected_if_needed(graph)
        node_count = undirected.num_nodes()
        if node_count == 0:
            return 0.0

        sampled_nodes = RxInvariants._pick_seeds(node_count, max_nodes)
        if not sampled_nodes:
            return 0.0

        closed_triplets = 0.0
        triplets = 0.0
        for node in sampled_nodes:
            neighbors = list(undirected.neighbors(node))
            degree = len(neighbors)
            if degree < 2:
                continue
            triplets += degree * (degree - 1) / 2
            for i, neighbor in enumerate(neighbors):
                for other in neighbors[i + 1 :]:
                    if undirected.has_edge(neighbor, other):
                        closed_triplets += 1.0

        if triplets == 0:
            return 0.0
        return closed_triplets / triplets

    @staticmethod
    def degree_assortativity_coefficient(graph: AnyGraph) -> float:
        undirected = RxInvariants._to_undirected_if_needed(graph)
        edge_count = undirected.num_edges()
        if edge_count == 0:
            return math.nan

        degrees = {node: undirected.degree(node) for node in undirected.node_indices()}
        sum_jk = 0.0
        sum_j_plus_k = 0.0
        sum_j2_plus_k2 = 0.0
        for source, target, _weight in undirected.weighted_edge_list():
            src_degree = degrees[source]
            dst_degree = degrees[target]
            sum_jk += src_degree * dst_degree
            sum_j_plus_k += src_degree + dst_degree
            sum_j2_plus_k2 += src_degree * src_degree + dst_degree * dst_degree

        inv_edge_count = 1.0 / edge_count
        term1 = inv_edge_count * sum_jk
        term2 = (inv_edge_count * 0.5 * sum_j_plus_k) ** 2
        term3 = inv_edge_count * 0.5 * sum_j2_plus_k2
        denominator = term3 - term2
        if denominator == 0:
            return math.nan
        return (term1 - term2) / denominator

    @staticmethod
    def reciprocity(graph: AnyGraph) -> float:
        if not isinstance(graph, rx.PyDiGraph):
            return math.nan
        edge_count = graph.num_edges()
        if edge_count == 0:
            return math.nan
        reciprocal_edges = 0
        for source, target, _weight in graph.weighted_edge_list():
            if source != target and graph.has_edge(target, source):
                reciprocal_edges += 1
        return reciprocal_edges / edge_count

    @staticmethod
    def molloy_reed_index(graph: AnyGraph) -> float:
        node_count = graph.num_nodes()
        if node_count == 0:
            return 0.0
        degrees = [RxInvariants._degree(graph, node) for node in graph.node_indices()]
        mean_degree = sum(degrees) / node_count
        if mean_degree == 0:
            return 0.0
        mean_degree_sq = sum(degree * degree for degree in degrees) / node_count
        return mean_degree_sq / mean_degree

    @staticmethod
    def degree_cv(graph: AnyGraph) -> float:
        degrees = [RxInvariants._degree(graph, node) for node in graph.node_indices()]
        if not degrees:
            return 0.0
        mean_degree = sum(degrees) / len(degrees)
        if mean_degree == 0:
            return 0.0
        variance = sum((degree - mean_degree) ** 2 for degree in degrees) / len(degrees)
        return math.sqrt(variance) / mean_degree

    @staticmethod
    def degree_gini(graph: AnyGraph) -> float:
        degrees = sorted(RxInvariants._degree(graph, node) for node in graph.node_indices())
        node_count = len(degrees)
        if node_count == 0:
            return 0.0
        total = sum(degrees)
        if total == 0:
            return 0.0
        weighted_sum = sum((index + 1) * degree for index, degree in enumerate(degrees))
        return (2 * weighted_sum) / (node_count * total) - (node_count + 1) / node_count


@dataclass(frozen=True)
class InvariantSpec:
    name: str
    func: Callable[[AnyGraph], float]
    fast_func: Callable[[AnyGraph], float] | None = None
    ylabel: str = ""
    default_on: str = "graph"
    on_overrides: Mapping[str, str] = field(default_factory=dict)
    datasets: frozenset[str] = frozenset({DATASET_CONNECTOME, DATASET_CONTACTOME})
    fast_enabled: bool = True

    def target_for(self, dataset: str) -> str:
        return self.on_overrides.get(dataset, self.default_on)

    def enabled_for(self, dataset: str, metric_profile: str) -> bool:
        if dataset not in self.datasets:
            return False
        if metric_profile == METRIC_PROFILE_FAST:
            return self.fast_enabled
        if metric_profile == METRIC_PROFILE_FULL:
            return True
        raise ValueError(f"Unknown metric profile: {metric_profile}")

    def func_for(self, metric_profile: str) -> Callable[[AnyGraph], float]:
        if metric_profile == METRIC_PROFILE_FAST and self.fast_func is not None:
            return self.fast_func
        return self.func


_INVARIANT_SPECS: tuple[InvariantSpec, ...] = (
    InvariantSpec(
        name="density",
        func=RxInvariants.density,
        ylabel="Density",
        on_overrides={DATASET_CONTACTOME: "undirected_graph"},
    ),
    InvariantSpec(
        name="average_clustering",
        func=RxInvariants.average_clustering,
        fast_func=RxInvariants.average_clustering_sampled,
        ylabel="Average Clustering Coefficient",
        on_overrides={DATASET_CONTACTOME: "undirected_graph"},
    ),
    InvariantSpec(
        name="transitivity",
        func=RxInvariants.transitivity,
        fast_func=RxInvariants.transitivity_sampled,
        ylabel="Transitivity",
        on_overrides={DATASET_CONTACTOME: "undirected_graph"},
    ),
    InvariantSpec(
        name="average_degree",
        func=RxInvariants.average_degree,
        ylabel="Average Degree",
        on_overrides={DATASET_CONTACTOME: "undirected_graph"},
    ),
    InvariantSpec(
        name="degree_assortativity",
        func=RxInvariants.degree_assortativity_coefficient,
        ylabel="Degree Assortativity",
        on_overrides={DATASET_CONTACTOME: "undirected_graph"},
    ),
    InvariantSpec(
        name="triangle_count",
        func=RxInvariants.triangle_count_avg,
        ylabel="Average Triangle Count",
        default_on="undirected_graph",
        on_overrides={DATASET_CONTACTOME: "undirected_graph"},
        fast_enabled=False,
    ),
    InvariantSpec(
        name="diameter",
        func=RxInvariants.diameter_dijkstra,
        ylabel="Diameter",
        default_on="largest_strong_component_graph",
        datasets=frozenset({DATASET_CONNECTOME}),
        fast_enabled=False,
    ),
    InvariantSpec(
        name="diameter_approx",
        func=RxInvariants.diameter_approx,
        ylabel="Approx. Diameter",
        default_on="largest_strong_component_graph",
        datasets=frozenset({DATASET_CONNECTOME}),
    ),
    InvariantSpec(
        name="giant_component_fraction",
        func=RxInvariants.giant_component_fraction,
        ylabel="Giant Component Fraction",
        datasets=frozenset({DATASET_CONNECTOME}),
    ),
    InvariantSpec(
        name="num_components",
        func=RxInvariants.num_components,
        ylabel="# Components",
        datasets=frozenset({DATASET_CONNECTOME}),
    ),
    InvariantSpec(
        name="component_size_cv",
        func=RxInvariants.component_size_cv,
        ylabel="Component Size CV",
        datasets=frozenset({DATASET_CONNECTOME}),
    ),
    InvariantSpec(
        name="kcore_max",
        func=RxInvariants.kcore_max,
        ylabel="Max k-core (Degeneracy)",
        on_overrides={DATASET_CONTACTOME: "undirected_graph"},
        datasets=frozenset({DATASET_CONNECTOME}),
    ),
    InvariantSpec(
        name="top1pct_degree_mass",
        func=RxInvariants.top1pct_degree_mass,
        ylabel="Top-1% Degree Mass",
        datasets=frozenset({DATASET_CONNECTOME}),
    ),
    InvariantSpec(
        name="degree_entropy",
        func=RxInvariants.degree_entropy,
        ylabel="Degree Entropy",
        datasets=frozenset({DATASET_CONNECTOME}),
        fast_enabled=True,
    ),
    InvariantSpec(
        name="reciprocity",
        func=RxInvariants.reciprocity,
        ylabel="Reciprocity",
        datasets=frozenset({DATASET_CONNECTOME}),
    ),
    InvariantSpec(
        name="molloy_reed_index",
        func=RxInvariants.molloy_reed_index,
        ylabel="Molloy-Reed Index",
        on_overrides={DATASET_CONTACTOME: "undirected_graph"},
    ),
    InvariantSpec(
        name="degree_cv",
        func=RxInvariants.degree_cv,
        ylabel="Degree CV",
        datasets=frozenset({DATASET_CONNECTOME}),
    ),
    InvariantSpec(
        name="degree_gini",
        func=RxInvariants.degree_gini,
        ylabel="Degree Gini",
        datasets=frozenset({DATASET_CONNECTOME}),
    ),
)


_INVARIANT_YLABELS: dict[str, str] = {
    spec.name: spec.ylabel
    for spec in _INVARIANT_SPECS
    if spec.ylabel
}


def invariant_ylabel(name: str) -> str:
    return _INVARIANT_YLABELS.get(name, name)


def select_invariants(
    dataset: str,
    *,
    metric_profile: str = METRIC_PROFILE_FAST,
) -> dict[str, InvariantSpec]:
    selected = [
        spec for spec in _INVARIANT_SPECS if spec.enabled_for(dataset, metric_profile)
    ]
    return {spec.name: spec for spec in selected}


def compute_invariants(
    graphs: Mapping[str, Mapping[str, AnyGraph]],
    dataset: str,
    specs: Mapping[str, InvariantSpec] | None = None,
    *,
    metric_profile: str = METRIC_PROFILE_FAST,
    parallel: bool | int = False,
    progress: bool = False,
) -> dict[str, dict[str, float]]:
    chosen_specs = specs or select_invariants(dataset, metric_profile=metric_profile)
    invariants_per_graph: dict[str, dict[str, float]] = {
        name: {graph_id: None for graph_id in graphs}  # type: ignore[typeddict-item]
        for name in chosen_specs
    }

    def compute_one(
        graph_id: str,
        graph_bundle: Mapping[str, AnyGraph],
        spec_name: str,
        spec: InvariantSpec,
    ) -> tuple[str, str, float]:
        target_key = spec.target_for(dataset)
        target_graph = graph_bundle.get(target_key, graph_bundle.get("graph"))
        if target_graph is None:
            raise KeyError(
                f"Graph bundle for {graph_id} missing target '{target_key}' and 'graph'."
            )
        return spec_name, graph_id, spec.func_for(metric_profile)(target_graph)

    if parallel is True:
        parallel = -1

    if parallel in [0, 1, False]:
        iterator = graphs.items()
        if progress:
            iterator = tqdm(list(iterator), disable=not progress)
        for graph_id, graph_bundle in iterator:
            for spec_name, spec in chosen_specs.items():
                name, gid, value = compute_one(graph_id, graph_bundle, spec_name, spec)
                invariants_per_graph[name][gid] = value
        return invariants_per_graph

    tasks = [
        (graph_id, graph_bundle, spec_name, spec)
        for graph_id, graph_bundle in graphs.items()
        for spec_name, spec in chosen_specs.items()
    ]
    task_iter = tqdm(tasks, disable=not progress) if progress else tasks
    results = Parallel(n_jobs=parallel, prefer="threads")(
        delayed(compute_one)(graph_id, graph_bundle, spec_name, spec)
        for graph_id, graph_bundle, spec_name, spec in task_iter
    )
    for spec_name, graph_id, value in results:
        invariants_per_graph[spec_name][graph_id] = value
    return invariants_per_graph


__all__ = [
    "AnyGraph",
    "InvariantSpec",
    "DATASET_CONTACTOME",
    "DATASET_CONNECTOME",
    "METRIC_PROFILE_FAST",
    "METRIC_PROFILE_FULL",
    "invariant_ylabel",
    "select_invariants",
    "compute_invariants",
]
