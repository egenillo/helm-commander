"""hcom drift <release> - Detect configuration drift."""

from __future__ import annotations

from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from helm_commander.cli.options import OutputOption, NamespaceOption, ContextOption
from helm_commander.core.drift_engine import detect_drift
from helm_commander.core.k8s_client import K8sClient
from helm_commander.core.release_store import ReleaseStore
from helm_commander.models.diff import DiffStatus

app = typer.Typer()
console = Console()

_STATUS_COLORS = {
    DiffStatus.UNCHANGED: "green",
    DiffStatus.MODIFIED: "yellow",
    DiffStatus.MISSING_LIVE: "red",
    DiffStatus.EXTRA_LIVE: "cyan",
}


@app.callback(invoke_without_command=True)
def drift(
    release: str = typer.Argument(help="Release name"),
    output: str = OutputOption,
    namespace: Optional[str] = NamespaceOption,
    context: Optional[str] = ContextOption,
) -> None:
    """Compare stored Helm manifests against live cluster state."""
    k8s = K8sClient(context=context)
    store = ReleaseStore(k8s)
    rel = store.get_release(release, namespace=namespace)
    if rel is None:
        typer.echo(f"Release '{release}' not found.", err=True)
        raise typer.Exit(code=1)

    result = detect_drift(rel, k8s)

    if output == "json":
        import json
        data = {
            "release": result.release_name,
            "namespace": result.namespace,
            "has_drift": result.has_drift,
            "summary": result.summary,
            "resources": [
                {
                    "kind": d.kind,
                    "name": d.name,
                    "namespace": d.namespace,
                    "status": d.status.value,
                    "details": d.details,
                }
                for d in result.diffs
            ],
        }
        console.print_json(json.dumps(data, indent=2))
        return

    if output == "yaml":
        import yaml
        data = {
            "release": result.release_name,
            "has_drift": result.has_drift,
            "summary": result.summary,
            "resources": [
                {"kind": d.kind, "name": d.name, "status": d.status.value, "details": d.details}
                for d in result.diffs
            ],
        }
        console.print(yaml.dump(data, default_flow_style=False))
        return

    # Table output
    table = Table(title=f"Drift Report: {release}", expand=True)
    table.add_column("Kind", style="cyan")
    table.add_column("Name", style="bold")
    table.add_column("Namespace", style="blue")
    table.add_column("Status", no_wrap=True)
    table.add_column("Details", max_width=60)

    for d in result.diffs:
        color = _STATUS_COLORS.get(d.status, "white")
        status_text = f"[{color}]{d.status.value}[/{color}]"
        detail = "\n".join(d.details[:3])
        if len(d.details) > 3:
            detail += f"\n... +{len(d.details) - 3} more"
        table.add_row(d.kind, d.name, d.namespace, status_text, detail)

    console.print(table)

    summary = result.summary
    if result.has_drift:
        console.print(f"\n[yellow]Drift detected:[/yellow] {summary}")
    else:
        console.print("\n[green]No drift detected. Cluster matches stored manifests.[/green]")
