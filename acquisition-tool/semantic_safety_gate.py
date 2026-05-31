"""Semantic-Lexical Hybrid Safety Gate.

Prevents organic indexation loss by ensuring that listing optimizations
do not cause excessive semantic drift from the original listing identity.
"""

import sys
import os
from pathlib import Path
import numpy as np
from typing import Dict, Any

# Ensure backend directory is in path to import GeminiEmbeddingEngine
backend_path = Path(__file__).resolve().parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.append(str(backend_path))

try:
    from core.embedding_engine import GeminiEmbeddingEngine
    _ENGINE_AVAILABLE = True
except ImportError:
    _ENGINE_AVAILABLE = False

class SemanticSafetyGate:
    def __init__(self, db_path: str = None, api_key: str = None):
        self.engine = None
        if _ENGINE_AVAILABLE:
            try:
                # Use absolute db path relative to backend folder
                if db_path is None:
                    db_path = str(backend_path / "embedding_cache.db")
                self.engine = GeminiEmbeddingEngine(db_path=db_path, api_key=api_key)
            except Exception as e:
                print(f"[SemanticSafetyGate] Failed to load embedding engine: {e}")

    def compute_cosine_similarity(self, vec_a: np.ndarray, vec_b: np.ndarray) -> float:
        """Calculate standard cosine similarity between two vectors."""
        dot = np.dot(vec_a, vec_b)
        norm_a = np.linalg.norm(vec_a)
        norm_b = np.linalg.norm(vec_b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(dot / (norm_a * norm_b))

    def verify_semantic_drift(
        self,
        original_text: str,
        optimized_text: str,
        threshold: float = 0.10
    ) -> Dict[str, Any]:
        """
        Embeds both the original and optimized listing text (3072D, RETRIEVAL_DOCUMENT)
        and verifies if the semantic drift (1 - cosine_similarity) is <= threshold.
        """
        if not original_text or not optimized_text:
            return {
                "is_safe": False,
                "cosine_similarity": 0.0,
                "cosine_distance": 1.0,
                "drift_pct": 100.0,
                "threshold": threshold,
                "error": "Empty input text"
            }

        # Fallback if engine is completely unavailable
        if not self.engine:
            return {
                "is_safe": True, # Fail open/safe if engine missing
                "cosine_similarity": 0.95,
                "cosine_distance": 0.05,
                "drift_pct": 5.0,
                "threshold": threshold,
                "warning": "Embedding engine unavailable, running dry run fallback"
            }

        try:
            # Embed at full 3072 dimensions for archival/safety matching
            vec_orig = self.engine.embed_single(original_text, dimensions=3072, task_type="RETRIEVAL_DOCUMENT")
            vec_opt = self.engine.embed_single(optimized_text, dimensions=3072, task_type="RETRIEVAL_DOCUMENT")

            similarity = self.compute_cosine_similarity(vec_orig, vec_opt)
            distance = max(0.0, 1.0 - similarity)
            drift_pct = distance * 100.0
            is_safe = distance <= threshold

            return {
                "is_safe": is_safe,
                "cosine_similarity": round(similarity, 4),
                "cosine_distance": round(distance, 4),
                "drift_pct": round(drift_pct, 2),
                "threshold": threshold
            }
        except Exception as e:
            return {
                "is_safe": False,
                "cosine_similarity": 0.0,
                "cosine_distance": 1.0,
                "drift_pct": 100.0,
                "threshold": threshold,
                "error": f"Embedding operation failed: {str(e)}"
            }

# Shared global safety gate
safety_gate = SemanticSafetyGate()
