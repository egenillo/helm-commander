"""hcom doctor - Run diagnostic checks."""

from __future__ import annotations

from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from helm_commander.cli.options import OutputOption, NamespaceOption, ContextOption
from helm_commander.core.doctor_engine import run_diagnostics
from helm_commander.core.k8s_client import K8sClient
from helm_commander.core.release_store import ReleaseStore
from helm_commander.models.doctor import Severity

app = typer.Typer()
console = Console()

_SEVERITY_COLORS = {
    Severity.INFO: "blue",
    Severity.WARNING: "yellow",
    Severity.ERROR: "red bold",
}
_SEVERITY_ICONS = {
    Severity.INFO: "i",
    Severity.WARNING: "!",
    Severity.ERROR: "X",
}


@app.callback(invoke_without_command=True)
def doctor(
    output: str = OutputOption,
    namespace: Optional[str] = NamespaceOption,
    context: Optional[str] = ContextOption,
    all_namespaces: bool = typer.Option(True, "--all-namespaces", "-A", help="Check across all namespaces"),
) -> None:
    """Run diagnostic checks on Helm releases."""
    ns = None if all_namespaces else namespace
    k8s = K8sClient(context=context)
    store = ReleaseStore(k8s)
    releases = store.list_releases(namespace=ns)
    results = run_diagnostics(releases, k8s, namespace=ns)

    if output == "json":
        import json
        data = [
            {
                "check": r.check_name,
                "severity": r.severity.value,
                "message": r.message,
                "suggestion": r.suggestion,
                "release": r.release_name,
                "namespace": r.namespace,
            }
            for r in results
        ]
        console.print_json(json.dumps(data, indent=2))
        return

    if output == "yaml":
        import yaml
        data = [
            {
                "check": r.check_name,
                "severity": r.severity.value,
                "message": r.message,
                "suggestion": r.suggestion,
            }
            for r in results
        ]
        console.print(yaml.dump(data, default_flow_style=False))
        return

    table = Table(title="Helm Doctor", expand=True)
    table.add_column("", width=3, no_wrap=True)
    table.add_column("Check", style="cyan", no_wrap=True)
    table.add_column("Message", max_width=60)
    table.add_column("Suggestion", style="dim", max_width=50)

    for r in results:
        color = _SEVERITY_COLORS.get(r.severity, "white")
        icon = _SEVERITY_ICONS.get(r.severity, "?")
        table.add_row(
            f"[{color}]{icon}[/{color}]",
            r.check_name,
            r.message,
            r.suggestion or "",
        )

    console.print(table)

    errors = sum(1 for r in results if r.severity == Severity.ERROR)
    warnings = sum(1 for r in results if r.severity == Severity.WARNING)
    infos = sum(1 for r in results if r.severity == Severity.INFO)

    summary_parts = []
    if errors:
        summary_parts.append(f"[red]{errors} error(s)[/red]")
    if warnings:
        summary_parts.append(f"[yellow]{warnings} warning(s)[/yellow]")
    if infos:
        summary_parts.append(f"[blue]{infos} info(s)[/blue]")

    console.print(f"\nDiagnostics complete: {', '.join(summary_parts) if summary_parts else '[green]all clear[/green]'}")
