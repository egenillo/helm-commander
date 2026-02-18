"""Shared CLI options."""

from __future__ import annotations

from typing import Optional

import typer

OutputOption = typer.Option("table", "--output", "-o", help="Output format: table, json, yaml")
NamespaceOption = typer.Option(None, "--namespace", "-n", help="Kubernetes namespace (default: all)")
ContextOption = typer.Option(None, "--context", help="Kubernetes context name")
