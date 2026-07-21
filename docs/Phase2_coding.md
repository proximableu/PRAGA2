### Phase 2: API Gateway & Dynamic Routing Implementation Contract

This contract defines the architectural boundaries, file mapping, and concrete implementation steps for the FastAPI Gateway and Dynamic Routing Engine. This phase establishes the entry point for all external requests, handles OpenAI-compatible payload validation, and manages the asynchronous routing to the correct PostgreSQL RAG database.

---

#### 1. Project Architecture & File Mapping
Phase 2 introduces a modular service layer to decouple routing logic from endpoint handlers. The coder must establish the following structure:

```text
rag_gateway/
├── main.py                 # FastAPI app instantiation & lifespan management
├── config.py               # (Updated) Pydantic settings loader
├── database/
│   ├── __init__.py
│   ├── engine.py           # Async connection pooling & dynamic router setup
│   ├── models.py           # (Phase 1) SQLAlchemy schema definitions
│   └── router.py           # New: Lazy-loading database session manager
├── services/
│   ├── __init__.py
│   └── routing.py          # New: Routing resolution & payload preparation
├── api/
│   ├── __init__.py
│   ├── models.py           # New: OpenAI-compatible request/response schemas
│   └── endpoints.py        # New: /v1/chat/completions & /models handlers
├── ingestion/              # (Phase 1) Ingestion pipeline
└── .env                    # Centralized configuration
```

---

#### 2. Centralized Configuration (`.env` Contract)
The coder must extend `config.py` to load routing-specific variables. These constants govern database discovery and connection pooling:

| Variable | Default | Purpose |
| :--- | :--- | :--- |
| `POSTGRES_DSN_BASE` | `postgresql+asyncpg://user:pass@localhost/` | Base connection string; database name is appended dynamically. |
| `RAG_DB_REGISTRY` | `{"default": "general_knowledge"}` | JSON string mapping model aliases to target PostgreSQL database names. |
| `MODEL_DB_MAP` | `{}` | JSON string preserving legacy alias-to-database/model mappings [1]. |
| `DEFAULT_LLM_MODEL` | `qwen3.5:35b-a3b` | Fallback LLM if no mapping is resolved. |
| `MAX_CONNECTIONS_PER_DB` | `5` | Connection pool size limit per dynamically mounted database. |

---

#### 3. Phase 2 Implementation Steps

**Step 1: FastAPI Application Lifecycle & Dependency Injection**
*   **Task**: Implement `main.py` to orchestrate application startup and shutdown.
*   **Specifications**:
    *   Utilize FastAPI's `lifespan` context manager instead of deprecated `on_event` hooks.
    *   **Startup**: Initialize the `DatabaseRouter` and load all configuration variables via `config.py`. Log the successful initialization of the gateway and the number of registered routing aliases.
    *   **Shutdown**: Gracefully dispose of all active connection pools in the `DatabaseRouter` to prevent connection leaks.
    *   **Dependency Injection**: Register the `DatabaseRouter` as a global FastAPI dependency, ensuring it is injected into all downstream services and endpoints.

**Step 2: Dynamic Database Routing Engine (`database/router.py`)**
*   **Task**: Implement a lazy-loading connection manager that supports on-the-fly database switching.
*   **Specifications**:
    *   **Pool Cache**: Maintain an internal `Dict[str, AsyncSession]` cache mapping database identifiers to their respective SQLAlchemy async session factories.
    *   **Session Resolution**: Implement a `get_session(db_identifier: str)` method. If the identifier exists in the cache, return an active session. If not, dynamically construct a new DSN using `POSTGRES_DSN_BASE`, instantiate an `AsyncEngine` with `MAX_CONNECTIONS_PER_DB`, create a session factory, cache it, and return a new session.
    *   **Transaction Context**: Ensure each session is wrapped in an async context manager (`async with session.begin():`) to guarantee atomic read operations during retrieval.

**Step 3: Routing Resolution Service (`services/routing.py`)**
*   **Task**: Implement the deterministic routing logic that prioritizes aliases, prefixes, and explicit parameters.
*   **Specifications**:
    *   **Priority 1 (Alias Mapping)**: Check if `req.model` exists in `MODEL_DB_MAP`. If yes, extract the target database name and LLM model [1].
    *   **Priority 2 (Dynamic Prefix)**: Check if `req.model` starts with `RAG:`. If yes, parse the suffix as the database identifier [1].
    *   **Priority 3 (Explicit Parameter)**: Check if `req.rag_db` is provided in the request payload. Use this as the database identifier [1].
    *   **Fallback**: If no routing criteria are met, raise a `400 Bad Request` HTTP exception with a descriptive error message.
    *   **Output**: Return a `RoutingContext` Pydantic object containing `target_db_identifier`, `target_llm_model`, and `resolved_model_alias`.

**Step 4: OpenAI-Compatible API Endpoints (`api/endpoints.py`)**
*   **Task**: Implement the primary interaction endpoints matching the OpenAI API schema.
*   **Specifications**:
    *   **`POST /v1/chat/completions`**:
        *   Validate the incoming `ChatRequest` payload using Pydantic v2.
        *   Invoke the `RoutingResolutionService` to determine the target database and LLM.
        *   Retrieve an active database session from the `DatabaseRouter`.
        *   *Phase 2 Handoff*: Package the validated request, routing context, and database session into a `ExecutionPayload` and pass it to the Agentic Execution Engine (Phase 3).
        *   Return an OpenAI-compatible `ChatCompletionResponse` object.
    *   **`GET /models`**:
        *   Dynamically generate a list of available models by combining keys from `MODEL_DB_MAP` and dynamically discovered RAG database identifiers [1].
        *   Format the output as a standard OpenAI model list response.
    *   **`GET /debug/retrieved/view`**:
        *   Maintain backward compatibility by serving the latest retrieved context log for diagnostic purposes [1].

---

#### 4. Integration Verification Criteria
The coder must validate Phase 2 against the following benchmarks before proceeding to Phase 3:
1.  **Routing Determinism**: Send requests with identical `model` aliases, `RAG:` prefixes, and `rag_db` parameters to verify that the `RoutingResolutionService` correctly prioritizes them and resolves to the expected PostgreSQL databases.
2.  **Connection Pooling**: Use a database monitoring tool (e.g., `pg_stat_activity`) to confirm that multiple requests to the same database reuse existing connections, while requests to new databases lazily instantiate new pools.
3.  **Payload Validation**: Submit malformed JSON payloads missing required fields (e.g., `messages` array) and verify that FastAPI returns a `422 Unprocessable Entity` response with clear Pydantic validation errors.
4.  **Graceful Shutdown**: Restart the FastAPI server and verify that all active PostgreSQL connections are cleanly terminated without leaving orphaned sessions.

This contract provides the coder with a deterministic, step-by-step roadmap to construct a robust, streaming-ready API gateway that strictly adheres to our architectural blueprint while preserving legacy routing compatibility.