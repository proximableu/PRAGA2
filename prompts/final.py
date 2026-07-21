"""Deterministic prompt assembly enforcing strict 3-category Markdown structure."""
from typing import List, Dict, Any


class FinalPromptAssembler:
    """Formats context and system instructions to guarantee structured LLM output."""

    @staticmethod
    def assemble(final_passages: List[Dict[str, Any]], user_query: str) -> str:
        """
        Constructs the final generation prompt.
        Strips redundant metadata, injects 3-category schema, and enforces tone constraints.
        """
        # Format context block efficiently to preserve token space
        context_lines = []
        for i, passage in enumerate(final_passages, 1):
            text = passage.get("text", "")
            hierarchy = " > ".join(passage.get("hierarchy", []))
            context_lines.append(f"[Source {i}] ({hierarchy})\n{text}")

        context_block = "\n\n---\n\n".join(context_lines)

        # Strict system instruction with 3-category enforcement
        system_instruction = """You are an expert academic researcher. Answer the user's query using ONLY the provided context.
Structure your response strictly into these three categories. Use the exact headings below:

### 1. Direct Answer from Sources
(Information explicitly stated in the provided context. Cite sources where applicable.)

### 2. Inferred Answer from Multiple Sources
(Logically derived conclusions connecting multiple context blocks. Clearly mark as inference.)

### 3. From Internal Knowledge
(General knowledge supplementing the context. Clearly mark as internal knowledge and note any divergence from sources.)

Tone Requirements: Maintain a strict, detached, encyclopedic tone. Do not use emojis, subjective anecdotes, or conversational filler. Be precise and objective."""

        return f"{system_instruction}\n\n=== CONTEXT ===\n{context_block}\n\n=== USER QUERY ===\n{user_query}"