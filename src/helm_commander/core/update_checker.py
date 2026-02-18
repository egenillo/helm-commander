"""Compare deployed chart versions against available versions."""

from __future__ import annotations

import logging
from typing import Callable

from helm_commander.core.repo_resolver import clear_caches, get_all_repo_versions, resolve_source
from helm_commander.models.release import HelmRelease
from helm_commander.models.repo import SourceMatch, UpdateInfo
from helm_commander.utils.version_compare import classify_update, is_newer, parse_version

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[int, int, str], None]


def check_updates(
    releases: list[HelmRelease],
    on_progress: ProgressCallback | None = None,
) -> list[UpdateInfo]:
    """Check for available updates for a list of releases."""
    clear_caches()
    results: list[UpdateInfo] = []
    total = len(releases)

    for i, release in enumerate(releases, 1):
        chart_name = release.chart_name
        current_version = release.chart_version

        if not chart_name or not current_version:
            continue

        if on_progress:
            on_progress(i, total, chart_name)

        source = resolve_source(chart_name, current_version)
        repo_versions = get_all_repo_versions(chart_name)

        latest = _find_latest(current_version, repo_versions)

        if latest:
            latest_version, _ = latest
            update_type = classify_update(current_version, latest_version)
        else:
            latest_version = current_version
            update_type = "up-to-date"

        results.append(UpdateInfo(
            chart_name=chart_name,
            current_version=current_version,
            latest_version=latest_version,
            app_version_current=release.app_version,
            app_version_latest="",  # Would need to parse index for this
            update_type=update_type,
            source=source,
        ))

    return results


def _find_latest(
    current: str, repo_versions: dict[str, list[str]]
) -> tuple[str, str] | None:
    """Find the latest version across all repos.

    Returns (version, repo_name) or None.
    """
    best_version = current
    best_repo = ""

    for repo_name, versions in repo_versions.items():
        for v in versions:
            if is_newer(best_version, v):
                best_version = v
                best_repo = repo_name

    if best_version != current:
        return (best_version, best_repo)
    return None
