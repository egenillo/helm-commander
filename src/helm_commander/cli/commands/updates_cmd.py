"""hcom updates - Check for chart updates."""

from __future__ import annotations

from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from helm_commander.cli.options import OutputOption, NamespaceOption, ContextOption
from helm_commander.core.k8s_client import K8sClient
from helm_commander.core.release_store import ReleaseStore
from helm_commander.core.update_checker import check_updates

app = typer.Typer()
console = Console()

_UPDATE_COLORS = {
    "major": "red bold",
    "minor": "yellow",
    "patch": "green",
    "up-to-date": "dim",
    "unknown": "dim",
}


@app.callback(invoke_without_command=True)
def updates(
    output: str = OutputOption,
    namespace: Optional[str] = NamespaceOption,
    context: Optional[str] = ContextOption,
    all_namespaces: bool = typer.Option(True, "--all-namespaces", "-A", help="Check across all namespaces"),
) -> None:
    """Check for available chart updates for all deployed releases."""
    ns = None if all_namespaces else namespace

    with console.status("[bold cyan]Connecting to cluster…") as status:
        k8s = K8sClient(context=context)
        store = ReleaseStore(k8s)

        status.update("[bold cyan]Fetching releases…")
        releases = store.list_releases(namespace=ns)

        if not releases:
            console.print("[dim]No releases found.[/dim]")
            return

        def on_progress(i: int, total: int, chart: str) -> None:
            status.update(f"[bold cyan]Checking updates… [dim]({i}/{total})[/dim] {chart}")

        results = check_updates(releases, on_progress=on_progress)

    if output == "json":
        import json
        data = [
            {
                "chart": u.chart_name,
                "current_version": u.current_version,
                "latest_version": u.latest_version,
                "update_type": u.update_type,
            }
            for u in results
        ]
        console.print_json(json.dumps(data, indent=2))
        return

    table = Table(title="Chart Updates", expand=True)
    table.add_column("Chart", style="magenta", no_wrap=True)
    table.add_column("Current", style="dim")
    table.add_column("Latest", style="bold")
    table.add_column("Update Type", no_wrap=True)
    table.add_column("Source", style="dim", max_width=30)

    for u in results:
        color = _UPDATE_COLORS.get(u.update_type, "white")
        update_text = f"[{color}]{u.update_type}[/{color}]"
        source_text = u.source.repo_name if u.source else "-"
        table.add_row(u.chart_name, u.current_version, u.latest_version, update_text, source_text)

    console.print(table)

    updates_available = [u for u in results if u.update_type not in ("up-to-date", "unknown")]
    if updates_available:
        console.print(f"\n[yellow]{len(updates_available)} update(s) available[/yellow]")
    else:
        console.print("\n[green]All charts are up to date (based on local cache)[/green]")
