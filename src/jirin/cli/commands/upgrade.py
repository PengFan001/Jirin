"""Upgrade Jirin to the latest version."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import typer
from rich.console import Console

from jirin import __version__

upgrade_app = typer.Typer(help="Manage Jirin upgrades")
console = Console()


@upgrade_app.command()
def check() -> None:
    """Check current version and upgrade instructions."""
    console.print(f"[bold]Jirin version:[/bold] {__version__}")
    console.print()
    console.print("[dim]To upgrade Jirin, navigate to the project directory and run:[/dim]")
    console.print("  [bold]pip install --upgrade -e .[/bold]")
    console.print()
    console.print("[dim]If you pulled updates from git, dependencies may have changed.[/dim]")
    console.print("[dim]The upgrade command will reinstall with the latest dependencies.[/dim]")


@upgrade_app.command()
def run() -> None:
    """Upgrade Jirin and refresh dependencies.

    This command re-installs Jirin in editable mode, picking up any
    dependency changes from pyproject.toml.
    """
    console.print("[bold]Upgrading Jirin...[/bold]")
    console.print()

    # Find the project root (where pyproject.toml is)
    project_root = _find_project_root()
    if not project_root:
        console.print("[red]Error: Could not find Jirin project directory.[/red]")
        console.print("[yellow]Please run this command from the Jirin project directory,[/yellow]")
        console.print("[yellow]or use: pip install --upgrade -e /path/to/jirin[/yellow]")
        raise typer.Exit(1)

    console.print(f"[dim]Project directory: {project_root}[/dim]")
    console.print()

    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--upgrade", "-e", str(project_root)],
            capture_output=True,
            text=True,
            cwd=str(project_root),
        )

        if result.returncode == 0:
            console.print("[green]Upgrade completed successfully![/green]")
            # Show summary
            for line in result.stdout.split("\n"):
                if "Successfully installed" in line or "Requirement already satisfied" in line:
                    console.print(f"[dim]{line}[/dim]")
        else:
            console.print("[red]Upgrade failed.[/red]")
            console.print(f"[red]{result.stderr}[/red]")
            raise typer.Exit(1)

    except FileNotFoundError:
        console.print("[red]Error: pip not found.[/red]")
        raise typer.Exit(1)


@upgrade_app.command()
def reinstall() -> None:
    """Force reinstall Jirin (useful for fixing broken installations)."""
    console.print("[bold]Force reinstalling Jirin...[/bold]")
    console.print()

    project_root = _find_project_root()
    if not project_root:
        console.print("[red]Error: Could not find Jirin project directory.[/red]")
        raise typer.Exit(1)

    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--force-reinstall", "-e", str(project_root)],
            capture_output=True,
            text=True,
            cwd=str(project_root),
        )

        if result.returncode == 0:
            console.print("[green]Reinstall completed successfully![/green]")
        else:
            console.print("[red]Reinstall failed.[/red]")
            console.print(f"[red]{result.stderr}[/red]")
            raise typer.Exit(1)

    except FileNotFoundError:
        console.print("[red]Error: pip not found.[/red]")
        raise typer.Exit(1)


def _find_project_root() -> Path | None:
    """Find the Jirin project root directory.

    Searches for pyproject.toml containing 'jirin' in the current directory
    and parent directories.
    """
    # Check current directory first
    cwd = Path.cwd()
    pyproject = cwd / "pyproject.toml"
    if pyproject.exists():
        content = pyproject.read_text(encoding="utf-8", errors="replace")
        if "jirin" in content.lower():
            return cwd

    # Check the package installation directory
    try:
        import jirin
        pkg_dir = Path(jirin.__file__).resolve().parent
        # Navigate up from src/jirin/__init__.py to project root
        project_root = pkg_dir.parent.parent.parent
        pyproject = project_root / "pyproject.toml"
        if pyproject.exists():
            return project_root
    except ImportError:
        pass

    return None
