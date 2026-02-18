"""Drift detection models."""

from __future__ import annotations

import enum
from dataclasses import dataclass, field


class DiffStatus(enum.Enum):
    UNCHANGED = "unchanged"
    MODIFIED = "modified"
    MISSING_LIVE = "missing_live"
    EXTRA_LIVE = "extra_live"


@dataclass
class ResourceDiff:
    api_version: str
    kind: str
    name: str
    namespace: str
    status: DiffStatus
    details: list[str] = field(default_factory=list)

    @property
    def has_drift(self) -> bool:
        return self.status != DiffStatus.UNCHANGED


@dataclass
class DriftResult:
    release_name: str
    namespace: str
    diffs: list[ResourceDiff] = field(default_factory=list)

    @property
    def has_drift(self) -> bool:
        return any(d.has_drift for d in self.diffs)

    @property
    def summary(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for d in self.diffs:
            key = d.status.value
            counts[key] = counts.get(key, 0) + 1
        return counts
