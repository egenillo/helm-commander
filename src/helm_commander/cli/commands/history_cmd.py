"""hcom history <release> - Show release revision history."""

from __future__ import annotations

from typing import Optional

import typer

from helm_commander.cli.options import OutputOption, NamespaceOption, ContextOption
from helm_commander.core.k8s_client import K8sClient
from helm_commander.core.release_store import ReleaseStore
from helm_commander.output.formatters import output_history

app = typer.Typer()


@app.callback(invoke_without_command=True)
def history(
    release: str = typer.Argument(help="Release name"),
    output: str = OutputOption,
    namespace: Optional[str] = NamespaceOption,
    context: Optional[str] = ContextOption,
) -> None:
    """Show the revision history of a Helm release."""
    k8s = K8sClient(context=context)
    store = ReleaseStore(k8s)
    revisions = store.get_all_revisions(release, namespace=namespace)
    if not revisions:
        typer.echo(f"No revisions found for release '{release}'.", err=True)
        raise typer.Exit(code=1)
    output_history(revisions, output)
