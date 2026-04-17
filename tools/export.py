"""Export the SQLite library back out as canonical .framework.json files.

Usage:
    python export.py --db library.db --out ./exported
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from pathlib import Path


def slugify(name: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "_", name).strip("_").lower()
    return s[:80] or "framework"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--filter-domain", default=None)
    args = ap.parse_args()

    if not args.db.exists():
        print(f"ERROR: db {args.db} does not exist", file=sys.stderr)
        return 2
    args.out.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    sql = "SELECT framework_id, name, content FROM frameworks"
    params: list = []
    if args.filter_domain:
        sql += " WHERE domain = ?"
        params.append(args.filter_domain)
    rows = conn.execute(sql, params).fetchall()

    count = 0
    for r in rows:
        data = json.loads(r["content"])
        fname = f"{r['framework_id']}_{slugify(r['name'])}.framework.json"
        (args.out / fname).write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        count += 1

    print(f"Exported {count} frameworks to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
