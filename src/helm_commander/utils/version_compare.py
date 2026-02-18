"""Semver comparison utilities."""

from __future__ import annotations

from packaging.version import Version, InvalidVersion


def parse_version(v: str) -> Version | None:
    """Parse a version string, returning None on failure."""
    try:
        return Version(v)
    except InvalidVersion:
        # Try stripping leading 'v'
        if v.startswith("v"):
            try:
                return Version(v[1:])
            except InvalidVersion:
                pass
    return None


def classify_update(current: str, latest: str) -> str:
    """Classify the update type between two version strings.

    Returns: "major", "minor", "patch", "up-to-date", or "unknown".
    """
    cur = parse_version(current)
    lat = parse_version(latest)

    if cur is None or lat is None:
        return "unknown"
    if lat <= cur:
        return "up-to-date"
    if lat.major > cur.major:
        return "major"
    if lat.minor > cur.minor:
        return "minor"
    return "patch"


def is_newer(current: str, candidate: str) -> bool:
    """Return True if candidate is newer than current."""
    cur = parse_version(current)
    cand = parse_version(candidate)
    if cur is None or cand is None:
        return False
    return cand > cur
