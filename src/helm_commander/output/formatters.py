"""Table / JSON / YAML output dispatch."""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

import yaml
from rich.console import Console

from helm_commander.models.release import HelmRelease, ReleaseStatus

console = Console()


def _release_to_dict(r: HelmRelease) -> dict[str, Any]:
    return {
        "name": r.name,
        "namespace": r.namespace,
        "context": r.context,
        "status": r.status.value,
        "revision": r.version,
        "chart": r.chart_name,
        "chart_version": r.chart_version,
        "app_version": r.app_version,
        "updated": r.updated,
    }


def output_releases(releases: list[HelmRelease], fmt: str) -> None:
    if fmt == "json":
        data = [_release_to_dict(r) for r in releases]
        console.print_json(json.dumps(data, indent=2))
    elif fmt == "yaml":
        data = [_release_to_dict(r) for r in releases]
        console.print(yaml.dump(data, default_flow_style=False))
    else:
        from helm_commander.output.tables import release_list_table
        console.print(release_list_table(releases))


def output_release_info(
    release: HelmRelease,
    fmt: str,
    show_values: bool = False,
    owner=None,
    resource_counts: dict[str, int] | None = None,
) -> None:
    if fmt == "json":
        data = _release_to_dict(release)
        data["chart_metadata"] = {
            "description": release.chart.description,
            "home": release.chart.home,
            "sources": release.chart.sources,
        }
        if show_values:
            data["values"] = release.config
        if resource_counts:
            data["resource_counts"] = resource_counts
        console.print_json(json.dumps(data, indent=2, default=str))
    elif fmt == "yaml":
        data = _release_to_dict(release)
        if show_values:
            data["values"] = release.config
        console.print(yaml.dump(data, default_flow_style=False))
    else:
        from helm_commander.output.tables import release_info_panel, resource_count_table, values_panel
        console.print(release_info_panel(release, owner=owner))
        if resource_counts:
            console.print(resource_count_table(resource_counts))
        if show_values:
            console.print(values_panel(release.config))


def output_history(revisions: list[HelmRelease], fmt: str) -> None:
    if fmt == "json":
        data = [_release_to_dict(r) for r in revisions]
        console.print_json(json.dumps(data, indent=2))
    elif fmt == "yaml":
        data = [_release_to_dict(r) for r in revisions]
        console.print(yaml.dump(data, default_flow_style=False))
    else:
        from helm_commander.output.tables import history_table
        console.print(history_table(revisions))
