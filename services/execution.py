"""Orchestrates agent, retrieval, streaming, and prompt assembly for Phase 4 execution."""

import json
from typing import Any, AsyncGenerator, Dict, List

from agents.context import ContextSynthesizer
from agents.loop import ReActLoop
from agents.retrieval import HybridRetriever
from database.router import DatabaseRouter
from prompts.final import FinalPromptAssembler
from streaming.generator import StreamingGenerator
from streaming.telemetry import TelemetryInjector


class ExecutionService:
    """Bridges API endpoints with the agentic execution and streaming pipeline."""

    def __init__(self, db_router: DatabaseRouter) -> None:
        self.db_router = db_router

    async def execute_request(
        self,
        routing_ctx,
        messages: List[Dict[str, str]],
        params: Dict[str, Any],
    ) -> AsyncGenerator[str, None]:
        """Wires the async generator to FastAPI StreamingResponse with session cleanup."""
        target_db = getattr(routing_ctx, "target_db_identifier", "default_db")
        target_llm = getattr(routing_ctx, "target_llm_model", "default_model")
        user_query = (
            messages[-1]["content"] if messages else "No query provided."
        )

        # Initialize pipeline components
        synthesizer = ContextSynthesizer()
        retriever = HybridRetriever()
        loop_orchestrator = ReActLoop()
        stream_gen = StreamingGenerator()

        agent_thoughts: List[Dict[str, Any]] = []

        async with self.db_router.get_session(target_db) as session:
            try:
                # Run agentic loop, collecting telemetry continuously
                selected_contexts = await loop_orchestrator.run_loop(
                    session=session,
                    retriever=retriever,
                    synthesizer=synthesizer,
                    initial_query=user_query,
                    stream_gen=stream_gen,  # Pass generator for internal telemetry yielding
                )

                # Capture agent thoughts for streaming phase
                agent_thoughts = loop_orchestrator.get_thought_log()

                # Handle zero-passage fallback
                diagnostic_prefix = ""
                if not selected_contexts:
                    diagnostic_prefix = (
                        TelemetryInjector.apply_diagnostic_fallback(user_query)
                    )

                # Assemble final prompt with strict 3-category structure
                final_prompt = FinalPromptAssembler.assemble(
                    selected_contexts, user_query
                )
                final_prompt = f"{diagnostic_prefix}{final_prompt}"

                # Build audit footer metadata safely
                sources = []
                for c in selected_contexts:
                    hierarchy = c.get("hierarchy")
                    if hierarchy and isinstance(hierarchy, list):
                        sources.append(hierarchy[-1])
                    else:
                        sources.append("Unknown")

                audit_footer = TelemetryInjector.build_audit_footer(
                    model=target_llm,
                    database=target_db,
                    turns=len(agent_thoughts),
                    candidate_count=len(selected_contexts),
                    sources=sources,
                )

                # Package payload and delegate to streaming generator
                payload = {"audit_footer": audit_footer}

                async for chunk in stream_gen.generate_stream(
                    payload=payload,
                    agent_thoughts=agent_thoughts,
                    final_prompt=final_prompt,
                    target_model=target_llm,
                ):
                    yield chunk

            except Exception as e:
                # Graceful error handling without crashing the event loop
                err_payload = {
                    "choices": [
                        {
                            "delta": {"content": f"⚠️ Execution Error: {str(e)}"},
                            "finish_reason": "error",
                        }
                    ]
                }
                yield f"data: {json.dumps(err_payload)}\n\n"
                yield "data: [DONE]\n\n"