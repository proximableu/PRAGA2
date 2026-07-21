"""Orchestration pipeline for embedding generation, upserting, and archiving."""
import asyncio
import hashlib
import shutil
from pathlib import Path
from typing import List
import httpx
import uuid

from sqlalchemy import select
from database.engine import AsyncSessionLocal
from database.models import Document, Chunk, Embedding
from ingestion.parser import extract_chunks
from ingestion.deduplication import LexicalDeduplicator
from config import settings


async def fetch_embeddings(texts: List[str]) -> List[List[float]]:
    """Dispatches batched text to Ollama embedding endpoint."""
    async with httpx.AsyncClient(timeout=60.0) as client:
        payload = {"model": settings.EMBED_MODEL, "input": texts}
        response = await client.post(f"{settings.OLLAMA_URL}/api/embed", json=payload)
        response.raise_for_status()
        return response.json()["embeddings"]


async def process_batch(file_paths: List[Path], dedup_engine: LexicalDeduplicator):
    """Processes a batch of files: parses, embeds, upserts atomically."""
    async with AsyncSessionLocal() as session:
        async with session.begin():
            for fpath in file_paths:
                raw_content = fpath.read_text(encoding="utf-8")
                content_hash = hashlib.sha256(raw_content.encode()).hexdigest()

                if dedup_engine.is_duplicate(content_hash, raw_content):
                    continue

                doc_id = uuid.uuid4()
                chunks_data = extract_chunks(raw_content)

                # Prepare chunk records
                chunk_records = []
                for chunk_text, hierarchy in chunks_data:
                    chunk_id = uuid.uuid4()
                    chunk_records.append(Chunk(
                        id=chunk_id,
                        document_id=doc_id,
                        chunk_text=chunk_text,
                        header_hierarchy=hierarchy
                    ))

                # Generate embeddings in parallel with DB prep
                texts_to_embed = [c.chunk_text for c in chunk_records]
                vectors = await fetch_embeddings(texts_to_embed)

                # Attach vectors to embedding records
                embed_records = [
                    Embedding(id=uuid.uuid4(), chunk_id=c.id, vector=v)
                    for c, v in zip(chunk_records, vectors)
                ]

                # Atomic upsert: Document -> Chunks -> Embeddings
                session.add(Document(
                    id=doc_id,
                    source_filename=fpath.name,
                    raw_content=raw_content
                ))
                session.add_all(chunk_records)
                session.add_all(embed_records)

            await session.commit()

            # Archive successfully processed files to ensure idempotency [3]
            archive_dir = settings.RAG_DB_DIR / "embedded"
            archive_dir.mkdir(exist_ok=True)
            for fpath in file_paths:
                shutil.move(str(fpath), str(archive_dir / fpath.name))


async def run_ingestion_pipeline():
    """Scans directory, batches files, and executes the ingestion workflow."""
    dedup_engine = LexicalDeduplicator()
    md_files = list(settings.RAG_DB_DIR.glob("*.md"))

    if not md_files:
        print("No Markdown files found in RAG_DB_DIR.")
        return

    # Process in configurable batches to optimize API throughput
    batch_size = 16
    for i in range(0, len(md_files), batch_size):
        batch = md_files[i:i + batch_size]
        await process_batch(batch, dedup_engine)
        print(f"Processed batch {i // batch_size + 1}/{(len(md_files) + batch_size - 1) // batch_size}")