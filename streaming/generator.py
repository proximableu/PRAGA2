"""Async SSE generator handling OpenAI-compatible token streaming and telemetry formatting."""

import json
import time
from typing import Any, AsyncGenerator, Dict, List

import httpx
from config import settings


class StreamingGenerator:
    """Formats agentic reasoning, LLM tokens, and audit footers into valid OpenAI SSE chunks."""

    def __init__(self) -> None:
        self.http_client = httpx.AsyncClient(
            timeout=120.0, base_url=settings.OLLAMA_URL
        )

    async def generate_stream(
        self,
        payload: Dict[str, Any],
        agent_thoughts: List[Dict[str, Any]],
        final_prompt: str,
        target_model: str,
    ) -> AsyncGenerator[str, None]:
        """Core async generator yielding OpenAI-compatible SSE chunks.

        Handles telemetry blocks, token streaming, and graceful error termination.
        """
        request_id = f"chatcmpl-{int(time.time())}"
        created_at = int(time.time())

        try:
            # 1. Yield Reasoning Telemetry if enabled
            if (
                getattr(settings, "ENABLE_REASONING_TELEMETRY", True)
                and agent_thoughts
            ):
                for thought_data in agent_thoughts:
                    telemetry_content = self._format_reasoning_block(
                        thought_data
                    )
                    yield self._build_sse_chunk(
                        request_id, created_at, target_model, telemetry_content
                    )

            # 2. Stream Final LLM Response Tokens
            async for token in self._stream_ollama_tokens(
                final_prompt, target_model
            ):
                yield self._build_sse_chunk(
                    request_id, created_at, target_model, token
                )

            # 3. Yield Audit Footer if enabled
            if getattr(settings, "ENABLE_AUDIT_FOOTER", True):
                audit_content = payload.get("audit_footer", "")
                if audit_content:
                    yield self._build_sse_chunk(
                        request_id, created_at, target_model, audit_content
                    )

            # 4. Terminate Stream
            yield self._build_sse_chunk(
                request_id, created_at, target_model, "", finish_reason="stop"
            )
            yield "data: [DONE]\n\n"

        except httpx.HTTPStatusError as e:
            error_msg = f"⚠️ LLM Streaming Error (HTTP {e.response.status_code}): {e.response.text}"
            yield self._build_sse_chunk(
                request_id,
                created_at,
                target_model,
                error_msg,
                finish_reason="error",
            )
        except Exception as e:
            error_msg = f"⚠️ Internal Generator Error: {str(e)}"
            yield self._build_sse_chunk(
                request_id,
                created_at,
                target_model,
                error_msg,
                finish_reason="error",
            )

    def _build_sse_chunk(
        self,
        req_id: str,
        created: int,
        model: str,
        content: str,
        finish_reason: str = None,
    ) -> str:
        """Constructs a strictly OpenAI-compatible delta chunk."""
        payload = {
            "id": req_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "delta": {"content": content},
                    "finish_reason": finish_reason,
                }
            ],
        }
        return f"data: {json.dumps(payload)}\n\n"

    def _format_reasoning_block(self, data: Dict[str, Any]) -> str:
        """Wraps agent thoughts and query expansions in <think> tags for Open-WebUI accordion rendering."""
        thought = data.get("thought", "Analyzing context...")
        queries = ", ".join(data.get("queries", []))
        preview_count = len(data.get("buffer_preview", []))

        return (
            f"<think>\n"
            f"Agent Thought: {thought}\n"
            f"Expanded Queries: {queries}\n"
            f"Candidates Loaded: {preview_count}\n"
            f"</think>\n\n"
        )

    async def _stream_ollama_tokens(
        self, prompt: str, model: str
    ) -> AsyncGenerator[str, None]:
        """Non-blocking token streaming from Ollama generation endpoint."""
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": True,
            "options": {
                "temperature": getattr(
                    settings, "FINAL_PROMPT_TEMPERATURE", 0.7
                ),
                "num_ctx": getattr(settings, "FINAL_PROMPT_NUM_CTX", 4096),
            },
        }

        async with self.http_client.stream(
            "POST", "/api/generate", json=payload
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line or not line.strip():
                    continue

                clean_line = (
                    line[5:].strip() if line.startswith("data:") else line.strip()
                )

                try:
                    data = json.loads(clean_line)
                    if "response" in data and data["response"]:
                        yield data["response"]
                except json.JSONDecodeError:
                    continue