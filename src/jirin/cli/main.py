"""Jirin CLI entry point.

Main CLI application using Typer for Android stability issue analysis.
Supports multi-platform log directory scanning and flexible output formats.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown

from jirin.cli.commands.analyze import analyze_cmd
from jirin.cli.commands.learn import learn_app
from jirin.cli.commands.export import export_app
from jirin.cli.commands.config import config_app
from jirin.cli.commands.upgrade import upgrade_app
from jirin.cli.commands.test_llm import test_app
from jirin.cli.commands.setup import setup_app

app = typer.Typer(
    name="jirin",
    help="AI Agent for Android stability issue analysis (JE/ANR/NE)",
    no_args_is_help=True,
)

console = Console()
logger = logging.getLogger(__name__)

# Register sub-commands
app.add_typer(learn_app, name="learn", help="Manage learning and case knowledge")
app.add_typer(export_app, name="export", help="Export agent as skill/plugin")
app.add_typer(config_app, name="config", help="Manage configuration")
app.add_typer(upgrade_app, name="upgrade", help="Upgrade Jirin to the latest version")
app.add_typer(test_app, name="test", help="Test LLM API connection")
app.add_typer(setup_app, name="setup", help="Initialize environment (download models)")


@app.command()
def analyze(
    log_path: Path = typer.Argument(
        ...,
        help="Path to log file or log directory (supports Qualcomm/MTK/SPRD structures)",
        exists=True,
        readable=True,
    ),
    config: Path | None = typer.Option(
        None,
        "--config", "-c",
        help="Path to configuration file (auto-discovers if not specified)",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose", "-v",
        help="Show detailed analysis process",
    ),
    export_format: str = typer.Option(
        "none",
        "--export", "-e",
        help="Export report format: none (text only), md, html",
    ),
    output: Path | None = typer.Option(
        None,
        "--output", "-o",
        help="Save report to file (auto-detects format from extension)",
    ),
    interactive: bool = typer.Option(
        True,
        "--interactive/--no-feedback",
        help="Enable/disable post-analysis feedback prompt",
    ),
) -> None:
    """Analyze Android stability issues from a log file or directory.

    Supports single log files or entire log directories from Qualcomm, MTK,
    and SPRD platforms. Automatically detects platform structure and locates
    relevant log files.

    Output modes:
    - Default: Plain text to terminal
    - --export md: Markdown report (Feishu/Lark compatible)
    - --export html: Styled HTML report
    - --output FILE: Save report to file
    """
    console.print(Panel("Jirin - Android Stability Issue Analyzer", style="bold blue"))

    # Check configuration
    _check_config(config)

    # Ensure embedding model is installed (auto-downloads if missing)
    from jirin.core.embedding_setup import ensure_embedding_model

    if not ensure_embedding_model(console):
        console.print("[yellow]Continuing without knowledge retrieval...[/yellow]")

    # Handle directory input
    if log_path.is_dir():
        _analyze_directory(log_path, config, verbose, export_format, output, interactive)
    else:
        _analyze_file(log_path, config, verbose, export_format, output, interactive)


def _analyze_file(
    log_file: Path,
    config: Path | None,
    verbose: bool,
    export_format: str,
    output: Path | None,
    interactive: bool = True,
) -> None:
    """Analyze a single log file."""
    log_content = log_file.read_text(encoding="utf-8", errors="replace")
    if not log_content.strip():
        console.print("[red]Error: Log file is empty[/red]")
        raise typer.Exit(1)

    console.print(f"[dim]Loaded log file: {log_file} ({len(log_content)} chars)[/dim]")

    try:
        result = asyncio.run(
            analyze_cmd(
                log_content=log_content,
                log_source=str(log_file),
                config_path=config,
                verbose=verbose,
            )
        )
    except Exception as e:
        console.print(f"[red]Analysis failed: {e}[/red]")
        if verbose:
            console.print_exception()
        raise typer.Exit(1)

    _output_result(result, export_format, output)

    # Show retrieval and learning status
    _show_retrieval_status(result)
    _show_learning_status(result, verbose)

    if interactive:
        _collect_feedback(result, config)


def _analyze_directory(
    log_dir: Path,
    config: Path | None,
    verbose: bool,
    export_format: str,
    output: Path | None,
    interactive: bool = True,
) -> None:
    """Analyze logs from a directory (supports multi-platform structures)."""
    from jirin.tools.log_scanner import LogDirectoryScanner

    scanner = LogDirectoryScanner()
    structure = scanner.scan_directory(log_dir)

    if structure is None:
        console.print(f"[red]Error: Cannot identify log directory structure: {log_dir}[/red]")
        console.print("[yellow]Tip: Provide a log file directly instead of a directory.[/yellow]")
        raise typer.Exit(1)

    console.print(f"[green]Detected platform: {structure.platform_name}[/green]")

    if structure.platform_name == "unknown":
        console.print("[yellow]Unknown platform structure. Will scan all files.[/yellow]")
        console.print(f"[dim]Tip: Use 'jirin learn structure <name> {log_dir}' to teach Jirin this structure.[/dim]")

    # Show found log files
    if structure.log_files:
        console.print(f"[dim]Found {len(structure.log_files)} log files:[/dim]")
        for mapping in structure.log_files:
            console.print(f"  [dim]- {mapping.log_type}: {mapping.file_path}[/dim]")
    else:
        console.print("[yellow]No recognized log files found in directory.[/yellow]")

    # Check for missing important files
    missing = scanner.get_missing_files(structure, log_dir)
    if missing:
        console.print("\n[yellow]Missing important log files:[/yellow]")
        for log_type, adb_cmd in missing:
            console.print(f"  [yellow]- {log_type}: {adb_cmd}[/yellow]")

    # Analyze each found log file
    all_content = []
    for mapping in structure.log_files:
        if mapping.file_path.exists():
            content = mapping.file_path.read_text(encoding="utf-8", errors="replace")
            if content.strip():
                all_content.append(f"=== {mapping.log_type} ({mapping.file_path.name}) ===\n{content}")

    if not all_content:
        console.print("[red]No readable log content found in directory.[/red]")
        raise typer.Exit(1)

    combined_content = "\n\n".join(all_content)
    console.print(f"[dim]Combined {len(all_content)} log files ({len(combined_content)} chars)[/dim]")

    try:
        result = asyncio.run(
            analyze_cmd(
                log_content=combined_content,
                log_source=str(log_dir),
                config_path=config,
                verbose=verbose,
            )
        )
    except Exception as e:
        console.print(f"[red]Analysis failed: {e}[/red]")
        if verbose:
            console.print_exception()
        raise typer.Exit(1)

    _output_result(result, export_format, output)

    # Show retrieval and learning status
    _show_retrieval_status(result)
    _show_learning_status(result, verbose)


def _output_result(result, export_format: str, output: Path | None) -> None:
    """Output analysis result in the requested format."""
    from jirin.export.report import save_report

    if output:
        # Save to user-specified path
        suffix = output.suffix.lower()
        if suffix in (".html",) or export_format == "html":
            fmt = "html"
        elif suffix in (".md",) or export_format == "md":
            fmt = "md"
        else:
            fmt = "text"
        saved_path = save_report(result, output, fmt=fmt)
        console.print(f"[green]Report saved to: {saved_path}[/green]")
    elif export_format in ("md", "html"):
        # --export md/html without --output: save to default path
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        ext = "md" if export_format == "md" else "html"
        default_path = Path(f".jirin/reports/jirin_report_{timestamp}.{ext}")
        saved_path = save_report(result, default_path, fmt=export_format)
        console.print(f"[green]Report saved to: {saved_path}[/green]")
    elif result.final_report:
        # Default: formatted text output to terminal
        console.print()
        console.print(Markdown(result.final_report))
    else:
        console.print("[yellow]No analysis report generated.[/yellow]")

    # Show errors if any
    if result.errors:
        console.print(f"\n[dim]Warnings: {len(result.errors)} issue(s) during analysis[/dim]")
        for error in result.errors:
            console.print(f"  [dim]- {error}[/dim]")


def _show_learning_status(result, verbose: bool) -> None:
    """Display the learning pipeline execution status."""
    metadata = result.metadata if hasattr(result, "metadata") and isinstance(result.metadata, dict) else {}
    learning_status = metadata.get("learning_status")

    if learning_status == "success":
        case_id = metadata.get("case_id", "")
        pattern = metadata.get("root_cause_pattern", "")
        category = metadata.get("root_cause_category", "")
        console.print(f"\n[green]Learning:[/green] Case saved [dim]({case_id})[/dim]")
        if pattern:
            console.print(f"  [dim]Pattern: {pattern}[/dim]")
        if category:
            console.print(f"  [dim]Category: {category}[/dim]")
    elif learning_status == "skipped":
        console.print("\n[dim]Learning: Skipped (no patterns extracted)[/dim]")
    elif metadata.get("learning_error"):
        error_msg = metadata["learning_error"]
        console.print(f"\n[yellow]Learning: Failed[/yellow] [dim]({error_msg})[/dim]")
        if verbose:
            console.print("[dim]Run with --verbose for more details.[/dim]")
    # If no learning_status and no agent_results, learning didn't run (expected)


def _show_retrieval_status(result) -> None:
    """Display knowledge retrieval statistics."""
    metadata = result.metadata if hasattr(result, "metadata") and isinstance(result.metadata, dict) else {}
    stats = metadata.get("retrieval_stats")
    if not stats:
        return

    snippets = stats.get("knowledge_snippets", 0)
    cases = stats.get("similar_cases", 0)

    if snippets > 0 or cases > 0:
        console.print(
            f"[dim]Knowledge:[/dim] {snippets} snippet(s), {cases} similar case(s) retrieved"
        )
    else:
        console.print("[dim]Knowledge: No relevant knowledge found[/dim]")


def _collect_feedback(result, config: Path | None) -> None:
    """Interactively collect user feedback on analysis results."""
    if not result.final_report:
        return

    console.print()
    feedback = console.input(
        "[bold]Was this analysis helpful?[/bold] "
        "[green](y)[/green]es / [red](n)[/red]o / [yellow](c)[/yellow]orrection: "
    ).strip().lower()

    if feedback == "y":
        _save_feedback(result, config, "positive", "")
        console.print("[dim]Thank you! Feedback recorded.[/dim]")
    elif feedback == "n":
        reason = console.input(
            "[dim]What was wrong? (optional, press Enter to skip): [/dim]"
        ).strip()
        _save_feedback(result, config, "negative", reason)
        console.print("[dim]Feedback recorded. We'll improve.[/dim]")
    elif feedback == "c":
        correction = console.input(
            "[bold]Please provide the correct analysis: [/bold]"
        ).strip()
        if correction:
            _save_feedback(result, config, "correction", correction)
            console.print("[dim]Correction recorded for learning.[/dim]")


def _save_feedback(
    result, config: Path | None, feedback_type: str, content: str
) -> None:
    """Save feedback to case store."""
    try:
        from jirin.core.context import ExecutionContext

        ctx = ExecutionContext(config_path=config)
        case_store = ctx.case_store

        # Use case_id from result metadata if available
        case_id = None
        if hasattr(result, "metadata") and isinstance(result.metadata, dict):
            case_id = result.metadata.get("case_id")

        # Fallback: find the most recent case
        if not case_id:
            recent_cases = case_store.list_cases(limit=1)
            if recent_cases:
                case_id = recent_cases[0]["id"]

        if not case_id:
            console.print("[dim]No case found to attach feedback.[/dim]")
            return

        feedback_data = {
            "type": feedback_type,
            "content": content,
            "detected_types": [t.value for t in result.detected_types],
            "agent_results_count": len(result.agent_results),
        }
        case_store.add_feedback(case_id, feedback_data)
    except Exception as e:
        logger.debug("Feedback save failed (non-fatal): %s", e)


def _check_config(config_path: Path | None) -> None:
    """Check configuration and print friendly warnings if needed."""
    from jirin.core.context import ExecutionContext

    ctx = ExecutionContext(config_path=config_path)

    if ctx.config_missing:
        console.print(
            f"[yellow]Warning: No config file found. Searched locations:[/yellow]\n"
            f"  [dim]- {ctx.config_missing_path}[/dim]\n"
            f"[yellow]Using default settings. To configure LLM, run:[/yellow]\n"
            f"  [bold]jirin config init[/bold]\n"
            f"[dim]See docs/jirin_user_guide.html for LLM configuration guide.[/dim]"
        )
        return

    llm_cfg = ctx.get_llm_config()
    provider = llm_cfg.get("provider", "")
    api_key = llm_cfg.get("api_key", "")

    if provider != "ollama" and not api_key:
        console.print(
            "[yellow]Warning: LLM API Key not configured.[/yellow]\n"
            "[yellow]Analysis requires an LLM. Configure one of:[/yellow]\n"
            "  [bold]- OpenAI / DeepSeek / Qwen / Kimi[/bold] (need API Key)\n"
            "  [bold]- Ollama[/bold] (local model, no API Key needed)\n"
            "[dim]Run 'jirin config init' or edit config/settings.toml[/dim]"
        )


@app.command(name="learn-structure")
def learn_structure(
    name: str = typer.Argument(..., help="Name for this directory structure"),
    log_dir: Path = typer.Argument(..., help="Path to log directory to learn", exists=True),
) -> None:
    """Teach Jirin a new log directory structure.

    After learning, Jirin will recognize this structure in future analyses.
    """
    from jirin.tools.log_scanner import LogDirectoryScanner

    scanner = LogDirectoryScanner()
    scanner.learn_structure(name, log_dir)
    console.print(f"[green]Learned structure '{name}' from {log_dir}[/green]")


@app.command()
def version() -> None:
    """Show Jirin version information."""
    from jirin import __version__
    console.print(f"Jirin v{__version__}")


if __name__ == "__main__":
    app()
