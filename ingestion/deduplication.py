"""Two-stage deduplication engine using cryptographic hashing and MinHashLSH."""
import hashlib
from typing import Set, Tuple
from datasketch import MinHash, MinHashLSH
from config import settings


def compute_sha256(content: str) -> str:
    """Stage 1: Cryptographic fingerprinting for exact duplicate detection."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


class LexicalDeduplicator:
    """Stage 2: Probabilistic similarity filtering using MinHashLSH."""

    def __init__(self):
        # Initialize LSH index with pre-defined permutation count and threshold [3]
        self.lsh_index = MinHashLSH(threshold=settings.DEDUP_JACCARD_THRESHOLD,
                                    perms=settings.NUM_PERM)
        self.processed_signatures: Set[str] = set()

    def _generate_shingles(self, text: str, n: int = 3) -> Set[str]:
        """Tokenizes text into n-gram shingles to preserve local context."""
        words = text.lower().split()
        return {" ".join(words[i:i + n]) for i in range(len(words) - n + 1)}

    def is_duplicate(self, content_hash: str, raw_text: str) -> bool:
        """Checks both exact hash match and lexical similarity threshold."""
        if content_hash in self.processed_signatures:
            return True

        # Compute MinHash signature for the new document
        shingles = self._generate_shingles(raw_text)
        minhash = MinHash(num_perm=settings.NUM_PERM)
        for shingle in shingles:
            minhash.update(shingle.encode("utf-8"))

        # Query LSH index for similar documents
        similar_docs = self.lsh_index.query(minhash)
        if similar_docs:
            return True

        # Register new signature and hash
        self.lsh_index.insert(content_hash, minhash)
        self.processed_signatures.add(content_hash)
        return False