"""Chat model with tool calling (Groq). Agents depend on this small interface so tests can replace it."""

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Protocol

from groq import Groq

from ...config import settings
from ..errors import ConfigurationError

logger = logging.getLogger(__name__)


@dataclass
class ToolCall:
    """A tool the model asks to run."""

    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class LLMReply:
    """One answer of the model: text and/or tool calls, plus the token usage."""

    content: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    usage: dict[str, int] = field(default_factory=dict)


class LLM(Protocol):
    """What an agent needs from a chat model."""

    model: str

    def complete(self, messages: list[dict], tools: list[dict] | None = None) -> LLMReply:
        """Return the model's answer to `messages`, optionally allowing it to call `tools`."""
        ...


class AgentLLM:
    """Groq chat completions."""

    def __init__(self, api_key: str):
        cfg = settings.agents
        self.model = cfg.model
        self._client = Groq(api_key=api_key, timeout=cfg.timeout_seconds, max_retries=cfg.max_retries)

    def complete(self, messages: list[dict], tools: list[dict] | None = None) -> LLMReply:
        """Call Groq and convert its answer to an LLMReply."""
        options: dict[str, Any] = {"temperature": settings.agents.temperature}
        if tools:
            options.update(tools=tools, tool_choice="auto")
        response = self._client.chat.completions.create(model=self.model, messages=messages, **options)
        message = response.choices[0].message
        calls = []
        for call in message.tool_calls or []:
            try:
                arguments = json.loads(call.function.arguments or "{}")
            except json.JSONDecodeError:
                arguments = {}
            calls.append(ToolCall(id=call.id, name=call.function.name, arguments=arguments))
        usage = response.usage
        return LLMReply(
            content=message.content,
            tool_calls=calls,
            usage={"prompt_tokens": usage.prompt_tokens, "completion_tokens": usage.completion_tokens} if usage else {},
        )


def is_configured() -> bool:
    """Return True when the Groq key is set."""
    return bool(settings.agents.api_key)


def get_llm() -> LLM:
    """Return the chat model, or raise ConfigurationError when the Groq key is missing."""
    if not is_configured():
        raise ConfigurationError("Falta la clave de API para el LLM de los agentes (AGENTS_API_KEY)")
    return AgentLLM(settings.agents.api_key)
