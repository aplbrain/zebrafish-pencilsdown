from typing import Union, overload
import math
import networkx as nx
import rustworkx as rx
import pathlib


@overload
def make_undirected(graph: nx.DiGraph) -> nx.Graph: ...
@overload
def make_undirected(graph: rx.PyDiGraph) -> rx.PyGraph: ...
def make_undirected(graph: Union[nx.DiGraph, rx.PyDiGraph]):
    if isinstance(graph, nx.DiGraph):
        return graph.to_undirected()
    if isinstance(graph, rx.PyDiGraph):
        g = rx.PyGraph()
        g.extend_from_edge_list(graph.edge_list())
        return g
    raise TypeError(f"Unsupported graph type: {type(graph)}")


@overload
def make_lcc(graph: nx.DiGraph) -> nx.DiGraph: ...
@overload
def make_lcc(graph: rx.PyDiGraph) -> rx.PyDiGraph: ...
def make_lcc(graph: Union[nx.DiGraph, rx.PyDiGraph]):
    if isinstance(graph, nx.DiGraph):
        return graph.subgraph(
            max(nx.strongly_connected_components(graph), key=len)
        ).copy()
    if isinstance(graph, rx.PyDiGraph):
        lcc_nodes = max(rx.strongly_connected_components(graph), key=len)
        return graph.subgraph(lcc_nodes).copy()
    raise TypeError(f"Unsupported graph type: {type(graph)}")


@overload
def make_lwcc_nodes(graph: nx.DiGraph) -> set[int]: ...
@overload
def make_lwcc_nodes(graph: rx.PyDiGraph) -> set[int]: ...
def make_lwcc_nodes(graph: Union[nx.DiGraph, rx.PyDiGraph]) -> set[int]:
    if isinstance(graph, nx.DiGraph):
        return max(nx.strongly_connected_components(graph), key=len)
    if isinstance(graph, rx.PyDiGraph):
        return max(rx.strongly_connected_components(graph), key=len)
    raise TypeError(f"Unsupported graph type: {type(graph)}")


class GraphUtils:
    @staticmethod
    def make_undirected(graph: Union[nx.DiGraph, rx.PyDiGraph]):
        return make_undirected(graph)

    @staticmethod
    def make_lcc(graph: Union[nx.DiGraph, rx.PyDiGraph]):
        return make_lcc(graph)

    @staticmethod
    def make_lwcc_nodes(graph: Union[nx.DiGraph, rx.PyDiGraph]) -> set[int]:
        return make_lwcc_nodes(graph)


def load_connectome_compound_key_csv_to_graph(csv_path: pathlib.Path) -> nx.DiGraph:
    # rows look like
    # graph_id,synapse_id
    # connectome-0k-101625,syn_x1000_y1093_z2152_pre37775021_post19204134
    G = nx.DiGraph()
    with open(csv_path, "r") as f:
        next(f)  # skip header
        for line in f:
            graph_id, synapse_id = line.strip().split(",")
            line_items = synapse_id.split("_")
            # either _, x, y, z, pre, post or _, x, y, z, pre, post, id
            if len(line_items) == 7:
                _, x, y, z, pre, post, _ = line_items
            elif len(line_items) == 6:
                _, x, y, z, pre, post = line_items
            else:
                raise ValueError(f"Unexpected synapse_id format: {synapse_id}")
            pre_id = pre[3:]  # remove 'pre' prefix
            post_id = post[4:]  # remove 'post' prefix
            # If the edge exists, increment weight, else set weight to 1
            if G.has_edge(pre_id, post_id):
                G[pre_id][post_id]["weight"] += 1
            else:
                G.add_edge(pre_id, post_id, weight=1)
    return G


def load_all_graphs_from_edgelists(
    edgelist_path: pathlib.Path,
    rustworkx: bool = True,
    remove_0: bool = True,
) -> dict[str, nx.DiGraph]:
    graphs = {}
    for edgelist_file in edgelist_path.glob("*.csv"):
        graph_name = edgelist_file.stem
        identifier = graph_name.split("-")[1]
        graph = load_connectome_compound_key_csv_to_graph(edgelist_file)
        if remove_0:
            graph.remove_nodes_from(["0"])
        if rustworkx:
            graphs[identifier] = rx.networkx_converter(graph)
        else:
            graphs[identifier] = graph

    return dict(sorted(graphs.items(), key=lambda item: int(item[0][:-1])))
