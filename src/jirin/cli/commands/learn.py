"""Learn command implementation.

Commands for managing the learning system and case knowledge.
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from jirin.core.context import ExecutionContext
from jirin.knowledge.case_store import CaseStore

console = Console()

learn_app = typer.Typer(no_args_is_help=True)


@learn_app.command("stats")
def stats(
    config: Path | None = typer.Option(
        None,
        "--config", "-c",
        help="Path to configuration file (auto-discovers if not specified)",
    ),
) -> None:
    """Show knowledge base statistics."""
    context = ExecutionContext(config_path=config)
    km = context.knowledge_manager
    summary = km.get_knowledge_summary()

    console.print("\n[bold]Knowledge Base Statistics[/bold]")
    console.print(f"  Static documents: {summary['static_docs']}")
    console.print(f"  Case embeddings: {summary.get('case_embeddings', 0)}")

    case_stats = summary.get("cases", {})
    console.print(f"  Total cases: {case_stats.get('total', 0)}")
    console.print(f"  Cases with feedback: {case_stats.get('with_feedback', 0)}")

    by_type = case_stats.get("by_type", {})
    if by_type:
        console.print("  Cases by type:")
        for issue_type, count in by_type.items():
            console.print(f"    {issue_type}: {count}")


@learn_app.command("list")
def list_cases(
    config: Path | None = typer.Option(
        None,
        "--config", "-c",
        help="Path to configuration file (auto-discovers if not specified)",
    ),
    issue_type: str = typer.Option(
        None,
        "--type", "-t",
        help="Filter by issue type (je/anr/ne)",
    ),
    limit: int = typer.Option(20, "--limit", "-l", help="Max cases to show"),
) -> None:
    """List stored analysis cases."""
    context = ExecutionContext(config_path=config)
    cases = context.case_store.list_cases(issue_type=issue_type, limit=limit)

    if not cases:
        console.print("[dim]No cases found.[/dim]")
        return

    table = Table(title="Analysis Cases")
    table.add_column("ID", style="cyan")
    table.add_column("Type", style="green")
    table.add_column("Root Cause")
    table.add_column("Date")
    table.add_column("Feedback")

    for case in cases:
        table.add_row(
            case.get("id", ""),
            case.get("issue_type", ""),
            case.get("root_cause", "")[:50],
            case.get("created_at", "")[:10],
            "Yes" if case.get("has_feedback") else "",
        )

    console.print(table)


@learn_app.command("feedback")
def feedback(
    case_id: str = typer.Argument(..., help="Case ID to add feedback to"),
    correction: str = typer.Option(..., "--correction", "-r", help="Correction text"),
    config: Path | None = typer.Option(
        None,
        "--config", "-c",
        help="Path to configuration file (auto-discovers if not specified)",
    ),
) -> None:
    """Add feedback/correction to a case."""
    context = ExecutionContext(config_path=config)
    success = context.case_store.add_feedback(
        case_id=case_id,
        feedback={"type": "correction", "content": correction},
    )

    if success:
        console.print(f"[green]Feedback added to case {case_id}[/green]")
    else:
        console.print(f"[red]Case {case_id} not found[/red]")
