"""Embedding model installation and management.

Handles automatic detection, download, and installation of the ChromaDB
embedding model (all-MiniLM-L6-v2) with smart mirror selection.

ChromaDB downloads its default embedding model from AWS S3, which is slow
in China. This module detects network conditions and uses HuggingFace mirror
(hf-mirror.com) when available for fast downloads.
"""

from __future__ import annotations

import logging
import os
import shutil
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ChromaDB's expected model directory and required files
MODEL_DIR = Path.home() / ".cache" / "chroma" / "onnx_models" / "all-MiniLM-L6-v2"
ONNX_DIR = MODEL_DIR / "onnx"
REQUIRED_FILES = [
    "config.json",
    "model.onnx",
    "special_tokens_map.json",
    "tokenizer_config.json",
    "tokenizer.json",
    "vocab.txt",
]

# Download sources
HF_MIRROR_URL = "https://hf-mirror.com"
HF_REPO = "Xenova/all-MiniLM-L6-v2"
# File mapping: (repo_path, target_filename)
HF_FILE_MAPPING = [
    ("config.json", "config.json"),
    ("onnx/model.onnx", "model.onnx"),
    ("special_tokens_map.json", "special_tokens_map.json"),
    ("tokenizer_config.json", "tokenizer_config.json"),
    ("tokenizer.json", "tokenizer.json"),
    ("vocab.txt", "vocab.txt"),
]


def is_model_installed() -> bool:
    """Check if the embedding model is already installed.

    Returns:
        True if all required model files exist, False otherwise.
    """
    return all((ONNX_DIR / f).exists() for f in REQUIRED_FILES)


def probe_mirror(url: str = HF_MIRROR_URL, timeout: float = 3.0) -> bool:
    """Probe whether a mirror URL is reachable.

    Args:
        url: The mirror URL to probe.
        timeout: Connection timeout in seconds.

    Returns:
        True if the mirror is reachable, False otherwise.
    """
    try:
        import httpx

        resp = httpx.head(url, timeout=timeout, follow_redirects=True)
        return resp.status_code < 500
    except Exception:
        return False


def _is_likely_china_user() -> bool:
    """Heuristic: check if system timezone suggests China (UTC+8).

    Uses time.localtime() vs time.gmtime() to determine the actual UTC
    offset, avoiding the platform-dependent sign convention of time.timezone
    (negative east of UTC on Unix, positive east on Windows).

    Returns:
        True if system timezone is UTC+8 (China Standard Time).
    """
    local = time.localtime()
    utc = time.gmtime()
    # Compute offset in seconds: positive = east of UTC
    offset_seconds = (
        (local.tm_hour - utc.tm_hour) * 3600
        + (local.tm_min - utc.tm_min) * 60
        + (local.tm_sec - utc.tm_sec)
    )
    # Normalize to [-86400, 86400] range (handle day wrap-around)
    if offset_seconds > 43200:
        offset_seconds -= 86400
    elif offset_seconds < -43200:
        offset_seconds += 86400
    return offset_seconds == 28800  # 28800 seconds = 8 hours = UTC+8


def choose_download_source() -> str:
    """Automatically choose the best download source.

    Priority:
    1. HF_ENDPOINT environment variable (user-specified)
    2. China timezone (UTC+8) + hf-mirror.com reachable
    3. "s3" - let ChromaDB use its default S3 download (for international users)

    Returns:
        "hf-mirror" for HuggingFace mirror, "s3" for ChromaDB default.
    """
    # 1. User explicitly set HF_ENDPOINT
    if os.environ.get("HF_ENDPOINT"):
        return "hf-mirror"  # Use huggingface_hub with user's endpoint

    # 2. China timezone -> probe hf-mirror.com
    if _is_likely_china_user() and probe_mirror():
        return "hf-mirror"

    # 3. Fall back to ChromaDB's default S3 download
    return "s3"


def _download_via_huggingface(console: Any = None) -> bool:
    """Download model files from HuggingFace (or mirror).

    Uses huggingface_hub to download individual files from Xenova/all-MiniLM-L6-v2
    and copies them to ChromaDB's expected cache directory.

    Args:
        console: Rich console for progress output.

    Returns:
        True if download succeeded, False otherwise.
    """
    try:
        from huggingface_hub import hf_hub_download
    except ImportError:
        if console:
            console.print("[red]huggingface_hub not installed.[/red]")
            console.print("[dim]Run: pip install huggingface_hub[/dim]")
        return False

    ONNX_DIR.mkdir(parents=True, exist_ok=True)

    for repo_path, target_name in HF_FILE_MAPPING:
        if (ONNX_DIR / target_name).exists():
            continue  # Skip already downloaded files
        try:
            if console:
                console.print(f"  [dim]Downloading {target_name}...[/dim]")
            src = hf_hub_download(HF_REPO, repo_path)
            shutil.copy2(src, ONNX_DIR / target_name)
        except Exception as e:
            if console:
                console.print(f"[red]Failed to download {target_name}: {e}[/red]")
            return False

    return True


def _download_via_chromadb(console: Any = None) -> bool:
    """Let ChromaDB download the model from its default S3 source.

    Triggers ChromaDB's built-in download mechanism by creating a
    temporary embedding function.

    Args:
        console: Rich console for progress output.

    Returns:
        True if download succeeded, False otherwise.
    """
    if console:
        console.print("  [dim]Downloading from ChromaDB default source...[/dim]")
    try:
        # Clear any HF_ENDPOINT that might interfere
        old_endpoint = os.environ.pop("HF_ENDPOINT", None)
        try:
            from chromadb.utils.embedding_functions.onnx_mini_lm_l6_v2 import ONNXMiniLM_L6_V2

            ef = ONNXMiniLM_L6_V2()
            ef._download_model_if_not_exists()
        finally:
            # Restore env var
            if old_endpoint is not None:
                os.environ["HF_ENDPOINT"] = old_endpoint

        return is_model_installed()
    except Exception as e:
        if console:
            console.print(f"[red]ChromaDB download failed: {e}[/red]")
        return False


def ensure_embedding_model(console: Any = None) -> bool:
    """Ensure the embedding model is installed, downloading if necessary.

    This is the main entry point called by CLI commands. It checks if the
    model is already installed, and if not, automatically downloads it
    from the best available source.

    Args:
        console: Rich console for user-facing output.

    Returns:
        True if model is ready, False if installation failed.
    """
    # Fast path: model already installed
    if is_model_installed():
        return True

    if console:
        console.print()
        console.print("[bold]Initializing embedding model...[/bold]")
        console.print("[dim]One-time download (~80MB) for knowledge retrieval.[/dim]")

    source = choose_download_source()

    if source == "hf-mirror":
        # Set HF_ENDPOINT for huggingface_hub
        if not os.environ.get("HF_ENDPOINT"):
            os.environ["HF_ENDPOINT"] = HF_MIRROR_URL
        if console:
            console.print("[dim]Using HuggingFace mirror for fast download...[/dim]")
        success = _download_via_huggingface(console)
    else:
        if console:
            console.print("[dim]Using default download source...[/dim]")
        success = _download_via_chromadb(console)

    if success and is_model_installed():
        if console:
            console.print("[green]Embedding model ready![/green]")
        return True
    else:
        if console:
            console.print("[red]Embedding model installation failed.[/red]")
            console.print("[yellow]Knowledge retrieval will be unavailable.[/yellow]")
            console.print("[dim]You can retry by running: jirin setup[/dim]")
        return False
