"""hcom list - List Helm releases."""

from __future__ import annotations

from typing import Optional

import typer

from helm_commander.cli.options import OutputOption, NamespaceOption, ContextOption
from helm_commander.core.k8s_client import K8sClient
from helm_commander.core.release_store import ReleaseStore
from helm_commander.output.formatters import output_releases

app = typer.Typer()


@app.callback(invoke_without_command=True)
def list_releases(
    output: str = OutputOption,
    namespace: Optional[str] = NamespaceOption,
    context: Optional[str] = ContextOption,
    all_namespaces: bool = typer.Option(True, "--all-namespaces", "-A", help="List across all namespaces"),
    filter: Optional[str] = typer.Option(None, "--filter", "-f", help="Regex filter on release/chart name"),
    only: Optional[str] = typer.Option(
        None, "--only", help="Filter by status category: deployed, failed, pending, problematic",
    ),
) -> None:
    """List all Helm releases on the cluster."""
    ns = None if all_namespaces else namespace
    k8s = K8sClient(context=context)
    store = ReleaseStore(k8s)
    releases = store.list_releases(namespace=ns, filter_regex=filter, only=only)
    output_releases(releases, output)
