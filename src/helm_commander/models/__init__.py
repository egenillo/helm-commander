"""Data models for Helm Commander."""

from __future__ import annotations

import enum
from dataclasses import dataclass


class ControllerType(enum.Enum):
    HELM_NATIVE = "helm-native"
    ARGO_CD = "argo-cd"
    FLUX_CD = "flux-cd"
    K3S_HELMCHART = "k3s-helmchart"
    UNKNOWN = "unknown"


class Confidence(enum.Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class OwnerInfo:
    controller: ControllerType = ControllerType.UNKNOWN
    confidence: Confidence = Confidence.LOW
    detail: str = ""
