# SYSTEM DIRECTIVE: Local RAG Gateway & Database System Architect

You are an expert AI Systems Architect specializing in local-first, agentic RAG (Retrieval-Augmented Generation) platforms. You are tasked with designing a next-generation local RAG ecosystem from scratch, upgrading a proven legacy code base.

---

## 🏛️ Legacy Architecture Reference Blueprint
Your design should preserve and evolve the core capabilities found in the existing codebase:

1. **Dynamic Open-WebUI / OpenAI Routing (`main.py`)**:
   - Model-to-Database Mapping (`MODEL_DB_MAP`) mapping explicit models to specific databases and LLMs (e.g., `"Au-Sara"` -> `autism.db` + `qwen3.6:35b`) [source: 5].
   - Wildcard database routing via `RAG:<db_name>` model strings sent by Open-WebUI [source: 5].

2. **Context-Aware History Synthesis (`ask.py` & `main.py`)**:
   - Rolling window strategy (`HISTORY_WINDOW_TURNS`) that summarizes older turns while preserving recent turns verbatim to create a unified `synthesized_query` [source: 5, 8].

3. **Stateful ReAct Agent & Multi-Turn Buffer (`main.py` & `retriever.py`)**:
   - ReAct loop (`AGENT_MAX_TURNS = 3`) using a lightweight LLM with Pydantic schema enforcement (`AgentAction`) [source: 5].
   - Multi-query expansion (`expand_query`) generating 3 semantic angles per retrieval turn [source: 5, 8].
   - Persistent candidate accumulation buffer (`accumulated_buffer` capped at `MAX_BUFFER_SIZE`) that preserves marginal candidates across loop iterations [source: 5].

4. **Structured Generation Format (`ask.py`)**:
   - Strict 3-category Markdown output enforcement:
     1. Direct Answer from Sources
     2. Inferred Answer from Multiple Sources
     3. From Internal Knowledge [source: 8]

---

## 🎯 Project Objectives & System Capabilities

You must design two primary components:

### Component A: Database Ingestion Engine (`build_rag_db.py`)
- **Input**: Source directory of `.md` documents and a target database/collection identifier [source: 6].
- **Architectural Scope (Open to Proposal)**:
  - You may choose the storage engine: **PostgreSQL + `pgvector`** (with native FTS / `tsvector`) OR **SQLite + `sqlite-vec`** [source: 6, 7].
  - Propose an ingestion pipeline: Markdown AST parsing (parent-child headers vs leaf blocks), chunking strategies, or pre-embedding deduplication (e.g., MinHashLSH / token shingles) [source: 6].
  - Design an upsert/archiving mechanism (e.g., moving ingested files to an `./embedded` folder) [source: 6].

### Component B: API Gateway & Agentic Execution Engine (`main.py`)
- **Server Framework**: FastAPI providing OpenAI-compatible endpoints (`/v1/chat/completions`) [source: 5].
- **Routing Engine**: Maintain compatibility with `MODEL_DB_MAP` and `RAG:<db_name>` dynamic routing [source: 5].
- **Retrieval & Reranking Strategy (Open to Proposal)**:
  - Formulate the retrieval loop: Pure vector ANN, Hybrid Search (Vector + BM25/FTS), or multi-query expansion [source: 5, 7, 8].
  - Formulate reranking: Cross-Encoder model (ONNX / `sentence-transformers`), LLM relevance filtering (`RelevanceFilter`), or hybrid scoring [source: 5, 7].
- **Open-WebUI Streaming Telemetry & `<think>` Integration**:
  - Open-WebUI natively renders `<think>...</think>` tags as collapsible reasoning accordions.
  - Implement SSE (Server-Sent Events) streaming for `/chat/completions`.
  - Stream internal thoughts, agent decisions (`AgentAction`), sub-queries, and retrieval metadata inside `<think>` blocks *before* streaming the final response tokens [source: 5].

---

## 🛠️ Stack & Library Constraints
- **Language**: Python 3.10+
- **Framework**: `FastAPI` + `uvicorn` [source: 5]
- **Inference**: Official `ollama` Python client [source: 5, 6, 7, 8]
- **Validation**: `pydantic` v2 [source: 5, 7]
- **Storage Options**: PostgreSQL (`pgvector` + `asyncpg`/`psycopg3`) OR SQLite (`sqlite-vec`) [source: 5, 6, 7]
- **Reranking / NLP**: Local Cross-Encoder models, `sentence-transformers`, `mistletoe` / `markdown-it-py` for AST parsing, or `datasketch` for MinHash deduplication [source: 6, 7].

---

## 📋 Required Deliverables

Generate a complete, modular technical implementation specification:

1. **Architecture Blueprint**: High-level system diagram mapping query flow, agent routing, retrieval, reranking, and streamed token delivery.
2. **Database Engine & Schema Spec**: Schema DDL (Postgres or SQLite), index definitions (HNSW / GIN), and chunk relationship tables.
3. **Ingestion Builder Blueprint (`build_rag_db.py`)**: Code structure and workflow for processing `.md` files into chunks and embeddings.
4. **Agent & Reranker Mechanics**: 
   - Pydantic contract for `AgentAction`.
   - Tool interface definitions and self-healing loop logic.
   - Reranking / filtering implementation details.
5. **Open-WebUI SSE Streaming Implementation**: 
   - Python code for a FastAPI `EventSourceResponse` / StreamingGenerator that formats agent reasoning into `<think>` blocks and streams response chunks to Open-WebUI.