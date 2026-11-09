import time
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Literal, Protocol, TypedDict

import httpx

from triage.schemas import Triage

DEFAULT_REPLY = Triage(
    topic="other",
    urgency="low",
    needs_human=False,
    explanation="Fake provider: no model was called.",
).model_dump_json()


class Message(TypedDict):
    role: Literal["system", "user", "assistant"]
    content: str


@dataclass(frozen=True)
class LLMResponse:
    text: str
    model: str
    input_tokens: int
    output_tokens: int
    latency_ms: float


class LLMError(Exception):
    """The model could not be reached or returned an error."""


class LLMClient(Protocol):
    model: str

    def chat(
        self,
        messages: Sequence[Message],
        *,
        schema: dict[str, Any] | None = None,
        temperature: float = 0.0,
    ) -> LLMResponse: ...


class OllamaClient:
    def __init__(
        self,
        model: str,
        base_url: str = "http://localhost:11434",
        timeout: float = 120.0,
        http: httpx.Client | None = None,
    ) -> None:
        self.model = model
        self._http = http or httpx.Client(base_url=base_url, timeout=timeout)

    def chat(
        self,
        messages: Sequence[Message],
        *,
        schema: dict[str, Any] | None = None,
        temperature: float = 0.0,
    ) -> LLMResponse:
        body: dict[str, Any] = {
            "model": self.model,
            "messages": list(messages),
            "stream": False,
            "options": {"temperature": temperature},
        }
        if schema is not None:
            body["format"] = schema

        start = time.perf_counter()
        try:
            response = self._http.post("/api/chat", json=body)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise LLMError(f"ollama request failed: {exc}") from exc
        latency_ms = (time.perf_counter() - start) * 1000

        data = response.json()
        return LLMResponse(
            text=data["message"]["content"],
            model=data.get("model", self.model),
            input_tokens=data.get("prompt_eval_count", 0),
            output_tokens=data.get("eval_count", 0),
            latency_ms=latency_ms,
        )


class FakeClient:
    def __init__(self, replies: Sequence[str | Exception] | None = None) -> None:
        self.model = "fake"
        self.calls: list[list[Message]] = []
        self._replies = None if replies is None else list(replies)

    def chat(
        self,
        messages: Sequence[Message],
        *,
        schema: dict[str, Any] | None = None,
        temperature: float = 0.0,
    ) -> LLMResponse:
        self.calls.append(messages)
        if self._replies is None:
            reply: str | Exception = DEFAULT_REPLY
        elif not self._replies:
            raise AssertionError("FakeClient ran out of replies")
        else:
            reply = self._replies.pop(0)

        if isinstance(reply, Exception):
            raise reply
        return LLMResponse(
            text=reply, model=self.model, input_tokens=100, output_tokens=20, latency_ms=1.0
        )


def make_client(provider: str, model: str, base_url: str) -> LLMClient:
    if provider == "ollama":
        return OllamaClient(model=model, base_url=base_url)
    if provider == "fake":
        return FakeClient()
    raise ValueError(f"unknown provider: {provider!r}")
