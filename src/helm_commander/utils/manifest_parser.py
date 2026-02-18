"""Parse multi-document YAML manifests into individual resources."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import yaml


@dataclass
class ParsedResource:
    api_version: str
    kind: str
    name: str
    namespace: str
    raw: dict[str, Any]


def parse_manifest(manifest: str) -> list[ParsedResource]:
    """Parse a multi-document YAML string into a list of ParsedResource."""
    resources: list[ParsedResource] = []
    if not manifest:
        return resources

    for doc in yaml.safe_load_all(manifest):
        if not doc or not isinstance(doc, dict):
            continue
        metadata = doc.get("metadata", {}) or {}
        resources.append(ParsedResource(
            api_version=doc.get("apiVersion", ""),
            kind=doc.get("kind", ""),
            name=metadata.get("name", ""),
            namespace=metadata.get("namespace", ""),
            raw=doc,
        ))
    return resources


def resource_counts(manifest: str) -> dict[str, int]:
    """Count resources by kind in a manifest string."""
    counts: dict[str, int] = {}
    for res in parse_manifest(manifest):
        counts[res.kind] = counts.get(res.kind, 0) + 1
    return counts
