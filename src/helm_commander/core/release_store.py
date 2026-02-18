"""High-level release list / get / filter operations."""

from __future__ import annotations

import re
from collections import defaultdict

from helm_commander.core.helm_decoder import decode_configmap, decode_secret, quick_metadata_from_labels
from helm_commander.core.k8s_client import K8sClient
from helm_commander.config.settings import settings
from helm_commander.models.release import HelmRelease, ReleaseStatus


class ReleaseStore:
    """Fetches and caches Helm releases from the cluster."""

    def __init__(self, k8s: K8sClient):
        self.k8s = k8s

    def list_releases(
        self,
        namespace: str | None = None,
        filter_regex: str | None = None,
        only: str | None = None,
    ) -> list[HelmRelease]:
        """List the latest revision of each Helm release."""
        context = self.k8s.active_context_name

        if settings.storage_driver == "configmaps":
            objects = self.k8s.list_helm_configmaps(namespace=namespace)
            decode_fn = decode_configmap
        else:
            objects = self.k8s.list_helm_secrets(namespace=namespace)
            decode_fn = decode_secret

        # Group by (release_name, namespace) and keep only the latest revision
        grouped: dict[tuple[str, str], list] = defaultdict(list)
        for obj in objects:
            meta = quick_metadata_from_labels(obj, context)
            key = (meta["name"], meta["namespace"])
            grouped[key].append((meta["version"], obj))

        releases: list[HelmRelease] = []
        for key, versions in grouped.items():
            # Pick the highest revision
            versions.sort(key=lambda x: x[0], reverse=True)
            _, latest_obj = versions[0]
            release = decode_fn(latest_obj, context=context)
            if release:
                releases.append(release)

        # Apply filters
        if filter_regex:
            pattern = re.compile(filter_regex, re.IGNORECASE)
            releases = [
                r for r in releases
                if pattern.search(r.name) or pattern.search(r.chart_name)
            ]

        if only:
            releases = self._apply_status_filter(releases, only)

        # Sort by namespace, then name
        releases.sort(key=lambda r: (r.namespace, r.name))
        return releases

    def get_release(
        self,
        name: str,
        namespace: str | None = None,
    ) -> HelmRelease | None:
        """Get the latest revision of a single release by name."""
        context = self.k8s.active_context_name

        if settings.storage_driver == "configmaps":
            objects = self.k8s.list_helm_configmaps(namespace=namespace, release_name=name)
            decode_fn = decode_configmap
        else:
            objects = self.k8s.list_helm_secrets(namespace=namespace, release_name=name)
            decode_fn = decode_secret

        if not objects:
            return None

        # Pick the highest revision
        best_version = -1
        best_obj = None
        for obj in objects:
            meta = quick_metadata_from_labels(obj, context)
            if meta["version"] > best_version:
                best_version = meta["version"]
                best_obj = obj

        if best_obj is None:
            return None

        return decode_fn(best_obj, context=context)

    def get_all_revisions(
        self,
        name: str,
        namespace: str | None = None,
    ) -> list[HelmRelease]:
        """Get all revisions of a release, sorted by version ascending."""
        context = self.k8s.active_context_name

        if settings.storage_driver == "configmaps":
            objects = self.k8s.list_helm_configmaps(namespace=namespace, release_name=name)
            decode_fn = decode_configmap
        else:
            objects = self.k8s.list_helm_secrets(namespace=namespace, release_name=name)
            decode_fn = decode_secret

        revisions: list[HelmRelease] = []
        for obj in objects:
            release = decode_fn(obj, context=context)
            if release:
                revisions.append(release)

        revisions.sort(key=lambda r: r.version)
        return revisions

    @staticmethod
    def _apply_status_filter(releases: list[HelmRelease], only: str) -> list[HelmRelease]:
        mapping = {
            "deployed": {ReleaseStatus.DEPLOYED},
            "failed": {ReleaseStatus.FAILED},
            "pending": {
                ReleaseStatus.PENDING_INSTALL,
                ReleaseStatus.PENDING_UPGRADE,
                ReleaseStatus.PENDING_ROLLBACK,
            },
            "problematic": {
                ReleaseStatus.FAILED,
                ReleaseStatus.PENDING_INSTALL,
                ReleaseStatus.PENDING_UPGRADE,
                ReleaseStatus.PENDING_ROLLBACK,
                ReleaseStatus.UNINSTALLING,
                ReleaseStatus.UNKNOWN,
            },
        }
        statuses = mapping.get(only)
        if statuses is None:
            return releases
        return [r for r in releases if r.status in statuses]
