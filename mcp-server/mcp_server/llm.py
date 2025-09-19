"""LLM provider abstractions for the MCP server.

This module centralises provider-specific logic behind a Strategy interface so
that the rest of the codebase can remain agnostic to concrete LLM vendors.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
import json
import os
from typing import Any, Dict, Iterable, Mapping, Optional

import httpx


Message = Dict[str, str]


class LLMError(Exception):
    """Raised when an LLM invocation fails or is misconfigured."""


class LLMProvider(ABC):
    """Strategy interface for invoking chat-completion style providers."""

    def __init__(self, *, timeout: float = 30.0) -> None:
        self._timeout = timeout

    @abstractmethod
    async def chat(self, messages: Iterable[Message], *, model: Optional[str] = None) -> str:
        """Perform a chat completion and return the provider's textual reply."""

    def _client(self) -> httpx.AsyncClient:
        """Factory for a configured HTTP client."""

        return httpx.AsyncClient(timeout=self._timeout)


@dataclass(frozen=True)
class OpenAISettings:
    api_key: str
    default_model: str


class OpenAIProvider(LLMProvider):
    def __init__(self, settings: OpenAISettings) -> None:
        super().__init__()
        self._settings = settings

    async def chat(self, messages: Iterable[Message], *, model: Optional[str] = None) -> str:
        payload_messages = list(messages)
        chosen_model = model or self._settings.default_model
        async with self._client() as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {self._settings.api_key}"},
                json={"model": chosen_model, "messages": payload_messages},
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip()


@dataclass(frozen=True)
class AnthropicSettings:
    api_key: str
    default_model: str


class AnthropicProvider(LLMProvider):
    def __init__(self, settings: AnthropicSettings) -> None:
        super().__init__()
        self._settings = settings

    async def chat(self, messages: Iterable[Message], *, model: Optional[str] = None) -> str:
        payload_messages = list(messages)
        chosen_model = model or self._settings.default_model
        system_text = "\n".join(m["content"] for m in payload_messages if m.get("role") == "system")
        content = []
        for message in payload_messages:
            role = message.get("role")
            if role == "user":
                content.append({"role": "user", "content": message.get("content")})
            elif role == "assistant":
                content.append({"role": "assistant", "content": message.get("content")})

        async with self._client() as client:
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self._settings.api_key,
                    "anthropic-version": "2023-06-01",
                },
                json={
                    "model": chosen_model,
                    "system": system_text or None,
                    "messages": content,
                    "max_tokens": 1024,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return "".join(block.get("text", "") for block in data.get("content", [])).strip()


@dataclass(frozen=True)
class OpenRouterSettings:
    api_key: str
    default_model: str


class OpenRouterProvider(LLMProvider):
    def __init__(self, settings: OpenRouterSettings) -> None:
        super().__init__()
        self._settings = settings

    async def chat(self, messages: Iterable[Message], *, model: Optional[str] = None) -> str:
        payload_messages = list(messages)
        chosen_model = model or self._settings.default_model
        async with self._client() as client:
            resp = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {self._settings.api_key}"},
                json={"model": chosen_model, "messages": payload_messages},
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip()


@dataclass(frozen=True)
class OllamaSettings:
    endpoint: str
    default_model: str
    options_json: Optional[str] = None


class OllamaProvider(LLMProvider):
    def __init__(self, settings: OllamaSettings) -> None:
        super().__init__()
        self._settings = settings

    async def chat(self, messages: Iterable[Message], *, model: Optional[str] = None) -> str:
        payload_messages = list(messages)
        chosen_model = model or self._settings.default_model
        payload: Dict[str, Any] = {
            "model": chosen_model,
            "messages": payload_messages,
            "stream": False,
        }
        if self._settings.options_json:
            try:
                payload["options"] = json.loads(self._settings.options_json)
            except json.JSONDecodeError:
                pass
        async with self._client() as client:
            resp = await client.post(f"{self._settings.endpoint}/api/chat", json=payload)
            resp.raise_for_status()
            data = resp.json()
            message = data.get("message", {}).get("content")
            if not message:
                raise LLMError("Ollama response missing message content")
            return message.strip()


@dataclass(frozen=True)
class AzureOpenAISettings:
    api_key: str
    endpoint: str
    deployment: str
    api_version: str


class AzureOpenAIProvider(LLMProvider):
    def __init__(self, settings: AzureOpenAISettings) -> None:
        super().__init__()
        self._settings = settings

    async def chat(self, messages: Iterable[Message], *, model: Optional[str] = None) -> str:  # noqa: D401
        del model  # Azure deployments are tied to a single model variant.
        payload_messages = list(messages)
        url = (
            f"{self._settings.endpoint}/openai/deployments/{self._settings.deployment}/"
            f"chat/completions?api-version={self._settings.api_version}"
        )
        async with self._client() as client:
            resp = await client.post(
                url,
                headers={"api-key": self._settings.api_key},
                json={"messages": payload_messages},
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip()


def _require(env: Mapping[str, str], key: str) -> str:
    value = env.get(key)
    if not value:
        raise LLMError(f"Environment variable {key} must be set for this provider")
    return value


def create_provider(environment: Optional[Mapping[str, str]] = None) -> LLMProvider:
    """Factory that builds a provider based on environment configuration."""

    env = dict(environment or os.environ)
    provider_name = env.get("LLM_PROVIDER", "openai").lower()

    if provider_name == "openai":
        api_key = _require(env, "OPENAI_API_KEY")
        default_model = env.get("LLM_MODEL", "gpt-4o-mini")
        return OpenAIProvider(OpenAISettings(api_key=api_key, default_model=default_model))

    if provider_name == "anthropic":
        api_key = _require(env, "ANTHROPIC_API_KEY")
        default_model = env.get("LLM_MODEL", "claude-3-5-sonnet-20240620")
        return AnthropicProvider(AnthropicSettings(api_key=api_key, default_model=default_model))

    if provider_name == "openrouter":
        api_key = _require(env, "OPENROUTER_API_KEY")
        default_model = env.get("LLM_MODEL", "openrouter/auto")
        return OpenRouterProvider(OpenRouterSettings(api_key=api_key, default_model=default_model))

    if provider_name == "ollama":
        endpoint = env.get("OLLAMA_ENDPOINT", "http://localhost:11434").rstrip("/")
        default_model = env.get("OLLAMA_MODEL", env.get("LLM_MODEL", "llama3"))
        options_json = env.get("OLLAMA_OPTIONS")
        return OllamaProvider(OllamaSettings(endpoint=endpoint, default_model=default_model, options_json=options_json))

    if provider_name == "azure_openai":
        api_key = _require(env, "AZURE_OPENAI_API_KEY")
        endpoint = _require(env, "AZURE_OPENAI_ENDPOINT")
        deployment = _require(env, "AZURE_OPENAI_DEPLOYMENT")
        api_version = env.get("AZURE_OPENAI_API_VERSION", "2024-05-01-preview")
        return AzureOpenAIProvider(
            AzureOpenAISettings(
                api_key=api_key,
                endpoint=endpoint,
                deployment=deployment,
                api_version=api_version,
            )
        )

    raise LLMError(f"Unsupported LLM_PROVIDER: {provider_name}")
