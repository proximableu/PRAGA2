"""CLI entry point for Phase 1 database construction."""
import asyncio
from ingestion.pipeline import run_ingestion_pipeline

def main():
    """Executes the asynchronous ingestion pipeline from a synchronous context."""
    print("Starting RAG Database Ingestion Pipeline...")
    asyncio.run(run_ingestion_pipeline())
    print("Pipeline execution complete.")

if __name__ == "__main__":
    main()