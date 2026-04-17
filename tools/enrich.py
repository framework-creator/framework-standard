"""Infer relationship edges for framework series that currently have empty blocks.

Rules (applied per family — the prefix after FRAMEWORK- and before the final numeric id):

  A. Foundation: lowest-numbered member of the family. Every other member gets
     depends_on -> foundation.
  B. Compound: highest-numbered member IF any of:
       - tier == "compound"
       - name contains "compound"
       - name starts with "Master "
     Compound gets parent_of -> each non-compound member.
     Non-compound members get child_of -> compound.
  C. Sequential extends (opt-in per family): member N gets extends -> N-1.
     Enabled for families where the series content is an explicit progression
     (RENDER, SEO).
  D. Content references: scan synopsis for FRAMEWORK-XXX-NNN patterns. Add
     related_to for each match that resolves to a real framework. Cap 3.

Hard limits:
  - Never add an edge to a framework_id that is not in the library.
  - Never add more than 3 related_to edges per framework.
  - Skip any family with < 2 members.

Usage:
  python3 tools/enrich.py --db library.db --out ./exported-enriched
  python3 tools/ingest.py --source ./exported-enriched --db library.db --strict
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path


FAMILIES_SEQUENTIAL_EXTENDS = {"RENDER", "SEO"}

# Families where the highest-numbered member is the compound, even if its name
# does not contain the word "compound". Authority: delegation brief confirmed
# these compounds explicitly. LEADS-SCORE has no compound yet (stops at -003).
COMPOUND_FAMILIES = {
    "FILM", "INFRA", "DIST", "MAGIC", "LEADS-GEN", "LEADS-QUAL",
}

# Priority families from the delegation brief. Anything not in here is skipped.
PRIORITY_FAMILIES = {
    "FILM", "RENDER", "INFRA", "DIST", "MAGIC", "ROBOT", "SEO",
    "LEADS-GEN", "LEADS-QUAL", "LEADS-SCORE",
}

# Families that only get content-reference (rule D) edges, no structural inference.
# VISUAL is disjoint, members don't form a progression.
CONTENT_ONLY_FAMILIES = {"VISUAL"}

FID_IN_TEXT = re.compile(r"\bFRAMEWORK-[A-Z0-9]+(?:-[A-Z0-9]+)?-\d{3,}\b")

# Phase 5 — Rule 2: known cross-domain pairs confirmed by library knowledge.
# These generate related_to edges in BOTH directions.
PHASE_5_CROSS_DOMAIN = [
    ("FRAMEWORK-FILM-007", "FRAMEWORK-RENDER-003"),
    ("FRAMEWORK-FILM-007", "FRAMEWORK-RENDER-005"),
    ("FRAMEWORK-MAGIC-001", "FRAMEWORK-CONVERT-036"),
    ("FRAMEWORK-PM-003", "FRAMEWORK-INFRA-001"),
    ("FRAMEWORK-PM-007", "FRAMEWORK-INFRA-001"),
    ("FRAMEWORK-DIST-001", "FRAMEWORK-LEADS-GEN-001"),
    ("FRAMEWORK-VISUAL-013", "FRAMEWORK-RENDER-002"),
]

# Phase 5 related_to cap per framework (brief raised from 3 to 5).
RELATED_TO_CAP = 5


def family_of(framework_id: str) -> tuple[str, int] | None:
    """Return (family, number) for a canonical framework_id, or None if unparseable."""
    m = re.match(r"^FRAMEWORK-([A-Z0-9]+(?:-[A-Z0-9]+)?)-(\d{3,})$", framework_id)
    if not m:
        return None
    family = m.group(1)
    # For three-part IDs like FRAMEWORK-LEADS-GEN-001, family = LEADS-GEN.
    try:
        return family, int(m.group(2))
    except ValueError:
        return None


def is_compound(member: dict) -> bool:
    tier = (member.get("classification") or {}).get("tier") or ""
    if tier.lower() == "compound":
        return True
    name = (member.get("name") or "").lower()
    if "compound" in name:
        return True
    if name.startswith("master "):
        return True
    return False


def load_frameworks(db_path: Path) -> dict[str, dict]:
    """Return map of framework_id -> canonical dict (from content JSON)."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    out = {}
    for r in conn.execute("SELECT framework_id, content FROM frameworks"):
        out[r["framework_id"]] = json.loads(r["content"])
    conn.close()
    return out


def slugify_name(name: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "_", name or "").strip("_").lower()
    return s[:80] or "framework"


def add_edge(frameworks: dict, from_id: str, rel_type: str, to_id: str) -> bool:
    """Add rel if not already present. Returns True if added."""
    if from_id == to_id:
        return False
    if to_id not in frameworks:
        return False
    rels = frameworks[from_id].setdefault("relationships", {})
    for t in ("depends_on", "extends", "related_to", "triggers",
              "conflicts_with", "parent_of", "child_of"):
        rels.setdefault(t, [])
    if to_id in rels[rel_type]:
        return False
    rels[rel_type].append(to_id)
    return True


def enrich(frameworks: dict) -> dict:
    """Apply inference rules in place. Returns stats dict."""
    # Group by family.
    families: dict[str, list[tuple[int, str]]] = defaultdict(list)
    for fid in frameworks:
        fam = family_of(fid)
        if fam:
            families[fam[0]].append((fam[1], fid))
    for fam in families:
        families[fam].sort()

    stats = {
        "families_enriched": 0,
        "foundation_edges": 0,
        "compound_edges": 0,
        "extends_edges": 0,
        "related_to_edges": 0,
    }

    for family, members in families.items():
        if family not in PRIORITY_FAMILIES and family not in CONTENT_ONLY_FAMILIES:
            continue
        if len(members) < 2:
            continue

        if family in PRIORITY_FAMILIES:
            stats["families_enriched"] += 1

            # Identify foundation and compound.
            foundation_id = members[0][1]
            compound_id = None
            # Explicit override for known compound families.
            if family in COMPOUND_FAMILIES and len(members) >= 3:
                compound_id = members[-1][1]
            else:
                top_member = frameworks[members[-1][1]]
                if is_compound(top_member):
                    compound_id = members[-1][1]
                for _, mid in members:
                    if mid != compound_id and is_compound(frameworks[mid]):
                        compound_id = mid  # last-wins; usually it's the top one

            # Rule A: every non-foundation depends_on foundation.
            for _, mid in members:
                if mid == foundation_id:
                    continue
                if add_edge(frameworks, mid, "depends_on", foundation_id):
                    stats["foundation_edges"] += 1

            # Rule B: compound parent_of each component; components child_of compound.
            if compound_id:
                # Clean up a common Phase 2 migration error: v2 compounds sometimes
                # had their components listed under the compound's child_of (via
                # integration_systems.parent_frameworks), when the correct direction
                # is parent_of. Strip those inverted edges before adding the right ones.
                compound_rels = frameworks[compound_id].setdefault("relationships", {})
                component_ids = {mid for _, mid in members if mid != compound_id}
                compound_rels.setdefault("child_of", [])
                compound_rels["child_of"] = [x for x in compound_rels["child_of"] if x not in component_ids]

                for _, mid in members:
                    if mid == compound_id:
                        continue
                    if add_edge(frameworks, compound_id, "parent_of", mid):
                        stats["compound_edges"] += 1
                    if add_edge(frameworks, mid, "child_of", compound_id):
                        stats["compound_edges"] += 1

            # Rule C: sequential extends.
            if family in FAMILIES_SEQUENTIAL_EXTENDS:
                for i in range(1, len(members)):
                    prev_id = members[i - 1][1]
                    cur_id = members[i][1]
                    if cur_id == compound_id:
                        continue
                    if add_edge(frameworks, cur_id, "extends", prev_id):
                        stats["extends_edges"] += 1

    # Rule D: content references (runs across ALL frameworks, including non-priority).
    for fid, data in frameworks.items():
        text_parts = [data.get("synopsis") or ""]
        l1 = data.get("layer_1_principles_foundation", {})
        for p in l1.get("core_principles", []) or []:
            if isinstance(p, dict):
                text_parts.append(p.get("description") or "")
        text = " ".join(text_parts)
        mentioned = set(FID_IN_TEXT.findall(text)) - {fid}
        real_mentions = [m for m in mentioned if m in frameworks]
        rels = data.setdefault("relationships", {})
        rels.setdefault("related_to", [])
        existing_related = set(rels["related_to"])
        slots_remaining = max(0, RELATED_TO_CAP - len(existing_related))
        for m in real_mentions:
            if slots_remaining == 0:
                break
            structural = set()
            for t in ("depends_on", "extends", "parent_of", "child_of"):
                structural.update(rels.get(t, []))
            if m in structural:
                continue
            if add_edge(frameworks, fid, "related_to", m):
                stats["related_to_edges"] += 1
                slots_remaining -= 1

    # ---- Phase 5: lateral related_to edges ----
    stats["phase5_tag_overlap"] = 0
    stats["phase5_cross_domain"] = 0

    # Rule 1: tag overlap >= 3 across series. Build a reverse tag index then
    # intersect pairs.
    tag_to_fids: dict[str, set[str]] = defaultdict(set)
    for fid, data in frameworks.items():
        for tag in (data.get("classification") or {}).get("tags", []) or []:
            if isinstance(tag, str) and tag.strip():
                tag_to_fids[tag.strip()].add(fid)

    overlap_counts: dict[tuple[str, str], int] = defaultdict(int)
    for tag, fids in tag_to_fids.items():
        fids_list = sorted(fids)
        for i, a in enumerate(fids_list):
            for b in fids_list[i + 1:]:
                overlap_counts[(a, b)] += 1

    for (a, b), count in overlap_counts.items():
        if count < 3:
            continue
        fa = family_of(a)
        fb = family_of(b)
        if not fa or not fb or fa[0] == fb[0]:
            continue
        # Respect the cap by counting current related_to.
        for src, dst in ((a, b), (b, a)):
            rels = frameworks[src].setdefault("relationships", {})
            rels.setdefault("related_to", [])
            if len(rels["related_to"]) >= RELATED_TO_CAP:
                continue
            structural = set()
            for t in ("depends_on", "extends", "parent_of", "child_of"):
                structural.update(rels.get(t, []))
            if dst in structural:
                continue
            if add_edge(frameworks, src, "related_to", dst):
                stats["phase5_tag_overlap"] += 1

    # Rule 2: explicit cross-domain pairs (bidirectional).
    for a, b in PHASE_5_CROSS_DOMAIN:
        if a not in frameworks or b not in frameworks:
            continue
        for src, dst in ((a, b), (b, a)):
            rels = frameworks[src].setdefault("relationships", {})
            rels.setdefault("related_to", [])
            if len(rels["related_to"]) >= RELATED_TO_CAP:
                continue
            structural = set()
            for t in ("depends_on", "extends", "parent_of", "child_of"):
                structural.update(rels.get(t, []))
            if dst in structural:
                continue
            if add_edge(frameworks, src, "related_to", dst):
                stats["phase5_cross_domain"] += 1

    return stats


def write_enriched(frameworks: dict, out_dir: Path) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)
    written = 0
    for fid, data in frameworks.items():
        slug = slugify_name(data.get("name", fid))
        fname = f"{fid}_{slug}.framework.json"
        (out_dir / fname).write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        written += 1
    return written


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    if not args.db.exists():
        print(f"ERROR: db {args.db} does not exist", file=sys.stderr)
        return 2

    print(f"Loading {args.db}...")
    frameworks = load_frameworks(args.db)
    print(f"  {len(frameworks)} frameworks loaded")

    stats = enrich(frameworks)
    print(f"\n=== Enrichment stats ===")
    for k, v in stats.items():
        print(f"  {k}: {v}")

    written = write_enriched(frameworks, args.out)
    print(f"\nWrote {written} enriched files to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
