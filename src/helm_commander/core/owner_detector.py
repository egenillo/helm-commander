"""Detect Argo CD, Flux CD, k3s HelmChart, or native Helm ownership."""

from __future__ import annotations

import logging

from helm_commander.core.k8s_client import K8sClient
from helm_commander.models import Confidence, ControllerType, OwnerInfo
from helm_commander.models.release import HelmRelease
from helm_commander.utils.manifest_parser import parse_manifest

logger = logging.getLogger(__name__)


def detect_owner(release: HelmRelease, k8s: K8sClient) -> OwnerInfo:
    """Detect who manages a Helm release, checking controllers in priority order."""
    # 1. Check Argo CD
    result = _check_argocd(release, k8s)
    if result:
        return result

    # 2. Check Flux CD
    result = _check_flux(release, k8s)
    if result:
        return result

    # 3. Check k3s HelmChart
    result = _check_k3s(release, k8s)
    if result:
        return result

    # 4. Check resource annotations
    result = _check_resource_annotations(release)
    if result:
        return result

    # 5. Fallback
    return OwnerInfo(
        controller=ControllerType.HELM_NATIVE,
        confidence=Confidence.LOW,
        detail="No controller labels or annotations detected",
    )


def _check_argocd(release: HelmRelease, k8s: K8sClient) -> OwnerInfo | None:
    """Check for Argo CD labels on rendered resources."""
    resources = parse_manifest(release.manifest)
    for res in resources:
        labels = res.raw.get("metadata", {}).get("labels", {}) or {}
        annotations = res.raw.get("metadata", {}).get("annotations", {}) or {}

        if "argocd.argoproj.io/instance" in labels:
            instance = labels["argocd.argoproj.io/instance"]
            return OwnerInfo(
                controller=ControllerType.ARGO_CD,
                confidence=Confidence.HIGH,
                detail=f"Argo CD Application: {instance}",
            )

        if "argocd.argoproj.io/tracking-id" in annotations:
            return OwnerInfo(
                controller=ControllerType.ARGO_CD,
                confidence=Confidence.HIGH,
                detail="Argo CD tracking annotation found",
            )
    return None


def _check_flux(release: HelmRelease, k8s: K8sClient) -> OwnerInfo | None:
    """Check for Flux CD HelmRelease labels."""
    resources = parse_manifest(release.manifest)
    for res in resources:
        labels = res.raw.get("metadata", {}).get("labels", {}) or {}
        if "helm.toolkit.fluxcd.io/name" in labels:
            hr_name = labels["helm.toolkit.fluxcd.io/name"]
            return OwnerInfo(
                controller=ControllerType.FLUX_CD,
                confidence=Confidence.HIGH,
                detail=f"Flux HelmRelease: {hr_name}",
            )

    # Also check for Flux HelmRelease CRDs
    try:
        flux_releases = k8s.list_custom_resources(
            group="helm.toolkit.fluxcd.io",
            version="v2beta1",
            plural="helmreleases",
            namespace=release.namespace,
        )
        for fr in flux_releases:
            if fr.get("metadata", {}).get("name") == release.name:
                return OwnerInfo(
                    controller=ControllerType.FLUX_CD,
                    confidence=Confidence.HIGH,
                    detail=f"Flux HelmRelease CRD: {release.name}",
                )
    except Exception:
        logger.debug("Could not query Flux HelmRelease CRDs", exc_info=True)
    return None


def _check_k3s(release: HelmRelease, k8s: K8sClient) -> OwnerInfo | None:
    """Check for k3s HelmChart CRDs in kube-system."""
    try:
        helmcharts = k8s.list_custom_resources(
            group="helm.cattle.io",
            version="v1",
            plural="helmcharts",
            namespace="kube-system",
        )
        for hc in helmcharts:
            if hc.get("metadata", {}).get("name") == release.name:
                return OwnerInfo(
                    controller=ControllerType.K3S_HELMCHART,
                    confidence=Confidence.HIGH,
                    detail=f"k3s HelmChart: {release.name}",
                )
    except Exception:
        logger.debug("Could not query k3s HelmChart CRDs", exc_info=True)
    return None


def _check_resource_annotations(release: HelmRelease) -> OwnerInfo | None:
    """Check app.kubernetes.io/managed-by annotation on rendered resources."""
    resources = parse_manifest(release.manifest)
    for res in resources:
        labels = res.raw.get("metadata", {}).get("labels", {}) or {}
        managed_by = labels.get("app.kubernetes.io/managed-by", "")

        if managed_by and managed_by.lower() != "helm":
            return OwnerInfo(
                controller=ControllerType.UNKNOWN,
                confidence=Confidence.MEDIUM,
                detail=f"managed-by: {managed_by}",
            )
    return None
