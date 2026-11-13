"""A scripted chat model for the agent tests: no network, fully predictable."""

from crm.services.agents.llm import LLMReply, ToolCall


def call(tool: str, **arguments) -> LLMReply:
    """Return a reply in which the model asks for one tool."""
    return LLMReply(tool_calls=[ToolCall(id=f"call-{tool}", name=tool, arguments=arguments)])


def say(text: str) -> LLMReply:
    """Return a final reply with only text."""
    return LLMReply(content=text)


class ScriptedLLM:
    """Answers with the given replies in order; an Exception in the list is raised instead."""

    model = "scripted-model"

    def __init__(self, *replies):
        self.replies = list(replies)
        self.calls: list[list[dict]] = []

    def complete(self, messages, tools=None):
        """Return the next scripted reply and remember what the agent sent."""
        self.calls.append(list(messages))
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply
