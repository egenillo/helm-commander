"""hcom info <release> - Show release details."""

from __future__ import annotations

from typing import Optional

import typer

from helm_commander.cli.options import OutputOption, NamespaceOption, ContextOption
from helm_commander.core.k8s_client import K8sClient
from helm_commander.core.release_store import ReleaseStore
from helm_commander.core.owner_detector import detect_owner
from helm_commander.output.formatters import output_release_info
from helm_commander.utils.manifest_parser import resource_counts

app = typer.Typer()


@app.callback(invoke_without_command=True)
def info(
    release: str = typer.Argument(help="Release name"),
    output: str = OutputOption,
    namespace: Optional[str] = NamespaceOption,
    context: Optional[str] = ContextOption,
    show_values: bool = typer.Option(False, "--show-values", help="Display user-supplied values"),
) -> None:
    """Show detailed information about a Helm release."""
    k8s = K8sClient(context=context)
    store = ReleaseStore(k8s)
    rel = store.get_release(release, namespace=namespace)
    if rel is None:
        typer.echo(f"Release '{release}' not found.", err=True)
        raise typer.Exit(code=1)

    owner = detect_owner(rel, k8s)
    counts = resource_counts(rel.manifest)
    output_release_info(rel, output, show_values=show_values, owner=owner, resource_counts=counts)
