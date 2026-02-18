"""Decode Helm v3 release data from Kubernetes Secrets or ConfigMaps."""

from __future__ import annotations

import base64
import logging
from typing import Any

from helm_commander.core.k8s_client import K8sClient
from helm_commander.models.release import HelmRelease
from helm_commander.utils.encoding import decode_release_configmap, decode_release_secret

logger = logging.getLogger(__name__)


def _label_metadata(obj: Any) -> dict[str, str]:
    """Extract Helm labels from a Secret/ConfigMap object."""
    labels = {}
    if hasattr(obj, "metadata") and obj.metadata and obj.metadata.labels:
        labels = dict(obj.metadata.labels)
    return labels


def decode_secret(secret: Any, context: str = "") -> HelmRelease | None:
    """Decode a single Kubernetes Secret into a HelmRelease."""
    try:
        data = secret.data
        if not data or "release" not in data:
            return None
        raw = data["release"]
        # kubernetes client base64-decodes Secret data, giving us bytes
        if isinstance(raw, str):
            raw = raw.encode("utf-8")
        release_dict = decode_release_secret(raw)
        release = HelmRelease.from_dict(release_dict, context=context)
        # Ensure namespace from the secret metadata
        if not release.namespace and secret.metadata:
            release.namespace = secret.metadata.namespace or ""
        return release
    except Exception:
        logger.debug("Failed to decode secret %s", _safe_name(secret), exc_info=True)
        return None


def decode_configmap(cm: Any, context: str = "") -> HelmRelease | None:
    """Decode a single Kubernetes ConfigMap into a HelmRelease."""
    try:
        data = cm.data
        if not data or "release" not in data:
            return None
        raw = data["release"]
        release_dict = decode_release_configmap(raw)
        release = HelmRelease.from_dict(release_dict, context=context)
        if not release.namespace and cm.metadata:
            release.namespace = cm.metadata.namespace or ""
        return release
    except Exception:
        logger.debug("Failed to decode configmap %s", _safe_name(cm), exc_info=True)
        return None


def quick_metadata_from_labels(obj: Any, context: str = "") -> dict:
    """Extract quick metadata from labels without decoding the release payload.

    Returns a dict with keys: name, namespace, status, version (revision), context.
    """
    labels = _label_metadata(obj)
    ns = ""
    if hasattr(obj, "metadata") and obj.metadata:
        ns = obj.metadata.namespace or ""
    return {
        "name": labels.get("name", ""),
        "namespace": ns,
        "status": labels.get("status", ""),
        "version": int(labels.get("version", "0")),
        "context": context,
    }


def _safe_name(obj: Any) -> str:
    if hasattr(obj, "metadata") and obj.metadata:
        return obj.metadata.name or "<unknown>"
    return "<unknown>"
