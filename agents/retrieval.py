"""Hybrid RRF search, cross-query deduplication, and LLM relevance filtering."""
import asyncio
from typing import List, Dict, Any
from sqlalchemy import select, text, func
from sqlalchemy.ext.asyncio import AsyncSession
from datasketch import MinHash, MinHashLSH
from config import settings
from database.models import Chunk


class HybridRetriever:
    """Executes parallel vector/lexical searches and merges results via Reciprocal Rank Fusion."""

    def __init__(self) -> None:
        # Initialize LSH index for cross-query deduplication
        self.lsh_index = MinHashLSH(threshold=settings.DEDUP_JACCARD_THRESHOLD,
                                    perms=settings.NUM_PERM)
        self.processed_hashes = set()

    async def execute_hybrid_search(self, session: AsyncSession, queries: List[str]) -> List[Dict[str, Any]]:
        """Runs concurrent vector and lexical searches for all expanded sub-queries."""
        all_candidates = []

        # Execute parallel retrieval tasks across all semantic angles
        tasks = [self._fetch_rrf_candidates(session, q) for q in queries]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for res in results:
            if isinstance(res, list):
                all_candidates.extend(res)

        # Apply cross-query deduplication before returning
        return self._deduplicate_candidates(all_candidates)

    async def _fetch_rrf_candidates(self, session: AsyncSession, query: str) -> List[Dict[str, Any]]:
        """Fetches top-K candidates via Vector and Lexical paths, then applies RRF scoring."""
        # 1. Vector Search (Cosine Similarity)
        vec_stmt = select(Chunk.id, Chunk.chunk_text, Chunk.header_hierarchy).where(
            Chunk.search_vector.isnot(None)
        ).order_by(
            text(f"embedding <=> '{self._escape_sql(query)}'::vector")
        ).limit(settings.TOP_K)

        # 2. Lexical Search (GIN Index / tsvector)
        lex_stmt = select(Chunk.id, Chunk.chunk_text, Chunk.header_hierarchy).where(
            text(f"search_vector @@ websearch_to_tsquery('english', '{self._escape_sql(query)}')")
        ).order_by(
            text(f"ts_rank(search_vector, websearch_to_tsquery('english', '{self._escape_sql(query)}')) DESC")
        ).limit(settings.TOP_K)

        vec_res = await session.scalars(vec_stmt)
        lex_res = await session.scalars(lex_stmt)

        # Merge via Reciprocal Rank Fusion
        return self._apply_rrf(list(vec_res), list(lex_res))

    def _apply_rrf(self, vec_results: List[Chunk], lex_results: List[Chunk]) -> List[Dict[str, Any]]:
        """Merges two ranked lists using Score = Σ(1 / (K + rank_i))."""
        scores: Dict[str, float] = {}
        chunks_map: Dict[str, Chunk] = {}

        for rank, chunk in enumerate(vec_results, start=1):
            cid = str(chunk.id)
            scores[cid] = scores.get(cid, 0.0) + (1.0 / (settings.RRF_K_CONSTANT + rank))
            chunks_map[cid] = chunk

        for rank, chunk in enumerate(lex_results, start=1):
            cid = str(chunk.id)
            scores[cid] = scores.get(cid, 0.0) + (1.0 / (settings.RRF_K_CONSTANT + rank))
            if cid not in chunks_map:
                chunks_map[cid] = chunk

        # Sort by descending RRF score and format for downstream consumption
        sorted_chunks = sorted(chunks_map.items(), key=lambda x: scores[x[0]], reverse=True)
        return [
            {"id": cid, "text": c.chunk_text, "hierarchy": c.header_hierarchy, "score": s}
            for cid, c in sorted_chunks for s in [scores[cid]]
        ]

    def _deduplicate_candidates(self, candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Filters near-duplicate passages using MinHashLSH to preserve lexical diversity."""
        unique_candidates = []

        for cand in candidates:
            shingles = self._generate_shingles(cand["text"])
            minhash = MinHash(num_perm=settings.NUM_PERM)
            for s in shingles:
                minhash.update(s.encode("utf-8"))

            # Query LSH index; if similar, skip to prevent redundancy
            if not self.lsh_index.query(minhash):
                unique_candidates.append(cand)
                self.lsh_index.insert(str(cand["id"]), minhash)

        return unique_candidates

    def _generate_shingles(self, text: str, n: int = 3) -> set:
        """Tokenizes text into n-gram shingles for probabilistic hashing."""
        words = text.lower().split()
        return {" ".join(words[i:i + n]) for i in range(len(words) - n + 1)}

    def _escape_sql(self, val: str) -> str:
        """Basic SQL string escaping to prevent injection in raw text fragments."""
        return val.replace("'", "''")