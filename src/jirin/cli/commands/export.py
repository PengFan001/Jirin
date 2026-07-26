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
        Path(".jirin/exports/qoder_skill"),
        "--output", "-o",
        help="Output directory for the skill",
    ),
    config: Path | None = typer.Option(
        None,
        "--config", "-c",
        help="Path to configuration file (auto-discovers if not specified)",
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
        Path(".jirin/exports/cursor_rules"),
        "--output", "-o",
        help="Output directory for cursor rules",
    ),
    config: Path | None = typer.Option(
        None,
        "--config", "-c",
        help="Path to configuration file (auto-discovers if not specified)",
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
        Path(".jirin/exports/generic"),
        "--output", "-o",
        help="Output directory",
    ),
    config: Path | None = typer.Option(
        None,
        "--config", "-c",
        help="Path to configuration file (auto-discovers if not specified)",
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
        Path(".jirin/exports/codex"),
        "--output", "-o",
        help="Output directory for AGENTS.md",
    ),
    config: Path | None = typer.Option(
        None,
        "--config", "-c",
        help="Path to configuration file (auto-discovers if not specified)",
    ),
    check: bool = typer.Option(
        False,
        "--check",
        help="Verify export content integrity after export",
    ),
) -> None:
    """Export as Codex AGENTS.md file."""
    from jirin.export.codex_agents import CodexExporter

    exporter = CodexExporter(config_path=config)
    exporter.export(output_dir=output_dir)
    console.print(f"[green]Codex AGENTS.md exported to: {output_dir}[/green]")

    if check:
        _verify_codex_export(output_dir)


def _verify_codex_export(output_dir: Path) -> None:
    """Verify that the Codex export contains valid knowledge content."""
    console.print("\n[bold]Export Verification[/bold]")
    errors = []
    warnings = []

    # Check AGENTS.md
    agents_md = output_dir / "AGENTS.md"
    if not agents_md.exists():
        errors.append("AGENTS.md not found")
    else:
        content = agents_md.read_text(encoding="utf-8")
        if len(content) < 100:
            errors.append(f"AGENTS.md too small ({len(content)} chars)")
        # Check for placeholder fallback text (means knowledge was empty)
        if "See jirin_knowledge/" in content:
            warnings.append("AGENTS.md contains fallback text - knowledge may be empty")
        else:
            console.print(f"  [green][OK][/green] AGENTS.md ({len(content)} chars, knowledge embedded)")

    # Check knowledge directory
    knowledge_dir = output_dir / "jirin_knowledge"
    if not knowledge_dir.exists():
        errors.append("jirin_knowledge/ directory not found")
    else:
        md_files = list(knowledge_dir.rglob("*.md"))
        if not md_files:
            errors.append("No .md files in jirin_knowledge/")
        else:
            empty_files = [f for f in md_files if f.stat().st_size == 0]
            if empty_files:
                errors.append(f"{len(empty_files)} empty knowledge file(s)")
            else:
                console.print(f"  [green][OK][/green] {len(md_files)} knowledge file(s) exported")

        # Check subdirectories
        for subdir_name in ["je", "anr", "ne"]:
            subdir = knowledge_dir / subdir_name
            if subdir.exists():
                files = list(subdir.glob("*.md"))
                console.print(f"    [dim]- {subdir_name}/: {len(files)} file(s)[/dim]")
            else:
                warnings.append(f"Missing knowledge subdirectory: {subdir_name}/")

    # Summary
    if errors:
        console.print(f"\n[red]Export verification FAILED ({len(errors)} error(s))[/red]")
        for err in errors:
            console.print(f"  [red]- {err}[/red]")
    elif warnings:
        console.print(f"\n[yellow]Export passed with warnings[/yellow]")
        for w in warnings:
            console.print(f"  [yellow]- {w}[/yellow]")
    else:
        console.print(f"\n[green]Export verification passed![/green]")


@export_app.command("check")
def export_check(
    output_dir: Path = typer.Argument(
        ...,
        help="Path to exported directory to verify",
        exists=True,
    ),
    export_type: str = typer.Option(
        "codex",
        "--type", "-t",
        help="Export type to verify: codex, cursor, qoder, generic",
    ),
) -> None:
    """Verify an existing export's content integrity."""
    if export_type == "codex":
        _verify_codex_export(output_dir)
    else:
        # Generic check: verify directory has files
        files = list(output_dir.rglob("*"))
        if not files:
            console.print(f"[red]No files found in {output_dir}[/red]")
        else:
            console.print(f"[green]Found {len(files)} file(s) in {output_dir}[/green]")
            for f in files[:10]:
                size = f.stat().st_size if f.is_file() else 0
                console.print(f"  [dim]- {f.relative_to(output_dir)} ({size} bytes)[/dim]")
