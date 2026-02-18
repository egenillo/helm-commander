"""Status and confidence color maps."""

from helm_commander.models import Confidence
from helm_commander.models.release import ReleaseStatus

STATUS_COLORS: dict[ReleaseStatus, str] = {
    ReleaseStatus.DEPLOYED: "green",
    ReleaseStatus.FAILED: "red bold",
    ReleaseStatus.SUPERSEDED: "dim",
    ReleaseStatus.PENDING_INSTALL: "yellow",
    ReleaseStatus.PENDING_UPGRADE: "yellow",
    ReleaseStatus.PENDING_ROLLBACK: "yellow",
    ReleaseStatus.UNINSTALLING: "magenta",
    ReleaseStatus.UNINSTALLED: "dim",
    ReleaseStatus.UNKNOWN: "red",
}

CONFIDENCE_COLORS: dict[Confidence, str] = {
    Confidence.HIGH: "green",
    Confidence.MEDIUM: "yellow",
    Confidence.LOW: "red",
}


def styled_status(status: ReleaseStatus) -> str:
    color = STATUS_COLORS.get(status, "white")
    return f"[{color}]{status.value}[/{color}]"


def styled_confidence(confidence: Confidence) -> str:
    color = CONFIDENCE_COLORS.get(confidence, "white")
    return f"[{color}]{confidence.value}[/{color}]"
