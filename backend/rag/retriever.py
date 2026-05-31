"""Semantic retriever for RAG.

Utilizes the Gemini/OpenRouter embedding engine to perform semantic search
and cosine similarity matching on knowledge base documents.
"""
from typing import List, Dict, Any, Tuple
import numpy as np
from core.embedding_engine import engine
from rag.knowledge_base import RAGDocument

class SemanticRetriever:
    def __init__(self, dimensions: int = 1536):
        self.dimensions = dimensions

    async def retrieve(self, query: str, documents: List[RAGDocument], top_k: int = 3) -> List[Tuple[RAGDocument, float]]:
        """Retrieve the top-K most semantically relevant documents for a given query."""
        if not documents:
            return []

        # 1. Embed query
        query_vector = await engine.async_embed_single(query, dimensions=self.dimensions, task_type="RETRIEVAL_QUERY")

        # 2. Embed documents (batch processed for high efficiency)
        doc_contents = [doc.content for doc in documents]
        doc_vectors = await engine.async_embed_batch(doc_contents, dimensions=self.dimensions, task_type="RETRIEVAL_DOCUMENT")

        # 3. Calculate cosine similarity
        scored_docs = []
        for doc, doc_vector in zip(documents, doc_vectors):
            score = engine.compute_similarity(query_vector, doc_vector)
            scored_docs.append((doc, score))

        # 4. Sort and return top_k
        scored_docs.sort(key=lambda x: x[1], reverse=True)
        return scored_docs[:top_k]
