"""Diagnostic checks for Helm releases."""

from __future__ import annotations

import logging
from collections import defaultdict

from helm_commander.core.helm_decoder import quick_metadata_from_labels
from helm_commander.core.k8s_client import K8sClient
from helm_commander.config.settings import settings
from helm_commander.models.doctor import DiagnosticResult, Severity
from helm_commander.models.release import HelmRelease, ReleaseStatus

logger = logging.getLogger(__name__)


def run_diagnostics(
    releases: list[HelmRelease],
    k8s: K8sClient,
    namespace: str | None = None,
) -> list[DiagnosticResult]:
    """Run all diagnostic checks and return results."""
    results: list[DiagnosticResult] = []
    results.extend(_check_storage_driver(k8s, namespace))
    results.extend(_check_failed_releases(releases))
    results.extend(_check_pending_releases(releases))
    results.extend(_check_superseded_only(k8s, namespace))
    results.extend(_check_duplicate_releases(releases))
    results.extend(_check_orphaned_secrets(k8s, namespace, releases))
    results.extend(_check_old_revisions(k8s, namespace))
    return results


def _check_storage_driver(k8s: K8sClient, namespace: str | None) -> list[DiagnosticResult]:
    """Detect which storage driver is in use."""
    results: list[DiagnosticResult] = []
    try:
        secrets = k8s.list_helm_secrets(namespace=namespace)
        configmaps = k8s.list_helm_configmaps(namespace=namespace)

        if secrets and configmaps:
            results.append(DiagnosticResult(
                check_name="storage_driver",
                severity=Severity.WARNING,
                message=f"Mixed storage: {len(secrets)} secrets and {len(configmaps)} configmaps found",
                suggestion="This may indicate migrated or misconfigured releases. Consider standardizing on secrets.",
            ))
        elif configmaps and not secrets:
            results.append(DiagnosticResult(
                check_name="storage_driver",
                severity=Severity.INFO,
                message=f"Storage driver: configmaps ({len(configmaps)} release objects)",
            ))
        else:
            results.append(DiagnosticResult(
                check_name="storage_driver",
                severity=Severity.INFO,
                message=f"Storage driver: secrets ({len(secrets)} release objects)",
            ))
    except Exception as e:
        results.append(DiagnosticResult(
            check_name="storage_driver",
            severity=Severity.ERROR,
            message=f"Could not detect storage driver: {e}",
            suggestion="Check cluster connectivity and RBAC permissions.",
        ))
    return results


def _check_failed_releases(releases: list[HelmRelease]) -> list[DiagnosticResult]:
    results: list[DiagnosticResult] = []
    for r in releases:
        if r.status == ReleaseStatus.FAILED:
            results.append(DiagnosticResult(
                check_name="failed_release",
                severity=Severity.ERROR,
                message=f"Release '{r.name}' in namespace '{r.namespace}' is in FAILED state",
                suggestion=f"Check release description: {r.info.description or 'N/A'}. "
                           "Consider rollback or uninstall.",
                release_name=r.name,
                namespace=r.namespace,
            ))
    return results


def _check_pending_releases(releases: list[HelmRelease]) -> list[DiagnosticResult]:
    pending_statuses = {
        ReleaseStatus.PENDING_INSTALL,
        ReleaseStatus.PENDING_UPGRADE,
        ReleaseStatus.PENDING_ROLLBACK,
    }
    results: list[DiagnosticResult] = []
    for r in releases:
        if r.status in pending_statuses:
            results.append(DiagnosticResult(
                check_name="pending_release",
                severity=Severity.WARNING,
                message=f"Release '{r.name}' in namespace '{r.namespace}' is stuck in '{r.status.value}'",
                suggestion="This may indicate a failed or interrupted operation. "
                           "Check pod status and consider rollback.",
                release_name=r.name,
                namespace=r.namespace,
            ))
    return results


def _check_superseded_only(k8s: K8sClient, namespace: str | None) -> list[DiagnosticResult]:
    """Check for releases where ALL revisions are superseded (no deployed version)."""
    results: list[DiagnosticResult] = []
    try:
        objects = k8s.list_helm_secrets(namespace=namespace)
        context = k8s.active_context_name

        grouped: dict[tuple[str, str], list[str]] = defaultdict(list)
        for obj in objects:
            meta = quick_metadata_from_labels(obj, context)
            key = (meta["name"], meta["namespace"])
            grouped[key].append(meta["status"])

        for (name, ns), statuses in grouped.items():
            if name and all(s == "superseded" for s in statuses):
                results.append(DiagnosticResult(
                    check_name="superseded_only",
                    severity=Severity.WARNING,
                    message=f"Release '{name}' in '{ns}' has only superseded revisions (no deployed version)",
                    suggestion="This release may be orphaned. Consider cleanup.",
                    release_name=name,
                    namespace=ns,
                ))
    except Exception:
        logger.debug("Failed superseded-only check", exc_info=True)
    return results


def _check_duplicate_releases(releases: list[HelmRelease]) -> list[DiagnosticResult]:
    """Check for releases with the same chart deployed multiple times in the same namespace."""
    results: list[DiagnosticResult] = []
    chart_locations: dict[tuple[str, str], list[str]] = defaultdict(list)

    for r in releases:
        if r.status == ReleaseStatus.DEPLOYED:
            chart_locations[(r.chart_name, r.namespace)].append(r.name)

    for (chart, ns), names in chart_locations.items():
        if len(names) > 1:
            results.append(DiagnosticResult(
                check_name="duplicate_chart",
                severity=Severity.INFO,
                message=f"Chart '{chart}' deployed {len(names)} times in namespace '{ns}': {', '.join(names)}",
                suggestion="This may be intentional. Verify if multiple instances are needed.",
            ))
    return results


def _check_orphaned_secrets(
    k8s: K8sClient, namespace: str | None, releases: list[HelmRelease]
) -> list[DiagnosticResult]:
    """Check for Helm secrets without a matching deployed release."""
    results: list[DiagnosticResult] = []
    deployed_names = {(r.name, r.namespace) for r in releases if r.status == ReleaseStatus.DEPLOYED}

    try:
        objects = k8s.list_helm_secrets(namespace=namespace)
        context = k8s.active_context_name

        all_names: set[tuple[str, str]] = set()
        for obj in objects:
            meta = quick_metadata_from_labels(obj, context)
            if meta["name"]:
                all_names.add((meta["name"], meta["namespace"]))

        orphaned = all_names - deployed_names
        for name, ns in orphaned:
            # Only flag if there's no deployed version
            if not any(r.name == name and r.namespace == ns for r in releases):
                results.append(DiagnosticResult(
                    check_name="orphaned_secrets",
                    severity=Severity.INFO,
                    message=f"Helm secrets exist for '{name}' in '{ns}' but no deployed release found",
                    suggestion="These may be leftover from an uninstall. Consider manual cleanup.",
                    release_name=name,
                    namespace=ns,
                ))
    except Exception:
        logger.debug("Failed orphaned secrets check", exc_info=True)
    return results


def _check_old_revisions(k8s: K8sClient, namespace: str | None) -> list[DiagnosticResult]:
    """Check for releases with many stored revisions."""
    results: list[DiagnosticResult] = []
    try:
        objects = k8s.list_helm_secrets(namespace=namespace)
        context = k8s.active_context_name

        revision_counts: dict[tuple[str, str], int] = defaultdict(int)
        for obj in objects:
            meta = quick_metadata_from_labels(obj, context)
            if meta["name"]:
                revision_counts[(meta["name"], meta["namespace"])] += 1

        for (name, ns), count in revision_counts.items():
            if count > 10:
                results.append(DiagnosticResult(
                    check_name="many_revisions",
                    severity=Severity.INFO,
                    message=f"Release '{name}' in '{ns}' has {count} stored revisions",
                    suggestion="Consider setting --history-max on helm upgrade to limit stored revisions.",
                    release_name=name,
                    namespace=ns,
                ))
    except Exception:
        logger.debug("Failed old revisions check", exc_info=True)
    return results
