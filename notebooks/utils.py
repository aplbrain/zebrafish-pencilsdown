import pathlib
import networkx as nx


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
