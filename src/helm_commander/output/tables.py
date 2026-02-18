"""Rich table builders for each command."""

from __future__ import annotations

from rich.panel import Panel
from rich.table import Table
from rich.syntax import Syntax
from rich.text import Text

from helm_commander.models import Confidence, OwnerInfo
from helm_commander.models.release import HelmRelease, ReleaseStatus
from helm_commander.output.themes import styled_status, styled_confidence


def release_list_table(releases: list[HelmRelease]) -> Table:
    table = Table(title="Helm Releases", expand=True, show_lines=False)
    table.add_column("Context", style="cyan", no_wrap=True, max_width=20)
    table.add_column("Namespace", style="blue", no_wrap=True)
    table.add_column("Release", style="bold white", no_wrap=True)
    table.add_column("Status", no_wrap=True)
    table.add_column("Rev", justify="right", style="dim")
    table.add_column("Chart", style="magenta", no_wrap=True)
    table.add_column("Chart Ver", style="magenta")
    table.add_column("App Ver", style="cyan")
    table.add_column("Updated", style="dim", no_wrap=True)

    for r in releases:
        table.add_row(
            r.context,
            r.namespace,
            r.name,
            styled_status(r.status),
            str(r.version),
            r.chart_name,
            r.chart_version,
            r.app_version,
            r.updated_short,
        )
    return table


def release_info_panel(release: HelmRelease, owner: OwnerInfo | None = None) -> Panel:
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Key", style="bold cyan", no_wrap=True)
    table.add_column("Value")

    table.add_row("Release", release.name)
    table.add_row("Namespace", release.namespace)
    table.add_row("Context", release.context)
    table.add_row("Status", styled_status(release.status))
    table.add_row("Revision", str(release.version))
    table.add_row("Chart", f"{release.chart_name}-{release.chart_version}")
    table.add_row("App Version", release.app_version or "-")
    table.add_row("Description", release.chart.description or "-")
    table.add_row("Last Deployed", release.updated_short or "-")

    if release.chart.home:
        table.add_row("Home", release.chart.home)
    if release.chart.sources:
        table.add_row("Sources", ", ".join(release.chart.sources))
    if release.chart.maintainers:
        maintainers = ", ".join(
            m.name + (f" <{m.email}>" if m.email else "") for m in release.chart.maintainers
        )
        table.add_row("Maintainers", maintainers)
    if release.chart.dependencies:
        deps = ", ".join(f"{d.name}@{d.version}" for d in release.chart.dependencies)
        table.add_row("Dependencies", deps)

    if owner:
        table.add_row("Managed By", f"{owner.controller.value} ({styled_confidence(owner.confidence)})")
        if owner.detail:
            table.add_row("Owner Detail", owner.detail)

    return Panel(table, title=f"[bold]Release: {release.name}[/bold]", border_style="blue")


def resource_count_table(counts: dict[str, int]) -> Table:
    table = Table(title="Resources by Kind", expand=False)
    table.add_column("Kind", style="cyan")
    table.add_column("Count", justify="right", style="bold")
    for kind, count in sorted(counts.items()):
        table.add_row(kind, str(count))
    return table


def values_panel(config: dict) -> Panel:
    import yaml
    text = yaml.dump(config, default_flow_style=False) if config else "(no user-supplied values)"
    syntax = Syntax(text, "yaml", theme="monokai", line_numbers=False)
    return Panel(syntax, title="[bold]User-Supplied Values[/bold]", border_style="green")


def history_table(revisions: list[HelmRelease]) -> Table:
    table = Table(title="Release History", expand=True)
    table.add_column("Revision", justify="right", style="bold")
    table.add_column("Status", no_wrap=True)
    table.add_column("Chart", style="magenta")
    table.add_column("Chart Ver", style="magenta")
    table.add_column("App Ver", style="cyan")
    table.add_column("Updated", style="dim", no_wrap=True)
    table.add_column("Description", max_width=40)

    for r in revisions:
        table.add_row(
            str(r.version),
            styled_status(r.status),
            r.chart_name,
            r.chart_version,
            r.app_version,
            r.updated_short,
            r.info.description or "",
        )
    return table
