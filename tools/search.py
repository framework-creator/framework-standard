"""Search the framework library.

Examples:
    python search.py --db library.db --text "compound intelligence"
    python search.py --db library.db --tag cinematography
    python search.py --db library.db --domain compound_intelligence
    python search.py --db library.db --series FILM
    python search.py --db library.db --id FRAMEWORK-FILM-007 --full
    python search.py --db library.db --trigger "shot list"
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path


def connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def row_summary(r: sqlite3.Row) -> str:
    return f"{r['framework_id']:30s} {r['name'][:50]:50s} [{r['domain']}]"


def search_text(conn, query: str, limit: int):
    cur = conn.execute(
        """SELECT f.framework_id, f.name, f.domain, f.synopsis, bm25(frameworks_fts) AS score
           FROM frameworks_fts
           JOIN frameworks f ON f.framework_id = frameworks_fts.framework_id
           WHERE frameworks_fts MATCH ?
           ORDER BY score LIMIT ?""",
        (query, limit),
    )
    return cur.fetchall()


def filter_query(conn, *, domain=None, series=None, tag=None, trigger=None, status=None, limit=50):
    clauses = []
    params: list = []
    joins = ""
    if domain:
        clauses.append("f.domain = ?")
        params.append(domain)
    if series:
        clauses.append("f.series = ?")
        params.append(series)
    if status:
        clauses.append("f.status = ?")
        params.append(status)
    if tag:
        joins += " JOIN tags t ON t.framework_id = f.framework_id"
        clauses.append("t.tag = ?")
        params.append(tag)
    if trigger:
        joins += " JOIN triggers tr ON tr.framework_id = f.framework_id"
        clauses.append("tr.trigger LIKE ?")
        params.append(f"%{trigger}%")
    sql = f"SELECT DISTINCT f.framework_id, f.name, f.domain, f.synopsis FROM frameworks f{joins}"
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY f.framework_id LIMIT ?"
    params.append(limit)
    return conn.execute(sql, params).fetchall()


def get_full(conn, framework_id: str):
    row = conn.execute("SELECT content FROM frameworks WHERE framework_id = ?", (framework_id,)).fetchone()
    return json.loads(row["content"]) if row else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, required=True)
    ap.add_argument("--text", help="FTS query across name, synopsis, principles, tags")
    ap.add_argument("--tag")
    ap.add_argument("--domain")
    ap.add_argument("--series")
    ap.add_argument("--trigger")
    ap.add_argument("--status")
    ap.add_argument("--id", dest="fid", help="Fetch a specific framework by id")
    ap.add_argument("--full", action="store_true", help="Print full JSON (with --id)")
    ap.add_argument("--limit", type=int, default=25)
    args = ap.parse_args()

    if not args.db.exists():
        print(f"ERROR: db {args.db} does not exist", file=sys.stderr)
        return 2

    conn = connect(args.db)

    if args.fid:
        data = get_full(conn, args.fid)
        if not data:
            print(f"Not found: {args.fid}")
            return 1
        if args.full:
            print(json.dumps(data, indent=2, ensure_ascii=False))
        else:
            print(f"{data['framework_id']}: {data['name']}")
            print(f"  domain: {data['classification'].get('domain')}")
            print(f"  tags:   {', '.join(data['classification'].get('tags', []))}")
            print(f"  synopsis: {data['synopsis']}")
        return 0

    if args.text:
        rows = search_text(conn, args.text, args.limit)
    else:
        rows = filter_query(
            conn,
            domain=args.domain,
            series=args.series,
            tag=args.tag,
            trigger=args.trigger,
            status=args.status,
            limit=args.limit,
        )

    if not rows:
        print("No results.")
        return 0

    for r in rows:
        print(row_summary(r))
    print(f"\n{len(rows)} result(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
