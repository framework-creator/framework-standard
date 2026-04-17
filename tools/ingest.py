"""Ingest .framework.json (or legacy SIOS .json) files into a SQLite database.

Auto-detects format, migrates to canonical v1.0, validates, and stores.

Usage:
    python ingest.py --source ~/Projects/SIOS/frameworks --db library.db
    python ingest.py --source ~/Projects/SIOS/frameworks --db library.db --limit 15
    python ingest.py --source ~/Projects/SIOS/frameworks --db library.db --strict
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path

from migrate import detect_format, migrate, _normalize_fid
from validate import validate


def _fallback_fid_from_filename(filename: str) -> str:
    stem = filename.rsplit(".json", 1)[0].rsplit(".framework", 1)[0]
    return _normalize_fid(stem)

SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def init_db(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA_PATH.read_text())
    conn.commit()
    return conn


def principles_text(data: dict) -> str:
    principles = data.get("layer_1_principles_foundation", {}).get("core_principles", [])
    parts = []
    for p in principles:
        if isinstance(p, dict):
            parts.append(p.get("principle", ""))
            parts.append(p.get("description", ""))
    return " ".join(p for p in parts if p)


def store(conn: sqlite3.Connection, canonical: dict, source_fmt: str, source_path: str) -> None:
    cls = canonical.get("classification", {})
    cur = conn.cursor()
    cur.execute("DELETE FROM frameworks WHERE framework_id = ?", (canonical["framework_id"],))
    cur.execute("DELETE FROM frameworks_fts WHERE framework_id = ?", (canonical["framework_id"],))
    cur.execute(
        """INSERT INTO frameworks (framework_id, name, version, created_date, updated_date,
            status, synopsis, domain, category, series, tier, source_format, source_path,
            content, ingested_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            canonical["framework_id"],
            canonical["name"],
            canonical["version"],
            canonical["created_date"],
            canonical["updated_date"],
            canonical["status"],
            canonical["synopsis"],
            cls.get("domain"),
            cls.get("category"),
            cls.get("series"),
            cls.get("tier"),
            source_fmt,
            source_path,
            json.dumps(canonical, ensure_ascii=False),
            datetime.utcnow().isoformat(timespec="seconds") + "Z",
        ),
    )

    for tag in cls.get("tags", []) or []:
        if isinstance(tag, str) and tag.strip():
            cur.execute("INSERT OR IGNORE INTO tags (framework_id, tag) VALUES (?, ?)",
                        (canonical["framework_id"], tag.strip()))

    for trig in cls.get("triggers", []) or []:
        if isinstance(trig, str) and trig.strip():
            cur.execute("INSERT OR IGNORE INTO triggers (framework_id, trigger) VALUES (?, ?)",
                        (canonical["framework_id"], trig.strip()))

    rel = canonical.get("relationships", {})
    for rel_type, targets in rel.items():
        for target in targets or []:
            cur.execute(
                "INSERT OR IGNORE INTO relationships (from_id, to_id, rel_type) VALUES (?, ?, ?)",
                (canonical["framework_id"], target, rel_type),
            )

    tags_text = " ".join(cls.get("tags", []) or [])
    cur.execute(
        "INSERT INTO frameworks_fts (framework_id, name, synopsis, principles_text, tags_text) VALUES (?, ?, ?, ?, ?)",
        (canonical["framework_id"], canonical["name"], canonical["synopsis"],
         principles_text(canonical), tags_text),
    )


def log_entry(conn: sqlite3.Connection, run_at: str, file_path: str, fid: str | None,
              fmt: str | None, status: str, message: str | None) -> None:
    conn.execute(
        "INSERT INTO ingest_log (run_at, file_path, framework_id, source_format, status, message) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (run_at, file_path, fid, fmt, status, message),
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="Ingest framework files into SQLite.")
    ap.add_argument("--source", type=Path, required=True, help="Folder containing framework JSON files")
    ap.add_argument("--db", type=Path, required=True, help="SQLite database path")
    ap.add_argument("--limit", type=int, default=None, help="Only ingest N files (for test runs)")
    ap.add_argument("--strict", action="store_true", help="Exit non-zero on any validation error")
    ap.add_argument("--pattern", default="*.json", help="Glob pattern (default: *.json)")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    if not args.source.is_dir():
        print(f"ERROR: source {args.source} is not a directory", file=sys.stderr)
        return 2

    args.db.parent.mkdir(parents=True, exist_ok=True)
    conn = init_db(args.db)
    run_at = datetime.utcnow().isoformat(timespec="seconds") + "Z"

    files = sorted(f for f in args.source.glob(args.pattern) if not f.name.startswith("."))
    if args.limit:
        files = files[: args.limit]

    counts = {"ok": 0, "migrated": 0, "skipped": 0, "error": 0, "invalid": 0}
    t0 = time.time()

    for f in files:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except Exception as e:
            counts["error"] += 1
            log_entry(conn, run_at, str(f), None, None, "error", f"json parse: {e}")
            if not args.quiet:
                print(f"  ERROR parse {f.name}: {e}")
            continue

        try:
            fmt = detect_format(data)
            if fmt == "unknown":
                counts["skipped"] += 1
                log_entry(conn, run_at, str(f), None, fmt, "skipped", "unknown format")
                if not args.quiet:
                    print(f"  SKIP  {f.name}: unknown format")
                continue
            canonical = migrate(data, source_path=str(f))
            if canonical.get("framework_id") == "FRAMEWORK-UNKNOWN-000":
                canonical["framework_id"] = _fallback_fid_from_filename(f.name)
        except Exception as e:
            counts["error"] += 1
            log_entry(conn, run_at, str(f), None, None, "error", f"migrate: {e}")
            if not args.quiet:
                print(f"  ERROR migrate {f.name}: {e}")
            continue

        errors = validate(canonical)
        if errors:
            counts["invalid"] += 1
            msg = "; ".join(errors[:5])
            log_entry(conn, run_at, str(f), canonical.get("framework_id"), fmt, "error", f"invalid: {msg}")
            if not args.quiet:
                print(f"  INVALID {f.name} ({canonical.get('framework_id')}): {msg}")
            if args.strict:
                continue

        try:
            store(conn, canonical, fmt, str(f))
            status = "ok" if fmt == "canonical_v1" else "migrated"
            counts[status] += 1
            log_entry(conn, run_at, str(f), canonical["framework_id"], fmt, status, None)
            if not args.quiet:
                print(f"  {status.upper():8s} {f.name} -> {canonical['framework_id']} [{fmt}]")
        except Exception as e:
            counts["error"] += 1
            log_entry(conn, run_at, str(f), canonical.get("framework_id"), fmt, "error", f"store: {e}")
            if not args.quiet:
                print(f"  ERROR store {f.name}: {e}")

    conn.commit()
    elapsed = time.time() - t0

    print(f"\n--- Ingest complete in {elapsed:.2f}s ---")
    print(f"Total files: {len(files)}")
    for k, v in counts.items():
        print(f"  {k:10s}: {v}")
    print(f"Database: {args.db}")

    conn.close()
    if args.strict and (counts["error"] or counts["invalid"]):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
