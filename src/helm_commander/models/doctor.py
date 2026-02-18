"""Diagnostic result models."""

from __future__ import annotations

import enum
from dataclasses import dataclass


class Severity(enum.Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass
class DiagnosticResult:
    check_name: str
    severity: Severity
    message: str
    suggestion: str = ""
    release_name: str = ""
    namespace: str = ""
