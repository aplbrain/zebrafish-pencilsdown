import polars as pl
import rustworkx as rx
from zfish.invariants import RxInvariants
import argparse

edit_counts = [
  ("28841c8277e044a7b187dda03e18da13", 0.0),
  ("305b514e13d0411c8fe6c789935e7030", 200758.0),
  ("a0dfa4f260244946b7abbab4dcd2cc86", 192992.0),
  ("0c6f54d9677f4d3181eedfb272b1c0b0", 169685.0),
  ("dd7b7e43bd0d4054aeb554633dfc4857", 119312.0),
  ("34d7acb0167d438baa85c47ea0a739d4", 170506.0),
  ("52a13328874c4bb7b15dc4280da26576", 188985.0),
  ("45bdcf98287347a39ee5eccb8a00e409", 175148.0),
  ("54c2700f0e204c9ab2a64a245cf925b0", 109418.0),
  ("e44b9e8ae63a4e3fa9e978e088348254", 373674.0),
  ("ef000defa00c42b7b5be64b81663aa25", 31570)
]


def build_graph(
    path: str,
    src: str = "pre_body",
    dst: str = "post_body",
    w: str = "weight",
    batch_rows: int = 2_000_000,  # kept for signature compatibility
    aggregate_duplicates: bool = True,
):
    df = pl.scan_parquet(path).select([src, dst, w])

    if aggregate_duplicates:
        df = df.group_by([src, dst]).agg(pl.col(w).sum().alias(w))

    # Build node table
    nodes = (
        pl.concat([
            df.select(pl.col(src).alias("node")),
            df.select(pl.col(dst).alias("node")),
        ])
        .unique()
        .with_row_index("id")
    )

    # Relabel edges to integer node ids
    edges = (
        df.join(nodes, left_on=src, right_on="node")
        .rename({"id": "src_id"})
        .join(nodes, left_on=dst, right_on="node")
        .rename({"id": "dst_id"})
        .select(["src_id", "dst_id", w])
        .collect()
    )

    print(edges.select(pl.max("src_id"), pl.max("dst_id")), flush=True)

    num_nodes = nodes.select(pl.len()).collect().item()

    G = rx.PyDiGraph()

    # Add all nodes first; payload can just be the integer id or None
    G.add_nodes_from(range(num_nodes))

    # Safe to add one edge per (src, dst)
    edge_list = list(
        zip(
            edges.get_column("src_id").to_list(),
            edges.get_column("dst_id").to_list(),
            edges.get_column(w).to_list(),
        )
    )
    G.add_edges_from(edge_list)

    return G

invariants_per_graph = {}

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="A simple script using argparse.")
    parser.add_argument("checkpoint_no")
    args = parser.parse_args()

    print(args.checkpoint_no)
    G = build_graph(f"graphs/{args.checkpoint_no}.parquet")
    print(f"nodes: {G.num_nodes()}", flush=True)
    print(f"edges: {G.num_edges()}", flush=True)
    print(f"diameter approx: {RxInvariants.diameter_approx(G)}", flush=True)
    print(f"molloy reed: {RxInvariants.molloy_reed_index(G)}", flush=True)
    print(f"approx average clustering: {RxInvariants.average_clustering(G, num=10000)}", flush=True)
    print(f"average degree: {RxInvariants.average_degree(G)}", flush=True)
    print(f"approx triangle count: {RxInvariants.triangle_count_avg(G, num=10000)}", flush=True)
    print(f"reciprocity: {RxInvariants.reciprocity(G)}", flush=True)
    print(f"transitivity: {RxInvariants.transitivity(G)}", flush=True)
    print(f"degree assortativity: {RxInvariants.degree_assortativity_coefficient(G)}", flush=True)
    print(f"degree entropy: {RxInvariants.degree_entropy(G)}", flush=True)
    print(f"giant component frac: {RxInvariants.giant_component_fraction(G)}", flush=True)
    print(f"density: {RxInvariants.density(G)}", flush=True)
    print(f"kcore max: {RxInvariants.kcore_max(G)}", flush=True)
    print(f"degree gini: {RxInvariants.degree_gini(G)}", flush=True)
    print(f"num components: {RxInvariants.num_components(G)}", flush=True)


# with open("invariants_per_connectome.json", "w") as f:
#     import json
#     json.dump(invariants_per_graph, f, indent=2)