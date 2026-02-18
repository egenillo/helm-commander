"""hcom source <release> - Detect chart source repository."""

from __future__ import annotations

from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from helm_commander.cli.options import OutputOption, NamespaceOption, ContextOption
from helm_commander.core.k8s_client import K8sClient
from helm_commander.core.release_store import ReleaseStore
from helm_commander.core.repo_resolver import resolve_source_with_annotations
from helm_commander.output.themes import styled_confidence

app = typer.Typer()
console = Console()


@app.callback(invoke_without_command=True)
def source(
    release: str = typer.Argument(help="Release name"),
    output: str = OutputOption,
    namespace: Optional[str] = NamespaceOption,
    context: Optional[str] = ContextOption,
) -> None:
    """Detect the source repository for a chart."""
    k8s = K8sClient(context=context)
    store = ReleaseStore(k8s)
    rel = store.get_release(release, namespace=namespace)
    if rel is None:
        typer.echo(f"Release '{release}' not found.", err=True)
        raise typer.Exit(code=1)

    match = resolve_source_with_annotations(
        rel.chart_name,
        rel.chart_version,
        rel.chart.annotations,
    )

    if output == "json":
        import json
        data = {
            "release": rel.name,
            "chart": rel.chart_name,
            "chart_version": rel.chart_version,
            "source": None,
        }
        if match:
            data["source"] = {
                "repo_url": match.repo_url,
                "repo_name": match.repo_name,
                "confidence": match.confidence.value,
                "match_reason": match.match_reason,
            }
        console.print_json(json.dumps(data, indent=2))
        return

    if match:
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Key", style="bold cyan")
        table.add_column("Value")
        table.add_row("Chart", f"{rel.chart_name}-{rel.chart_version}")
        table.add_row("Repository", match.repo_name)
        table.add_row("URL", match.repo_url)
        table.add_row("Confidence", styled_confidence(match.confidence))
        table.add_row("Reason", match.match_reason)
        console.print(Panel(table, title="[bold]Chart Source[/bold]", border_style="green"))
    else:
        console.print(f"[yellow]Could not determine source for {rel.chart_name}-{rel.chart_version}[/yellow]")
        console.print("Tip: Run 'helm repo update' to refresh local index cache.")
