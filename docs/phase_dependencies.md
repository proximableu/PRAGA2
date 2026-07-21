To ensure deterministic execution and prevent context window overflow, you should provide the coder model with a strictly curated set of dependency files for each phase transition. Below is the architectural dependency matrix mapping which files must be carried forward, along with the rationale for their inclusion.

### 1. Transition: Phase 1 → Phase 2
**Objective:** Establish the API Gateway and Dynamic Routing Engine.
**Required Context Files:**
| File Path | Architectural Rationale |
| :--- | :--- |
| `config.py` | Provides the shared constant registry (e.g., `POSTGRES_DSN`, `OLLAMA_URL`) required for router initialization. |
| `database/models.py` | Defines the SQLAlchemy schemas (`documents`, `chunks`, `embeddings`) that the router will query and manage. |
| `database/engine.py` | Contains the async connection pooling logic that the Phase 2 router must extend to support lazy-loading. |

---

### 2. Transition: Phase 2 → Phase 3
**Objective:** Implement the Agentic Execution Loop, Hybrid Retrieval, and Buffer Management.
**Required Context Files:**
| File Path | Architectural Rationale |
| :--- | :--- |
| `config.py` | Supplies agentic hyperparameters (`AGENT_MAX_TURNS`, `MAX_BUFFER_SIZE`, `RRF_K_CONSTANT`). |
| `database/router.py` | Provides the `get_session()` method the agent must call to execute RRF queries against the dynamically selected database. |
| `database/models.py` | Required for constructing the parallel Vector (`pgvector`) and Lexical (`tsvector`) queries inside the retriever. |
| `services/routing.py` | Supplies the `RoutingContext` object containing the resolved target database and LLM model identifiers [1]. |
| `api/models.py` | Defines the OpenAI-compatible `ChatRequest` schema that the execution service will unpack. |
| `ingestion/deduplication.py` | Contains the `MinHashLSH` logic that must be reused for cross-turn buffer deduplication and retrieval-time filtering [2], [3]. |

---

### 3. Transition: Phase 3 → Phase 4
**Objective:** Finalize Open-WebUI Streaming, `
</think>` Telemetry, and System Integration.
**Required Context Files:**
| File Path | Architectural Rationale |
| :--- | :--- |
| `config.py` | Supplies streaming toggles (`ENABLE_REASONING_TELEMETRY`, `ENABLE_AUDIT_FOOTER`) and generation constraints. |
| `agents/loop.py` | Contains the async ReAct orchestrator that the Phase 4 streaming generator must wrap and yield from. |
| `agents/streaming.py` | Provides the base SSE formatting logic that Phase 4 will extend to inject `
</think>` reasoning blocks [1]. |
| `services/execution.py` | Acts as the bridge between the API endpoint and the agentic components; must be updated to wire the final generator. |
| `api/endpoints.py` | Requires modification to return the `StreamingResponse` and inject the execution service dependency. |
| `main.py` | Requires lifespan updates to log final telemetry configurations and manage graceful stream termination. |

### Implementation Instruction for Context Management
When initiating a new phase, instruct the coder model to:
1. **Load the cumulative `config.py`**: Ensure all variables from previous phases are present.
2. **Inject the dependency files**: Provide only the files listed in the corresponding transition table above.
3. **Exclude completed logic**: Do not provide files from phases prior to the immediate dependency (e.g., do not provide `ingestion/pipeline.py` when starting Phase 3, as it is no longer modified).

This strategy ensures the coder model maintains architectural continuity while operating within a minimal, high-signal context window.