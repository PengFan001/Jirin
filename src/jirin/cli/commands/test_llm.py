"""Test LLM API connection."""

from __future__ import annotations

import asyncio
import time

import typer
from rich.console import Console

from jirin.core.context import ExecutionContext, find_config_file
from jirin.core.llm_client import LLMClient

test_app = typer.Typer(help="Test LLM API connectivity")
console = Console()


@test_app.command()
def connection(
    config: str = typer.Option(
        None,
        "--config", "-c",
        help="Path to configuration file",
    ),
) -> None:
    """Test LLM API connection with a minimal request.

    Sends a simple 'Hello' message to verify the API is accessible
    and the configuration is correct.
    """
    console.print("[bold]Testing LLM API connection...[/bold]")
    console.print()

    # Load configuration
    config_path = find_config_file(config)
    if not config_path:
        console.print("[red]Error: No configuration file found.[/red]")
        console.print("[yellow]Run 'jirin config init' to create one.[/yellow]")
        raise typer.Exit(1)

    console.print(f"[dim]Config: {config_path}[/dim]")

    ctx = ExecutionContext(config_path=config_path)
    llm_config = ctx.get_llm_config()

    if not llm_config:
        console.print("[red]Error: No [llm] section found in config.[/red]")
        raise typer.Exit(1)

    # Display config summary (hide API key)
    provider = llm_config.get("provider", "unknown")
    model = llm_config.get("model", "unknown")
    api_key = llm_config.get("api_key", "")
    api_base = llm_config.get("api_base", "")

    # Validate API key for non-ollama providers
    if not api_key and provider != "ollama":
        console.print("[red]Error: No API key configured for provider '[/red]"
                      f"[bold]{provider}[/bold][red]'.[/red]")
        console.print("[yellow]Please set api_key in config/settings.toml[/yellow]")
        raise typer.Exit(1)

    console.print(f"[dim]Provider: {provider}[/dim]")
    console.print(f"[dim]Model: {model}[/dim]")
    if api_base:
        console.print(f"[dim]API Base: {api_base}[/dim]")
    if api_key:
        masked_key = api_key[:8] + "..." + api_key[-4:] if len(api_key) > 12 else "***"
        console.print(f"[dim]API Key: {masked_key}[/dim]")
    console.print()

    # Test connection
    console.print("[dim]Sending test request...[/dim]")
    start_time = time.time()

    try:
        result = asyncio.run(_test_connection(llm_config))
        elapsed = time.time() - start_time

        if result["success"]:
            console.print(f"[green]Connection successful![/green]")
            console.print(f"[dim]Response time: {elapsed:.2f}s[/dim]")
            console.print(f"[dim]Model: {result.get('model', 'unknown')}[/dim]")
            console.print(f"[dim]Response: {result.get('content', '')[:100]}...[/dim]")
        else:
            console.print(f"[red]Connection failed![/red]")
            console.print(f"[red]Error: {result.get('error', 'Unknown error')}[/red]")
            raise typer.Exit(1)

    except Exception as e:
        elapsed = time.time() - start_time
        console.print(f"[red]Connection failed after {elapsed:.2f}s![/red]")
        console.print(f"[red]Error: {type(e).__name__}: {e}[/red]")
        raise typer.Exit(1)


async def _test_connection(llm_config: dict) -> dict:
    """Perform the actual connection test."""
    client = LLMClient(llm_config, max_retries=1, timeout=30.0)

    response = await client.complete(
        messages=[
            {"role": "user", "content": "Say 'Hello' in one word."},
        ],
        max_tokens=20,
    )

    if response.success:
        return {
            "success": True,
            "model": response.model,
            "content": response.content.strip(),
        }
    else:
        return {
            "success": False,
            "error": response.error,
        }


@test_app.command()
def models(
    config: str = typer.Option(
        None,
        "--config", "-c",
        help="Path to configuration file",
    ),
) -> None:
    """List available models from the configured API provider.

    Queries the /models endpoint to show what models are available.
    """
    console.print("[bold]Querying available models...[/bold]")
    console.print()

    config_path = find_config_file(config)
    if not config_path:
        console.print("[red]Error: No configuration file found.[/red]")
        raise typer.Exit(1)

    ctx = ExecutionContext(config_path=config_path)
    llm_config = ctx.get_llm_config()

    if not llm_config:
        console.print("[red]Error: No [llm] section found in config.[/red]")
        raise typer.Exit(1)

    try:
        result = asyncio.run(_list_models(llm_config))
        if result["success"]:
            console.print("[green]Available models:[/green]")
            for model in result.get("models", []):
                model_id = model.get("id", "unknown")
                owned_by = model.get("owned_by", "")
                console.print(f"  - [bold]{model_id}[/bold]")
                if owned_by:
                    console.print(f"    [dim]Owner: {owned_by}[/dim]")
        else:
            console.print(f"[red]Failed to list models: {result.get('error', 'Unknown error')}[/red]")
            raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error: {type(e).__name__}: {e}[/red]")
        raise typer.Exit(1)


async def _list_models(llm_config: dict) -> dict:
    """Query the /models endpoint."""
    import httpx

    api_key = llm_config.get("api_key", "")
    api_base = llm_config.get("api_base", "")

    # Build models URL
    if api_base:
        base = api_base.rstrip("/")
        if base.endswith("/v1"):
            models_url = f"{base}/models"
        else:
            models_url = f"{base}/v1/models"
    else:
        # Use provider default
        from jirin.core.llm_client import PROVIDER_DEFAULTS
        provider = llm_config.get("provider", "openai").lower()
        default_base = PROVIDER_DEFAULTS.get(provider, "https://api.openai.com/v1")
        models_url = f"{default_base}/models"

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(models_url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            return {
                "success": True,
                "models": data.get("data", []),
            }
        else:
            return {
                "success": False,
                "error": f"HTTP {response.status_code}: {response.text[:200]}",
            }
