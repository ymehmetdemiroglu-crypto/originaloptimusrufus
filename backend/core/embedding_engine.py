"""Google Gemini Embedding Engine with Two-Tier Caching (SQLite Tier-1 + Supabase Tier-2)."""

import hashlib
import sqlite3
import os
import logging
import asyncio
import threading
from pathlib import Path
import numpy as np
from typing import List, Optional, Literal

# Attempt to import google-genai
try:
    from google import genai
    from google.genai import types
    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False

from core.supabase import get_supabase

class GeminiEmbeddingEngine:
    DIMENSIONS = 3072
    
    def __init__(self, db_path: Optional[str] = None, api_key: Optional[str] = None):
        # Resolve absolute DB path relative to this file to prevent dependence on working directory
        if db_path is None:
            self.db_path = str(Path(__file__).resolve().parent.parent / "embedding_cache.db")
        else:
            self.db_path = db_path
            
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.mock_mode = os.getenv("MOCK_EMBEDDINGS", "false").lower() == "true"
        self.client = None
        self.lock = threading.Lock()
        
        if not self.mock_mode and HAS_GENAI and self.api_key:
            try:
                self.client = genai.Client(api_key=self.api_key)
            except Exception as e:
                logging.warning(f"Failed to initialize Gemini Client: {e}. Falling back to Mock.")
                
        # Initialize SQLite (Tier-1 Local Cache)
        self._conn = None
        self._init_db()
        
        # Initialize Supabase (Tier-2 Distributed Shared Cache)
        self.sb = get_supabase()
        if self.sb:
            logging.info("✅ Shared Embedding Cache (Tier-2 Supabase) integrated successfully.")
        else:
            logging.warning("⚠️ Shared Embedding Cache (Tier-2 Supabase) is not available. Falling back to local cache.")
        
    def _init_db(self):
        try:
            # Persistent SQLite connection with check_same_thread=False for high-concurrency event loops
            self._conn = sqlite3.connect(self.db_path, timeout=30.0, check_same_thread=False)
            with self.lock:
                self._conn.execute("PRAGMA journal_mode=WAL;")
                self._conn.execute("PRAGMA synchronous=NORMAL;")
                self._conn.execute("""
                    CREATE TABLE IF NOT EXISTS embedding_cache (
                        text_hash TEXT NOT NULL,
                        text_content TEXT,
                        dimensions INTEGER,
                        task_type TEXT,
                        vector BLOB,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(text_hash, dimensions, task_type)
                    )
                """)
                self._conn.execute("CREATE INDEX IF NOT EXISTS idx_hash_dims_task ON embedding_cache (text_hash, dimensions, task_type)")
                self._conn.commit()
        except Exception as e:
            logging.error(f"Error initializing SQLite cache: {e}")

    def _get_hash(self, text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    # --- Tier 1 (SQLite Local) Cache Reads/Writes ---
    def _read_cache_t1(self, text_hash: str, dimensions: int, task_type: str) -> Optional[np.ndarray]:
        if not self._conn:
            return None
        try:
            with self.lock:
                cursor = self._conn.cursor()
                cursor.execute(
                    "SELECT vector FROM embedding_cache WHERE text_hash = ? AND dimensions = ? AND task_type = ?",
                    (text_hash, dimensions, task_type)
                )
                row = cursor.fetchone()
                if row:
                    return np.frombuffer(row[0], dtype=np.float32)
        except Exception as e:
            logging.error(f"Tier-1 Cache read error: {e}")
        return None

    def _write_cache_t1(self, text_hash: str, text_content: str, dimensions: int, task_type: str, vector: np.ndarray):
        if not self._conn:
            return
        try:
            with self.lock:
                cursor = self._conn.cursor()
                cursor.execute(
                    "INSERT OR REPLACE INTO embedding_cache (text_hash, text_content, dimensions, task_type, vector) VALUES (?, ?, ?, ?, ?)",
                    (text_hash, text_content, dimensions, task_type, vector.tobytes())
                )
                cursor.execute("DELETE FROM embedding_cache WHERE created_at < datetime('now', '-30 days')")
                self._conn.commit()
        except Exception as e:
            logging.error(f"Tier-1 Cache write error: {e}")

    # --- Tier 2 (Supabase Central) Cache Reads/Writes ---
    def _read_cache_t2(self, text_hash: str, dimensions: int, task_type: str) -> Optional[np.ndarray]:
        if not self.sb:
            return None
        try:
            res = self.sb.table("embedding_cache").select("vector").eq("text_hash", text_hash).eq("dimensions", dimensions).eq("task_type", task_type).execute()
            if res.data:
                # Stored as float8[] dynamic array inside Postgres
                return np.array(res.data[0]["vector"], dtype=np.float32)
        except Exception as e:
            logging.warning(f"Tier-2 Supabase Cache read warning: {e}")
        return None

    def _write_cache_t2(self, text_hash: str, text_content: str, dimensions: int, task_type: str, vector: np.ndarray):
        if not self.sb:
            return
        try:
            # Dynamic upsert utilizing double precision list arrays
            self.sb.table("embedding_cache").upsert({
                "text_hash": text_hash,
                "text_content": text_content,
                "dimensions": dimensions,
                "task_type": task_type,
                "vector": vector.tolist()
            }).execute()
        except Exception as e:
            logging.warning(f"Tier-2 Supabase Cache write warning: {e}")

    # --- Embedding Computation ---
    def embed_single(
        self, 
        text: str, 
        dimensions: int = 768, 
        task_type: Literal["RETRIEVAL_DOCUMENT", "RETRIEVAL_QUERY", "SEMANTIC_SIMILARITY"] = "RETRIEVAL_DOCUMENT"
    ) -> np.ndarray:
        if not text or not text.strip():
            return np.zeros(dimensions, dtype=np.float32)
            
        text_hash = self._get_hash(text)
        
        # 1. Tier-1 (SQLite) Cache Check
        cached_vec = self._read_cache_t1(text_hash, dimensions, task_type)
        if cached_vec is not None:
            return cached_vec
            
        # 2. Tier-2 (Supabase) Cache Check
        cached_vec = self._read_cache_t2(text_hash, dimensions, task_type)
        if cached_vec is not None:
            # Write back to local cache to bypass network for subsequent reads
            self._write_cache_t1(text_hash, text, dimensions, task_type, cached_vec)
            return cached_vec
            
        # 3. Call Upgraded Gemini v2 API if available
        if not self.mock_mode and self.client:
            try:
                # Model generational upgrade: text-embedding-004
                result = self.client.models.embed_content(
                    model="text-embedding-004",
                    contents=text,
                    config=types.EmbedContentConfig(
                        task_type=task_type,
                        output_dimensionality=dimensions
                    )
                )
                if result and result.embeddings:
                    vec = np.array(result.embeddings[0].values, dtype=np.float32)
                    self._write_cache_t2(text_hash, text, dimensions, task_type, vec)
                    self._write_cache_t1(text_hash, text, dimensions, task_type, vec)
                    return vec
            except Exception as e:
                logging.warning(f"Gemini text-embedding-004 API Call failed: {e}. Trying OpenRouter fallback...")
                
        # Fallback to OpenRouter Embeddings if configured
        openrouter_key = None if self.mock_mode else os.getenv("OPENROUTER_API_KEY")
        if openrouter_key:
            try:
                import httpx
                resp = httpx.post(
                    "https://openrouter.ai/api/v1/embeddings",
                    headers={
                        "Authorization": f"Bearer {openrouter_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": "openai/text-embedding-3-small",
                        "input": text
                    },
                    timeout=15.0
                )
                if resp.status_code == 200:
                    raw_emb = resp.json()["data"][0]["embedding"]
                    vec = np.array(raw_emb, dtype=np.float32)
                    # Adjust dimensions to fit the requested target size (native is 1536)
                    if len(vec) < dimensions:
                        vec = np.pad(vec, (0, dimensions - len(vec)), "constant")
                    elif len(vec) > dimensions:
                        vec = vec[:dimensions]
                        norm = np.linalg.norm(vec)
                        if norm > 0:
                            vec = vec / norm
                    self._write_cache_t2(text_hash, text, dimensions, task_type, vec)
                    self._write_cache_t1(text_hash, text, dimensions, task_type, vec)
                    return vec
            except Exception as ex:
                logging.warning(f"OpenRouter embedding fallback failed: {ex}")
                
        # Fallback: Mock deterministic vector
        is_mock = True
        seed = int(text_hash[:16], 16)
        rng = np.random.default_rng(seed)
        vec = rng.standard_normal(dimensions).astype(np.float32)
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
            
        # Cache fallback vector to keep subsequent mock calls at sub-millisecond speeds
        if not is_mock:
            self._write_cache_t2(text_hash, text, dimensions, task_type, vec)
        self._write_cache_t1(text_hash, text, dimensions, task_type, vec)
        return vec

    async def async_embed_single(
        self, 
        text: str, 
        dimensions: int = 768, 
        task_type: Literal["RETRIEVAL_DOCUMENT", "RETRIEVAL_QUERY", "SEMANTIC_SIMILARITY"] = "RETRIEVAL_DOCUMENT"
    ) -> np.ndarray:
        """Async wrapper for embed_single to avoid blocking the event loop."""
        return await asyncio.to_thread(self.embed_single, text, dimensions, task_type)

    def embed_batch(
        self, 
        texts: List[str], 
        dimensions: int = 768,
        task_type: str = "RETRIEVAL_DOCUMENT"
    ) -> List[np.ndarray]:
        if not texts:
            return []

        results = [None] * len(texts)
        uncached_indices = []
        uncached_texts = []
        
        # 1. Tier-1 (SQLite) Local Cache Check
        for i, text in enumerate(texts):
            if not text or not text.strip():
                results[i] = np.zeros(dimensions, dtype=np.float32)
                continue
                
            text_hash = self._get_hash(text)
            cached_vec = self._read_cache_t1(text_hash, dimensions, task_type)
            if cached_vec is not None:
                results[i] = cached_vec
            else:
                uncached_indices.append(i)
                uncached_texts.append(text)
                
        # 2. Tier-2 (Supabase) Central Cache Check for Tier-1 misses
        if uncached_texts:
            tier2_miss_indices = []
            tier2_miss_texts = []
            
            for idx, text in zip(uncached_indices, uncached_texts):
                text_hash = self._get_hash(text)
                cached_vec = self._read_cache_t2(text_hash, dimensions, task_type)
                if cached_vec is not None:
                    # Write hit back to Tier-1
                    self._write_cache_t1(text_hash, text, dimensions, task_type, cached_vec)
                    results[idx] = cached_vec
                else:
                    tier2_miss_indices.append(idx)
                    tier2_miss_texts.append(text)
            
            # 3. Compute all residual cache misses
            if tier2_miss_texts:
                computed_vectors = []
                
                # Call text-embedding-004 API if available
                if not self.mock_mode and self.client:
                    try:
                        api_result = self.client.models.embed_content(
                            model="text-embedding-004",
                            contents=tier2_miss_texts,
                            config=types.EmbedContentConfig(
                                task_type=task_type,
                                output_dimensionality=dimensions
                            )
                        )
                        if api_result and api_result.embeddings:
                            computed_vectors = [np.array(emb.values, dtype=np.float32) for emb in api_result.embeddings]
                    except Exception as e:
                        logging.warning(f"Gemini API Batch Call failed: {e}. Trying OpenRouter fallback...")
                
                # OpenRouter fallback
                openrouter_key = None if self.mock_mode else os.getenv("OPENROUTER_API_KEY")
                if not computed_vectors and openrouter_key:
                    try:
                        import httpx
                        resp = httpx.post(
                            "https://openrouter.ai/api/v1/embeddings",
                            headers={
                                "Authorization": f"Bearer {openrouter_key}",
                                "Content-Type": "application/json"
                            },
                            json={
                                "model": "openai/text-embedding-3-small",
                                "input": tier2_miss_texts
                            },
                            timeout=30.0
                        )
                        if resp.status_code == 200:
                            data = resp.json()["data"]
                            for item in data:
                                raw_emb = item["embedding"]
                                vec = np.array(raw_emb, dtype=np.float32)
                                if len(vec) < dimensions:
                                    vec = np.pad(vec, (0, dimensions - len(vec)), "constant")
                                elif len(vec) > dimensions:
                                    vec = vec[:dimensions]
                                    norm = np.linalg.norm(vec)
                                    if norm > 0:
                                        vec = vec / norm
                                computed_vectors.append(vec)
                    except Exception as ex:
                        logging.warning(f"OpenRouter batch embedding fallback failed: {ex}")

                # Fallback: Mock generation for misses
                is_mock = False
                if not computed_vectors:
                    is_mock = True
                    for text in tier2_miss_texts:
                        text_hash = self._get_hash(text)
                        seed = int(text_hash[:16], 16)
                        rng = np.random.default_rng(seed)
                        vec = rng.standard_normal(dimensions).astype(np.float32)
                        norm = np.linalg.norm(vec)
                        if norm > 0:
                            vec = vec / norm
                        computed_vectors.append(vec)
                        
                # 4. Write back new computations to both Tier-2 and Tier-1
                for idx, text, vec in zip(tier2_miss_indices, tier2_miss_texts, computed_vectors):
                    text_hash = self._get_hash(text)
                    if not is_mock:
                        self._write_cache_t2(text_hash, text, dimensions, task_type, vec)
                    self._write_cache_t1(text_hash, text, dimensions, task_type, vec)
                    results[idx] = vec
                    
        return results

    async def async_embed_batch(
        self, 
        texts: List[str], 
        dimensions: int = 768,
        task_type: str = "RETRIEVAL_DOCUMENT"
    ) -> List[np.ndarray]:
        """Async wrapper for embed_batch to avoid blocking the event loop."""
        return await asyncio.to_thread(self.embed_batch, texts, dimensions, task_type)

    def compute_similarity(self, emb_a: np.ndarray, emb_b: np.ndarray) -> float:
        dot = np.dot(emb_a, emb_b)
        norm_a = np.linalg.norm(emb_a)
        norm_b = np.linalg.norm(emb_b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(dot / (norm_a * norm_b))

    def reduce_dimensions(self, embedding: np.ndarray, target_dims: int) -> np.ndarray:
        if target_dims >= len(embedding):
            return embedding
        reduced = embedding[:target_dims]
        norm = np.linalg.norm(reduced)
        if norm > 0:
            reduced = reduced / norm
        return reduced

    def __del__(self):
        try:
            if hasattr(self, "_conn") and self._conn:
                self._conn.close()
        except Exception:
            pass

# Shared global engine
engine = GeminiEmbeddingEngine()
