"""Centralized configuration loader with Phase 4 streaming & telemetry constants."""
import json
from pathlib import Path
from typing import Dict, Any

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Phase 1: Core Ingestion & Vector Parameters
    POSTGRES_DSN: str = "postgresql+asyncpg://user:password@localhost:5432/rag_db"
    OLLAMA_URL: str = "http://localhost:11434"
    EMBED_MODEL: str = "snowflake-arctic-embed2:568m"
    EMBED_DIM: int = 1024
    RAG_DB_DIR: Path = Path("./rag_databases")
    NUM_PERM: int = 256
    DEDUP_JACCARD_THRESHOLD: float = 0.98
    HNSW_M: int = 32
    HNSW_EF_CONSTRUCTION: int = 200

    # Phase 2: Dynamic Routing & Gateway Parameters
    POSTGRES_DSN_BASE: str = "postgresql+asyncpg://user:pass@localhost/"
    DEFAULT_LLM_MODEL: str = "qwen3.5:35b-a3b"
    MAX_CONNECTIONS_PER_DB: int = 5
    RAG_DB_REGISTRY: Dict[str, str] = {"default": "general_knowledge"}
    MODEL_DB_MAP: Dict[str, Dict[str, str]] = {}

    # Phase 3: Agentic Loop & Retrieval Mechanics
    AGENT_MAX_TURNS: int = 3
    AGENT_NUM_CTX: int = 8192
    NUM_SUB_QUERIES: int = 3
    MAX_BUFFER_SIZE: int = 30
    HISTORY_WINDOW_TURNS: int = 10
    RRF_K_CONSTANT: int = 60
    TOP_K: int = 12
    LIGHTWEIGHT_LLM_MODEL: str = "llama3.2:3b"

    # Phase 4: Streaming & Telemetry Controls
    ENABLE_REASONING_TELEMETRY: bool = True
    ENABLE_AUDIT_FOOTER: bool = True
    FINAL_PROMPT_TEMPERATURE: float = 0.7
    FINAL_PROMPT_NUM_CTX: int = 64000
    DIAGNOSTIC_FALLBACK_MSG: str = (
        "⚠️ Retrieval Diagnostic: No relevant passages were found in the target database. "
        "The following response relies exclusively on internal model knowledge."
    )

    @field_validator("RAG_DB_REGISTRY", "MODEL_DB_MAP", mode="before")
    @classmethod
    def parse_json_registries(cls, v: Any) -> Any:
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                raise ValueError("Registry configuration must be valid JSON.")
        return v

settings = Settings()