"""RAG-powered AI chat router — conversational assistant on prospect landing pages.

Routes:
  POST /api/chat/{brand_key}         → Send message, get AI response
  GET  /api/chat/{brand_key}/history → Get conversation history
"""
import os
import json
import asyncio
import uuid
import time
from datetime import datetime
from typing import Optional
from collections import OrderedDict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from rag.knowledge_base import KnowledgeBaseBuilder
from rag.retriever import SemanticRetriever
from rag.generator import RAGGenerator

router = APIRouter(prefix="/api/chat", tags=["RAG Chat"])

# Instantiate RAG components
kb_builder = KnowledgeBaseBuilder()
retriever = SemanticRetriever()
generator = RAGGenerator()

import logging
from core.supabase import get_supabase


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None


class ChatMessage(BaseModel):
    role: str  # 'user' or 'assistant'
    content: str
    timestamp: str


class ChatResponse(BaseModel):
    conversation_id: str
    message: ChatMessage
    sources: list[str] = []


# ---------------------------------------------------------------------------
# In-memory conversation store (backed by Supabase when available)
# ---------------------------------------------------------------------------
_conversations: OrderedDict[str, list[dict]] = OrderedDict()
MAX_CONVERSATIONS = 1000

def _set_conversation(conv_id: str, data: list[dict]):
    if len(_conversations) >= MAX_CONVERSATIONS:
        _conversations.popitem(last=False)
    _conversations[conv_id] = data


_docs_cache: dict[str, list] = {}
_docs_cache_ttl: dict[str, float] = {}
DOCS_CACHE_TTL = 300.0

def _get_cached_docs(brand_key: str):
    now = time.time()
    if brand_key in _docs_cache and now - _docs_cache_ttl.get(brand_key, 0) < DOCS_CACHE_TTL:
        return _docs_cache[brand_key]
    return None

def _set_cached_docs(brand_key: str, docs: list):
    _docs_cache[brand_key] = docs
    _docs_cache_ttl[brand_key] = time.time()

# ---------------------------------------------------------------------------
# RAG System Prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are an AI assistant for Optimus Rufus, a premium Amazon listing optimization service powered by COSMO (Customer-Oriented Semantic Model for Optimization) analysis and Amazon's Rufus AI shopping assistant intelligence.

You are chatting with a prospect on their personalized audit landing page. You have access to their actual listing data, Rufus scores, and weakness analysis.

YOUR PERSONALITY:
- Consultative and knowledgeable — you understand Amazon SEO, Rufus AI, and listing optimization deeply
- Confident but not pushy — you share insights and let the data speak
- Specific and data-driven — always reference their actual scores and weaknesses, never generic advice
- Helpful and patient — answer questions thoroughly, even if they're skeptical
- Natural and human — use conversational language, not corporate jargon

YOUR OBJECTIVES:
1. Answer their questions about their listing audit, scores, and what the data means
2. Explain how Rufus AI works and why their listing underperforms
3. Share specific, actionable insights they could implement themselves (builds trust)
4. Naturally guide toward booking a meeting when they show interest (never force it)
5. Address objections with empathy and evidence

HARD RULES:
- NEVER make up data about their listing — only use what's provided in the context
- NEVER claim guaranteed results — speak in terms of "potential," "typically," "based on similar brands"
- ALWAYS be honest if you don't know something
- Keep responses concise — 2-4 sentences for simple questions, 4-8 for complex ones
- If they ask about pricing, say "pricing depends on the scope — a 15-minute call would help us scope that. Should I pull up the calendar?"
- Reference their specific ASIN, brand name, and weakness data when relevant

PROSPECT CONTEXT (from their audit):
{prospect_context}
"""


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/{brand_key}", response_model=ChatResponse)
async def send_message(brand_key: str, request: ChatRequest):
    """Send a message to the RAG-powered AI assistant."""
    sb = get_supabase()
    
    # Fetch prospect data for RAG context
    brand_data = {}
    prospect_data = None
    competitors = []
    
    if sb:
        try:
            brand_res = sb.table("brands").select("*").eq("brand_key", brand_key).limit(1).execute()
            if brand_res.data:
                brand_data = brand_res.data[0]
                
                anchor_asin = brand_data.get("anchor_asin")
                if anchor_asin and anchor_asin != "apollo_direct":
                    prospect_res = sb.table("prospects").select("*").eq("asin", anchor_asin).limit(1).execute()
                    if prospect_res.data:
                        prospect_data = prospect_res.data[0]
                
                comp_res = sb.table("competitors").select("*").eq("brand_key", brand_key).limit(3).execute()
                competitors = comp_res.data or []
        except Exception:
            logging.exception("Failed to retrieve prospect and brand RAG context from Supabase")
    
    if not brand_data:
        raise HTTPException(status_code=404, detail=f"Brand {brand_key} not found")
    
    # 1. Build semantic RAG documents from current state (cached)
    docs = _get_cached_docs(brand_key)
    if docs is None:
        docs = kb_builder.build_prospect_documents(brand_data, prospect_data, competitors)
        _set_cached_docs(brand_key, docs)
    
    # 2. Retrieve top-K relevant documents semantically
    retrieved_docs = await retriever.retrieve(request.message, docs, top_k=3)
    retrieved_doc_objects = [doc for doc, _ in retrieved_docs]
    sources = [doc.metadata.get("title", "General Info") for doc in retrieved_doc_objects]
    
    # Get or create conversation
    conv_id = request.conversation_id or str(uuid.uuid4())[:12]
    if conv_id not in _conversations:
        _set_conversation(conv_id, [])
    
    # Add user message
    now = datetime.utcnow().isoformat()
    user_msg = {"role": "user", "content": request.message, "timestamp": now}
    _conversations[conv_id].append(user_msg)
    
    # 3. Generate response using RAG generator
    retrieved_context_text = "\n\n".join(getattr(doc, "page_content", str(doc)) for doc in retrieved_doc_objects)
    formatted_system = SYSTEM_PROMPT.replace("{prospect_context}", retrieved_context_text)
    response_text = await generator.generate(_conversations[conv_id], retrieved_doc_objects, formatted_system)
    
    assistant_msg = {"role": "assistant", "content": response_text, "timestamp": datetime.utcnow().isoformat()}
    _conversations[conv_id].append(assistant_msg)
    
    # Persist to Supabase
    if sb:
        try:
            existing = sb.table("chat_sessions").select("id").eq("id", conv_id).limit(1).execute()
            if existing.data:
                sb.table("chat_sessions").update({
                    "messages": _conversations[conv_id],
                    "updated_at": datetime.utcnow().isoformat(),
                }).eq("id", conv_id).execute()
            else:
                sb.table("chat_sessions").insert({
                    "id": conv_id,
                    "brand_key": brand_key,
                    "messages": _conversations[conv_id],
                }).execute()
        except Exception:
            logging.exception(f"Failed to persist chat session {conv_id} to Supabase")
    
    return ChatResponse(
        conversation_id=conv_id,
        message=ChatMessage(
            role="assistant",
            content=response_text,
            timestamp=assistant_msg["timestamp"],
        ),
        sources=sources,
    )


@router.get("/{brand_key}/history")
async def get_history(brand_key: str, conversation_id: Optional[str] = None):
    """Get conversation history for a brand."""
    if conversation_id and conversation_id in _conversations:
        return {"conversation_id": conversation_id, "messages": _conversations[conversation_id]}
    
    # Try Supabase
    sb = get_supabase()
    if sb and conversation_id:
        try:
            res = sb.table("chat_sessions").select("*").eq("id", conversation_id).limit(1).execute()
            if res.data:
                return {"conversation_id": conversation_id, "messages": res.data[0].get("messages", [])}
        except Exception:
            logging.exception(f"Failed to fetch chat session history for {conversation_id}")
    
    return {"conversation_id": conversation_id or "", "messages": []}
