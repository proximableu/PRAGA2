"""SSE generator handling Open-WebUI telemetry formatting and token streaming."""

import json
from typing import Any, AsyncGenerator, Dict, List

import httpx
from config import settings


class StreamingFormatter:
    """Formats agent reasoning, retrieval telemetry, and LLM tokens into valid SSE chunks."""

    def __init__(self) -> None:
        self.http_client = httpx.AsyncClient(
            timeout=120.0, base_url=settings.OLLAMA_URL
        )

    async def yield_thinking(
        self,
        thought: str,
        queries: List[str],
        buffer_preview: List[Dict[str, Any]],
    ) -> AsyncGenerator[str, None]:
        """Yields internal agent reasoning wrapped in <think> tags for Open-WebUI accordions."""
        telemetry = (
            f"<think>\n"
            f"Agent Thought: {thought}\n"
            f"Expanded Queries: {queries}\n"
            f"Buffer Preview: {len(buffer_preview)} candidates loaded.\n"
            f"</think>\n\n"
        )
        yield self._format_sse(telemetry)

    async def generate_final_response(
        self,
        user_query: str,
        selected_contexts: List[Dict[str, Any]],
        model: str,
    ) -> AsyncGenerator[str, None]:
        """Assembles final prompt with 3-category structure and streams tokens via SSE."""
        context_block = "\n\n---\n\n".join(
            [
                f"### Source {i + 1}\n{c.get('text', '')}"
                for i, c in enumerate(selected_contexts)
            ]
        )

        # Enforce strict 3-category Markdown structure for response generation
        final_prompt = (
            "You are an expert AI assistant. Answer the user's query using ONLY the provided context.\n"
            "Structure your response strictly into these three categories if applicable:\n"
            "1. Direct Answer (Explicitly stated in context)\n"
            "2. Inferred Answer (Logically derived from context)\n"
            "3. Internal Knowledge (General knowledge supplementing context, clearly marked)\n\n"
            f"Context Information:\n{context_block}\n\n"
            f"User Question: {user_query}"
        )

        # Stream raw tokens aggregated into OpenAI-compatible delta chunks
        async for token in self._stream_ollama_tokens(final_prompt, model):
            yield self._format_sse(token)

        # Append collapsible audit footer with execution telemetry
        audit = (
            f"\n\n<details>\n"
            f"<summary>Execution Telemetry</summary>\n"
            f"- Model: {model}\n"
            f"- Context Sources: {len(selected_contexts)}\n"
            f"- Database: Dynamic RAG Cluster\n"
            f"</details>"
        )
        yield self._format_sse(audit)
        yield "data: [DONE]\n\n"

    async def _stream_ollama_tokens(
        self, prompt: str, model: str
    ) -> AsyncGenerator[str, None]:
        """Non-blocking token streaming from Ollama API."""
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": True,
            "options": {
                "num_ctx": getattr(settings, "AGENT_NUM_CTX", 4096)
            },
        }

        async with self.http_client.stream(
            "POST", "/api/generate", json=payload
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line or not line.strip():
                    continue

                # Strip 'data:' prefix if present (SSE), otherwise use raw line (NDJSON)
                clean_line = (
                    line[5:].strip() if line.startswith("data:") else line.strip()
                )

                try:
                    data = json.loads(clean_line)
                    if "response" in data and data["response"]:
                        yield data["response"]
                except json.JSONDecodeError:
                    continue

    def _format_sse(self, content: str) -> str:
        """Wraps content in standard OpenAI SSE delta format."""
        payload = {"choices": [{"delta": {"content": content}}]}
        return f"data: {json.dumps(payload)}\n\n"