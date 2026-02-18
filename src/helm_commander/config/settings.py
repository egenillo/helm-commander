"""Application configuration and defaults."""

from __future__ import annotations

import os
import platform
from dataclasses import dataclass, field
from pathlib import Path


def _default_helm_cache_dir() -> Path:
    """Return the default Helm cache directory for the current platform.

    Checks HELM_REPOSITORY_CACHE and HELM_CACHE_HOME env vars first,
    matching helm's own resolution order.
    """
    repo_cache = os.environ.get("HELM_REPOSITORY_CACHE", "")
    if repo_cache:
        return Path(repo_cache)
    cache_home = os.environ.get("HELM_CACHE_HOME", "")
    if cache_home:
        return Path(cache_home) / "repository"
    system = platform.system()
    if system == "Windows":
        # Helm on Windows uses %TEMP%\helm as default cache home
        temp = os.environ.get("TEMP", "")
        if temp:
            candidate = Path(temp) / "helm" / "repository"
            if candidate.exists():
                return candidate
        appdata = os.environ.get("APPDATA", "")
        if appdata:
            return Path(appdata) / "helm" / "repository"
        return Path.home() / "AppData" / "Roaming" / "helm" / "repository"
    # Linux / macOS
    xdg = os.environ.get("XDG_CACHE_HOME", "")
    if xdg:
        return Path(xdg) / "helm" / "repository"
    return Path.home() / ".cache" / "helm" / "repository"


def _default_helm_config_dir() -> Path:
    config_home = os.environ.get("HELM_CONFIG_HOME", "")
    if config_home:
        return Path(config_home)
    system = platform.system()
    if system == "Windows":
        appdata = os.environ.get("APPDATA", "")
        if appdata:
            return Path(appdata) / "helm"
        return Path.home() / "AppData" / "Roaming" / "helm"
    xdg = os.environ.get("XDG_CONFIG_HOME", "")
    if xdg:
        return Path(xdg) / "helm"
    return Path.home() / ".config" / "helm"


@dataclass
class Settings:
    helm_cache_dir: Path = field(default_factory=_default_helm_cache_dir)
    helm_config_dir: Path = field(default_factory=_default_helm_config_dir)
    storage_driver: str = "secrets"  # "secrets" or "configmaps"
    default_output: str = "table"
    helm_label_selector: str = "owner=helm"
    secret_type: str = "helm.sh/release.v1"

    @property
    def repositories_file(self) -> Path:
        return self.helm_config_dir / "repositories.yaml"

    @property
    def index_cache_dir(self) -> Path:
        return self.helm_cache_dir


# Global singleton
settings = Settings()
