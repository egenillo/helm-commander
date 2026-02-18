"""Compare stored Helm manifests against live cluster resources."""

from __future__ import annotations

import logging
from typing import Any

from deepdiff import DeepDiff

from helm_commander.core.k8s_client import K8sClient
from helm_commander.models.diff import DiffStatus, DriftResult, ResourceDiff
from helm_commander.models.release import HelmRelease
from helm_commander.utils.manifest_parser import ParsedResource, parse_manifest

logger = logging.getLogger(__name__)

# Fields managed by the server that should be ignored in drift comparison
IGNORED_FIELDS = {
    "metadata.resourceVersion",
    "metadata.uid",
    "metadata.creationTimestamp",
    "metadata.generation",
    "metadata.managedFields",
    "metadata.selfLink",
    "metadata.annotations.kubectl.kubernetes.io/last-applied-configuration",
    "status",
}


def _strip_server_fields(obj: dict, prefix: str = "") -> dict:
    """Remove server-managed fields from a resource dict for comparison."""
    cleaned = {}
    for key, value in obj.items():
        full_key = f"{prefix}.{key}" if prefix else key
        if full_key in IGNORED_FIELDS:
            continue
        if isinstance(value, dict):
            inner = _strip_server_fields(value, full_key)
            if inner:
                cleaned[key] = inner
        else:
            cleaned[key] = value
    return cleaned


def _fetch_live_resource(
    res: ParsedResource, namespace: str, k8s: K8sClient
) -> dict | None:
    """Fetch the live version of a resource from the cluster."""
    kind = res.kind
    api_version = res.api_version

    # Cluster-scoped resources don't use namespace
    if K8sClient.is_cluster_scoped(kind, res.namespace):
        return k8s.get_cluster_resource(api_version, kind, res.name)

    ns = res.namespace or namespace

    # Try apps/v1 resources
    if api_version in ("apps/v1",):
        return k8s.get_apps_resource(kind, res.name, ns)

    # Core and custom resources
    return k8s.get_resource(api_version, kind, res.name, ns)


def detect_drift(release: HelmRelease, k8s: K8sClient) -> DriftResult:
    """Compare stored manifests with live cluster state."""
    result = DriftResult(release_name=release.name, namespace=release.namespace)
    resources = parse_manifest(release.manifest)

    for res in resources:
        if not res.kind or not res.name:
            continue

        cluster_scoped = K8sClient.is_cluster_scoped(res.kind, res.namespace)
        diff_namespace = "" if cluster_scoped else (res.namespace or release.namespace)

        live = _fetch_live_resource(res, release.namespace, k8s)

        if live is None:
            result.diffs.append(ResourceDiff(
                api_version=res.api_version,
                kind=res.kind,
                name=res.name,
                namespace=diff_namespace,
                status=DiffStatus.MISSING_LIVE,
                details=["Resource not found in cluster"],
            ))
            continue

        # Strip server-managed fields from both
        stored_clean = _strip_server_fields(res.raw)
        live_clean = _strip_server_fields(live)

        diff = DeepDiff(
            stored_clean,
            live_clean,
            ignore_order=True,
            verbose_level=2,
        )

        if diff:
            details = _format_diff(diff)
            result.diffs.append(ResourceDiff(
                api_version=res.api_version,
                kind=res.kind,
                name=res.name,
                namespace=diff_namespace,
                status=DiffStatus.MODIFIED,
                details=details,
            ))
        else:
            result.diffs.append(ResourceDiff(
                api_version=res.api_version,
                kind=res.kind,
                name=res.name,
                namespace=diff_namespace,
                status=DiffStatus.UNCHANGED,
            ))

    return result


def _format_diff(diff: DeepDiff) -> list[str]:
    """Format DeepDiff output into human-readable strings."""
    details: list[str] = []

    if "values_changed" in diff:
        for path, change in diff["values_changed"].items():
            old = change.get("old_value", "?")
            new = change.get("new_value", "?")
            details.append(f"Changed {path}: {old!r} -> {new!r}")

    if "dictionary_item_added" in diff:
        for path in diff["dictionary_item_added"]:
            details.append(f"Added: {path}")

    if "dictionary_item_removed" in diff:
        for path in diff["dictionary_item_removed"]:
            details.append(f"Removed: {path}")

    if "iterable_item_added" in diff:
        for path in diff["iterable_item_added"]:
            details.append(f"List item added: {path}")

    if "iterable_item_removed" in diff:
        for path in diff["iterable_item_removed"]:
            details.append(f"List item removed: {path}")

    if "type_changes" in diff:
        for path, change in diff["type_changes"].items():
            details.append(f"Type changed {path}: {change}")

    return details or ["Differences detected (see raw diff)"]
