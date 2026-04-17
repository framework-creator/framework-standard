"""
Format detection and migration to canonical v1.0.

Three known input formats:
  - canonical_v1: matches SPECIFICATION.md v1.0
  - seven_section_v2: framework_identity / core_architecture / force_multipliers /
                      implementation_methodology / success_metrics /
                      integration_systems / evolution_protocol
  - five_layer_loose: older SIOS five-layer style (FRAMEWORK-0001 etc.) that
                      does not strictly match canonical (missing required fields,
                      different field names, etc.)

Migration is lossless: anything we do not understand is preserved under `_sios`.
"""
from __future__ import annotations

import copy
import json
import re
from datetime import date
from typing import Any

CANONICAL_LAYERS = [
    "layer_1_principles_foundation",
    "layer_2_systematic_approach",
    "layer_3_force_multipliers",
    "layer_4_success_metrics",
    "layer_5_implementation_guidance",
]

REL_TYPES = [
    "depends_on", "extends", "related_to", "triggers",
    "conflicts_with", "parent_of", "child_of",
]


def detect_format(data: dict) -> str:
    if all(k in data for k in CANONICAL_LAYERS) and "classification" in data and "relationships" in data:
        return "canonical_v1"
    if "framework_identity" in data or "framework_metadata" in data:
        return "seven_section_v2"
    if any(k in data for k in ("principles_foundation", "systematic_approach")) and "force_multipliers" in data:
        return "seven_section_v2"
    if any(k.startswith("layer_") for k in data.keys()):
        return "five_layer_loose"
    if isinstance(data.get("layers"), dict) and ("principles" in data or "methodology" in data):
        return "domain_layers"
    if "framework_id" in data or ("name" in data and "category" in data):
        return "domain_layers"
    return "unknown"


def migrate(data: dict, source_path: str | None = None) -> dict:
    fmt = detect_format(data)
    if fmt == "canonical_v1":
        out = _normalize_canonical(data)
    elif fmt == "seven_section_v2":
        out = _migrate_seven_section(data)
    elif fmt == "five_layer_loose":
        out = _migrate_five_layer_loose(data)
    elif fmt == "domain_layers":
        out = _migrate_domain_layers(data)
    else:
        raise ValueError(f"Unknown framework format (source={source_path})")
    return _normalize_common_fields(out)


STATUS_MAP = {
    "converted": "active",
    "production_ready": "active",
    "production": "active",
    "live": "active",
    "awaiting_development": "draft",
    "in_progress": "draft",
    "wip": "draft",
    "published": "active",
    "complete": "active",
    "completed": "active",
}


def _normalize_version(v: str) -> str:
    s = str(v).strip().lstrip("v")
    parts = s.split(".")
    parts = [p for p in parts if p.isdigit()]
    while len(parts) < 3:
        parts.append("0")
    return ".".join(parts[:3])


def _normalize_date(v: str) -> str:
    s = str(v or "").strip()
    if DATE_ISO := re.match(r"^(\d{4}-\d{2}-\d{2})", s):
        return DATE_ISO.group(1)
    return _today()


def _normalize_status(v: str) -> str:
    s = (v or "").strip().lower()
    if s in {"draft", "active", "deprecated", "archived"}:
        return s
    return STATUS_MAP.get(s, "active")


def _normalize_fid(raw: str) -> str:
    if not raw:
        return "FRAMEWORK-UNKNOWN-000"
    s = str(raw).strip()
    up = s.upper()
    # Accept canonical two-part (FRAMEWORK-SERIES-NNN) or three-part
    # (FRAMEWORK-SERIES-SUB-NNN, e.g. VISUAL-2026-001) identifiers.
    if re.match(r"^FRAMEWORK-[A-Z0-9]+(?:-[A-Z0-9]+)?-\d{3,}$", up):
        return up
    # Strip the FRAMEWORK- prefix if present so later regex never matches it as a series.
    # We will re-add it at the end.
    if up.startswith("FRAMEWORK-"):
        s = s[len("FRAMEWORK-"):]
    # Strip descriptive tail after the numeric id segment, e.g.
    # "FILM-001_Shot_Types_Content_Hierarchy" -> "FILM-001"
    m_prefix = re.match(r"^([A-Za-z0-9]+)-(\d{1,4})[-_\s]", s)
    if m_prefix:
        series = m_prefix.group(1).upper()
        num = m_prefix.group(2).zfill(3)
        return f"FRAMEWORK-{series}-{num}"
    m_prefix3 = re.match(r"^([A-Za-z0-9]+)-([A-Za-z0-9]+)-(\d{1,4})[-_\s]", s)
    if m_prefix3:
        a = m_prefix3.group(1).upper()
        b = m_prefix3.group(2).upper()
        n = m_prefix3.group(3).zfill(3)
        return f"FRAMEWORK-{a}-{b}-{n}"
    # Strip common version suffixes like _v1, _v1_0, -v2 before further parsing.
    stripped = re.sub(r"[-_\s]v\d+(?:[-_\s]\d+)?$", "", s, flags=re.IGNORECASE)
    stripped = re.sub(r"\.framework$", "", stripped, flags=re.IGNORECASE)
    up2 = ("FRAMEWORK-" + stripped).upper()
    if re.match(r"^FRAMEWORK-[A-Z0-9]+(?:-[A-Z0-9]+)?-\d{3,}$", up2):
        return up2
    # Pattern: SERIES-SUBSERIES-NUM
    m3 = re.search(r"([A-Za-z][A-Za-z0-9]*)[-_\s]+([A-Za-z0-9]+)[-_\s]+(\d{1,4})(?!\d)", stripped)
    if m3:
        a = re.sub(r"[^A-Za-z0-9]", "", m3.group(1)).upper()
        b = re.sub(r"[^A-Za-z0-9]", "", m3.group(2)).upper()
        n = m3.group(3).zfill(3)
        if a and b:
            if b.isdigit() or len(b) <= 8:
                return f"FRAMEWORK-{a}-{b}-{n}"
            return f"FRAMEWORK-{a}-{n}"
    m = re.search(r"([A-Za-z][A-Za-z0-9]*)[-_\s]+(\d{1,4})(?!\d)", stripped)
    if m:
        series = re.sub(r"[^A-Za-z0-9]", "", m.group(1)).upper()
        num = m.group(2).zfill(3)
        if series and series != "V":
            return f"FRAMEWORK-{series}-{num}"
    series = re.sub(r"[^A-Za-z0-9]", "", stripped).upper()[:20] or "UNKNOWN"
    return f"FRAMEWORK-{series}-001"


def _normalize_common_fields(out: dict) -> dict:
    """Apply final normalization to ensure canonical validity for any migrated file."""
    out["framework_id"] = _normalize_fid(out.get("framework_id", ""))
    out["version"] = _normalize_version(out.get("version", "1.0.0"))
    out["created_date"] = _normalize_date(out.get("created_date", ""))
    out["updated_date"] = _normalize_date(out.get("updated_date", out.get("created_date", "")))
    out["status"] = _normalize_status(out.get("status", "active"))
    out["relationships"] = _ensure_relationships(out.get("relationships"))
    # Scrub relationship targets.
    for rt in REL_TYPES:
        out["relationships"][rt] = [_normalize_fid(x) for x in out["relationships"][rt] if x]
    # Ensure classification.tags non-empty.
    cls = out.setdefault("classification", {})
    cls.setdefault("domain", "uncategorized")
    if not cls.get("tags"):
        cls["tags"] = ["untagged"]
    # Re-derive series from the normalized framework_id so classification always agrees with id.
    m_series = re.match(r"^FRAMEWORK-([A-Z0-9]+)-(?:\d{3,}|[A-Z0-9]+-\d{3,})$", out["framework_id"])
    if m_series:
        cls["series"] = m_series.group(1)
    # Ensure synopsis non-empty.
    if not out.get("synopsis"):
        out["synopsis"] = out.get("name", out["framework_id"])
    # Truncate overly long synopsis.
    out["synopsis"] = str(out["synopsis"])[:4000]
    return out


def _today() -> str:
    return date.today().isoformat()


def _ensure_relationships(rel: dict | None) -> dict:
    rel = dict(rel or {})
    for k in REL_TYPES:
        rel.setdefault(k, [])
        if not isinstance(rel[k], list):
            rel[k] = [rel[k]]
    return rel


def _coerce_list(v: Any) -> list:
    if v is None:
        return []
    if isinstance(v, list):
        return v
    return [v]


def _slug_id(raw: str) -> str:
    """Normalize an arbitrary framework id string to FRAMEWORK-XXX-NNN form when possible.

    If already well-formed, return as is.
    """
    if not raw:
        return raw
    s = str(raw).strip()
    if s.upper().startswith("FRAMEWORK-"):
        return s
    m = re.match(r"^([A-Z0-9]+)[-_ ](\d+)", s.upper())
    if m:
        return f"FRAMEWORK-{m.group(1)}-{m.group(2).zfill(3)}"
    return s


def _normalize_canonical(data: dict) -> dict:
    out = copy.deepcopy(data)
    out["_spec_version"] = out.get("_spec_version", "1.0")
    out["relationships"] = _ensure_relationships(out.get("relationships"))
    cls = out.setdefault("classification", {})
    cls.setdefault("domain", "uncategorized")
    cls.setdefault("tags", [])
    if not cls["tags"]:
        cls["tags"] = ["untagged"]
    return out


def _find_architecture_block(src: dict) -> dict:
    """Some v2 files rename core_architecture to master_architecture, compound_architecture, etc."""
    if isinstance(src.get("core_architecture"), dict):
        return src["core_architecture"]
    for k, v in src.items():
        if isinstance(v, dict) and k.endswith("_architecture"):
            return v
    return {}


def _migrate_seven_section(data: dict) -> dict:
    src = copy.deepcopy(data)
    ident = src.get("framework_identity") or src.get("framework_metadata") or {}
    if not isinstance(ident, dict):
        ident = {}
    core = _find_architecture_block(src)
    if not core:
        # VISUAL-019 style: principles_foundation / systematic_approach at top level
        synth = {}
        for k in ("principles_foundation", "systematic_approach", "core_thesis", "context"):
            if k in src:
                synth[k] = src[k]
        core = synth
    fm = src.get("force_multipliers") or src.get("compound_force_multipliers") or src.get("compound_leverage_points") or {}
    if not isinstance(fm, dict):
        fm = {"primary_multipliers": fm} if isinstance(fm, list) else {}
    impl_raw = src.get("implementation_methodology") or {}
    impl = impl_raw if isinstance(impl_raw, dict) else {}
    metrics_raw = src.get("success_metrics") or {}
    if isinstance(metrics_raw, list):
        metrics = {"leading_indicators": [str(m) for m in metrics_raw]}
    else:
        metrics = metrics_raw if isinstance(metrics_raw, dict) else {}
    integration_raw = src.get("integration_systems") or {}
    integration = integration_raw if isinstance(integration_raw, dict) else {}
    evolution = src.get("evolution_protocol", {})

    fid = _slug_id(ident.get("framework_id") or src.get("framework_id") or "FRAMEWORK-UNKNOWN-000")
    created = ident.get("creation_date") or ident.get("created_date") or src.get("created") or _today()

    out: dict[str, Any] = {
        "_spec_version": "1.0",
        "framework_id": fid,
        "name": ident.get("name") or src.get("name") or fid,
        "version": str(ident.get("version") or src.get("version") or "1.0.0"),
        "created_date": created,
        "updated_date": ident.get("updated_date") or src.get("updated") or created,
        "status": ident.get("status") or "active",
        "creator": ident.get("creator_context") or ident.get("creator"),
        "synopsis": (ident.get("purpose") or core.get("core_thesis") or ident.get("name") or "No synopsis available.")[:4000],
    }
    if ident.get("origin_story"):
        out["origin_story"] = ident["origin_story"]

    # Classification
    cat = src.get("category") or ident.get("category")
    domain = ident.get("domain") or cat or "uncategorized"
    tags = ident.get("trigger_keywords") or []
    if not tags and cat:
        tags = [cat]
    if not tags:
        tags = ["untagged"]
    series_match = re.match(r"FRAMEWORK-([A-Z0-9]+)-\d+", fid)
    out["classification"] = {
        "domain": domain,
        "tags": list(tags),
        "category": cat,
        "series": series_match.group(1) if series_match else None,
        "triggers": ident.get("trigger_keywords") or [],
    }
    out["classification"] = {k: v for k, v in out["classification"].items() if v is not None}

    # Layer 1: principles derived from core_thesis + any principle-like entries in core_architecture.
    principles = []
    thesis = core.get("core_thesis")
    if thesis:
        principles.append({
            "principle": (thesis.split(".")[0] + ".") if "." in thesis else thesis,
            "description": thesis,
        })
    # If there's a principles_foundation block under core_architecture, lift it.
    for key in ("principles", "principles_foundation", "core_principles"):
        if isinstance(core.get(key), list):
            for p in core[key]:
                if isinstance(p, dict) and p.get("principle"):
                    principles.append(p)
                elif isinstance(p, str):
                    principles.append({"principle": p, "description": p})
    if not principles:
        principles.append({
            "principle": "Framework principles were not explicit in the source document.",
            "description": "This framework was migrated from a v2 seven-section file that did not carry explicit principles. See _sios.core_architecture for the original content.",
        })
    out["layer_1_principles_foundation"] = {"core_principles": principles}

    # Layer 2: protocol steps from any *_protocol or systematic_approach block.
    steps = []
    candidate_blocks: list[dict] = []
    for key, val in core.items():
        if isinstance(val, dict) and (key.endswith("_protocol") or "systematic" in key.lower()):
            candidate_blocks.append(val)
    if isinstance(core.get("systematic_approach"), dict):
        candidate_blocks.append(core["systematic_approach"])
    if isinstance(src.get("systematic_approach"), dict):
        candidate_blocks.append(src["systematic_approach"])
    step_idx = 1
    for block in candidate_blocks:
        for step_key, step_val in block.items():
            if not step_key.startswith("step_"):
                continue
            if isinstance(step_val, dict):
                name = step_val.get("framework") or step_val.get("name") or step_val.get("title") or step_key.replace("_", " ").title()
                desc = step_val.get("action") or step_val.get("description") or step_val.get("detail") or name
            else:
                name = step_key.replace("_", " ").title()
                desc = str(step_val)
            steps.append({"step": step_idx, "name": name, "description": desc or name})
            step_idx += 1
    if not steps:
        steps.append({
            "step": 1,
            "name": "Apply the framework",
            "description": "Source document did not provide a numbered protocol. See _sios for original structure.",
        })
    out["layer_2_systematic_approach"] = {"methodology": out["name"], "steps": steps}

    # Layer 3: force_multipliers
    primary = []
    raw_primary = fm.get("primary_multipliers")
    if isinstance(raw_primary, list):
        for m in raw_primary:
            if isinstance(m, dict) and m.get("name"):
                entry = {"name": m["name"], "mechanism": m.get("mechanism") or m.get("description") or m.get("impact") or ""}
                for opt in ("estimated_return", "interaction_effects"):
                    if m.get(opt):
                        entry[opt] = m[opt]
                primary.append(entry)
            elif isinstance(m, str):
                # Coerce a bare string into a multiplier dict. Use first sentence as name.
                first = m.split(".")[0].strip()
                name = (first[:80] + "...") if len(first) > 80 else (first or "Multiplier")
                primary.append({"name": name, "mechanism": m})
            elif isinstance(m, dict):
                # Dict without explicit name: derive from first key.
                key = next(iter(m.keys()), "Multiplier")
                primary.append({"name": str(key), "mechanism": json.dumps(m, ensure_ascii=False)[:1000]})
    elif isinstance(fm.get("compound_effect"), dict):
        ce = fm["compound_effect"]
        primary.append({
            "name": "Compound effect",
            "mechanism": ce.get("compound_impact") or ce.get("example") or "See _sios.force_multipliers for full detail.",
        })
    if not primary:
        primary.append({"name": "Unspecified", "mechanism": "See _sios.force_multipliers for original content."})
    out["layer_3_force_multipliers"] = {"primary_multipliers": primary}

    # Layer 4: success_metrics
    sm = {
        "leading_indicators": _coerce_list(metrics.get("leading_indicators")),
        "lagging_indicators": _coerce_list(metrics.get("lagging_indicators")),
        "failure_modes": _coerce_list(metrics.get("failure_modes")),
        "red_flags_do_not_use_when": _coerce_list(metrics.get("red_flags_do_not_use_when")),
    }
    if not any(sm.values()):
        # Try nested (e.g. success_metrics.success_metrics)
        nested = metrics.get("success_metrics")
        if isinstance(nested, dict):
            for k, v in nested.items():
                sm["leading_indicators"].append(f"{k}: {v}")
    if not any(sm.values()):
        sm["leading_indicators"].append("Source document did not define explicit success metrics.")
    out["layer_4_success_metrics"] = sm

    # Layer 5: implementation_guidance
    guidance = {
        "entry_conditions": {"required": [], "optimal": []},
        "exit_conditions": [],
        "deployment_contexts": [],
    }
    if isinstance(impl, dict):
        if isinstance(impl.get("entry_conditions"), dict):
            ec = impl["entry_conditions"]
            guidance["entry_conditions"]["required"] = _coerce_list(ec.get("required"))
            guidance["entry_conditions"]["optimal"] = _coerce_list(ec.get("optimal"))
        guidance["exit_conditions"] = _coerce_list(impl.get("exit_conditions"))
        guidance["deployment_contexts"] = _coerce_list(impl.get("deployment_contexts"))
    if not guidance["entry_conditions"]["required"]:
        guidance["entry_conditions"]["required"] = ["Source document did not define explicit entry conditions."]
    if not guidance["exit_conditions"]:
        guidance["exit_conditions"] = ["Source document did not define explicit exit conditions."]
    out["layer_5_implementation_guidance"] = guidance

    # Relationships
    rel = _ensure_relationships(None)
    parents = _coerce_list(integration.get("parent_frameworks"))
    rel["depends_on"] = [_slug_id(x) for x in parents if isinstance(x, str)]
    rel["child_of"] = list(rel["depends_on"])
    related_compound = integration.get("related_compound")
    if related_compound:
        rel["related_to"].append(_slug_id(related_compound))
    out["relationships"] = rel

    # Preserve original structure namespaced
    out["_sios"] = {
        "original_format": "seven_section_v2",
        "core_architecture": core,
        "integration_systems": integration,
        "evolution_protocol": evolution,
    }
    # Preserve any other unknown top-level keys
    known = {
        "framework_identity", "core_architecture", "force_multipliers",
        "implementation_methodology", "success_metrics", "integration_systems",
        "evolution_protocol", "category",
    }
    for k, v in src.items():
        if k not in known and not k.startswith("_"):
            out["_sios"].setdefault("extra", {})[k] = v

    return out


def _migrate_five_layer_loose(data: dict) -> dict:
    """Handle older SIOS five-layer files that mostly match canonical but are missing
    required fields (classification, relationships block, etc.)."""
    src = copy.deepcopy(data)
    fid = _slug_id(src.get("framework_id") or "FRAMEWORK-UNKNOWN-000")
    created = src.get("created") or src.get("created_date") or _today()
    updated = src.get("updated") or src.get("updated_date") or created

    out: dict[str, Any] = {
        "_spec_version": "1.0",
        "framework_id": fid,
        "name": src.get("name") or fid,
        "version": str(src.get("version") or "1.0.0"),
        "created_date": created,
        "updated_date": updated,
        "status": src.get("status") or "active",
        "synopsis": (src.get("synopsis") or src.get("description") or src.get("name") or "No synopsis available.")[:4000],
    }

    # Classification
    category = src.get("category")
    series = src.get("series")
    series_match = re.match(r"FRAMEWORK-([A-Z0-9]+)-\d+", fid)
    if not series and series_match:
        series = series_match.group(1)
    triggers_block = src.get("triggers")
    trigger_list: list[str] = []
    tag_list: list[str] = []
    if isinstance(triggers_block, dict):
        for k in ("primary", "semantic", "auto_activation"):
            trigger_list.extend(_coerce_list(triggers_block.get(k)))
    elif isinstance(triggers_block, list):
        trigger_list = list(triggers_block)
    if category:
        tag_list.append(category)
    if series:
        tag_list.append(series.lower())
    if not tag_list:
        tag_list = ["untagged"]

    out["classification"] = {
        "domain": category or "uncategorized",
        "tags": tag_list,
        "category": category,
        "series": series,
        "tier": src.get("tier"),
        "triggers": trigger_list,
    }
    out["classification"] = {k: v for k, v in out["classification"].items() if v is not None}

    # Layers: copy if present, otherwise synthesize.
    for layer in CANONICAL_LAYERS:
        if layer in src and isinstance(src[layer], dict):
            out[layer] = src[layer]
        else:
            out[layer] = _default_layer(layer)

    # Ensure each layer meets its minimum schema requirements.
    out["layer_1_principles_foundation"] = _ensure_layer_1(out["layer_1_principles_foundation"])
    out["layer_2_systematic_approach"] = _ensure_layer_2(out["layer_2_systematic_approach"], out["name"])
    out["layer_3_force_multipliers"] = _ensure_layer_3(out["layer_3_force_multipliers"])
    out["layer_4_success_metrics"] = _ensure_layer_4(out["layer_4_success_metrics"])
    out["layer_5_implementation_guidance"] = _ensure_layer_5(out["layer_5_implementation_guidance"])

    # Relationships: derived from implementation_guidance.related_frameworks if present.
    rel = _ensure_relationships(src.get("relationships"))
    impl = out.get("layer_5_implementation_guidance", {})
    rf = impl.get("related_frameworks") if isinstance(impl, dict) else None
    if isinstance(rf, dict):
        for child in _coerce_list(rf.get("child_frameworks")):
            if isinstance(child, str):
                rel["parent_of"].append(_slug_id(child))
        for parent in _coerce_list(rf.get("parent_frameworks")):
            if isinstance(parent, str):
                rel["child_of"].append(_slug_id(parent))
    out["relationships"] = rel

    # Preserve unknown top-level keys under _sios.
    known = set(CANONICAL_LAYERS) | {
        "framework_id", "name", "version", "created", "updated", "created_date",
        "updated_date", "status", "synopsis", "description", "category", "series",
        "tier", "triggers", "relationships",
    }
    preserved = {k: v for k, v in src.items() if k not in known and not k.startswith("_")}
    if preserved:
        out["_sios"] = {"original_format": "five_layer_loose", "extra": preserved}
    else:
        out["_sios"] = {"original_format": "five_layer_loose"}

    return out


def _migrate_domain_layers(data: dict) -> dict:
    """Flat files with name/description/category/layers-dict/principles/methodology.
    Seen in Bach_Counterpoint and similar craft-translation files."""
    src = copy.deepcopy(data)
    name = src.get("name") or "Unknown Framework"
    fid = _slug_id(src.get("framework_id") or f"FRAMEWORK-{re.sub(r'[^A-Za-z0-9]', '', name).upper()[:20]}-001")
    created = src.get("created") or src.get("created_date") or _today()

    out: dict[str, Any] = {
        "_spec_version": "1.0",
        "framework_id": fid,
        "name": name,
        "version": str(src.get("version") or "1.0.0"),
        "created_date": created,
        "updated_date": src.get("updated") or src.get("updated_date") or created,
        "status": src.get("status") or "active",
        "synopsis": (src.get("description") or src.get("synopsis") or name)[:4000],
    }

    category = src.get("category")
    triggers_raw = src.get("triggers")
    if isinstance(triggers_raw, dict):
        triggers = []
        for v in triggers_raw.values():
            triggers.extend(_coerce_list(v))
    else:
        triggers = _coerce_list(triggers_raw)

    tags = [category] if category else []
    if not tags:
        tags = ["untagged"]
    out["classification"] = {
        "domain": category or "uncategorized",
        "tags": tags,
        "category": category,
        "triggers": triggers,
    }
    out["classification"] = {k: v for k, v in out["classification"].items() if v is not None}

    # Layer 1 from principles
    principles_raw = src.get("principles")
    principles: list[dict] = []
    if isinstance(principles_raw, list):
        for p in principles_raw:
            if isinstance(p, dict) and p.get("principle"):
                principles.append({"principle": p["principle"], "description": p.get("description") or p["principle"]})
            elif isinstance(p, str):
                principles.append({"principle": p, "description": p})
    elif isinstance(principles_raw, dict):
        for k, v in principles_raw.items():
            text = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False) if False else str(v)
            principles.append({"principle": k, "description": text if isinstance(v, str) else k})
    if not principles:
        principles = [{"principle": name, "description": out["synopsis"]}]
    out["layer_1_principles_foundation"] = {"core_principles": principles}

    # Layer 2 from methodology
    steps = []
    meth = src.get("methodology")
    if isinstance(meth, list):
        for i, step in enumerate(meth, 1):
            if isinstance(step, dict):
                steps.append({"step": i, "name": step.get("name") or step.get("step") or f"Step {i}", "description": step.get("description") or ""})
            elif isinstance(step, str):
                steps.append({"step": i, "name": f"Step {i}", "description": step})
    elif isinstance(meth, dict):
        for i, (k, v) in enumerate(meth.items(), 1):
            desc = v if isinstance(v, str) else str(v)
            steps.append({"step": i, "name": k, "description": desc})
    if not steps:
        steps = [{"step": 1, "name": "Apply the framework", "description": out["synopsis"]}]
    out["layer_2_systematic_approach"] = {"methodology": name, "steps": steps}

    # Layer 3: no explicit multipliers, derive from layers dict (named domain layers).
    layers = src.get("layers") or {}
    multipliers = []
    if isinstance(layers, dict):
        for k, v in layers.items():
            desc = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)[:500]
            multipliers.append({"name": k.replace("_", " ").title(), "mechanism": desc[:1000]})
    if not multipliers:
        multipliers = [{"name": "Domain principles", "mechanism": "See _sios.original for source structure."}]
    out["layer_3_force_multipliers"] = {"primary_multipliers": multipliers}

    # Layer 4
    out["layer_4_success_metrics"] = {
        "leading_indicators": ["Source document did not define explicit metrics."],
        "lagging_indicators": [],
        "failure_modes": [],
        "red_flags_do_not_use_when": [],
    }

    # Layer 5
    out["layer_5_implementation_guidance"] = {
        "entry_conditions": {"required": ["Source document did not define explicit entry conditions."], "optimal": []},
        "exit_conditions": ["Source document did not define explicit exit conditions."],
        "deployment_contexts": [],
    }

    out["relationships"] = _ensure_relationships(None)
    out["_sios"] = {"original_format": "domain_layers", "original": src}
    return out


def _default_layer(layer_key: str) -> dict:
    defaults = {
        "layer_1_principles_foundation": {"core_principles": []},
        "layer_2_systematic_approach": {"methodology": "", "steps": []},
        "layer_3_force_multipliers": {"primary_multipliers": []},
        "layer_4_success_metrics": {"leading_indicators": [], "lagging_indicators": [], "failure_modes": [], "red_flags_do_not_use_when": []},
        "layer_5_implementation_guidance": {"entry_conditions": {"required": [], "optimal": []}, "exit_conditions": [], "deployment_contexts": []},
    }
    return defaults[layer_key]


def _ensure_layer_1(layer: dict) -> dict:
    principles = layer.get("core_principles") or []
    if not principles:
        principles = [{
            "principle": "Principles were not explicit in the source document.",
            "description": "See _sios for original structure.",
        }]
    clean = []
    for p in principles:
        if isinstance(p, str):
            clean.append({"principle": p, "description": p})
        elif isinstance(p, dict) and p.get("principle"):
            entry = {"principle": p["principle"], "description": p.get("description") or p["principle"]}
            if p.get("evidence"):
                entry["evidence"] = p["evidence"]
            clean.append(entry)
    if not clean:
        clean = [{"principle": "Source document did not carry explicit principles.", "description": "See _sios for original structure."}]
    return {"core_principles": clean}


def _ensure_layer_2(layer: dict, name: str) -> dict:
    steps = layer.get("steps") or []
    clean = []
    for i, s in enumerate(steps, start=1):
        if isinstance(s, dict):
            clean.append({
                "step": s.get("step") or i,
                "name": s.get("name") or f"Step {i}",
                "description": s.get("description") or "",
            })
        elif isinstance(s, str):
            clean.append({"step": i, "name": f"Step {i}", "description": s})
    if not clean:
        clean = [{"step": 1, "name": "Apply the framework", "description": "Source document did not define explicit steps."}]
    return {"methodology": layer.get("methodology") or name, "steps": clean}


def _ensure_layer_3(layer: dict) -> dict:
    pm = layer.get("primary_multipliers") or []
    clean = []
    for m in pm:
        if isinstance(m, dict) and m.get("name"):
            clean.append({
                "name": m["name"],
                "mechanism": m.get("mechanism") or "",
                **({"estimated_return": m["estimated_return"]} if m.get("estimated_return") else {}),
                **({"interaction_effects": m["interaction_effects"]} if m.get("interaction_effects") else {}),
            })
        elif isinstance(m, str):
            clean.append({"name": m, "mechanism": m})
    if not clean:
        clean = [{"name": "Unspecified", "mechanism": "Source document did not define explicit force multipliers."}]
    return {"primary_multipliers": clean}


def _ensure_layer_4(layer: dict) -> dict:
    out = {
        "leading_indicators": _coerce_list(layer.get("leading_indicators")),
        "lagging_indicators": _coerce_list(layer.get("lagging_indicators")),
        "failure_modes": _coerce_list(layer.get("failure_modes")),
        "red_flags_do_not_use_when": _coerce_list(layer.get("red_flags_do_not_use_when")),
    }
    if not any(out.values()):
        out["leading_indicators"].append("Source document did not define explicit success metrics.")
    return out


def _ensure_layer_5(layer: dict) -> dict:
    ec = layer.get("entry_conditions") or {}
    if not isinstance(ec, dict):
        ec = {"required": _coerce_list(ec), "optimal": []}
    required = _coerce_list(ec.get("required"))
    optimal = _coerce_list(ec.get("optimal"))
    if not required:
        required = ["Source document did not define explicit entry conditions."]
    exit_conditions = _coerce_list(layer.get("exit_conditions"))
    if not exit_conditions:
        exit_conditions = ["Source document did not define explicit exit conditions."]
    deployment = _coerce_list(layer.get("deployment_contexts"))
    return {
        "entry_conditions": {"required": required, "optimal": optimal},
        "exit_conditions": exit_conditions,
        "deployment_contexts": deployment,
    }
