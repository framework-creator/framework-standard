"""Emit a relationship-map JSON for Phase 3 graph visualization.

Output shape:
{
  "generated_at": "...",
  "nodes": [{id, name, domain, series, tier, status, tags, degree}],
  "edges": [{from, to, type}],
  "stats": {nodes, edges, edges_by_type, orphan_ids}
}

Orphan detection: edges that reference a framework_id not present as a node.

Usage:
    python graph.py --db library.db --out graph.json
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    if not args.db.exists():
        print(f"ERROR: db {args.db} does not exist", file=sys.stderr)
        return 2

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row

    node_rows = conn.execute(
        "SELECT framework_id, name, domain, series, tier, status, synopsis FROM frameworks ORDER BY framework_id"
    ).fetchall()
    node_ids = {r["framework_id"] for r in node_rows}

    edge_rows = conn.execute(
        "SELECT from_id, to_id, rel_type FROM relationships"
    ).fetchall()

    tag_rows = conn.execute("SELECT framework_id, tag FROM tags").fetchall()
    tags_by_fid: dict[str, list[str]] = {}
    for r in tag_rows:
        tags_by_fid.setdefault(r["framework_id"], []).append(r["tag"])

    degree: Counter = Counter()
    for e in edge_rows:
        degree[e["from_id"]] += 1
        degree[e["to_id"]] += 1

    nodes = []
    for r in node_rows:
        nodes.append({
            "id": r["framework_id"],
            "name": r["name"],
            "domain": r["domain"],
            "series": r["series"],
            "tier": r["tier"],
            "status": r["status"],
            "synopsis": r["synopsis"],
            "tags": tags_by_fid.get(r["framework_id"], []),
            "degree": degree.get(r["framework_id"], 0),
        })

    edges = [{"from": e["from_id"], "to": e["to_id"], "type": e["rel_type"]} for e in edge_rows]

    edges_by_type = Counter(e["type"] for e in edges)
    orphan_ids = sorted({e["to"] for e in edges if e["to"] not in node_ids})

    out = {
        "generated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "stats": {
            "nodes": len(nodes),
            "edges": len(edges),
            "edges_by_type": dict(edges_by_type),
            "orphan_ids": orphan_ids,
            "orphan_count": len(orphan_ids),
        },
        "nodes": nodes,
        "edges": edges,
    }
    args.out.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    # Also emit a JS file that assigns the same payload to window.GRAPH_DATA so
    # the HTML viewer can load it via a <script> tag under file:// without CORS issues.
    js_path = args.out.with_suffix(".js") if args.out.suffix == ".json" else args.out.parent / (args.out.name + ".js")
    js_payload = "window.GRAPH_DATA = " + json.dumps(out, ensure_ascii=False) + ";\n"
    js_path.write_text(js_payload, encoding="utf-8")
    print(f"Graph written: {args.out}")
    print(f"           + {js_path}")
    print(f"  nodes: {len(nodes)}, edges: {len(edges)}, orphan refs: {len(orphan_ids)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
