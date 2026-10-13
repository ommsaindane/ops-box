"""
llm/client.py

Universal async LLM client supporting local Ollama and free cloud providers
(e.g., Groq, OpenRouter, Google AI Studio) with automatic 429 rate-limit backoff.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from typing import Any, Dict, List, Optional

import httpx

from orchestrator.orchestrator import LLMClientProtocol, LLMStepResponse, ToolCallRequest

logger = logging.getLogger(__name__)


class UniversalLLMClient(LLMClientProtocol):
    """
    Universal async client for interacting with OpenAI-compatible endpoints.
    Handles rate-limit retries (HTTP 429) and robust parameter parsing.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        timeout_seconds: float = 60.0,
        max_retries: int = 4,
    ) -> None:
        raw_groq_key = os.getenv("GROQ_API_KEY")
        env_groq_key = raw_groq_key.strip() if raw_groq_key else None

        if api_key:
            self.api_key = api_key.strip()
            self.base_url = (base_url or os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1")).strip().rstrip("/")
            self.model_name = (model_name or os.getenv("LLM_MODEL", "qwen/qwen3.8-27b")).strip()
        elif env_groq_key:
            self.api_key = env_groq_key
            self.base_url = (base_url or os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1")).strip().rstrip("/")
            self.model_name = (model_name or os.getenv("LLM_MODEL", "qwen/qwen3.8-27b")).strip()
            logger.info("Using free cloud inference via Groq (%s)", self.model_name)
        else:
            self.api_key = "ollama"
            self.base_url = (
                base_url
                or os.getenv("OLLAMA_BASE_URL")
                or os.getenv("LLM_BASE_URL")
                or "http://localhost:11434/v1"
            ).strip().rstrip("/")
            self.model_name = (model_name or os.getenv("LLM_MODEL", "qwen2.5-coder:7b")).strip()
            logger.info("Defaulting to local Ollama at %s (%s)", self.base_url, self.model_name)

        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries

    async def generate_step(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
    ) -> LLMStepResponse:
        """
        Sends the message history and tool schemas to the model and extracts
        reasoning thoughts and structured tool calls with backoff on rate limits.
        """
        endpoint = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload: Dict[str, Any] = {
            "model": self.model_name,
            "messages": messages,
            "tools": tools,
            "tool_choice": "auto",
            "temperature": 0.1,
        }

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            for attempt in range(self.max_retries):
                try:
                    response = await client.post(endpoint, json=payload, headers=headers)
                    
                    if response.status_code == 429:
                        error_text = response.text
                        wait_seconds = 5.0
                        # Attempt to parse retry duration from error message if available
                        match = re.search(r"try again in ([\d\.]+)s", error_text)
                        if match:
                            wait_seconds = float(match.group(1)) + 0.5

                        logger.warning(
                            "Rate limited (429). Retrying in %.2f seconds (attempt %d/%d)...",
                            wait_seconds, attempt + 1, self.max_retries
                        )
                        await asyncio.sleep(wait_seconds)
                        continue

                    response.raise_for_status()
                    data = response.json()
                    return self._parse_llm_response(data)

                except httpx.ConnectError as exc:
                    if "11434" in self.base_url:
                        raise RuntimeError(
                            f"Failed to connect to local Ollama at {self.base_url}. Ensure Ollama is running (`ollama serve`)."
                        ) from exc
                    raise RuntimeError(f"Connection failed to LLM endpoint at {self.base_url}: {exc}") from exc
                except httpx.HTTPStatusError as exc:
                    error_body = exc.response.text
                    logger.error("LLM Provider returned error %d: %s", exc.response.status_code, error_body)
                    raise RuntimeError(
                        f"LLM API error (Status {exc.response.status_code}): {error_body}"
                    ) from exc

            raise RuntimeError("Rate limit (429) retries exhausted. Please try again in a few moments.")

    def _parse_llm_response(self, data: Dict[str, Any]) -> LLMStepResponse:
        """
        Robustly parses choices, thoughts, and function arguments.
        """
        choices = data.get("choices", [])
        if not choices:
            return LLMStepResponse(thought="No completion choice returned by model.", tool_calls=[])

        message = choices[0].get("message", {})
        raw_content = message.get("content")
        raw_tool_calls = message.get("tool_calls", [])

        parsed_tool_calls: List[ToolCallRequest] = []

        for call in raw_tool_calls:
            call_id = call.get("id", "")
            function_data = call.get("function", {})
            name = function_data.get("name", "")
            raw_args = function_data.get("arguments", {})

            if isinstance(raw_args, str):
                try:
                    arguments = json.loads(raw_args)
                except json.JSONDecodeError:
                    logger.warning("Failed to decode JSON arguments for tool %s: %s", name, raw_args)
                    arguments = {"raw_input": raw_args}
            elif isinstance(raw_args, dict):
                arguments = raw_args
            else:
                arguments = {}

            parsed_tool_calls.append(
                ToolCallRequest(
                    name=name,
                    arguments=arguments,
                    call_id=call_id,
                )
            )

        return LLMStepResponse(
            thought=raw_content,
            tool_calls=parsed_tool_calls,
            raw_content=raw_content,
        )