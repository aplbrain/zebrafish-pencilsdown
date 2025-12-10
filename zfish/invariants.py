from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable, Mapping
from joblib import Parallel, delayed
from tqdm import tqdm

import networkx as nx

DATASET_CONTACTOME = "contactome"
DATASET_CONNECTOME = "connectome"


@dataclass(frozen=True)
class InvariantSpec:
    name: str
    func: Callable[[nx.Graph], float]
    ylabel: str
    default_on: str = "graph"
    on_overrides: Mapping[str, str] = field(default_factory=dict)
    contactome_enabled: bool = True
    connectome_enabled: bool = True

    def target_for(self, dataset: str) -> str:
        return self.on_overrides.get(dataset, self.default_on)


_INVARIANT_SPECS: tuple[InvariantSpec, ...] = (
    InvariantSpec(
        name="density",
        func=nx.density,
        ylabel="Density",
        on_overrides={DATASET_CONTACTOME: "undirected_graph"},
    ),
    InvariantSpec(
        name="average_clustering",
        func=nx.average_clustering,
        ylabel="Average Clustering Coefficient",
        on_overrides={DATASET_CONTACTOME: "undirected_graph"},
    ),
    InvariantSpec(
        name="transitivity",
        func=nx.transitivity,
        ylabel="Transitivity",
        on_overrides={DATASET_CONTACTOME: "undirected_graph"},
    ),
    InvariantSpec(
        name="average_degree",
        func=lambda g: sum(dict(g.degree()).values()) / g.number_of_nodes(),
        ylabel="Average Degree",
        on_overrides={DATASET_CONTACTOME: "undirected_graph"},
    ),
    InvariantSpec(
        name="degree_assortativity",
        func=nx.degree_assortativity_coefficient,
        ylabel="Degree Assortativity",
        on_overrides={DATASET_CONTACTOME: "undirected_graph"},
    ),
    InvariantSpec(
        name="triangle_count",
        func=lambda g: sum(nx.triangles(g).values()) / g.number_of_nodes(),
        ylabel="Average Triangle Count",
        default_on="undirected_graph",
        on_overrides={DATASET_CONTACTOME: "undirected_graph"},
    ),
    InvariantSpec(
        name="diameter",
        func=lambda g: nx.diameter(nx.Graph(g)),
        ylabel="Diameter",
        default_on="lcc_graph",
        contactome_enabled=False,
    ),
    InvariantSpec(
        name="giant_component_fraction",
        func=lambda g: len(
            max(
                (
                    nx.weakly_connected_components(g)
                    if g.is_directed()
                    else nx.connected_components(g)
                ),
                key=len,
            )
        )
        / g.number_of_nodes(),
        ylabel="Giant Component Fraction",
        contactome_enabled=False,
    ),
    InvariantSpec(
        name="degree_entropy",
        func=lambda g: -sum(
            p * math.log(p)
            for p in (
                d / sum(dict(g.degree()).values()) for d in dict(g.degree()).values()
            )
            if p > 0
        ),
        ylabel="Degree Entropy",
        contactome_enabled=False,
    ),
    InvariantSpec(
        name="reciprocity",
        func=nx.reciprocity,
        ylabel="Reciprocity",
        contactome_enabled=False,
    ),
    InvariantSpec(
        name="molloy_reed_index",
        func=lambda g: (
            (sum(d**2 for d in dict(g.degree()).values()) / g.number_of_nodes())
            / (sum(dict(g.degree()).values()) / g.number_of_nodes())
        ),
        ylabel="Molloy–Reed Index",
        on_overrides={DATASET_CONTACTOME: "undirected_graph"},
    ),
)


def select_invariants(
    dataset: str, *, include_disabled: bool = False
) -> dict[str, InvariantSpec]:
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


def compute_invariants(
    graphs: Mapping[str, Mapping[str, nx.Graph]],
    dataset: str,
    specs: Mapping[str, InvariantSpec] | None = None,
    parallel: bool | int = False,
    progress: bool = False,
) -> dict[str, dict[str, float]]:
    chosen_specs = specs or select_invariants(dataset)
    invariants_per_graph: dict[str, dict[str, float]] = {
        name: {graph_id: None for graph_id in graphs} for name in chosen_specs
    }

    def _compute_invariants_for_graph(
        graph_id: str,
        graph_bundle: Mapping[str, nx.Graph],
        specs: Mapping[str, InvariantSpec],
        dataset: str,
    ) -> tuple[str, dict[str, float]]:
        invariants: dict[str, float] = {}
        for name, spec in specs.items():
            target_key = spec.target_for(dataset)
            target_graph = graph_bundle.get(target_key, graph_bundle.get("graph"))
            value = spec.func(target_graph)
            invariants[name] = value
        return graph_id, invariants

    if parallel in [0, 1, False]:
        for graph_id, graph_bundle in tqdm(graphs.items(), disable=not progress):
            _, invariants = _compute_invariants_for_graph(
                graph_id, graph_bundle, chosen_specs, dataset
            )
            for name, value in invariants.items():
                invariants_per_graph[name][graph_id] = value
        return invariants_per_graph
    else:
        results = Parallel(n_jobs=parallel)(
            delayed(_compute_invariants_for_graph)(
                graph_id, graph_bundle, chosen_specs, dataset
            )
            for graph_id, graph_bundle in tqdm(graphs.items(), disable=not progress)
        )
        for graph_id, invariants in results:
            for name, value in invariants.items():
                invariants_per_graph[name][graph_id] = value
        return invariants_per_graph


__all__ = [
    "InvariantSpec",
    "DATASET_CONTACTOME",
    "DATASET_CONNECTOME",
    "select_invariants",
    "compute_invariants",
]
