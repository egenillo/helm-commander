"""Repository and update models."""

from __future__ import annotations

from dataclasses import dataclass

from helm_commander.models import Confidence


@dataclass
class SourceMatch:
    repo_url: str
    repo_name: str
    confidence: Confidence
    match_reason: str


@dataclass
class UpdateInfo:
    chart_name: str
    current_version: str
    latest_version: str
    app_version_current: str
    app_version_latest: str
    update_type: str  # "major", "minor", "patch", "up-to-date"
    source: SourceMatch | None = None
