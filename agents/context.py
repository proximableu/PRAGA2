"""History synthesis, rolling window management, and multi-angle query expansion."""
import json
from typing import List, Dict, Any, Optional
import httpx
from config import settings


class ContextSynthesizer:
    """Manages conversation history compression and semantic query expansion."""

    def __init__(self) -> None:
        self.http_client = httpx.AsyncClient(timeout=60.0, base_url=settings.OLLAMA_URL)

    async def synthesize_history(self, messages: List[Dict[str, str]]) -> str:
        """
        Applies a rolling window strategy to conversation history.
        Summarizes older turns using the lightweight LLM while preserving recent context verbatim.
        """
        recent_turns = messages[-settings.HISTORY_WINDOW_TURNS:]
        older_turns = messages[:-settings.HISTORY_WINDOW_TURNS]

        summary = ""
        if older_turns:
            summary = await self._summarize_turns(older_turns)

        # Assemble synthesized query context
        recent_context = "\n".join([f"{m['role']}: {m['content']}" for m in recent_turns])
        latest_prompt = messages[-1]["content"] if messages else ""

        return f"""[Historical Summary]
{summary}

[Recent Context]
{recent_context}

[Current Query]
{latest_prompt}"""

    async def _summarize_turns(self, turns: List[Dict[str, str]]) -> str:
        """Compresses historical conversation turns into a concise summary."""
        prompt = "Summarize the following conversation history concisely:\n" + \
                 "\n".join([f"{m['role']}: {m['content']}" for m in turns])

        response = await self._call_llm(prompt, settings.LIGHTWEIGHT_LLM_MODEL)
        return response if response else "No historical context available."

    async def expand_query(self, synthesized_query: str) -> List[str]:
        """Generates NUM_SUB_QUERIES distinct semantic reformulations of the input query."""
        prompt = f"""Generate exactly {settings.NUM_SUB_QUERIES} distinct search queries to find relevant information for this request. 
Return ONLY a valid JSON array of strings. No markdown, no explanations.
Request: {synthesized_query}"""

        response = await self._call_llm(prompt, settings.LIGHTWEIGHT_LLM_MODEL)

        try:
            # Strict JSON parsing with deterministic fallback
            queries = json.loads(response)
            if isinstance(queries, list) and len(queries) > 0:
                return [str(q) for q in queries]
        except (json.JSONDecodeError, TypeError):
            pass

        # Fallback: duplicate original query to ensure pipeline continuity
        base_query = synthesized_query.split("[Current Query]\n")[-1].strip()
        return [base_query] * settings.NUM_SUB_QUERIES

    async def _call_llm(self, prompt: str, model: str) -> str:
        """Non-blocking Ollama chat completion."""
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "options": {"num_ctx": settings.AGENT_NUM_CTX}
        }
        resp = await self.http_client.post("/api/chat", json=payload)
        resp.raise_for_status()
        return resp.json().get("message", {}).get("content", "")