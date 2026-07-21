"""Audit metadata construction and diagnostic fallback injection."""

from typing import Any, Dict, List
from config import settings


class TelemetryInjector:
    """Aggregates execution metrics and formats collapsible audit footers."""

    @staticmethod
    def build_audit_footer(
        model: str,
        database: str,
        turns: int,
        candidate_count: int,
        sources: List[str],
    ) -> str:
        """Constructs a <details> block containing execution telemetry."""
        unique_sources = sorted(list(set(sources))) if sources else []
        formatted_sources = ", ".join([f'"{s}"' for s in unique_sources])

        return (
            f"\n\n<details>\n"
            f"<summary>Retrieval Audit</summary>\n\n"
            f"```json\n"
            f"{{\n"
            f'  "model": "{model}",\n'
            f'  "database": "{database}",\n'
            f'  "agent_turns": {turns},\n'
            f'  "final_candidates": {candidate_count},\n'
            f'  "source_files": [{formatted_sources}]\n'
            f"}}\n"
            f"```\n"
            f"</details>"
        )

    @staticmethod
    def apply_diagnostic_fallback(user_query: str) -> str:
        """Prepends diagnostic warning when retrieval pipeline yields zero passages."""
        fallback_msg = getattr(
            settings,
            "DIAGNOSTIC_FALLBACK_MSG",
            "No relevant context found.",
        )
        return f"{fallback_msg}\n\n**User Query**: {user_query}\n---\n"