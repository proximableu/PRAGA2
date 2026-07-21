### Phase 4: Open-WebUI Streaming Interface & Final System Integration Contract

This contract defines the final architectural layer, transforming the synchronous response assembly into a real-time, Server-Sent Events (SSE) streaming pipeline. This phase ensures seamless Open-WebUI integration by exposing the agentic reasoning process via `
</think>` telemetry blocks and enforcing the strict 3-category Markdown output structure.

---

#### 1. Project Architecture & File Mapping
Phase 4 introduces a dedicated `streaming` and `prompts` package to isolate generator logic and prompt engineering. The coder must establish the following structure:

```text
rag_gateway/
├── streaming/
│   ├── __init__.py
│   ├── generator.py        # New: Async SSE generator &
</think> formatting
│   └── telemetry.py        # New: Audit metadata & execution log injection
├── prompts/
│   ├── __init__.py
│   └── final.py            # New: 3-category Markdown enforcement logic
├── services/
│   └── execution.py        # (Phase 3) Wires streaming generator to FastAPI
├── api/
│   └── endpoints.py        # (Phase 2) Final endpoint wiring & lifespan mgmt
├── main.py                 # FastAPI app instantiation
└── config.py               # (Updated) Streaming & telemetry constants
```

---

#### 2. Centralized Configuration (`.env` Contract)
The coder must extend `config.py` to load streaming and telemetry-specific variables. These constants govern output formatting, audit visibility, and generation constraints:

| Variable | Default | Purpose |
| :--- | :--- | :--- |
| `ENABLE_REASONING_TELEMETRY` | `true` | Toggle for streaming `
</think>` agent thoughts to Open-WebUI. |
| `ENABLE_AUDIT_FOOTER` | `true` | Toggle for appending the collapsible `<details>` execution log [1]. |
| `FINAL_PROMPT_TEMPERATURE` | `0.7` | Temperature setting for the final generation LLM [4]. |
| `FINAL_PROMPT_NUM_CTX` | `64000` | Context window limit for the final generation LLM [4]. |
| `DIAGNOSTIC_FALLBACK_MSG` | `...` | Custom message injected when retrieval pipeline returns zero passages [1]. |

---

#### 3. Phase 4 Implementation Steps

**Step 1: Async Streaming Generator & `
</think>` Telemetry (`streaming/generator.py`)**
*   **Task**: Implement the core async generator that yields OpenAI-compatible SSE chunks and formats agentic telemetry.
*   **Specifications**:
    *   **Generator Signature**: Define an `async def` generator that accepts the `ExecutionPayload` (containing routing context, database session, and synthesized query) and yields JSON-encoded SSE strings.
    *   **Reasoning Blocks**: If `ENABLE_REASONING_TELEMETRY` is true, yield the agent's internal `thought`, expanded `search_queries`, and retrieved passage previews wrapped in `
</think>` tags before streaming the final answer. Open-WebUI natively renders these as collapsible reasoning accordions, providing real-time visibility into the agentic process [1].
    *   **Token Streaming**: Once the agentic loop terminates, dispatch the final prompt to the target LLM. Yield raw response tokens via SSE, aggregating them into OpenAI-compatible `delta` chunks with proper `finish_reason` handling.
    *   **Error Handling**: Implement graceful stream termination with a `429` or `500` SSE error chunk if the LLM or database connection fails mid-stream.

**Step 2: Structured Output Enforcement (`prompts/final.py`)**
*   **Task**: Implement the deterministic prompt assembly logic that enforces the strict 3-category Markdown structure.
*   **Specifications**:
    *   **Context Injection**: Format the `final_passages` (selected by the agent) into a clean `=== CONTEXT ===` block, stripping redundant metadata to preserve token space [4].
    *   **3-Category Schema**: Construct the system instruction to mandate three distinct headings:
        1.  `### 1. Direct Answer from Sources` (with required disclaimer)
        2.  `### 2. Inferred Answer from Multiple Sources` (with required disclaimer)
        3.  `### 3. From Internal Knowledge` (with required disclaimer) [4].
    *   **Tone Enforcement**: Inject instructions to maintain a strict, detached, encyclopedic tone, prohibiting emojis or subjective anecdotes [4].

**Step 3: Audit Metadata Injection (`streaming/telemetry.py`)**
*   **Task**: Implement the metadata construction logic that appends execution telemetry to the final response.
*   **Specifications**:
    *   **Telemetry Aggregation**: Collect execution metrics: target model used, database queried, number of agent turns executed, final candidate count, and unique source filenames [1].
    *   **Collapsible Footer**: If `ENABLE_AUDIT_FOOTER` is true, construct a `<details>` block containing a `<summary> Retrieval Audit </summary>` and a code-formatted log of the telemetry data [1].
    *   **Diagnostic Fallback**: If the retrieval pipeline returns zero passages, prepend the `DIAGNOSTIC_FALLBACK_MSG` to the final answer to alert the user of potential database or embedding misalignment [1].

**Step 4: Final System Integration & Endpoint Wiring (`main.py` & `api/endpoints.py`)**
*   **Task**: Wire the streaming generator to the FastAPI endpoint and finalize the application lifecycle.
*   **Specifications**:
    *   **Endpoint Integration**: Update the `POST /v1/chat/completions` endpoint to return a `StreamingResponse` backed by the async generator, replacing the legacy synchronous JSON response [1].
    *   **Lifespan Management**: Implement FastAPI's `lifespan` context manager. On startup, log the loaded databases, active routing aliases, and agentic loop configuration [1]. On shutdown, gracefully dispose of all database connection pools.
    *   **Health & Debug Endpoints**: Maintain the `GET /models` endpoint to dynamically list available RAG databases and aliases [1]. Preserve the `GET /debug/retrieved/view` endpoint for diagnostic purposes [1].

---

#### 4. Integration Verification Criteria
The coder must validate Phase 4 against the following benchmarks before declaring the system complete:
1.  **Real-Time Telemetry**: Verify that Open-WebUI correctly renders `
</think>` blocks as collapsible accordions, displaying agent thoughts and sub-queries in real-time before the final answer streams.
2.  **Structured Output Fidelity**: Confirm that the final LLM response strictly adheres to the 3-category Markdown structure, including all required disclaimers [4].
3.  **Audit Footer Injection**: Validate that the collapsible `<details>` block is appended to the final response, accurately reflecting the execution telemetry (model, DB, turns, sources) [1].
4.  **Zero-Passage Fallback**: Simulate a retrieval failure (empty buffer) and verify that the diagnostic fallback message is correctly prepended to the LLM response [1].
5.  **Graceful Stream Termination**: Introduce a mid-stream database disconnection and verify that the generator terminates cleanly without crashing the FastAPI server.

This contract provides the coder with a deterministic, step-by-step roadmap to construct a robust, streaming-native Open-WebUI interface that strictly adheres to our architectural blueprint while preserving the proven reliability of the legacy retrieval mechanics.