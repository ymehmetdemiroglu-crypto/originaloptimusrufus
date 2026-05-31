"""RAG-powered Response Generator.

Uses retrieved context and system prompt to generate professional, natural,
and highly personalized responses via OpenRouter or LLM fallbacks.
"""
import os
import httpx
import logging
from typing import List, Dict, Any
from rag.knowledge_base import RAGDocument

class RAGGenerator:
    def __init__(self):
        self.api_key = os.getenv("OPENROUTER_API_KEY", "")
        self.model = os.getenv("CHAT_MODEL", os.getenv("OPENROUTER_DRAFT_MODEL", "deepseek/deepseek-chat-v3-0324"))

    async def generate(self, messages: List[Dict[str, str]], retrieved_docs: List[RAGDocument], system_prompt: str) -> str:
        """Generate response combining history, retrieved documents, and prompt templates."""
        if not self.api_key:
            return "I am currently running in offline demonstration mode. Please book a brief 15-minute call using the button below, and our team will walk you through the custom listing audit in detail!"

        # Construct retrieved context text
        context_parts = []
        for idx, doc in enumerate(retrieved_docs, 1):
            context_parts.append(f"--- Source {idx}: {doc.metadata.get('title', 'General Info')} ---\n{doc.content}")
        
        retrieved_context_text = "\n\n".join(context_parts)
        
        # Inject the retrieved context into system prompt
        formatted_system = system_prompt.format(prospect_context=retrieved_context_text)
        
        api_messages = [{"role": "system", "content": formatted_system}]
        
        # Keep last 10 messages to protect token count
        for msg in messages[-10:]:
            api_messages.append({"role": msg["role"], "content": msg["content"]})

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.model,
                        "max_tokens": 500,
                        "temperature": 0.7,
                        "messages": api_messages,
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                return (data["choices"][0]["message"]["content"] or "").strip()
        except Exception as e:
            logging.error(f"Error during RAG generation: {e}")
            return "I apologize, I'm having a brief connection issue. You can book a quick meeting using the booking calendar link above, and we can discuss your optimization questions live!"
