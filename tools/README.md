# Framework Standard Tools

CLI toolkit for the portable framework format (spec: `../SPECIFICATION.md`).

## Requirements

Python 3.9+. Standard library only, no external dependencies. SQLite 3.9+ for FTS5.

## Commands

### Ingest

Scan a folder of framework JSON files, auto-detect format, migrate to canonical v1.0, store in SQLite.

```bash
python ingest.py --source ~/Projects/SIOS/frameworks --db ../library.db
python ingest.py --source ~/Projects/SIOS/frameworks --db ../library.db --limit 15   # test run
python ingest.py --source ~/Projects/SIOS/frameworks --db ../library.db --strict     # exit 1 on any validation error
python ingest.py --source ~/Projects/SIOS/frameworks --db ../library.db --quiet      # summary only
```

Supported input formats (auto-detected):

- **canonical_v1**: matches SPECIFICATION.md v1.0 exactly
- **seven_section_v2**: `framework_identity` + architecture block (including renamed variants: master_architecture, compound_architecture, etc.)
- **five_layer_loose**: older SIOS files with `layer_N_*` keys but missing required canonical fields
- **domain_layers**: flat files with `layers` dict + `principles` + `methodology` (e.g. Bach_Counterpoint_Interface_Design.json)

Dotfiles (`.vector_manifest.json`, etc.) are ignored.

### Search

```bash
python search.py --db ../library.db --text "compound intelligence"           # FTS
python search.py --db ../library.db --tag strategy                           # tag filter
python search.py --db ../library.db --domain visual_intelligence             # domain
python search.py --db ../library.db --series FILM                            # series
python search.py --db ../library.db --trigger "shot list"                    # trigger substring
python search.py --db ../library.db --id FRAMEWORK-FILM-007 --full           # full JSON
```

Filters compose: `--tag X --series Y` applies both.

### Export

Dump the library back out as canonical `.framework.json` files.

```bash
python export.py --db ../library.db --out ./exported
python export.py --db ../library.db --out ./exported --filter-domain distribution
```

Round-trip guarantee: `export` output re-ingested with `--strict` produces zero errors.

### Graph

Emit relationship map for Phase 3 visualization.

```bash
python graph.py --db ../library.db --out ../graph.json
```

Output:

```json
{
  "generated_at": "...",
  "stats": {"nodes": N, "edges": M, "edges_by_type": {...}, "orphan_ids": [...]},
  "nodes": [{id, name, domain, series, tier, status, tags, degree}, ...],
  "edges": [{from, to, type}, ...]
}
```

Orphan IDs are relationship targets that no framework in the DB defines. These are typically frameworks referenced by compounds but not yet migrated.

### Validate

Check a single canonical file against the spec.

```bash
python -c "import json, sys; from validate import validate; errs = validate(json.load(open(sys.argv[1]))); print(errs or 'OK')" path/to/file.framework.json
```

## Database schema

See `schema.sql`. Tables:

- `frameworks` — one row per unique `framework_id`, canonical JSON in `content` column
- `relationships` — edge list (from_id, to_id, rel_type)
- `tags` — many-to-many
- `triggers` — many-to-many
- `frameworks_fts` — FTS5 index over name + synopsis + principles + tags
- `ingest_log` — audit trail for every ingest attempt

## Known behaviors

- **ID collisions overwrite.** When two source files produce the same `framework_id` (e.g. `v1_0.json` and `v1_1.json` versions of the same framework), the later-ingested file wins. In SIOS's 627-file library this affects ~11 files, all legitimate versioned duplicates.
- **Filename fallback.** Source files with no `framework_id` field get an ID derived from their filename.
- **Lossless namespace.** Anything the migrator can't map to canonical layers is preserved under `_sios` for later inspection.
