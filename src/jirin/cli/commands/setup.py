"""Setup command for initial environment configuration.

Pre-downloads required models (ChromaDB embedding model) from
accessible mirrors, avoiding slow default download sources.
"""

from __future__ import annotations

import typer
from rich.console import Console

console = Console()

setup_app = typer.Typer(invoke_without_command=True)


@setup_app.callback(invoke_without_command=True)
def setup_main(ctx: typer.Context) -> None:
    """Pre-download required models and initialize the environment."""
    if ctx.invoked_subcommand is None:
        # Default: run full setup
        from jirin.core.embedding_setup import ensure_embedding_model

        console.print("[bold]Jirin Environment Setup[/bold]\n")
        success = ensure_embedding_model(console)
        if success:
            console.print("\n[green]Setup complete! Jirin is ready to use.[/green]")
        else:
            console.print("\n[yellow]Setup incomplete. Some features may be unavailable.[/yellow]")
            console.print("[dim]You can retry by running: jirin setup[/dim]")
