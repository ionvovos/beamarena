"""Beam Client Module.

Handles API communication with Reflection AI (Beam-1.0-501B-A23B).
Supports streaming, reasoning trace extraction, and structured token telemetry.
"""

from dataclasses import dataclass, field
import json
import os
import ssl
from typing import Any, Callable, Dict, Iterator, List, Optional
import urllib.request


@dataclass
class TokenUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    reasoning_tokens: int = 0
    total_tokens: int = 0


@dataclass
class StreamChunk:
    reasoning_chunk: str = ""
    content_chunk: str = ""
    finish_reason: Optional[str] = None
    usage: Optional[TokenUsage] = None


@dataclass
class BeamResponse:
    content: str = ""
    reasoning: str = ""
    usage: TokenUsage = field(default_factory=TokenUsage)
    raw: Dict[str, Any] = field(default_factory=dict)


class BeamClient:
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: str = "Beam-1.0-501B-A23B",
    ):
        self.api_key = api_key or os.environ.get("REFLECTION_API_KEY", "")
        self.base_url = (
            base_url
            or os.environ.get("REFLECTION_BASE_URL", "https://api.reflection.ai/openai/v1")
        ).rstrip("/")
        self.model = model or os.environ.get("MODEL_NAME", "Beam-1.0-501B-A23B")

        if not self.api_key:
            # Fallback to local .env check
            env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
            if os.path.exists(env_path):
                with open(env_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("REFLECTION_API_KEY="):
                            self.api_key = line.split("=", 1)[1].strip().strip('"').strip("'")
                            break

        if not self.api_key:
            raise ValueError("REFLECTION_API_KEY is missing. Check your .env file or environment.")

    def _get_ssl_context(self) -> ssl.SSLContext:
        try:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            return ctx
        except Exception:
            return ssl._create_unverified_context()

    def chat_complete(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        top_p: float = 0.95,
        max_tokens: int = 16000,
        reasoning_effort: str = "max",
    ) -> BeamResponse:
        """Non-streaming convenience wrapper that consumes stream_chat to bypass Beta API non-streaming truncation."""
        return self.stream_chat(
            messages=messages,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
        )

    def stream_chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        top_p: float = 0.95,
        max_tokens: int = 4096,
        on_reasoning: Optional[Callable[[str], None]] = None,
        on_content: Optional[Callable[[str], None]] = None,
    ) -> BeamResponse:
        """Streams tokens from Beam, calling callbacks for reasoning and content chunks."""
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "top_p": top_p,
            "max_tokens": max_tokens,
            "stream": True,
        }

        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            data=json.dumps(payload).encode("utf-8"),
        )

        ctx = self._get_ssl_context()
        try:
            resp = urllib.request.urlopen(req, context=ctx)
        except urllib.error.URLError:
            ctx_unverified = ssl._create_unverified_context()
            resp = urllib.request.urlopen(req, context=ctx_unverified)

        full_reasoning: List[str] = []
        full_content: List[str] = []
        usage = TokenUsage()

        with resp:
            for raw_line in resp:
                line = raw_line.decode("utf-8").strip()
                if not line or not line.startswith("data:"):
                    continue
                data_str = line[5:].strip()
                if data_str == "[DONE]":
                    break

                try:
                    chunk_json = json.loads(data_str)
                except Exception:
                    continue

                if "usage" in chunk_json and chunk_json["usage"]:
                    u = chunk_json["usage"]
                    usage.prompt_tokens = u.get("prompt_tokens", 0)
                    usage.completion_tokens = u.get("completion_tokens", 0)
                    usage.total_tokens = u.get("total_tokens", 0)
                    if "completion_tokens_details" in u:
                        usage.reasoning_tokens = u["completion_tokens_details"].get(
                            "reasoning_tokens", 0
                        )

                choices = chunk_json.get("choices")
                if not choices:
                    continue

                delta = choices[0].get("delta", {})

                # Check reasoning delta
                if "reasoning_content" in delta and delta["reasoning_content"]:
                    r_text = delta["reasoning_content"]
                    full_reasoning.append(r_text)
                    if on_reasoning:
                        on_reasoning(r_text)

                # Check content delta
                if "content" in delta and delta["content"]:
                    c_text = delta["content"]
                    full_content.append(c_text)
                    if on_content:
                        on_content(c_text)

        return BeamResponse(
            content="".join(full_content),
            reasoning="".join(full_reasoning),
            usage=usage,
        )
