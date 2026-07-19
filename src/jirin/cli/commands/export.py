"""Export command implementation.

Commands for exporting the agent as a skill/plugin for other AI IDEs.
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

console = Console()

export_app = typer.Typer(no_args_is_help=True)


@export_app.command("qoder")
def export_qoder(
    output_dir: Path = typer.Option(
        Path("data/exports/qoder_skill"),
        "--output", "-o",
        help="Output directory for the skill",
    ),
    config: Path = typer.Option(
        Path("config/settings.toml"),
        "--config", "-c",
        help="Path to configuration file",
    ),
) -> None:
    """Export as Qoder Skill."""
    from jirin.export.qoder_skill import QoderSkillExporter

    exporter = QoderSkillExporter(config_path=config)
    exporter.export(output_dir=output_dir)
    console.print(f"[green]Qoder Skill exported to: {output_dir}[/green]")


@export_app.command("cursor")
def export_cursor(
    output_dir: Path = typer.Option(
        Path("data/exports/cursor_rules"),
        "--output", "-o",
        help="Output directory for cursor rules",
    ),
    config: Path = typer.Option(
        Path("config/settings.toml"),
        "--config", "-c",
        help="Path to configuration file",
    ),
) -> None:
    """Export as Cursor Rules."""
    from jirin.export.cursor_rules import CursorRulesExporter

    exporter = CursorRulesExporter(config_path=config)
    exporter.export(output_dir=output_dir)
    console.print(f"[green]Cursor Rules exported to: {output_dir}[/green]")


@export_app.command("generic")
def export_generic(
    output_dir: Path = typer.Option(
        Path("data/exports/generic"),
        "--output", "-o",
        help="Output directory",
    ),
    config: Path = typer.Option(
        Path("config/settings.toml"),
        "--config", "-c",
        help="Path to configuration file",
    ),
) -> None:
    """Export as generic Markdown documentation."""
    from jirin.export.generic import GenericExporter

    exporter = GenericExporter(config_path=config)
    exporter.export(output_dir=output_dir)
    console.print(f"[green]Generic export saved to: {output_dir}[/green]")


@export_app.command("codex")
def export_codex(
    output_dir: Path = typer.Option(
        Path("data/exports/codex"),
        "--output", "-o",
        help="Output directory for AGENTS.md",
    ),
    config: Path = typer.Option(
        Path("config/settings.toml"),
        "--config", "-c",
        help="Path to configuration file",
    ),
) -> None:
    """Export as Codex AGENTS.md file."""
    from jirin.export.codex_agents import CodexExporter

    exporter = CodexExporter(config_path=config)
    exporter.export(output_dir=output_dir)
    console.print(f"[green]Codex AGENTS.md exported to: {output_dir}[/green]")
