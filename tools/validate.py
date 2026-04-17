"""Validate canonical v1.0 framework files against SPECIFICATION.md."""
from __future__ import annotations

import re
from typing import Any

from migrate import CANONICAL_LAYERS, REL_TYPES

FID_PATTERN = re.compile(r"^FRAMEWORK-[A-Z0-9]+(?:-[A-Z0-9]+)?-\d{3,}$")
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
SEMVER_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")
STATUS_VALUES = {"draft", "active", "deprecated", "archived"}


def validate(data: dict) -> list[str]:
    errors: list[str] = []

    for key in ("framework_id", "name", "version", "created_date", "updated_date", "status", "synopsis"):
        if key not in data:
            errors.append(f"missing required field: {key}")

    if "framework_id" in data and not FID_PATTERN.match(str(data["framework_id"])):
        errors.append(f"framework_id '{data['framework_id']}' does not match FRAMEWORK-XXX-NNN")
    if "version" in data and not SEMVER_PATTERN.match(str(data["version"])):
        errors.append(f"version '{data['version']}' is not semver")
    for df in ("created_date", "updated_date"):
        if df in data and not DATE_PATTERN.match(str(data[df])):
            errors.append(f"{df} '{data[df]}' is not YYYY-MM-DD")
    if "status" in data and data["status"] not in STATUS_VALUES:
        errors.append(f"status '{data['status']}' not one of {STATUS_VALUES}")

    cls = data.get("classification")
    if not isinstance(cls, dict):
        errors.append("classification block missing or not an object")
    else:
        if not cls.get("domain"):
            errors.append("classification.domain required")
        tags = cls.get("tags")
        if not isinstance(tags, list) or not tags:
            errors.append("classification.tags required (at least one)")

    for layer in CANONICAL_LAYERS:
        if layer not in data:
            errors.append(f"missing layer: {layer}")

    l1 = data.get("layer_1_principles_foundation", {})
    if not l1.get("core_principles"):
        errors.append("layer_1.core_principles required (at least one)")
    else:
        for i, p in enumerate(l1["core_principles"]):
            if not isinstance(p, dict) or not p.get("principle") or not p.get("description"):
                errors.append(f"layer_1.core_principles[{i}] needs principle and description")

    l2 = data.get("layer_2_systematic_approach", {})
    if not l2.get("steps"):
        errors.append("layer_2.steps required (at least one)")
    else:
        for i, s in enumerate(l2["steps"]):
            if not isinstance(s, dict) or not s.get("name") or not s.get("description"):
                errors.append(f"layer_2.steps[{i}] needs name and description")

    l3 = data.get("layer_3_force_multipliers", {})
    if not l3.get("primary_multipliers"):
        errors.append("layer_3.primary_multipliers required (at least one)")
    else:
        for i, m in enumerate(l3["primary_multipliers"]):
            if not isinstance(m, dict) or not m.get("name") or not m.get("mechanism"):
                errors.append(f"layer_3.primary_multipliers[{i}] needs name and mechanism")

    l4 = data.get("layer_4_success_metrics", {})
    if not any([
        l4.get("leading_indicators"),
        l4.get("lagging_indicators"),
        l4.get("failure_modes"),
    ]):
        errors.append("layer_4 requires at least one of leading_indicators, lagging_indicators, failure_modes")

    l5 = data.get("layer_5_implementation_guidance", {})
    ec = l5.get("entry_conditions") or {}
    if not ec.get("required"):
        errors.append("layer_5.entry_conditions.required required (at least one)")
    if not l5.get("exit_conditions"):
        errors.append("layer_5.exit_conditions required (at least one)")

    rel = data.get("relationships")
    if not isinstance(rel, dict):
        errors.append("relationships block missing")
    else:
        for rt in REL_TYPES:
            if rt not in rel:
                errors.append(f"relationships.{rt} missing (may be empty array)")
            elif not isinstance(rel[rt], list):
                errors.append(f"relationships.{rt} must be an array")
            else:
                for j, ref in enumerate(rel[rt]):
                    if not isinstance(ref, str) or not FID_PATTERN.match(ref):
                        errors.append(f"relationships.{rt}[{j}] '{ref}' not a valid framework_id")

    return errors
