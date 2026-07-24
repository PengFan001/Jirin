"""Config command implementation.

Commands for managing Jirin configuration.
"""

from __future__ import annotations

import sys
from pathlib import Path

import typer
from rich.console import Console

if sys.version_info >= (3, 12):
    import tomllib
else:
    import tomli as tomllib

from jirin.core.context import find_config_file

console = Console()

config_app = typer.Typer(no_args_is_help=True)


@config_app.command("show")
def show_config(
    config: Path | None = typer.Option(
        None,
        "--config", "-c",
        help="Path to configuration file (auto-discovers if not specified)",
    ),
) -> None:
    """Show current configuration."""
    resolved = find_config_file(config)
    if not resolved:
        console.print("[red]Config file not found.[/red]")
        console.print("[yellow]Searched: CWD and package directory.[/yellow]")
        console.print("[dim]Run 'jirin config init' to create one.[/dim]")
        raise typer.Exit(1)

    with open(resolved, "rb") as f:
        data = tomllib.load(f)

    console.print(f"[bold]Current Configuration[/bold] [dim]({resolved})[/dim]\n")
    _print_dict(data)


@config_app.command("init")
def init_config(
    output: Path = typer.Option(
        Path("config/settings.toml"),
        "--output", "-o",
        help="Output path for new config file",
    ),
    force: bool = typer.Option(False, "--force", help="Overwrite existing config"),
) -> None:
    """Initialize a new configuration file from template."""
    if output.exists() and not force:
        console.print(f"[yellow]Config already exists: {output}[/yellow]")
        console.print("Use --force to overwrite.")
        raise typer.Exit(1)

    # Find example config
    example = Path("config/settings.example.toml")
    if example.exists():
        content = example.read_text(encoding="utf-8")
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(content, encoding="utf-8")
        console.print(f"[green]Config initialized: {output}[/green]")
    else:
        console.print("[red]Template not found: config/settings.example.toml[/red]")
        raise typer.Exit(1)


@config_app.command("set")
def set_config(
    key: str = typer.Argument(..., help="Config key (e.g., llm.model)"),
    value: str = typer.Argument(..., help="Value to set"),
    config: Path | None = typer.Option(
        None,
        "--config", "-c",
        help="Path to configuration file (auto-discovers if not specified)",
    ),
) -> None:
    """Set a configuration value."""
    import tomli_w

    resolved = find_config_file(config)
    if not resolved:
        console.print("[red]Config file not found.[/red]")
        console.print("[dim]Run 'jirin config init' to create one.[/dim]")
        raise typer.Exit(1)

    with open(resolved, "rb") as f:
        data = tomllib.load(f)

    # Set value using dot notation
    keys = key.split(".")
    d = data
    for k in keys[:-1]:
        if k not in d:
            d[k] = {}
        d = d[k]
    d[keys[-1]] = value

    with open(resolved, "wb") as f:
        tomli_w.dump(data, f)

    console.print(f"[green]Set {key} = {value}[/green]")


def _print_dict(d: dict, indent: int = 0) -> None:
    """Pretty print a dictionary."""
    prefix = "  " * indent
    for key, value in d.items():
        if isinstance(value, dict):
            console.print(f"{prefix}[bold]{key}:[/bold]")
            _print_dict(value, indent + 1)
        else:
            console.print(f"{prefix}{key}: {value}")
