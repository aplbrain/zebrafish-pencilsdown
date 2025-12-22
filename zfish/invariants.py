from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable, Mapping, Any, Iterable

from joblib import Parallel, delayed
from tqdm import tqdm

import networkx as nx
import rustworkx as rx

# Assuming these exist in your codebase already
DATASET_CONTACTOME = "contactome"
DATASET_CONNECTOME = "connectome"


# -----------------------------
# rustworkx invariants
# -----------------------------
class RxInvariants:
    # ---------- helpers ----------
    @staticmethod
    def _n_m(G) -> tuple[int, int]:
        return G.num_nodes(), G.num_edges()

    @staticmethod
    def _is_directed(G) -> bool:
        return isinstance(G, rx.PyDiGraph)

    @staticmethod
    def _degree(G, i: int) -> int:
        # total degree for both types
        if isinstance(G, rx.PyDiGraph):
            return G.in_degree(i) + G.out_degree(i)
        return G.degree(i)

    @staticmethod
    def _to_undirected_if_needed(G):
        if isinstance(G, rx.PyDiGraph):
            return G.to_undirected(multigraph=G.multigraph)
        return G

    @staticmethod
    def _neighbors_undirected(G: rx.PyGraph, u: int) -> Iterable[int]:
        # neighbors() is available and fast in rx
        return G.neighbors(u)

    @staticmethod
    def _bfs_distances_undirected(G: rx.PyGraph, source: int) -> dict[int, int]:
        """
        Simple BFS on PyGraph. Returns distances to reachable nodes.
        O(n+m) per source; used for diameter_approx.
        """
        dist: dict[int, int] = {source: 0}
        q = [source]
        head = 0
        while head < len(q):
            u = q[head]
            head += 1
            du = dist[u]
            for v in RxInvariants._neighbors_undirected(G, u):
                if v not in dist:
                    dist[v] = du + 1
                    q.append(v)
        return dist

    @staticmethod
    def _pick_seeds(n: int, num_seeds: int) -> list[int]:
        if n <= 0:
            return []
        k = min(num_seeds, n)
        # deterministic spread over node indices
        if k == n:
            return list(range(n))
        step = max(1, n // k)
        seeds = list(range(0, n, step))[:k]
        return seeds

    # ---------- invariants ----------
    @staticmethod
    def density(G: rx.PyGraph | rx.PyDiGraph) -> float:
        """
        Match nx.density:
          - undirected: 2m / (n(n-1))
          - directed:   m / (n(n-1))
        """
        n, m = RxInvariants._n_m(G)
        if n <= 1:
            return 0.0
        denom = n * (n - 1)
        if RxInvariants._is_directed(G):
            return m / denom
        return (2 * m) / denom

    @staticmethod
    def average_degree(G: rx.PyGraph | rx.PyDiGraph) -> float:
        """
        Total average degree, consistent with NX lambda:
        average over total degree (in+out for directed).
        """
        n, m = RxInvariants._n_m(G)
        if n == 0:
            return 0.0
        return (2 * m) / n

    @staticmethod
    def transitivity(G: rx.PyGraph | rx.PyDiGraph) -> float:
        """
        rustworkx transitivity exists for PyGraph and PyDiGraph.
        """
        return rx.transitivity(G)

    @staticmethod
    def diameter_dijkstra(
        G: rx.PyGraph | rx.PyDiGraph,
        weight_fn=None,
        disconnected_ok: bool = False,
        weak_for_directed: bool = True,
    ) -> float:
        """
        All-pairs Dijkstra diameter.
        For directed graphs defaults to weak diameter (undirected view).

        NOTE: This is expensive (all-pairs shortest paths).
        Disabled by default for large connectome runs in specs below.
        """
        n = G.num_nodes()
        if n <= 1:
            return 0.0

        work = G
        if isinstance(G, rx.PyDiGraph) and weak_for_directed:
            work = G.to_undirected(multigraph=G.multigraph)

        if isinstance(work, rx.PyDiGraph):
            dist = rx.digraph_all_pairs_dijkstra_path_lengths(work, lambda _: 1.0)
        else:
            dist = rx.graph_all_pairs_dijkstra_path_lengths(work, lambda _: 1.0)

        max_d = 0.0
        # Missing targets in a row => unreachable
        for _u, row in dist.items():
            if not disconnected_ok and len(row) < n - 1:
                return math.inf
            for _v, d in row.items():
                if d is None or math.isinf(d):
                    if not disconnected_ok:
                        return math.inf
                    continue
                if d > max_d:
                    max_d = d
        return max_d

    @staticmethod
    def diameter_approx(
        G: rx.PyGraph | rx.PyDiGraph,
        *,
        num_seeds: int = 64,
        weak_for_directed: bool = True,
        disconnected_ok: bool = True,
    ) -> float:
        """
        Fast approximate diameter via BFS from a small number of seeds.

        - Directed graphs are treated as weak/undirected by default.
        - Returns max shortest-path length observed from sampled seeds.
        - If disconnected_ok=False and any BFS doesn't reach all nodes, returns inf.

        Cost: O(num_seeds * (n+m)) with small num_seeds.
        """
        n = G.num_nodes()
        if n <= 1:
            return 0.0

        work = G
        if isinstance(G, rx.PyDiGraph) and weak_for_directed:
            work = G.to_undirected(multigraph=G.multigraph)

        # We only BFS on an undirected PyGraph
        if isinstance(work, rx.PyDiGraph):
            # Should not happen with weak_for_directed=True, but safe fallback
            work = work.to_undirected(multigraph=work.multigraph)

        seeds = RxInvariants._pick_seeds(n, num_seeds)
        max_d = 0.0
        for s in seeds:
            dist = RxInvariants._bfs_distances_undirected(work, s)
            if not disconnected_ok and len(dist) < n:
                return math.inf
            local_max = max(dist.values()) if dist else 0
            if local_max > max_d:
                max_d = local_max
        return float(max_d)

    @staticmethod
    def triangle_count_avg(G: rx.PyGraph | rx.PyDiGraph) -> float:
        """
        Average triangles per node (matches NX spec).
        For directed graphs, uses weak/undirected view.

        NOTE: Explicit triangle enumeration; can get expensive
        if max degree grows. Disabled by default for large connectomes
        in specs below.
        """
        UG = RxInvariants._to_undirected_if_needed(G)
        n = UG.num_nodes()
        if n == 0:
            return 0.0

        tri_times3 = 0
        for u in UG.node_indices():
            nbrs = list(UG.neighbors(u))
            k = len(nbrs)
            if k < 2:
                continue
            for i in range(k):
                v = nbrs[i]
                for j in range(i + 1, k):
                    w = nbrs[j]
                    if UG.has_edge(v, w):
                        tri_times3 += 1

        triangles = tri_times3 // 3
        return triangles / n

    @staticmethod
    def giant_component_fraction(G: rx.PyGraph | rx.PyDiGraph) -> float:
        """
        Largest weakly connected component fraction for digraphs;
        largest connected component for undirected.
        """
        n = G.num_nodes()
        if n == 0:
            return 0.0

        if isinstance(G, rx.PyDiGraph):
            UG = G.to_undirected(multigraph=G.multigraph)
            comps = rx.connected_components(UG)
        else:
            comps = rx.connected_components(G)

        largest = max(comps, key=len)
        return len(largest) / n

    @staticmethod
    def num_components(G: rx.PyGraph | rx.PyDiGraph) -> float:
        """
        Number of weakly connected components (directed -> undirected view).
        Cost: O(n+m).
        """
        if isinstance(G, rx.PyDiGraph):
            UG = G.to_undirected(multigraph=G.multigraph)
            comps = rx.connected_components(UG)
        else:
            comps = rx.connected_components(G)
        return float(len(comps))

    @staticmethod
    def component_size_cv(G: rx.PyGraph | rx.PyDiGraph) -> float:
        """
        CV of component sizes (weak components if directed).
        Cost dominated by connectivity: O(n+m).
        """
        n = G.num_nodes()
        if n == 0:
            return 0.0

        if isinstance(G, rx.PyDiGraph):
            UG = G.to_undirected(multigraph=G.multigraph)
            comps = rx.connected_components(UG)
        else:
            comps = rx.connected_components(G)

        sizes = [len(c) for c in comps]
        if not sizes:
            return 0.0
        mean_s = sum(sizes) / len(sizes)
        if mean_s == 0:
            return 0.0
        var_s = sum((s - mean_s) ** 2 for s in sizes) / len(sizes)
        return math.sqrt(var_s) / mean_s

    @staticmethod
    def kcore_max(G: rx.PyGraph | rx.PyDiGraph) -> float:
        """
        Degeneracy / maximum k-core level.
        Implemented via linear-time peeling on an undirected view.

        Cost: O(n+m).
        """
        UG = RxInvariants._to_undirected_if_needed(G)
        n = UG.num_nodes()
        if n == 0:
            return 0.0

        # Build adjacency lists once
        adj: dict[int, set[int]] = {u: set(UG.neighbors(u)) for u in UG.node_indices()}
        deg: dict[int, int] = {u: len(adj[u]) for u in adj}

        # Bucket queue by degree
        max_deg = max(deg.values(), default=0)
        buckets: list[list[int]] = [[] for _ in range(max_deg + 1)]
        for u, d in deg.items():
            buckets[d].append(u)

        core = 0
        removed = set()

        current_deg = 0
        for current_deg in range(max_deg + 1):
            stack = buckets[current_deg]
            while stack:
                u = stack.pop()
                if u in removed:
                    continue
                removed.add(u)
                core = max(core, current_deg)
                for v in list(adj[u]):
                    if v in removed:
                        continue
                    dv = deg[v]
                    if dv <= current_deg:
                        continue
                    # decrement v degree, move to lower bucket
                    deg[v] = dv - 1
                    buckets[dv - 1].append(v)
                    adj[v].discard(u)

        return float(core)

    @staticmethod
    def top1pct_degree_mass(
        G: rx.PyGraph | rx.PyDiGraph, *, frac: float = 0.01
    ) -> float:
        """
        Fraction of total degree accounted for by top `frac` nodes by degree.
        Cost: O(n log n) due to sorting.
        """
        n = G.num_nodes()
        if n == 0:
            return 0.0

        degs = [RxInvariants._degree(G, i) for i in G.node_indices()]
        total = sum(degs)
        if total == 0:
            return 0.0

        k = max(1, int(math.ceil(frac * n)))
        top_sum = sum(sorted(degs, reverse=True)[:k])
        return top_sum / total

    @staticmethod
    def degree_entropy(G: rx.PyGraph | rx.PyDiGraph, *, base: float = math.e) -> float:
        n = G.num_nodes()
        if n == 0:
            return 0.0

        degs = [RxInvariants._degree(G, i) for i in G.node_indices()]
        total = sum(degs)
        if total == 0:
            return 0.0

        log = math.log if base == math.e else (lambda x: math.log(x, base))
        return -sum((d / total) * log(d / total) for d in degs if d > 0)

    @staticmethod
    def average_clustering(G: rx.PyGraph | rx.PyDiGraph) -> float:
        """
        Average local clustering coefficient.
        Directed graphs are treated as weak/undirected.
        """
        UG = RxInvariants._to_undirected_if_needed(G)
        n = UG.num_nodes()
        if n == 0:
            return 0.0

        total_c = 0.0
        for u in UG.node_indices():
            nbrs = list(UG.neighbors(u))
            k = len(nbrs)
            if k < 2:
                continue

            links = 0
            for i in range(k):
                v = nbrs[i]
                for j in range(i + 1, k):
                    w = nbrs[j]
                    if UG.has_edge(v, w):
                        links += 1

            total_c += (2 * links) / (k * (k - 1))

        return total_c / n

    @staticmethod
    def degree_assortativity_coefficient(G: rx.PyGraph | rx.PyDiGraph) -> float:
        """
        Pearson correlation of endpoint total degrees across edges.
        Directed graphs are treated as weak/undirected (edge direction ignored).
        """
        UG = RxInvariants._to_undirected_if_needed(G)
        m = UG.num_edges()
        if m == 0:
            return math.nan

        deg = {i: UG.degree(i) for i in UG.node_indices()}

        sum_jk = 0.0
        sum_j_plus_k = 0.0
        sum_j2_plus_k2 = 0.0

        for u, v, _w in UG.weighted_edge_list():
            ju = deg[u]
            kv = deg[v]
            sum_jk += ju * kv
            sum_j_plus_k += ju + kv
            sum_j2_plus_k2 += ju * ju + kv * kv

        m_inv = 1.0 / m
        term1 = m_inv * sum_jk
        term2 = (m_inv * 0.5 * sum_j_plus_k) ** 2
        term3 = m_inv * 0.5 * sum_j2_plus_k2

        denom = term3 - term2
        if denom == 0:
            return math.nan

        return (term1 - term2) / denom

    @staticmethod
    def reciprocity(G: rx.PyGraph | rx.PyDiGraph) -> float:
        """
        For directed graphs: fraction of edges with a reverse partner.
        For undirected graphs: nan (undefined).
        """
        if not isinstance(G, rx.PyDiGraph):
            return math.nan

        m = G.num_edges()
        if m == 0:
            return math.nan

        reciprocal_edges = 0
        for u, v, _w in G.weighted_edge_list():
            if u == v:
                continue
            if G.has_edge(v, u):
                reciprocal_edges += 1

        return reciprocal_edges / m

    @staticmethod
    def molloy_reed_index(G: rx.PyGraph | rx.PyDiGraph) -> float:
        n = G.num_nodes()
        if n == 0:
            return 0.0

        degs = [RxInvariants._degree(G, i) for i in G.node_indices()]
        mean_k = sum(degs) / n
        if mean_k == 0:
            return 0.0

        mean_k2 = sum(d * d for d in degs) / n
        return mean_k2 / mean_k

    @staticmethod
    def degree_cv(G: rx.PyGraph | rx.PyDiGraph) -> float:
        degs = [RxInvariants._degree(G, i) for i in G.node_indices()]
        n = len(degs)
        if n == 0:
            return 0.0
        mean_k = sum(degs) / n
        if mean_k == 0:
            return 0.0
        var_k = sum((d - mean_k) ** 2 for d in degs) / n
        return math.sqrt(var_k) / mean_k

    @staticmethod
    def degree_gini(G: rx.PyGraph | rx.PyDiGraph) -> float:
        degs = sorted(RxInvariants._degree(G, i) for i in G.node_indices())
        n = len(degs)
        if n == 0:
            return 0.0
        total = sum(degs)
        if total == 0:
            return 0.0

        weighted_sum = sum((i + 1) * x for i, x in enumerate(degs))
        return (2 * weighted_sum) / (n * total) - (n + 1) / n


# -----------------------------
# networkx invariants
# -----------------------------
class NxInvariants:
    @staticmethod
    def density(G: nx.Graph) -> float:
        return nx.density(G)

    @staticmethod
    def average_clustering(G: nx.Graph) -> float:
        return nx.average_clustering(G)

    @staticmethod
    def transitivity(G: nx.Graph) -> float:
        return nx.transitivity(G)

    @staticmethod
    def average_degree(G: nx.Graph) -> float:
        n = G.number_of_nodes()
        if n == 0:
            return 0.0
        return (2 * G.number_of_edges()) / n

    @staticmethod
    def degree_assortativity(G: nx.Graph) -> float:
        return nx.degree_assortativity_coefficient(G)

    @staticmethod
    def triangle_count_avg(G: nx.Graph) -> float:
        n = G.number_of_nodes()
        if n == 0:
            return 0.0
        return sum(nx.triangles(G).values()) / n

    @staticmethod
    def diameter_undirected(G: nx.Graph) -> float:
        return nx.diameter(nx.Graph(G))

    @staticmethod
    def diameter_approx(
        G: nx.Graph,
        *,
        num_seeds: int = 64,
        weak_for_directed: bool = True,
        disconnected_ok: bool = True,
    ) -> float:
        """
        Approx diameter via BFS from sampled seeds.
        Cost: O(num_seeds * (n+m)).
        """
        if G.number_of_nodes() <= 1:
            return 0.0

        work = G
        if weak_for_directed and G.is_directed():
            work = nx.Graph(G)

        n = work.number_of_nodes()
        nodes = list(work.nodes())
        if n == 0:
            return 0.0

        k = min(num_seeds, n)
        if k == n:
            seeds = nodes
        else:
            step = max(1, n // k)
            seeds = nodes[0::step][:k]

        max_d = 0
        for s in seeds:
            dist = nx.single_source_shortest_path_length(work, s)
            if not disconnected_ok and len(dist) < n:
                return math.inf
            local_max = max(dist.values()) if dist else 0
            max_d = max(max_d, local_max)

        return float(max_d)

    @staticmethod
    def giant_component_fraction(G: nx.Graph) -> float:
        n = G.number_of_nodes()
        if n == 0:
            return 0.0
        comps = (
            nx.weakly_connected_components(G)
            if G.is_directed()
            else nx.connected_components(G)
        )
        largest = max(comps, key=len)
        return len(largest) / n

    @staticmethod
    def num_components(G: nx.Graph) -> float:
        comps = (
            nx.weakly_connected_components(G)
            if G.is_directed()
            else nx.connected_components(G)
        )
        return float(sum(1 for _ in comps))

    @staticmethod
    def component_size_cv(G: nx.Graph) -> float:
        n = G.number_of_nodes()
        if n == 0:
            return 0.0
        comps = (
            nx.weakly_connected_components(G)
            if G.is_directed()
            else nx.connected_components(G)
        )
        sizes = [len(c) for c in comps]
        if not sizes:
            return 0.0
        mean_s = sum(sizes) / len(sizes)
        if mean_s == 0:
            return 0.0
        var_s = sum((s - mean_s) ** 2 for s in sizes) / len(sizes)
        return math.sqrt(var_s) / mean_s

    @staticmethod
    def kcore_max(G: nx.Graph) -> float:
        work = nx.Graph(G) if G.is_directed() else G
        if work.number_of_nodes() == 0:
            return 0.0
        core_num = nx.core_number(work)  # O(n+m)
        return float(max(core_num.values(), default=0))

    @staticmethod
    def top1pct_degree_mass(G: nx.Graph, *, frac: float = 0.01) -> float:
        n = G.number_of_nodes()
        if n == 0:
            return 0.0
        degs = [d for _, d in G.degree()]
        total = sum(degs)
        if total == 0:
            return 0.0
        k = max(1, int(math.ceil(frac * n)))
        top_sum = sum(sorted(degs, reverse=True)[:k])
        return top_sum / total

    @staticmethod
    def degree_entropy(G: nx.Graph) -> float:
        degs = dict(G.degree())
        total = sum(degs.values())
        if total == 0:
            return 0.0
        return -sum(
            p * math.log(p) for p in (d / total for d in degs.values()) if p > 0
        )

    @staticmethod
    def reciprocity(G: nx.Graph) -> float:
        return nx.reciprocity(G)

    @staticmethod
    def molloy_reed_index(G: nx.Graph) -> float:
        n = G.number_of_nodes()
        if n == 0:
            return 0.0
        degs = dict(G.degree()).values()
        mean_k = sum(degs) / n
        if mean_k == 0:
            return 0.0
        mean_k2 = sum(d * d for d in degs) / n
        return mean_k2 / mean_k

    @staticmethod
    def degree_cv(G: nx.Graph) -> float:
        degs = list(dict(G.degree()).values())
        if not degs:
            return 0.0
        mean_k = sum(degs) / len(degs)
        if mean_k == 0:
            return 0.0
        var_k = sum((d - mean_k) ** 2 for d in degs) / len(degs)
        return math.sqrt(var_k) / mean_k

    @staticmethod
    def degree_gini(G: nx.Graph) -> float:
        degs = sorted(dict(G.degree()).values())
        n = len(degs)
        if n == 0:
            return 0.0
        total = sum(degs)
        if total == 0:
            return 0.0

        # Gini = (2 * sum_i i*x_i)/(n*sum x) - (n+1)/n
        weighted_sum = sum((i + 1) * x for i, x in enumerate(degs))
        return (2 * weighted_sum) / (n * total) - (n + 1) / n


# -----------------------------
# invariant specs
# -----------------------------
@dataclass(frozen=True)
class InvariantSpec:
    name: str
    func_nx: Callable[[nx.Graph], float]
    func_rx: Callable[[Any], float]
    ylabel: str = ""
    default_on: str = "graph"
    on_overrides: Mapping[str, str] = field(default_factory=dict)
    contactome_enabled: bool = True
    connectome_enabled: bool = True

    def target_for(self, dataset: str) -> str:
        return self.on_overrides.get(dataset, self.default_on)


_INVARIANT_SPECS: tuple[InvariantSpec, ...] = (
    InvariantSpec(
        name="density",
        func_nx=NxInvariants.density,
        func_rx=RxInvariants.density,
        ylabel="Density",
        on_overrides={DATASET_CONTACTOME: "undirected_graph"},
    ),
    InvariantSpec(
        name="average_clustering",
        func_nx=NxInvariants.average_clustering,
        func_rx=RxInvariants.average_clustering,
        ylabel="Average Clustering Coefficient",
        on_overrides={DATASET_CONTACTOME: "undirected_graph"},
    ),
    InvariantSpec(
        name="transitivity",
        func_nx=NxInvariants.transitivity,
        func_rx=RxInvariants.transitivity,
        ylabel="Transitivity",
        on_overrides={DATASET_CONTACTOME: "undirected_graph"},
    ),
    InvariantSpec(
        name="average_degree",
        func_nx=NxInvariants.average_degree,
        func_rx=RxInvariants.average_degree,
        ylabel="Average Degree",
        on_overrides={DATASET_CONTACTOME: "undirected_graph"},
    ),
    InvariantSpec(
        name="degree_assortativity",
        func_nx=NxInvariants.degree_assortativity,
        func_rx=RxInvariants.degree_assortativity_coefficient,
        ylabel="Degree Assortativity",
        on_overrides={DATASET_CONTACTOME: "undirected_graph"},
    ),
    InvariantSpec(
        name="triangle_count",
        func_nx=NxInvariants.triangle_count_avg,
        func_rx=RxInvariants.triangle_count_avg,
        ylabel="Average Triangle Count",
        default_on="undirected_graph",
        on_overrides={DATASET_CONTACTOME: "undirected_graph"},
        # Explicit triangle enumeration; disable for big connectomes by default.
        connectome_enabled=False,
    ),
    InvariantSpec(
        name="diameter",
        func_nx=NxInvariants.diameter_undirected,
        func_rx=RxInvariants.diameter_dijkstra,
        ylabel="Diameter",
        default_on="lcc_graph",
        contactome_enabled=False,
        # All-pairs shortest paths; disable for big connectomes by default.
        connectome_enabled=False,
    ),
    InvariantSpec(
        name="diameter_approx",
        func_nx=NxInvariants.diameter_approx,
        func_rx=RxInvariants.diameter_approx,
        ylabel="Approx. Diameter",
        default_on="lcc_graph",
        contactome_enabled=False,
    ),
    InvariantSpec(
        name="giant_component_fraction",
        func_nx=NxInvariants.giant_component_fraction,
        func_rx=RxInvariants.giant_component_fraction,
        ylabel="Giant Component Fraction",
        contactome_enabled=False,
    ),
    InvariantSpec(
        name="num_components",
        func_nx=NxInvariants.num_components,
        func_rx=RxInvariants.num_components,
        ylabel="# Components",
        contactome_enabled=False,
    ),
    InvariantSpec(
        name="component_size_cv",
        func_nx=NxInvariants.component_size_cv,
        func_rx=RxInvariants.component_size_cv,
        ylabel="Component Size CV",
        contactome_enabled=False,
    ),
    InvariantSpec(
        name="kcore_max",
        func_nx=NxInvariants.kcore_max,
        func_rx=RxInvariants.kcore_max,
        ylabel="Max k-core (Degeneracy)",
        on_overrides={DATASET_CONTACTOME: "undirected_graph"},
        contactome_enabled=False,
    ),
    InvariantSpec(
        name="top1pct_degree_mass",
        func_nx=NxInvariants.top1pct_degree_mass,
        func_rx=RxInvariants.top1pct_degree_mass,
        ylabel="Top-1% Degree Mass",
        contactome_enabled=False,
    ),
    InvariantSpec(
        name="degree_entropy",
        func_nx=NxInvariants.degree_entropy,
        func_rx=RxInvariants.degree_entropy,
        ylabel="Degree Entropy",
        contactome_enabled=False,
        connectome_enabled=False,
    ),
    InvariantSpec(
        name="reciprocity",
        func_nx=NxInvariants.reciprocity,
        func_rx=RxInvariants.reciprocity,
        ylabel="Reciprocity",
        contactome_enabled=False,
    ),
    InvariantSpec(
        name="molloy_reed_index",
        func_nx=NxInvariants.molloy_reed_index,
        func_rx=RxInvariants.molloy_reed_index,
        ylabel="Molloy–Reed Index",
        on_overrides={DATASET_CONTACTOME: "undirected_graph"},
    ),
    InvariantSpec(
        name="degree_cv",
        func_nx=NxInvariants.degree_cv,
        func_rx=RxInvariants.degree_cv,
        ylabel="Degree CV",
        contactome_enabled=False,
    ),
    InvariantSpec(
        name="degree_gini",
        func_nx=NxInvariants.degree_gini,
        func_rx=RxInvariants.degree_gini,
        ylabel="Degree Gini",
        contactome_enabled=False,
    ),
)


def select_invariants(
    dataset: str, *, include_disabled: bool = False
) -> dict[str, InvariantSpec]:
    """Select invariant specs for the requested dataset.

    Args:
        dataset: Dataset identifier (e.g., contactome/connectome).
        include_disabled: Whether to include invariants disabled by default.

    Returns:
        A mapping of invariant name to ``InvariantSpec``.
    """
    selected: list[InvariantSpec] = []
    for spec in _INVARIANT_SPECS:
        enabled = (
            spec.contactome_enabled
            if dataset == DATASET_CONTACTOME
            else spec.connectome_enabled
        )
        if enabled or include_disabled:
            selected.append(spec)
    return {spec.name: spec for spec in selected}


# -----------------------------
# computation
# -----------------------------
def compute_invariants(
    graphs: Mapping[str, Mapping[str, nx.Graph]],
    dataset: str,
    specs: Mapping[str, InvariantSpec] | None = None,
    parallel: bool | int = False,
    progress: bool = False,
    use_rustworkx: bool = False,
) -> dict[str, dict[str, float]]:
    """Compute invariant values for a bundle of graphs.

    Args:
        graphs: Mapping of graph_id to graph bundles with named variants.
        dataset: Dataset identifier (e.g., contactome/connectome).
        specs: Optional mapping of invariant specs to compute.
        parallel: ``True``/``-1`` for all cores, ``0``/``1`` for serial, or
            an explicit job count.
        progress: Whether to show tqdm progress bars.
        use_rustworkx: Whether to call ``func_rx`` instead of ``func_nx``.

    Returns:
        Mapping from invariant name to per-graph values.

    Raises:
        KeyError: If a graph bundle lacks the target graph variant.
    """
    chosen_specs = specs or select_invariants(dataset)

    invariants_per_graph: dict[str, dict[str, float]] = {
        name: {graph_id: None for graph_id in graphs}  # type: ignore[typeddict-item]
        for name in chosen_specs
    }

    def _compute_one(
        graph_id: str,
        graph_bundle: Mapping[str, nx.Graph],
        spec_name: str,
        spec: InvariantSpec,
    ) -> tuple[str, str, float]:
        target_key = spec.target_for(dataset)
        target_graph = graph_bundle.get(target_key, graph_bundle.get("graph"))
        if target_graph is None:
            raise KeyError(
                f"Graph bundle for {graph_id} missing target '{target_key}' and 'graph'."
            )

        value = (
            spec.func_rx(target_graph) if use_rustworkx else spec.func_nx(target_graph)
        )
        return spec_name, graph_id, value

    # Normalize parallel flag
    if parallel is True:
        parallel = -1

    # Serial path
    if parallel in [0, 1, False]:
        iterator = graphs.items()
        if progress:
            iterator = tqdm(list(iterator), disable=not progress)

        for graph_id, graph_bundle in iterator:
            for spec_name, spec in chosen_specs.items():
                name, gid, val = _compute_one(graph_id, graph_bundle, spec_name, spec)
                invariants_per_graph[name][gid] = val
        return invariants_per_graph

    # Parallel path: each (graph, invariant) is a task
    tasks = [
        (graph_id, graph_bundle, spec_name, spec)
        for graph_id, graph_bundle in graphs.items()
        for spec_name, spec in chosen_specs.items()
    ]

    task_iter = tasks
    if progress:
        task_iter = tqdm(tasks, disable=not progress)

    results = Parallel(n_jobs=parallel)(
        delayed(_compute_one)(graph_id, graph_bundle, spec_name, spec)
        for graph_id, graph_bundle, spec_name, spec in task_iter
    )

    for spec_name, graph_id, value in results:
        invariants_per_graph[spec_name][graph_id] = value

    return invariants_per_graph


__all__ = [
    "InvariantSpec",
    "DATASET_CONTACTOME",
    "DATASET_CONNECTOME",
    "select_invariants",
    "compute_invariants",
]
