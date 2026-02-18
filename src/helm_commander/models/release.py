"""Helm release models."""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import datetime

from helm_commander.models.chart import ChartMetadata


class ReleaseStatus(enum.Enum):
    DEPLOYED = "deployed"
    FAILED = "failed"
    SUPERSEDED = "superseded"
    PENDING_INSTALL = "pending-install"
    PENDING_UPGRADE = "pending-upgrade"
    PENDING_ROLLBACK = "pending-rollback"
    UNINSTALLING = "uninstalling"
    UNINSTALLED = "uninstalled"
    UNKNOWN = "unknown"

    @classmethod
    def from_str(cls, s: str) -> ReleaseStatus:
        for member in cls:
            if member.value == s:
                return member
        return cls.UNKNOWN


@dataclass
class ReleaseInfo:
    first_deployed: str = ""
    last_deployed: str = ""
    status: ReleaseStatus = ReleaseStatus.UNKNOWN
    description: str = ""
    deleted: str = ""
    notes: str = ""

    @classmethod
    def from_dict(cls, d: dict) -> ReleaseInfo:
        if not d:
            return cls()
        return cls(
            first_deployed=d.get("first_deployed", ""),
            last_deployed=d.get("last_deployed", ""),
            status=ReleaseStatus.from_str(d.get("status", "unknown")),
            description=d.get("description", ""),
            deleted=d.get("deleted", ""),
            notes=d.get("notes", ""),
        )


@dataclass
class HelmRelease:
    name: str = ""
    namespace: str = ""
    version: int = 0
    context: str = ""
    info: ReleaseInfo = field(default_factory=ReleaseInfo)
    chart: ChartMetadata = field(default_factory=ChartMetadata)
    config: dict = field(default_factory=dict)
    manifest: str = ""
    hooks: list[dict] = field(default_factory=list)

    @property
    def chart_name(self) -> str:
        return self.chart.name

    @property
    def chart_version(self) -> str:
        return self.chart.version

    @property
    def app_version(self) -> str:
        return self.chart.app_version

    @property
    def updated(self) -> str:
        return self.info.last_deployed

    @property
    def status(self) -> ReleaseStatus:
        return self.info.status

    @property
    def updated_short(self) -> str:
        """Return a human-readable short timestamp."""
        raw = self.info.last_deployed
        if not raw:
            return ""
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except (ValueError, AttributeError):
            return raw[:19] if len(raw) > 19 else raw

    @classmethod
    def from_dict(cls, d: dict, context: str = "") -> HelmRelease:
        chart_raw = d.get("chart", {})
        chart_meta = ChartMetadata.from_dict(chart_raw.get("metadata", {}))
        return cls(
            name=d.get("name", ""),
            namespace=d.get("namespace", ""),
            version=d.get("version", 0),
            context=context,
            info=ReleaseInfo.from_dict(d.get("info", {})),
            chart=chart_meta,
            config=d.get("config", {}),
            manifest=d.get("manifest", ""),
            hooks=d.get("hooks", []),
        )
