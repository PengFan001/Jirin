"""Unified LLM client with retry, timeout, and fallback.

Wraps litellm.completion with:
- Exponential backoff retry (configurable max retries)
- Timeout control
- Structured error fallback instead of crash
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

import litellm

logger = logging.getLogger(__name__)


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
        timeout: float = 60.0,
    ) -> None:
        self.provider = llm_config.get("provider", "openai")
        self.model = llm_config.get("model", "gpt-4o")
        self.api_key = llm_config.get("api_key", "")
        self.api_base = llm_config.get("api_base", "")
        self.temperature = llm_config.get("temperature", 0.1)
        self.max_tokens = llm_config.get("max_tokens", 4096)
        self.max_retries = max_retries
        self.timeout = timeout
        self._full_model = f"{self.provider}/{self.model}"

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

        last_error = ""
        for attempt in range(1, self.max_retries + 1):
            try:
                logger.debug(
                    "LLM call attempt %d/%d, model=%s",
                    attempt, self.max_retries, self._full_model,
                )

                response = await asyncio.wait_for(
                    asyncio.to_thread(
                        litellm.completion,
                        model=self._full_model,
                        messages=messages,
                        temperature=temp,
                        max_tokens=tokens,
                        api_key=self.api_key or None,
                        api_base=self.api_base or None,
                    ),
                    timeout=self.timeout,
                )

                content = response.choices[0].message.content or ""
                usage = {}
                if hasattr(response, "usage"):
                    usage = {
                        "prompt_tokens": getattr(response.usage, "prompt_tokens", 0),
                        "completion_tokens": getattr(response.usage, "completion_tokens", 0),
                    }

                logger.info(
                    "LLM call success, tokens: prompt=%s completion=%s",
                    usage.get("prompt_tokens", "?"),
                    usage.get("completion_tokens", "?"),
                )

                return LLMResponse(
                    content=content,
                    model=self._full_model,
                    usage=usage,
                    success=True,
                )

            except asyncio.TimeoutError:
                last_error = f"LLM call timed out after {self.timeout}s (attempt {attempt})"
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
            model=self._full_model,
            error=last_error,
            success=False,
        )

    def complete_sync(
        self,
        messages: list[dict[str, str]],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        """Synchronous wrapper for complete().

        Args:
            messages: Chat messages list.
            temperature: Override temperature.
            max_tokens: Override max tokens.

        Returns:
            LLMResponse with content or error.
        """
        return asyncio.run(self.complete(messages, temperature, max_tokens))
