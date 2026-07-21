"""Deterministic routing resolution service prioritizing aliases, prefixes, and explicit parameters."""
from typing import Optional
from pydantic import BaseModel
from fastapi import HTTPException
from config import settings


class RoutingContext(BaseModel):
    """Structured payload carrying resolved execution targets."""
    target_db_identifier: str
    target_llm_model: str
    resolved_model_alias: str


class RoutingResolutionService:
    """Evaluates incoming request metadata against routing priority rules [3]."""

    def resolve(self, model_alias: Optional[str], explicit_rag_db: Optional[str]) -> RoutingContext:
        # Priority 1: Explicit Alias Mapping
        if model_alias and model_alias in settings.MODEL_DB_MAP:
            mapping = settings.MODEL_DB_MAP[model_alias]
            return RoutingContext(
                target_db_identifier=mapping.get("db", "default"),
                target_llm_model=mapping.get("llm", settings.DEFAULT_LLM_MODEL),
                resolved_model_alias=model_alias
            )

        # Priority 2: Dynamic RAG Prefix Parsing
        if model_alias and model_alias.startswith("RAG:"):
            db_suffix = model_alias.split(":", 1)[1]
            return RoutingContext(
                target_db_identifier=db_suffix if db_suffix else "default",
                target_llm_model=settings.DEFAULT_LLM_MODEL,
                resolved_model_alias=model_alias
            )

        # Priority 3: Explicit Payload Parameter
        if explicit_rag_db:
            return RoutingContext(
                target_db_identifier=explicit_rag_db,
                target_llm_model=settings.DEFAULT_LLM_MODEL,
                resolved_model_alias="explicit_override"
            )

        # Fallback: Reject malformed routing attempts
        raise HTTPException(
            status_code=400,
            detail="Routing failure: No valid model alias, RAG prefix, or explicit rag_db parameter provided."
        )