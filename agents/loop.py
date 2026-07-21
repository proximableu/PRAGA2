"""Asynchronous ReAct loop orchestrator with persistent buffer management."""
import json
from typing import List, Dict, Any, Optional, AsyncGenerator
from pydantic import BaseModel, Field
from enum import Enum
import httpx
from config import settings


class Action(str, Enum):
    VECTOR_SEARCH = "vector_search"
    FINAL_ANSWER = "final_answer"


class AgentAction(BaseModel):
    thought: str = Field(description="Reasoning on context quality and required next steps.")
    action: Action = Field(description="Action to perform: reformulate search or conclude retrieval.")
    search_queries: Optional[List[str]] = Field(default=None, description="Reformulated queries if searching.")
    selected_indices: Optional[List[int]] = Field(default=None,
                                                  description="Indices from buffer to use for final answer.")


class ReActLoop:
    """Stateful execution loop managing accumulation buffers and agent decision cycles."""

    def __init__(self) -> None:
        self.http_client = httpx.AsyncClient(timeout=60.0, base_url=settings.OLLAMA_URL)
        self.accumulated_buffer: List[Dict[str, Any]] = []

    async def run_loop(
            self,
            session,
            retriever,
            synthesizer,
            initial_query: str,
            stream_gen: AsyncGenerator
    ) -> List[Dict[str, Any]]:
        """Orchestrates the agentic retrieval cycle up to AGENT_MAX_TURNS."""
        synthesized_ctx = await synthesizer.synthesize_history([{"role": "user", "content": initial_query}])

        for turn in range(settings.AGENT_MAX_TURNS):
            # 1. Expand queries & retrieve candidates
            sub_queries = await synthesizer.expand_query(synthesized_ctx)
            new_candidates = await retriever.execute_hybrid_search(session, sub_queries)

            # 2. Merge into persistent buffer with hard ceiling enforcement
            self._update_buffer(new_candidates)

            # 3. Stream telemetry for Open-WebUI collapsible accordions
            await stream_gen.yield_thinking(
                thought=f"Turn {turn + 1}: Expanded to {len(sub_queries)} angles. Buffer size: {len(self.accumulated_buffer)}",
                queries=sub_queries,
                buffer_preview=self.accumulated_buffer[:5]
            )

            # 4. Evaluate context via lightweight LLM with strict schema enforcement
            action = await self._evaluate_context(synthesized_ctx)

            if action.action == Action.FINAL_ANSWER:
                return self._resolve_final_indices(action.selected_indices)

        # Fallback: Max turns reached, force exit with top-K buffer items
        return self.accumulated_buffer[:settings.TOP_K]

    def _update_buffer(self, new_candidates: List[Dict[str, Any]]) -> None:
        """Merges new candidates into the buffer, enforcing MAX_BUFFER_SIZE."""
        self.accumulated_buffer.extend(new_candidates)
        # Sort by RRF score descending and truncate to hard ceiling
        self.accumulated_buffer.sort(key=lambda x: x.get("score", 0), reverse=True)
        if len(self.accumulated_buffer) > settings.MAX_BUFFER_SIZE:
            self.accumulated_buffer = self.accumulated_buffer[:settings.MAX_BUFFER_SIZE]

    async def _evaluate_context(self, context: str) -> AgentAction:
        """Dispatches evaluation prompt to LLM with Pydantic JSON schema validation."""
        buffer_summary = "\n".join([f"[{i}] {c['text'][:100]}..." for i, c in enumerate(self.accumulated_buffer)])

        prompt = f"""You are a retrieval agent. Evaluate the following context and buffer.
If the buffer contains sufficient information to answer the query, output action 'final_answer' with selected_indices.
Otherwise, output action 'vector_search' with new search_queries.

Context: {context}
Buffer:
{buffer_summary}

Respond strictly in JSON matching this schema:
{AgentAction.model_json_schema()}"""

        resp = await self.http_client.post("/api/chat", json={
            "model": settings.LIGHTWEIGHT_LLM_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "format": AgentAction.model_json_schema()
        })
        resp.raise_for_status()

        try:
            return AgentAction.model_validate(resp.json()["message"]["content"])
        except Exception:
            # Deterministic fallback on parsing failure
            return AgentAction(action=Action.FINAL_ANSWER, thought="Parse fallback",
                               selected_indices=list(range(min(5, len(self.accumulated_buffer)))))

    def _resolve_final_indices(self, indices: Optional[List[int]]) -> List[Dict[str, Any]]:
        """Extracts specified indices from buffer with safety net validation."""
        if not indices or not self.accumulated_buffer:
            return self.accumulated_buffer[:settings.TOP_K]

        valid_items = [self.accumulated_buffer[i] for i in indices if 0 <= i < len(self.accumulated_buffer)]
        # Pad with top-K if too few selected
        if len(valid_items) < 3:
            valid_items.extend(self.accumulated_buffer[:settings.TOP_K])

        return valid_items