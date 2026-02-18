"""Root Typer application, mounts sub-commands."""

from __future__ import annotations

import typer

app = typer.Typer(
    name="hcom",
    help="Helm Commander - Better visibility into Helm deployments.",
    no_args_is_help=True,
)


def _register_commands() -> None:
    from helm_commander.cli.commands.list_cmd import app as list_app
    from helm_commander.cli.commands.info_cmd import app as info_app
    from helm_commander.cli.commands.source_cmd import app as source_app
    from helm_commander.cli.commands.updates_cmd import app as updates_app
    from helm_commander.cli.commands.doctor_cmd import app as doctor_app
    from helm_commander.cli.commands.drift_cmd import app as drift_app
    from helm_commander.cli.commands.history_cmd import app as history_app

    app.add_typer(list_app, name="list", help="List Helm releases")
    app.add_typer(info_app, name="info", help="Show release details")
    app.add_typer(source_app, name="source", help="Detect chart source repository")
    app.add_typer(updates_app, name="updates", help="Check for chart updates")
    app.add_typer(doctor_app, name="doctor", help="Run diagnostic checks")
    app.add_typer(drift_app, name="drift", help="Detect configuration drift")
    app.add_typer(history_app, name="history", help="Show release revision history")


_register_commands()


def main() -> None:
    app()
