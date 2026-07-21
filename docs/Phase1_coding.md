### Phase 1: Database Engine & Ingestion Pipeline Implementation Contract

To ensure rigorous maintainability and decouple storage logic from agentic execution, we will transition from a flat file structure to a modular, package-based architecture. The following contract defines the directory mapping, configuration requirements, and concrete implementation steps for the coder model to execute Phase 1.

---

#### 1. Project Architecture & File Mapping
The coder must establish the following directory structure. This isolates database interactions, ingestion logic, and configuration, preventing the monolithic coupling observed in the legacy system [1], [3].

```text
rag_gateway/
├── .env                  # Centralized configuration (see Section 2)
├── config.py             # Pydantic settings loader & constant registry
├── database/
│   ├── __init__.py
│   ├── engine.py         # Async connection pooling & dynamic router setup
│   └── models.py         # SQLAlchemy/asyncpg schema definitions
├── ingestion/
│   ├── __init__.py
│   ├── parser.py         # Markdown AST parsing & hierarchical chunking
│   ├── deduplication.py  # SHA-256 & MinHashLSH filtering logic
│   └── pipeline.py       # Orchestration: embedding, upserting, archiving
├── build_rag_db.py       # CLI entry point for database construction
└── main.py               # (Phase 2) FastAPI Gateway & Agentic Loop
```

---

#### 2. Centralized Configuration (`.env` Contract)
The coder must ensure `config.py` utilizes `python-dotenv` and `pydantic-settings` to load the following variables. These constants will govern all Phase 1 operations:

| Variable | Default | Purpose |
| :--- | :--- | :--- |
| `POSTGRES_DSN` | `postgresql+asyncpg://...` | Connection string for the primary RAG database cluster. |
| `OLLAMA_URL` | `http://localhost:11434` | Endpoint for embedding generation. |
| `EMBED_MODEL` | `snowflake-arctic-embed2:568m` | Model identifier for vector generation [2], [3]. |
| `EMBED_DIM` | `1024` | Vector dimensionality alignment [2]. |
| `RAG_DB_DIR` | `./rag_databases` | Source directory for raw `.md` files [1]. |
| `NUM_PERM` | `256` | Permutation count for MinHashLSH resolution [3]. |
| `DEDUP_JACCARD_THRESHOLD` | `0.98` | Similarity threshold for ingestion-time deduplication [3]. |
| `HNSW_M` | `32` | HNSW index parameter for vector search connectivity. |
| `HNSW_EF_CONSTRUCTION` | `200` | HNSW index parameter for vector search accuracy. |

---

#### 3. Phase 1 Implementation Steps

**Step 1: Database Engine & Schema Definition**
*   **Task**: Implement `database/models.py` to define three core tables using SQLAlchemy 2.0 async syntax.
*   **Specifications**:
    *   `documents`: Stores `id` (UUID), `source_filename` (Text, Unique), `raw_content` (Text), and `ingestion_timestamp`.
    *   `chunks`: Stores `id` (UUID), `document_id` (FK), `parent_id` (UUID, Nullable), `chunk_text` (Text), `header_hierarchy` (Array[String]), and `search_vector` (TSVector). The `search_vector` must be auto-generated from `chunk_text` via a PostgreSQL trigger or ORM event to enable native BM25 indexing.
    *   `embeddings`: Stores `id` (UUID), `chunk_id` (FK), and `vector` (Vector type with dimension `EMBED_DIM`).
*   **Indexing**: Apply an HNSW index on the `vector` column using the `EMBED_DIM` and `HNSW_M` parameters. Apply a GIN index on the `search_vector` column for Full-Text Search.

**Step 2: Markdown AST Parser & Hierarchical Chunking**
*   **Task**: Implement `ingestion/parser.py` to transform raw Markdown into structured chunks.
*   **Specifications**:
    *   Utilize `markdown-it-py` or `mistletoe` to traverse the Markdown Abstract Syntax Tree.
    *   **Header Tracking**: Maintain a stack of active headers (`#`, `##`, `###`). As the parser traverses the tree, push headers onto the stack and pop them when exiting the section.
    *   **Leaf Extraction**: Identify leaf nodes (paragraphs, lists, code blocks). Extract their text as `chunk_text`.
    *   **Context Inheritance**: Attach the current header stack to each chunk as the `header_hierarchy` array. This ensures that when a chunk is retrieved, the system knows exactly which section of the document it belongs to.

**Step 3: Two-Stage Deduplication Engine**
*   **Task**: Implement `ingestion/deduplication.py` to prevent redundant embeddings.
*   **Specifications**:
    *   **Stage 1 (Cryptographic)**: Compute the SHA-256 hash of the raw file content. Maintain a set of processed hashes in memory. If a hash exists, skip the file immediately.
    *   **Stage 2 (Lexical Similarity)**: For files passing Stage 1, apply `MinHashLSH` using `datasketch`. Tokenize the text into 3-gram shingles to preserve local context and prevent bag-of-words false positives [3]. Compute the MinHash signature and query the LSH index. If the Jaccard similarity exceeds `DEDUP_JACCARD_THRESHOLD`, mark the file as a duplicate [2], [3].

**Step 4: Ingestion Pipeline Orchestration**
*   **Task**: Implement `ingestion/pipeline.py` and `build_rag_db.py` to execute the workflow.
*   **Specifications**:
    *   **File Discovery**: Scan `RAG_DB_DIR` for all `.md` files.
    *   **Batch Processing**: Group unique files into batches (e.g., 16-32 files per batch) to optimize Ollama API throughput.
    *   **Embedding Dispatch**: Send the `chunk_text` of all chunks in the batch to the Ollama embedding endpoint [2].
    *   **Atomic Upsert**: Commit the `documents`, `chunks`, and `embeddings` records in a single database transaction. If the transaction fails, log the error and skip the batch without corrupting the database.
    *   **Archiving**: Upon successful commit, atomically move the source `.md` files to the `./embedded` subdirectory within `RAG_DB_DIR` [3]. This ensures idempotent execution; re-running the script will only process new files.

---

#### 4. Integration Verification Criteria
The coder must validate the implementation against the following benchmarks before proceeding to Phase 2:
1.  **Schema Integrity**: Verify that `pgvector` HNSW indexes and `tsvector` GIN indexes are correctly applied via `EXPLAIN ANALYZE` on sample queries.
2.  **Hierarchical Fidelity**: Confirm that retrieved chunks accurately reflect their `header_hierarchy` metadata.
3.  **Deduplication Efficacy**: Intentionally ingest near-identical Markdown files and verify that the MinHashLSH engine correctly identifies them as duplicates based on the `DEDUP_JACCARD_THRESHOLD`.
4.  **Idempotency**: Run the ingestion script twice on the same directory. The second run must process zero files and move nothing, confirming the SHA-256 and archival logic functions correctly.

This contract provides the coder with a deterministic, step-by-step roadmap to construct a robust, high-performance ingestion engine that strictly adheres to our architectural blueprint.