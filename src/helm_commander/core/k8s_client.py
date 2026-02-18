"""Kubernetes API wrapper."""

from __future__ import annotations

from typing import Any

from kubernetes import client, config
from kubernetes.client import ApiException

from helm_commander.config.settings import settings


CLUSTER_SCOPED_KINDS: frozenset[str] = frozenset({
    "ClusterRole",
    "ClusterRoleBinding",
    "IngressClass",
    "CustomResourceDefinition",
    "Namespace",
    "PersistentVolume",
    "Node",
    "StorageClass",
    "PriorityClass",
    "MutatingWebhookConfiguration",
    "ValidatingWebhookConfiguration",
    "PodSecurityPolicy",
})


class K8sClient:
    """Thin wrapper around the Kubernetes Python client."""

    def __init__(self, context: str | None = None):
        self.context = context
        self._core_v1: client.CoreV1Api | None = None
        self._apps_v1: client.AppsV1Api | None = None
        self._custom: client.CustomObjectsApi | None = None
        self._rbac_v1: client.RbacAuthorizationV1Api | None = None
        self._networking_v1: client.NetworkingV1Api | None = None
        self._apiextensions_v1: client.ApiextensionsV1Api | None = None
        self._api_client: client.ApiClient | None = None

    def _load_config(self) -> client.ApiClient:
        if self._api_client is not None:
            return self._api_client
        try:
            cfg = client.Configuration()
            config.load_kube_config(
                context=self.context,
                client_configuration=cfg,
            )
            # Prevent indefinite hangs on unreachable clusters
            cfg.retries = 1
            if not cfg.connection_pool_maxsize:
                cfg.connection_pool_maxsize = 4
            self._api_client = client.ApiClient(configuration=cfg)
        except config.ConfigException:
            config.load_incluster_config()
            self._api_client = client.ApiClient()
        return self._api_client

    @property
    def core_v1(self) -> client.CoreV1Api:
        if self._core_v1 is None:
            self._core_v1 = client.CoreV1Api(api_client=self._load_config())
        return self._core_v1

    @property
    def apps_v1(self) -> client.AppsV1Api:
        if self._apps_v1 is None:
            self._apps_v1 = client.AppsV1Api(api_client=self._load_config())
        return self._apps_v1

    @property
    def custom(self) -> client.CustomObjectsApi:
        if self._custom is None:
            self._custom = client.CustomObjectsApi(api_client=self._load_config())
        return self._custom

    @property
    def rbac_v1(self) -> client.RbacAuthorizationV1Api:
        if self._rbac_v1 is None:
            self._rbac_v1 = client.RbacAuthorizationV1Api(api_client=self._load_config())
        return self._rbac_v1

    @property
    def networking_v1(self) -> client.NetworkingV1Api:
        if self._networking_v1 is None:
            self._networking_v1 = client.NetworkingV1Api(api_client=self._load_config())
        return self._networking_v1

    @property
    def apiextensions_v1(self) -> client.ApiextensionsV1Api:
        if self._apiextensions_v1 is None:
            self._apiextensions_v1 = client.ApiextensionsV1Api(api_client=self._load_config())
        return self._apiextensions_v1

    @staticmethod
    def is_cluster_scoped(kind: str, namespace: str) -> bool:
        """Return True if the resource kind is cluster-scoped."""
        if kind in CLUSTER_SCOPED_KINDS:
            return True
        # Heuristic: unknown Cluster*-prefixed kinds with no namespace
        if kind.startswith("Cluster") and not namespace:
            return True
        return False

    @property
    def active_context_name(self) -> str:
        if self.context:
            return self.context
        try:
            _, ctx = config.list_kube_config_contexts()
            return ctx.get("name", "unknown") if ctx else "unknown"
        except Exception:
            return "in-cluster"

    def list_helm_secrets(
        self, namespace: str | None = None, release_name: str | None = None,
    ) -> list[Any]:
        """List all Helm release secrets, optionally filtered by namespace and release name."""
        label = settings.helm_label_selector
        if release_name:
            label += f",name={release_name}"
        if namespace:
            result = self.core_v1.list_namespaced_secret(
                namespace=namespace,
                label_selector=label,
                field_selector=f"type={settings.secret_type}",
                _request_timeout=30,
            )
        else:
            result = self.core_v1.list_secret_for_all_namespaces(
                label_selector=label,
                field_selector=f"type={settings.secret_type}",
                _request_timeout=30,
            )
        return result.items

    def list_helm_configmaps(
        self, namespace: str | None = None, release_name: str | None = None,
    ) -> list[Any]:
        """List all Helm release ConfigMaps."""
        label = settings.helm_label_selector
        if release_name:
            label += f",name={release_name}"
        if namespace:
            result = self.core_v1.list_namespaced_config_map(
                namespace=namespace,
                label_selector=label,
                _request_timeout=30,
            )
        else:
            result = self.core_v1.list_config_map_for_all_namespaces(
                label_selector=label,
                _request_timeout=30,
            )
        return result.items

    def get_resource(
        self,
        api_version: str,
        kind: str,
        name: str,
        namespace: str,
    ) -> dict | None:
        """Get a single cluster resource by api_version/kind/name/namespace."""
        try:
            if "/" in api_version:
                group, version = api_version.rsplit("/", 1)
                return self.custom.get_namespaced_custom_object(
                    group=group,
                    version=version,
                    namespace=namespace,
                    plural=self._kind_to_plural(kind),
                    name=name,
                )
            # Core API
            return self._get_core_resource(kind, name, namespace)
        except ApiException as e:
            if e.status == 404:
                return None
            raise

    def _get_core_resource(self, kind: str, name: str, namespace: str) -> dict | None:
        kind_lower = kind.lower()
        method_map = {
            "service": self.core_v1.read_namespaced_service,
            "configmap": self.core_v1.read_namespaced_config_map,
            "secret": self.core_v1.read_namespaced_secret,
            "serviceaccount": self.core_v1.read_namespaced_service_account,
            "persistentvolumeclaim": self.core_v1.read_namespaced_persistent_volume_claim,
            "pod": self.core_v1.read_namespaced_pod,
            "endpoints": self.core_v1.read_namespaced_endpoints,
        }
        method = method_map.get(kind_lower)
        if method is None:
            return None
        result = method(name=name, namespace=namespace)
        return self._api_client.sanitize_for_serialization(result) if result else None

    def get_apps_resource(self, kind: str, name: str, namespace: str) -> dict | None:
        kind_lower = kind.lower()
        try:
            if kind_lower == "deployment":
                result = self.apps_v1.read_namespaced_deployment(name=name, namespace=namespace)
            elif kind_lower == "statefulset":
                result = self.apps_v1.read_namespaced_stateful_set(name=name, namespace=namespace)
            elif kind_lower == "daemonset":
                result = self.apps_v1.read_namespaced_daemon_set(name=name, namespace=namespace)
            elif kind_lower == "replicaset":
                result = self.apps_v1.read_namespaced_replica_set(name=name, namespace=namespace)
            else:
                return None
            return self._api_client.sanitize_for_serialization(result) if result else None
        except ApiException as e:
            if e.status == 404:
                return None
            raise

    def get_cluster_resource(
        self,
        api_version: str,
        kind: str,
        name: str,
    ) -> dict | None:
        """Get a single cluster-scoped resource by api_version/kind/name."""
        try:
            if "/" in api_version:
                # Try typed API first
                typed = self._get_cluster_typed_resource(api_version, kind, name)
                if typed is not None:
                    return typed
                # Fallback to custom objects API
                group, version = api_version.rsplit("/", 1)
                return self.custom.get_cluster_custom_object(
                    group=group,
                    version=version,
                    plural=self._kind_to_plural(kind),
                    name=name,
                )
            # Core API cluster-scoped resources
            return self._get_core_cluster_resource(kind, name)
        except ApiException as e:
            if e.status == 404:
                return None
            raise

    def _get_cluster_typed_resource(
        self, api_version: str, kind: str, name: str
    ) -> dict | None:
        """Handle cluster-scoped resources via typed Kubernetes APIs."""
        result = None
        if api_version == "rbac.authorization.k8s.io/v1":
            if kind == "ClusterRole":
                result = self.rbac_v1.read_cluster_role(name=name)
            elif kind == "ClusterRoleBinding":
                result = self.rbac_v1.read_cluster_role_binding(name=name)
        elif api_version == "networking.k8s.io/v1":
            if kind == "IngressClass":
                result = self.networking_v1.read_ingress_class(name=name)
        elif api_version == "apiextensions.k8s.io/v1":
            if kind == "CustomResourceDefinition":
                result = self.apiextensions_v1.read_custom_resource_definition(name=name)
        if result is None:
            return None
        return self._api_client.sanitize_for_serialization(result)

    def _get_core_cluster_resource(self, kind: str, name: str) -> dict | None:
        """Handle core API cluster-scoped resources (Namespace, PV, Node)."""
        kind_lower = kind.lower()
        method_map = {
            "namespace": self.core_v1.read_namespace,
            "persistentvolume": self.core_v1.read_persistent_volume,
            "node": self.core_v1.read_node,
        }
        method = method_map.get(kind_lower)
        if method is None:
            return None
        result = method(name=name)
        return self._api_client.sanitize_for_serialization(result) if result else None

    def list_custom_resources(
        self,
        group: str,
        version: str,
        plural: str,
        namespace: str | None = None,
    ) -> list[dict]:
        try:
            if namespace:
                result = self.custom.list_namespaced_custom_object(
                    group=group, version=version, namespace=namespace, plural=plural,
                )
            else:
                result = self.custom.list_cluster_custom_object(
                    group=group, version=version, plural=plural,
                )
            return result.get("items", [])
        except ApiException:
            return []

    @staticmethod
    def _kind_to_plural(kind: str) -> str:
        k = kind.lower()
        if k.endswith("s"):
            return k + "es"
        if k.endswith("y"):
            return k[:-1] + "ies"
        return k + "s"
