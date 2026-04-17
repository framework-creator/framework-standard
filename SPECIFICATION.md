# Portable Framework Format Specification

**Version:** 1.0
**Status:** Draft for internal validation
**File extension:** `.framework.json`
**Encoding:** UTF-8
**License of spec:** MIT

## 1. Purpose

A `.framework.json` file is a portable, self-contained description of a single reusable framework. The format is designed so that:

1. Any tool (SIOS, a future graph UI, a third-party ingester) can read a framework without additional context.
2. Relationships between frameworks are expressed explicitly, so a collection of files can be assembled into a graph without running the original authoring system.
3. A human can open the file in any editor and read it.
4. The format survives round-tripping: export from one tool, import into another, export again, with no structural loss.

This spec is derived from the SIOS framework library (600+ files as of April 2026). It formalizes what is already working.

## 2. Top-level structure

A framework file is a single JSON object. Fields are grouped into four blocks:

| Block | Purpose |
|------|---------|
| Identity | What this framework is, who made it, when |
| Classification | Where it sits in the taxonomy |
| Content (Layers 1 to 5) | The framework itself |
| Relationships | How it connects to other frameworks |

All blocks MUST be present at the top level of the JSON object. Fields within each block are marked REQUIRED or OPTIONAL below.

## 3. Identity block

```json
{
  "framework_id": "FRAMEWORK-FILM-007",
  "name": "Cinematographic Web Design Intelligence",
  "version": "1.0.0",
  "created_date": "2026-02-24",
  "updated_date": "2026-02-24",
  "status": "active",
  "creator": "RageDesigner Strategic Intelligence Operating System",
  "synopsis": "One-paragraph description of what this framework does."
}
```

### Required fields

- **framework_id** (string). Unique identifier. Format: `FRAMEWORK-{DOMAIN}-{NNN}` where DOMAIN is an uppercase alphanumeric identifier (FILM, INFRA, AUDIO, 0001, etc.) and NNN is a zero-padded 3-digit sequence. The full identifier must be unique across any library that contains this file.
- **name** (string). Human-readable title. Keep under 80 characters.
- **version** (string). Semver (`MAJOR.MINOR.PATCH`). MAJOR bumps indicate breaking changes to the framework's architecture. MINOR bumps add content. PATCH bumps fix errors.
- **created_date** (string). ISO 8601 date (`YYYY-MM-DD`).
- **updated_date** (string). ISO 8601 date. Equal to `created_date` on first write.
- **status** (string). One of: `draft`, `active`, `deprecated`, `archived`.
- **synopsis** (string). One paragraph, 1 to 4 sentences, describing what the framework does and why it exists. Used for search and preview cards.

### Optional fields

- **creator** (string). Author or system that produced the framework.
- **origin_story** (string). How or why the framework was built. Narrative context, useful for teaching and for future maintainers.

## 4. Classification block

```json
{
  "classification": {
    "domain": "compound_intelligence",
    "category": "video",
    "series": "FILM",
    "tier": "compound",
    "tags": ["cinematography", "web_design", "compound"],
    "triggers": ["shot list", "cinematographic", "direct the page"]
  }
}
```

### Required fields

- **classification.domain** (string). The broad subject area (e.g. `cinematography`, `infrastructure`, `distribution`, `compound_intelligence`).
- **classification.tags** (array of strings). Freeform tags for search. At least one tag is required.

### Optional fields

- **classification.category** (string). Narrower grouping within the domain.
- **classification.series** (string). Series identifier if the framework is part of a numbered series (e.g. `FILM`, `INFRA`, `0000`).
- **classification.tier** (string). Position within a series: `foundation`, `component`, `compound`, `meta`.
- **classification.triggers** (array of strings). Keywords or phrases that should activate this framework when matched against user intent. Case-insensitive substring match is the default semantic.

## 5. 343 coordinates block (optional)

For frameworks that have been placed within the SIOS 343 taxonomy. Any framework MAY include this block; tools MUST treat it as informational and MUST NOT require it.

```json
{
  "coordinates_343": {
    "primary_meta_category": "Intelligence",
    "cognitive_foundations_activated": ["Logic", "Intelligence", "Strategy"],
    "transformation_pattern": "Integration Architecture",
    "contextual_triggers": {
      "situation_triggers": ["..."],
      "signal_triggers": ["..."],
      "problem_state_triggers": ["..."],
      "transition_triggers": ["..."]
    }
  }
}
```

Full rationale strings (`primary_meta_category_rationale`, etc.) are permitted but not required.

## 6. Content block (five layers)

The framework's actual content is expressed as five layers. Every framework MUST define all five layers. A layer with no content is still present as an empty object or empty array, so that ingesters can rely on the key existing.

### Layer 1 — Principles foundation

The non-negotiable beliefs the framework rests on. Each principle should be stateable as a single claim and defensible with evidence.

```json
{
  "layer_1_principles_foundation": {
    "core_principles": [
      {
        "principle": "Short claim stated as a single sentence.",
        "description": "Longer explanation of why the claim holds.",
        "evidence": "Empirical or logical support for the claim."
      }
    ]
  }
}
```

Required: `core_principles` array with at least one entry. Each entry requires `principle` and `description`. `evidence` is optional but strongly encouraged.

### Layer 2 — Systematic approach

The ordered steps, methodology, or protocol that operationalises the principles.

```json
{
  "layer_2_systematic_approach": {
    "methodology": "Short name for the methodology.",
    "steps": [
      {
        "step": 1,
        "name": "Step name",
        "description": "What happens in this step and what it produces."
      }
    ]
  }
}
```

Required: `steps` array with at least one entry. Each step requires `step` (integer, starting at 1), `name`, and `description`.

### Layer 3 — Force multipliers

The mechanisms that make the framework produce outsized returns. These are the leverage points, not the surface behaviour.

```json
{
  "layer_3_force_multipliers": {
    "primary_multipliers": [
      {
        "name": "Multiplier name",
        "mechanism": "How the multiplier produces its effect.",
        "estimated_return": "Rough size of the effect.",
        "interaction_effects": "How this multiplier compounds with others."
      }
    ]
  }
}
```

Required: `primary_multipliers` array with at least one entry. Each entry requires `name` and `mechanism`.

### Layer 4 — Success metrics

How a practitioner knows the framework is working.

```json
{
  "layer_4_success_metrics": {
    "leading_indicators": ["..."],
    "lagging_indicators": ["..."],
    "failure_modes": [
      {
        "mode": "Name of the failure mode",
        "symptom": "What it looks like",
        "resolution": "How to correct it"
      }
    ],
    "red_flags_do_not_use_when": ["..."]
  }
}
```

Required: at least one of `leading_indicators`, `lagging_indicators`, or `failure_modes` must be non-empty.

### Layer 5 — Implementation guidance

How to apply the framework in practice. Entry and exit conditions, deployment contexts, teaching protocol.

```json
{
  "layer_5_implementation_guidance": {
    "entry_conditions": {
      "required": ["..."],
      "optimal": ["..."]
    },
    "exit_conditions": ["..."],
    "deployment_contexts": [
      {
        "context": "Context name",
        "description": "How the framework is used in this context"
      }
    ]
  }
}
```

Required: `entry_conditions.required` (array with at least one entry) and `exit_conditions` (array with at least one entry).

## 7. Relationships block

Explicit graph edges from this framework to others. This is the primary data source for the Phase 3 visual graph.

```json
{
  "relationships": {
    "depends_on": ["FRAMEWORK-FILM-001", "FRAMEWORK-FILM-002"],
    "extends": [],
    "related_to": ["FRAMEWORK-2001-006"],
    "triggers": [],
    "conflicts_with": [],
    "parent_of": [],
    "child_of": []
  }
}
```

### Relationship types

- **depends_on**: This framework requires the listed frameworks to function. A SPOF audit without redundancy architecture is diagnosis without treatment.
- **extends**: This framework builds directly on the listed frameworks, adding capability while preserving compatibility.
- **related_to**: Topically adjacent. Useful for recommendations, not for dependency resolution.
- **triggers**: Applying this framework should automatically activate the listed frameworks.
- **conflicts_with**: Listed frameworks cover similar ground differently. Using both in the same session may produce contradictory guidance.
- **parent_of** / **child_of**: Hierarchical containment. A compound framework is `parent_of` its components; those components are `child_of` the compound.

All relationship arrays MUST be present (may be empty). Every listed value MUST be a valid `framework_id` string. Ingesters SHOULD warn when a referenced ID is not present in the loaded library, but MUST NOT reject the file.

## 8. Evidence and history (optional)

```json
{
  "evidence_base": {
    "validation_sources": ["..."],
    "case_studies": ["..."]
  },
  "version_history": {
    "1.0.0_2026_02_24": "Initial release."
  }
}
```

Both blocks are optional and freeform. Tools MUST preserve them on round-trip even when they do not understand the contents.

## 9. Extensibility

Unknown top-level fields MUST be preserved by any tool that reads and rewrites the file. This permits experimental metadata (embedding vectors, usage analytics, PAP governance signatures) to travel with the framework without requiring a spec change.

Tools MAY add fields under a namespaced key such as `_sios`, `_ragedesigner`, or `_experimental`. Namespaced keys MUST be ignored by tools that did not write them.

## 10. Validation rules summary

A file is a valid `.framework.json` if and only if:

1. It parses as a single JSON object.
2. All Identity required fields are present with correct types.
3. `classification.domain` and `classification.tags` are present, with at least one tag.
4. All five content layer keys are present (`layer_1_principles_foundation` through `layer_5_implementation_guidance`).
5. Each layer satisfies its own required-fields rules (Section 6).
6. `relationships` is present with all six relationship arrays defined (possibly empty).
7. Every value in every `relationships` array is a string matching the `framework_id` format.

A minimal valid framework demonstrating each rule at its smallest form is provided in `examples/minimal-example.framework.json`. A full example is `examples/full-example.framework.json`.

## 11. Relationship to existing SIOS framework files

The SIOS library currently contains two structural variants:

- **v1 (five-layer):** `layer_1_principles_foundation` through `layer_5_implementation_guidance`. Example: `FRAMEWORK-0001_Master_Strategic_Intelligence_v8_0.json`.
- **v2 (seven-section):** `framework_identity`, `core_architecture`, `force_multipliers`, `implementation_methodology`, `success_metrics`, `integration_systems`, `evolution_protocol`. Example: `FRAMEWORK-FILM-007`, `FRAMEWORK-INFRA-008`.

This specification canonicalises the five-layer structure. A Phase 2 migration tool will convert v2 files to the canonical form using the following mapping:

| v2 section | Canonical destination |
|------------|----------------------|
| `framework_identity` | Identity block + `classification` |
| `core_architecture` | `layer_1_principles_foundation` (principles extracted from `core_thesis` and protocol steps) |
| `core_architecture.*_protocol` | `layer_2_systematic_approach` |
| `force_multipliers` | `layer_3_force_multipliers` |
| `success_metrics` | `layer_4_success_metrics` |
| `implementation_methodology` | `layer_5_implementation_guidance` |
| `integration_systems.parent_frameworks` | `relationships.child_of` |
| `integration_systems.related_compound` | `relationships.related_to` |
| `evolution_protocol` | Preserved under `_sios.evolution_protocol` |

The migration is lossless: every v2 field either maps to a canonical destination or is preserved under the `_sios` namespace.

## 12. File naming

The canonical filename is:

```
{framework_id}_{slugified_name}.framework.json
```

Example: `FRAMEWORK-FILM-007_cinematographic_web_design_intelligence.framework.json`.

Tools MUST NOT require this filename. The authoritative `framework_id` lives inside the file. Renaming a file does not change its identity.

## 13. Versioning of this specification

This specification itself uses semver. Changes that add optional fields are MINOR. Changes that add required fields or reinterpret existing fields are MAJOR. The current version is `1.0`.

A framework file MAY declare the spec version it targets via `_spec_version: "1.0"` at the top level. When absent, tools MUST assume `1.0`.
