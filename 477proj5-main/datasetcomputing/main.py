#!/usr/bin/env python3
"""
Build topological order + D3-friendly datasets from a GO OBO-Graphs JSON,
with fixes for sub/obj edge fields and predicate IRI normalization.

Examples
--------
# Slim-only view (goslim_drosophila), strict DAG (is_a only)
python make_go_topo.py goslim_drosophila.json --predicates is_a -o droso_slim

# Include part_of as well
python make_go_topo.py goslim_drosophila.json --predicates is_a,part_of -o droso_slim

# Restrict to biological_process namespace
python make_go_topo.py goslim_drosophila.json --namespace biological_process -o droso_bp

# Pull in ancestors of slim terms even if they aren't tagged as slim
python make_go_topo.py goslim_drosophila.json --include-ancestors -o droso_with_anc
"""

from __future__ import annotations
import json, csv, argparse, re, sys
from collections import defaultdict, deque
from typing import Dict, List, Tuple, Set

# ---------- normalization helpers

# Matches .../GO_0003677 or GO:0003677 endings
GO_IRI_RE = re.compile(r'(?:/|#)?GO[_:](\d+)$')

def norm_go_id(s: str | None) -> str | None:
    """Normalize 'http://.../GO_0003677' or 'GO:0003677' -> 'GO:0003677'."""
    if not s:
        return None
    m = GO_IRI_RE.search(s)
    return f"GO:{m.group(1)}" if m else s

def edge_field(e: dict, *keys) -> str | None:
    """Return the first present (non-None) edge field among given keys."""
    for k in keys:
        if k in e and e[k] is not None:
            return e[k]
    return None

def pred_name(p: str | None) -> str:
    """Normalize common GO/RO/BFO predicates to short names."""
    if not p:
        return ""
    # direct 'is_a'
    if p == "is_a" or p.endswith("is_a"):
        return "is_a"
    # part_of / has_part (BFO)
    if p.endswith("BFO_0000050") or p.endswith("BFO:0000050") or p.endswith("part_of"):
        return "part_of"
    if p.endswith("BFO_0000051") or p.endswith("BFO:0000051") or p.endswith("has_part"):
        return "has_part"
    # regulates family (RO)
    if p.endswith("RO_0002211") or p.endswith("regulates"):
        return "regulates"
    if p.endswith("RO_0002212") or p.endswith("positively_regulates"):
        return "positively_regulates"
    if p.endswith("RO_0002213") or p.endswith("negatively_regulates"):
        return "negatively_regulates"
    # fallback: trailing path/fragment token
    return p.rsplit("/", 1)[-1].rsplit("#", 1)[-1]

def get_namespace(node_meta: dict | None) -> str | None:
    """Read the OBO namespace from meta.basicPropertyValues hasOBONamespace, or fallback to meta.namespace."""
    m = node_meta or {}
    for v in (m.get("basicPropertyValues") or []):
        pred = v.get("pred") or ""
        if pred.endswith("hasOBONamespace"):
            return v.get("val")
    return m.get("namespace")

def in_subset(node_meta: dict | None, subset_iri_suffix: str) -> bool:
    """True iff node.meta.subsets contains an IRI that ends with subset_iri_suffix (e.g., 'goslim_drosophila')."""
    sets_ = (node_meta or {}).get("subsets") or []
    for iri in sets_:
        if isinstance(iri, str) and iri.endswith(subset_iri_suffix):
            return True
    return False

# ---------- IO

def load_graph(path: str):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    graphs = data.get("graphs") or []
    if not graphs:
        raise SystemExit("No graphs[] found in JSON.")
    g = graphs[0]
    nodes = g.get("nodes", [])
    edges = g.get("edges", [])
    return nodes, edges, g.get("id"), g.get("meta", {})

# ---------- core building

def build_subset(nodes: List[dict], edges: List[dict],
                 keep_pred: Tuple[str, ...] = ("is_a", "part_of"),
                 subset_suffix: str | None = "goslim_drosophila",
                 restrict_namespace: str | None = None,
                 include_ancestors: bool = False):
    """
    Returns:
      node_map: id -> {id,label,meta,namespace}
      E: list of (child, parent, predicate)
      in_edges, out_edges: adjacency maps
      roots: list of root ids (no incoming kept edges)
    """
    # --- initial pass: collect nodes (slim-tagged if subset_suffix is set)
    node_map: Dict[str, dict] = {}
    slim_seeds: Set[str] = set()

    for n in nodes:
        nid = norm_go_id(n.get("id"))
        if not nid:
            continue
        meta = n.get("meta") or {}
        ns = get_namespace(meta)

        # namespace filter (optional)
        if restrict_namespace and ns and ns != restrict_namespace:
            # Skip nodes outside namespace; if ns missing, we keep it (conservative).
            if ns != restrict_namespace:
                continue

        # subset filter (optional)
        if subset_suffix:
            if in_subset(meta, subset_suffix):
                node_map[nid] = {"id": nid, "label": n.get("lbl") or nid, "meta": meta, "namespace": ns}
                slim_seeds.add(nid)
        else:
            node_map[nid] = {"id": nid, "label": n.get("lbl") or nid, "meta": meta, "namespace": ns}

    # --- Read all edges; keep only normalized predicates in keep_pred
    raw_edges: List[Tuple[str, str, str]] = []
    for e in edges:
        s = norm_go_id(edge_field(e, "subj", "sub", "subject"))
        o = norm_go_id(edge_field(e, "obj", "object"))
        if not s or not o:
            continue
        p = pred_name(edge_field(e, "pred", "predicate", "pred_iri", "pred_curie"))
        if p in keep_pred:
            # direction: child -> parent for hierarchical relations
            raw_edges.append((s, o, p))

    # --- If include_ancestors is requested, add ancestor nodes of slim seeds (or of all nodes if no subset)
    if include_ancestors:
        # Build a quick parent adjacency from raw_edges, regardless of node_map membership
        parents = defaultdict(set)
        for c, p, _t in raw_edges:
            parents[c].add(p)

        # Choose start set: if we had a subset suffix, start from slim_seeds; else from all current node_map
        frontier: deque[str] = deque(slim_seeds if (subset_suffix and slim_seeds) else node_map.keys())
        visited: Set[str] = set(frontier)

        # Walk up to ancestors, adding them to node_map if we have metadata in 'nodes'
        # Build a lookup from all provided nodes to their meta/labels for later inclusion
        node_raw_lookup = {norm_go_id(n.get("id")): n for n in nodes}

        while frontier:
            u = frontier.popleft()
            for p in parents.get(u, []):
                if p in visited:
                    continue
                visited.add(p)
                frontier.append(p)
                # If ancestor isn't yet in node_map but exists in source nodes, include it
                if p not in node_map and p in node_raw_lookup:
                    rn = node_raw_lookup[p]
                    meta = rn.get("meta") or {}
                    ns = get_namespace(meta)
                    # still respect namespace restriction (if any)
                    if (not restrict_namespace) or (ns is None) or (ns == restrict_namespace):
                        node_map[p] = {
                            "id": p,
                            "label": rn.get("lbl") or p,
                            "meta": meta,
                            "namespace": ns
                        }

    # --- Now trim edges to those entirely within node_map
    E: List[Tuple[str, str, str]] = [(c, p, t) for (c, p, t) in raw_edges if c in node_map and p in node_map]

    # --- Build adjacency
    in_edges = defaultdict(list)   # node -> list[(parent, type)]
    out_edges = defaultdict(list)  # node -> list[(child, type)]
    for c, p, t in E:
        in_edges[c].append((p, t))
        out_edges[p].append((c, t))

    # --- Roots: no incoming edges among kept preds
    roots = [nid for nid in node_map if nid not in in_edges]
    return node_map, E, in_edges, out_edges, roots

def topo_order(node_map: Dict[str, dict], E: List[Tuple[str, str, str]]) -> List[str]:
    """Kahn's algorithm on child->parent edges. If residual cycles remain, append remaining nodes stably."""
    indeg = defaultdict(int)
    children = defaultdict(list)
    for c, p, _t in E:
        indeg[c] += 1
        children[p].append(c)

    Q = deque([nid for nid in node_map if indeg[nid] == 0])
    order: List[str] = []
    while Q:
        u = Q.popleft()
        order.append(u)
        for v in children[u]:
            indeg[v] -= 1
            if indeg[v] == 0:
                Q.append(v)

    if len(order) < len(node_map):
        # Non-DAG bits (likely from has_part/regulation) — keep stable completion
        seen = set(order)
        remaining = [nid for nid in node_map if nid not in seen]
        remaining.sort()
        order.extend(remaining)
    return order

def compute_depths(roots: List[str], out_edges: Dict[str, List[Tuple[str, str]]]) -> Dict[str, int]:
    """Depth = BFS distance from nearest root along root->children edges."""
    depth: Dict[str, int] = {}
    dq = deque()
    for r in roots:
        depth[r] = 0
        dq.append(r)
    while dq:
        u = dq.popleft()
        d = depth[u]
        for v, _t in out_edges.get(u, []):  # u -> child
            if v not in depth or d + 1 < depth[v]:
                depth[v] = d + 1
                dq.append(v)
    return depth

# ---------- output writers

def write_outputs(node_map, E, order, depth, out_prefix: str):
    index = {nid: i for i, nid in enumerate(order)}

    # Nodes CSV
    with open(f"{out_prefix}_nodes.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "label", "namespace", "depth", "index"])
        for nid in order:
            n = node_map[nid]
            w.writerow([nid, n["label"], n.get("namespace") or "", depth.get(nid, ""), index[nid]])

    # Edges CSV (child -> parent)
    with open(f"{out_prefix}_edges.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["source", "target", "type"])
        for c, p, t in E:
            w.writerow([c, p, t])

    # D3 Sankey JSON (indexed)
    sankey = {
        "nodes": [{"name": node_map[nid]["label"], "id": nid, "depth": depth.get(nid, 0)} for nid in order],
        "links": [{"source": index[c], "target": index[p], "value": 1, "type": t} for c, p, t in E]
    }
    with open(f"{out_prefix}_sankey.json", "w", encoding="utf-8") as f:
        json.dump(sankey, f, indent=2)

    # Arc-diagram JSON (ids, keep strings)
    arc = {
        "nodes": [{"id": nid, "label": node_map[nid]["label"], "depth": depth.get(nid, 0), "index": index[nid]}
                  for nid in order],
        "links": [{"source": c, "target": p, "type": t} for c, p, t in E]
    }
    with open(f"{out_prefix}_arc.json", "w", encoding="utf-8") as f:
        json.dump(arc, f, indent=2)

# ---------- CLI

def main():
    ap = argparse.ArgumentParser(description="Make topological order + D3 datasets from GO OBO-Graphs JSON.")
    ap.add_argument("json", help="Path to GO OBO-Graphs JSON (e.g., goslim_drosophila.json)")
    ap.add_argument("--subset", default="goslim_drosophila",
                    help="Subset suffix to keep (default: goslim_drosophila). Use '' to disable subset filtering.")
    ap.add_argument("--namespace", choices=["biological_process","molecular_function","cellular_component"],
                    help="Restrict to an OBO namespace (optional).")
    ap.add_argument("--predicates", default="is_a,part_of",
                    help="Comma list to keep (short names: is_a, part_of, has_part, regulates, positively_regulates, negatively_regulates).")
    ap.add_argument("--include-ancestors", action="store_true",
                    help="Also include ancestors of slim terms (or of all kept nodes if --subset '').")
    ap.add_argument("-o", "--out", default="go_out",
                    help="Output file prefix (default: go_out)")
    args = ap.parse_args()

    try:
        nodes, edges, gid, gmeta = load_graph(args.json)
    except Exception as e:
        print(f"Failed to load JSON: {e}", file=sys.stderr)
        sys.exit(1)

    keep_pred = tuple(p.strip() for p in args.predicates.split(",") if p.strip())
    subset_suffix = args.subset if args.subset != "" else None

    node_map, E, inE, outE, roots = build_subset(
        nodes, edges,
        keep_pred=keep_pred,
        subset_suffix=subset_suffix,
        restrict_namespace=args.namespace,
        include_ancestors=args.include_ancestors
    )

    if not node_map:
        print("No nodes survived the filters; check --subset / --namespace and that your JSON has matching nodes.",
              file=sys.stderr)
        sys.exit(2)

    order = topo_order(node_map, E)
    depth = compute_depths(roots, outE)
    write_outputs(node_map, E, order, depth, args.out)

    print(f"Done.\nWrote:\n  {args.out}_nodes.csv\n  {args.out}_edges.csv\n  {args.out}_sankey.json\n  {args.out}_arc.json")

if __name__ == "__main__":
    main()
