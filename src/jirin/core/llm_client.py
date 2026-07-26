"""Unified LLM client with retry, timeout, and fallback.

Uses httpx to call OpenAI-compatible APIs directly with:
- Exponential backoff retry (configurable max retries)
- Timeout control
- Structured error fallback instead of crash

Supports all OpenAI-compatible providers: OpenAI, DeepSeek, Qwen, Kimi, Ollama, etc.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# Default API base URLs for common providers
PROVIDER_DEFAULTS: dict[str, str] = {
    "openai": "https://api.openai.com/v1",
    "ollama": "http://localhost:11434/v1",
    "deepseek": "https://api.deepseek.com/v1",
    "qwen": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "kimi": "https://api.moonshot.cn/v1",
}


@dataclass
class LLMResponse:
    """Structured LLM response."""

    content: str = ""
    model: str = ""
    usage: dict[str, int] = field(default_factory=dict)
    error: str = ""
    success: bool = True


class LLMClient:
    """Unified LLM client with retry and error handling.

    Calls OpenAI-compatible APIs directly via httpx.
    Supports: OpenAI, DeepSeek, Qwen, Kimi, Ollama, and any OpenAI-compatible endpoint.

    Usage:
        client = LLMClient(llm_config)
        response = await client.complete(messages=[...])
        if response.success:
            text = response.content
        else:
            error = response.error
    """

    def __init__(
        self,
        llm_config: dict[str, Any],
        max_retries: int = 3,
        timeout: float | None = None,
    ) -> None:
        self.provider = llm_config.get("provider", "openai")
        self.model = llm_config.get("model", "gpt-4o")
        self.api_key = llm_config.get("api_key", "")
        self.api_base = self._resolve_api_base(llm_config)
        self.temperature = llm_config.get("temperature", 0.1)
        self.max_tokens = llm_config.get("max_tokens", 4096)
        self.max_retries = max_retries
        # Use provided timeout, or config value, or default (120s)
        self.timeout = timeout if timeout is not None else llm_config.get("timeout", 120.0)

    def _resolve_api_base(self, llm_config: dict[str, Any]) -> str:
        """Resolve the API base URL from config or provider defaults."""
        # If user explicitly configured api_base, use it
        configured_base = llm_config.get("api_base", "")
        if configured_base:
            return configured_base.rstrip("/")

        # Fall back to provider default
        provider = self.provider.lower()
        if provider in PROVIDER_DEFAULTS:
            return PROVIDER_DEFAULTS[provider]

        # Unknown provider: assume OpenAI-compatible with provider name as hint
        return PROVIDER_DEFAULTS.get("openai", "https://api.openai.com/v1")

    @property
    def _completions_url(self) -> str:
        """Get the chat completions endpoint URL."""
        base = self.api_base
        # If already contains /chat/completions, return as-is
        if "/chat/completions" in base:
            return base
        # Ensure the URL ends with /v1 or similar, then append /chat/completions
        if base.endswith("/v1"):
            return f"{base}/chat/completions"
        return f"{base}/v1/chat/completions"

    @property
    def _headers(self) -> dict[str, str]:
        """Get request headers."""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def complete(
        self,
        messages: list[dict[str, str]],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        """Send completion request with retry logic.

        Args:
            messages: Chat messages list.
            temperature: Override temperature.
            max_tokens: Override max tokens.

        Returns:
            LLMResponse with content or error.
        """
        temp = temperature if temperature is not None else self.temperature
        tokens = max_tokens if max_tokens is not None else self.max_tokens

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temp,
            "max_tokens": tokens,
        }

        last_error = ""
        for attempt in range(1, self.max_retries + 1):
            try:
                logger.debug(
                    "LLM call attempt %d/%d, model=%s, url=%s",
                    attempt, self.max_retries, self.model, self._completions_url,
                )

                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(
                        self._completions_url,
                        json=payload,
                        headers=self._headers,
                    )

                if response.status_code != 200:
                    error_body = response.text[:500]
                    last_error = f"HTTP {response.status_code}: {error_body}"
                    logger.warning(last_error)
                    # Don't retry on 4xx client errors (except 429 rate limit)
                    if 400 <= response.status_code < 500 and response.status_code != 429:
                        break
                else:
                    data = response.json()
                    message = data.get("choices", [{}])[0].get("message", {})
                    # For reasoning models (like kimi-k2.6, o1), content might be empty
                    # and the actual response is in reasoning_content
                    content = message.get("content", "")
                    reasoning = message.get("reasoning_content", "")
                    # Use reasoning_content if content is empty
                    if not content and reasoning:
                        content = reasoning
                    usage_data = data.get("usage", {})
                    usage = {
                        "prompt_tokens": usage_data.get("prompt_tokens", 0),
                        "completion_tokens": usage_data.get("completion_tokens", 0),
                    }

                    logger.info(
                        "LLM call success, tokens: prompt=%s completion=%s",
                        usage.get("prompt_tokens", "?"),
                        usage.get("completion_tokens", "?"),
                    )

                    return LLMResponse(
                        content=content,
                        model=self.model,
                        usage=usage,
                        success=True,
                    )

            except httpx.TimeoutException:
                last_error = f"LLM call timed out after {self.timeout}s (attempt {attempt})"
                logger.warning(last_error)
            except httpx.HTTPError as e:
                last_error = f"LLM call failed: {type(e).__name__}: {e} (attempt {attempt})"
                logger.warning(last_error)
            except Exception as e:
                last_error = f"LLM call failed: {type(e).__name__}: {e} (attempt {attempt})"
                logger.warning(last_error)

            # Exponential backoff before retry
            if attempt < self.max_retries:
                wait_time = 2 ** attempt
                logger.debug("Retrying in %ds...", wait_time)
                await asyncio.sleep(wait_time)

        # All retries exhausted
        logger.error("LLM call failed after %d attempts: %s", self.max_retries, last_error)
        return LLMResponse(
            content="",
            model=self.model,
            error=last_error,
            success=False,
        )
