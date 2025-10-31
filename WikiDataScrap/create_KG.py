import json
import networkx as nx
import matplotlib.pyplot as plt

# Relative path to your Wikidata JSON file
INPUT_FILE = "WikiDataScrap/detailed_info_turkish/Q863496.json"

def load_json(path):
    """Load JSON data from file."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def build_knowledge_graph(data):
    """Build a Knowledge Graph (KG) from Wikidata-style JSON."""
    G = nx.MultiDiGraph()

    for entity_id, entity_data in data.items():
        # Add entity node
        label = entity_data.get("label_tr", entity_id)
        G.add_node(entity_id, label=label)

        # Extract claims (relations)
        claims = entity_data.get("claims", {})
        for prop, statements in claims.items():
            for stmt in statements:
                mainsnak = stmt.get("mainsnak", {})
                datavalue = mainsnak.get("datavalue", {})
                value = datavalue.get("value")

                if isinstance(value, dict) and value.get("entity-type") == "item":
                    target_id = value.get("id")
                    G.add_node(target_id, label=target_id)
                    G.add_edge(entity_id, target_id, property=prop)
                elif isinstance(value, str):
                    # Handle literal value as a separate node
                    literal_node = f"{prop}:{value}"
                    G.add_node(literal_node, label=value)
                    G.add_edge(entity_id, literal_node, property=prop)
    return G

def visualize_graph(G, limit=40):
    """Visualize the Knowledge Graph with edge labels."""
    plt.figure(figsize=(14, 12))

    # Limit number of nodes for clarity
    sub_nodes = list(G.nodes)[:limit]
    subgraph = G.subgraph(sub_nodes)

    # Compute layout
    pos = nx.spring_layout(subgraph, k=0.5, seed=42)

    # Node labels
    node_labels = {n: d.get("label", n) for n, d in subgraph.nodes(data=True)}
    edge_labels = {(u, v): d.get("property", "") for u, v, d in subgraph.edges(data=True)}

    # Draw
    nx.draw_networkx_nodes(subgraph, pos, node_color="skyblue", node_size=900, alpha=0.8)
    nx.draw_networkx_labels(subgraph, pos, labels=node_labels, font_size=8, font_weight="bold")
    nx.draw_networkx_edges(subgraph, pos, edge_color="gray", arrows=True, arrowsize=15, width=1)
    nx.draw_networkx_edge_labels(subgraph, pos, edge_labels=edge_labels, font_size=7, label_pos=0.5)

    plt.title("Knowledge Graph (Property Relations Shown)", fontsize=14)
    plt.axis("off")
    plt.tight_layout()
    plt.show()

def main():
    print("Loading data...")
    data = load_json(INPUT_FILE)

    print("Building Knowledge Graph...")
    G = build_knowledge_graph(data)
    print(f"Graph built with {len(G.nodes)} nodes and {len(G.edges)} edges.")

    visualize_graph(G)

    # Save graph to Gephi-compatible file
    nx.write_gexf(G, "wikidata_kg.gexf")
    print("Knowledge Graph saved as wikidata_kg.gexf (for Gephi).")

if __name__ == "__main__":
    main()
