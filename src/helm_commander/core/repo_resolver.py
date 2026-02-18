"""Chart origin resolution from local Helm cache and OCI registries."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import yaml

from helm_commander.config.settings import settings
from helm_commander.models import Confidence
from helm_commander.models.repo import SourceMatch

logger = logging.getLogger(__name__)

# Prefer the C-accelerated YAML loader when available (~10x faster).
_YamlLoader = getattr(yaml, "CSafeLoader", yaml.SafeLoader)

# Module-level caches — cleared between runs via clear_caches()
_repos_cache: dict[str, str] | None = None
_index_cache: dict[Path, dict] = {}


def clear_caches() -> None:
    """Reset all module-level caches (call once per command invocation)."""
    global _repos_cache
    _repos_cache = None
    _index_cache.clear()


def resolve_source(chart_name: str, chart_version: str) -> SourceMatch | None:
    """Try to determine the source repository for a chart.

    Checks local Helm cache index files and repositories.yaml.
    """
    # 1. Check repositories.yaml for known repos
    repos = _load_repositories()

    # 2. Scan cached index.yaml files
    for repo_name, repo_url in repos.items():
        index_path = settings.index_cache_dir / f"{repo_name}-index.yaml"
        if not index_path.exists():
            continue

        match = _search_index(index_path, chart_name, chart_version, repo_name, repo_url)
        if match:
            return match

    # 3. Check chart annotations for source hints
    return None


def resolve_source_with_annotations(
    chart_name: str,
    chart_version: str,
    annotations: dict[str, str],
) -> SourceMatch | None:
    """Resolve source, also checking chart annotations for OCI/repo hints."""
    # Check annotations first
    for key in ("artifacthub.io/repository", "helm.sh/chart-url"):
        if key in annotations:
            return SourceMatch(
                repo_url=annotations[key],
                repo_name="(annotation)",
                confidence=Confidence.MEDIUM,
                match_reason=f"Chart annotation: {key}",
            )

    return resolve_source(chart_name, chart_version)


def get_all_repo_versions(chart_name: str) -> dict[str, list[str]]:
    """Get all available versions for a chart from all known repos.

    Returns {repo_name: [versions...]}.
    """
    repos = _load_repositories()
    result: dict[str, list[str]] = {}

    for repo_name, repo_url in repos.items():
        index_path = settings.index_cache_dir / f"{repo_name}-index.yaml"
        if not index_path.exists():
            continue

        versions = _get_versions_from_index(index_path, chart_name)
        if versions:
            result[repo_name] = versions

    return result


def _load_repositories() -> dict[str, str]:
    """Load repo name -> URL mapping from repositories.yaml (cached)."""
    global _repos_cache
    if _repos_cache is not None:
        return _repos_cache

    repos_file = settings.repositories_file
    if not repos_file.exists():
        _repos_cache = {}
        return _repos_cache
    try:
        data = yaml.safe_load(repos_file.read_text(encoding="utf-8"))
        if not data or "repositories" not in data:
            _repos_cache = {}
        else:
            _repos_cache = {r["name"]: r["url"] for r in data["repositories"] if "name" in r and "url" in r}
    except Exception:
        logger.debug("Failed to parse repositories.yaml", exc_info=True)
        _repos_cache = {}
    return _repos_cache


# ---------------------------------------------------------------------------
# Lightweight JSON sidecar cache for index.yaml files
#
# Helm repo index files can be 25+ MB of YAML.  Even the C loader takes
# >10 s to parse them.  We extract only {chart_name: [{version, appVersion}]}
# into a small JSON file (<1 MB) that loads in milliseconds.  The sidecar is
# regenerated whenever the source index.yaml is newer.
# ---------------------------------------------------------------------------

def _sidecar_path(index_path: Path) -> Path:
    """Return the JSON sidecar path for a given index.yaml."""
    return index_path.with_suffix(".json")


def _sidecar_is_fresh(index_path: Path, sidecar: Path) -> bool:
    """True if the sidecar exists and is at least as new as the index."""
    if not sidecar.exists():
        return False
    try:
        return sidecar.stat().st_mtime >= index_path.stat().st_mtime
    except OSError:
        return False


def _build_sidecar(index_path: Path) -> dict | None:
    """Parse the full YAML index once and write a lightweight JSON sidecar.

    Returns the lightweight dict or None on failure.
    """
    try:
        data = yaml.load(index_path.read_text(encoding="utf-8"), Loader=_YamlLoader)
        if not data or "entries" not in data:
            return None
    except Exception:
        logger.debug("Failed to parse index at %s", index_path, exc_info=True)
        return None

    entries = data["entries"]
    lightweight: dict[str, list[dict[str, str]]] = {}
    for chart_name, chart_entries in entries.items():
        lightweight[chart_name] = [
            {"version": e.get("version", ""), "appVersion": e.get("appVersion", "")}
            for e in chart_entries
            if "version" in e
        ]

    sidecar = _sidecar_path(index_path)
    try:
        sidecar.write_text(json.dumps(lightweight), encoding="utf-8")
    except OSError:
        logger.debug("Could not write sidecar cache %s", sidecar, exc_info=True)

    return lightweight


def _load_index(index_path: Path) -> dict | None:
    """Load a repo index, using a fast JSON sidecar cache when available.

    Returns {chart_name: [{version, appVersion}, ...]} or None.
    """
    if index_path in _index_cache:
        return _index_cache[index_path]

    sidecar = _sidecar_path(index_path)
    if _sidecar_is_fresh(index_path, sidecar):
        try:
            lightweight = json.loads(sidecar.read_text(encoding="utf-8"))
            _index_cache[index_path] = lightweight
            return lightweight
        except Exception:
            logger.debug("Corrupt sidecar %s, rebuilding", sidecar, exc_info=True)

    lightweight = _build_sidecar(index_path)
    _index_cache[index_path] = lightweight
    return lightweight


def _search_index(
    index_path: Path,
    chart_name: str,
    chart_version: str,
    repo_name: str,
    repo_url: str,
) -> SourceMatch | None:
    """Search a cached index for a specific chart name and version."""
    data = _load_index(index_path)
    if data is None:
        return None

    entries = data.get(chart_name)
    if not entries:
        return None

    # Exact version match
    for entry in entries:
        if entry.get("version") == chart_version:
            return SourceMatch(
                repo_url=repo_url,
                repo_name=repo_name,
                confidence=Confidence.HIGH,
                match_reason=f"Exact version match in {repo_name} index",
            )

    # Chart exists but version not found
    return SourceMatch(
        repo_url=repo_url,
        repo_name=repo_name,
        confidence=Confidence.MEDIUM,
        match_reason=f"Chart found in {repo_name} (version {chart_version} not in cache)",
    )


def _get_versions_from_index(index_path: Path, chart_name: str) -> list[str]:
    """Extract all versions for a chart from an index."""
    data = _load_index(index_path)
    if data is None:
        return []
    entries = data.get(chart_name, [])
    return [e["version"] for e in entries if "version" in e]
