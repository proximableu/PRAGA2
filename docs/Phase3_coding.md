### Phase 3: Agentic Execution & Retrieval Mechanics Implementation Contract

This contract defines the architectural boundaries, file mapping, and concrete implementation steps for the asynchronous agentic loop, hybrid retrieval engine, and Open-WebUI streaming interface. This phase transforms the synchronous, blocking retrieval logic into a non-blocking, telemetry-rich generator that streams agent reasoning in real-time.

---

#### 1. Project Architecture & File Mapping
Phase 3 introduces a dedicated `agents` package to isolate loop orchestration, retrieval mechanics, and streaming logic. The coder must establish the following structure:

```text
rag_gateway/
├── agents/
│   ├── __init__.py
│   ├── context.py          # New: History synthesis & query expansion
│   ├── retrieval.py        # New: Hybrid RRF search, deduplication, LLM filtering
│   ├── loop.py             # New: Async ReAct loop orchestrator
│   └── streaming.py        # New: SSE generator &
</think> formatting
├── services/
│   ├── __init__.py
│   └── execution.py        # New: Orchestrates agent, retrieval, & streaming
├── api/
│   └── endpoints.py        # (Phase 2) Injects execution service
├── database/               # (Phase 1) Async engine & schemas
└── config.py               # (Updated) Agentic & retrieval constants
```

---

#### 2. Centralized Configuration (`.env` Contract)
The coder must extend `config.py` to load agentic and retrieval-specific variables. These constants govern loop behavior, ranking mathematics, and buffer limits:

| Variable | Default | Purpose |
| :--- | :--- | :--- |
| `AGENT_MAX_TURNS` | `3` | Maximum iterations for the ReAct search loop [1]. |
| `AGENT_NUM_CTX` | `8192` | Context window limit for the routing LLM [1]. |
| `NUM_SUB_QUERIES` | `3` | Number of semantic angles for query expansion [4]. |
| `MAX_BUFFER_SIZE` | `30` | Hard ceiling for the accumulated passage buffer [1]. |
| `HISTORY_WINDOW_TURNS` | `10` | Rolling window size for conversation history synthesis [4]. |
| `RRF_K_CONSTANT` | `60` | Smoothing constant for Reciprocal Rank Fusion calculation. |
| `TOP_K` | `12` | Base candidate count per retrieval angle [1]. |
| `LIGHTWEIGHT_LLM_MODEL` | `llama3.2:3b` | Model identifier for filtering and expansion [2], [4]. |

---

#### 3. Phase 3 Implementation Steps

**Step 1: Context Synthesis & Query Expansion (`agents/context.py`)**
*   **Task**: Implement deterministic history summarization and multi-angle query generation.
*   **Specifications**:
    *   **Rolling Window Strategy**: Implement the legacy synthesis logic. If conversation history exceeds `HISTORY_WINDOW_TURNS`, summarize older turns using the lightweight LLM while preserving recent turns verbatim [4].
    *   **Synthesized Query Assembly**: Concatenate the summary, recent context, and the latest user prompt into a unified `synthesized_query` string [4].
    *   **Query Expansion**: Dispatch the synthesized query to the lightweight LLM to generate exactly `NUM_SUB_QUERIES` distinct semantic reformulations. Enforce strict JSON output parsing. If parsing fails, fallback to duplicating the original query [4].

**Step 2: Hybrid RRF Retrieval & Deduplication (`agents/retrieval.py`)**
*   **Task**: Implement the native PostgreSQL hybrid search pipeline, replacing the legacy pure ANN search [2].
*   **Specifications**:
    *   **Parallel Query Execution**: For each expanded sub-query, execute two concurrent database queries:
        1.  **Vector Search**: Cosine similarity against `pgvector` HNSW index.
        2.  **Lexical Search**: `tsvector` matching against the GIN index for exact keyword retrieval.
    *   **Reciprocal Rank Fusion (RRF)**: Merge the two result sets using the formula `Score = Σ(1 / (RRF_K_CONSTANT + rank_i))`. This ensures exact technical matches and semantic similarities are weighted equally without secondary models.
    *   **Cross-Query Deduplication**: Apply `MinHashLSH` to the merged RRF results using the configured `DEDUP_JACCARD_THRESHOLD` and `NUM_PERM` parameters. This ensures lexical diversity across the expanded query angles [2], [3].
    *   **Lightweight LLM Filtering**: Pass the deduplicated candidates through the proven relevance filter. The lightweight LLM evaluates snippets against the synthesized query, returning a structured list of relevant indices [2]. Implement a deterministic safety net: if the filter returns too few passages, pad the results with the highest-scoring RRF candidates.

**Step 3: Asynchronous ReAct Loop Orchestrator (`agents/loop.py`)**
*   **Task**: Implement the stateful, non-blocking execution loop that manages the accumulation buffer and agent decisions.
*   **Specifications**:
    *   **Persistent Buffer**: Initialize an `accumulated_buffer` list that survives loop iterations. Merge new RRF-filtered candidates into this buffer, applying cross-turn `MinHashLSH` deduplication and enforcing the `MAX_BUFFER_SIZE` hard ceiling [1].
    *   **Agent Evaluation Prompt**: Construct a deterministic prompt containing the synthesized context, current search queries, formatted buffer contents, and execution history.
    *   **Pydantic Schema Enforcement**: Dispatch the evaluation prompt to the routing LLM with strict `AgentAction` JSON schema validation [1]. The schema must enforce `thought`, `action` (`vector_search` or `final_answer`), `search_queries`, and `selected_indices` [1].
    *   **Loop Control & Fallback**: If the agent selects `final_answer`, extract the specified indices from the buffer and break the loop. If indices are invalid or the buffer is empty, trigger a deterministic fallback to the top-K buffer items [1]. If `AGENT_MAX_TURNS` is reached, force an early exit with the accumulated buffer [1].

**Step 4: SSE Streaming Generator & `
</think>` Integration (`agents/streaming.py`)**
*   **Task**: Implement the async generator that formats agent telemetry and final responses for Open-WebUI.
*   **Specifications**:
    *   **Reasoning Telemetry**: Before the final answer, yield the agent's internal `thought`, the expanded `search_queries`, and a preview of the `retrieved_passages` wrapped in `
</think>` tags. Open-WebUI natively renders these as collapsible reasoning accordions, providing real-time visibility into the agentic process [1].
    *   **Final Answer Generation**: Once the loop terminates, assemble the final prompt using the strict 3-category Markdown structure (Direct Answer, Inferred Answer, Internal Knowledge) [4].
    *   **Token Streaming**: Dispatch the final prompt to the target LLM and yield raw response tokens via SSE. Aggregate tokens into OpenAI-compatible `delta` chunks.
    *   **Audit Footer**: Append a collapsible `<details>` block to the final chunk containing execution telemetry: model used, database queried, agent turns executed, and source citations [1].

**Step 5: Execution Service Integration (`services/execution.py`)**
*   **Task**: Implement the service layer that bridges the API endpoint, database router, and agentic loop.
*   **Specifications**:
    *   Inject the `DatabaseRouter` session and `RoutingContext` (from Phase 2) into the execution workflow.
    *   Initialize the `ContextSynthesizer`, `HybridRetriever`, and `ReActLoop` components.
    *   Wire the async generator from `streaming.py` to the FastAPI `StreamingResponse`, ensuring proper error handling and graceful cleanup of database sessions upon stream completion.

---

#### 4. Integration Verification Criteria
The coder must validate Phase 3 against the following benchmarks before proceeding to final system integration:
1.  **Async Non-Blocking Execution**: Verify that the agentic loop yields SSE chunks continuously without blocking the event loop, even during heavy RRF search or LLM filtering operations.
2.  **RRF Ranking Fidelity**: Inject test queries containing exact technical symbols and semantic concepts. Verify that the RRF merger correctly elevates exact matches alongside semantic hits.
3.  **Buffer Capacity & Fallbacks**: Simulate a scenario where the agent selects invalid indices or stalls. Verify that the deterministic fallback correctly surfaces the top-K buffer items without crashing [1].
4.  **Open-WebUI Telemetry Rendering**: Confirm that `
</think>` blocks are correctly formatted and rendered as collapsible accordions in the Open-WebUI interface, and that the final response strictly adheres to the 3-category Markdown structure [4].
5.  **Graceful Session Cleanup**: Ensure that database sessions are properly closed and connection pools are returned to the cache after every streaming response completes.

This contract provides the coder with a deterministic, step-by-step roadmap to construct a robust, streaming-native agentic execution engine that strictly adheres to our architectural blueprint while preserving the proven reliability of the legacy retrieval mechanics.