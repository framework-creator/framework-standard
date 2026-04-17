-- Framework Standard SQLite schema v1.0
-- Normalized frameworks (canonical v1.0 form) stored in `frameworks.content` as JSON.
-- Edges, tags, and triggers are extracted into relational tables for fast query.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS frameworks (
    framework_id    TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    version         TEXT NOT NULL,
    created_date    TEXT NOT NULL,
    updated_date    TEXT NOT NULL,
    status          TEXT NOT NULL,
    synopsis        TEXT NOT NULL,
    domain          TEXT NOT NULL,
    category        TEXT,
    series          TEXT,
    tier            TEXT,
    source_format   TEXT NOT NULL,    -- 'canonical_v1', 'seven_section_v2', 'five_layer_loose'
    source_path     TEXT,             -- original file path at ingest time
    content         TEXT NOT NULL,    -- full canonical JSON blob
    ingested_at     TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_frameworks_domain ON frameworks(domain);
CREATE INDEX IF NOT EXISTS idx_frameworks_series ON frameworks(series);
CREATE INDEX IF NOT EXISTS idx_frameworks_status ON frameworks(status);

CREATE TABLE IF NOT EXISTS relationships (
    from_id         TEXT NOT NULL,
    to_id           TEXT NOT NULL,
    rel_type        TEXT NOT NULL,   -- depends_on, extends, related_to, triggers, conflicts_with, parent_of, child_of
    PRIMARY KEY (from_id, to_id, rel_type),
    FOREIGN KEY (from_id) REFERENCES frameworks(framework_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_rel_from ON relationships(from_id);
CREATE INDEX IF NOT EXISTS idx_rel_to ON relationships(to_id);
CREATE INDEX IF NOT EXISTS idx_rel_type ON relationships(rel_type);

CREATE TABLE IF NOT EXISTS tags (
    framework_id    TEXT NOT NULL,
    tag             TEXT NOT NULL,
    PRIMARY KEY (framework_id, tag),
    FOREIGN KEY (framework_id) REFERENCES frameworks(framework_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_tags_tag ON tags(tag);

CREATE TABLE IF NOT EXISTS triggers (
    framework_id    TEXT NOT NULL,
    trigger         TEXT NOT NULL,
    PRIMARY KEY (framework_id, trigger),
    FOREIGN KEY (framework_id) REFERENCES frameworks(framework_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_triggers_trigger ON triggers(trigger);

-- Full-text search over synopsis + principles + tags.
CREATE VIRTUAL TABLE IF NOT EXISTS frameworks_fts USING fts5(
    framework_id UNINDEXED,
    name,
    synopsis,
    principles_text,
    tags_text,
    tokenize = 'porter unicode61'
);

CREATE TABLE IF NOT EXISTS ingest_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    run_at          TEXT NOT NULL,
    file_path       TEXT NOT NULL,
    framework_id    TEXT,
    source_format   TEXT,
    status          TEXT NOT NULL,   -- 'ok', 'migrated', 'skipped', 'error'
    message         TEXT
);
