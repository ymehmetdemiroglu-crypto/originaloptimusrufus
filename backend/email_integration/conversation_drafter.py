"""Conversational B2B Email reply drafter.

Generates highly personalized objection handling and nurture responses
that look and feel fully human and conversational.
"""
import os
import json
import httpx
import logging
from typing import Optional, List, Dict, Any

REPLY_SYSTEM_PROMPT = """You are Yahya, an Amazon listing optimization consultant. You are replying to an email from a brand founder/owner who received your cold outreach about their Amazon listing's Rufus AI visibility gaps.

YOUR VOICE:
- Warm, direct, and peer-to-peer — you're a fellow entrepreneur, not a salesperson
- Confident in your expertise but never arrogant
- Use their first name naturally
- Short paragraphs, 2-3 sentences each
- Sound like you're replying from your phone between calls — authentic, not polished

YOUR OBJECTIVE:
- Respond naturally to whatever they said
- If they're INTERESTED → share one more specific insight about their listing, then smoothly offer a 15-minute call with your booking link
- If they have an OBJECTION → acknowledge it genuinely, address it with evidence/logic, offer a low-commitment next step
- If they say NOT_NOW → be gracious, leave the door open, mention you'll keep their audit on file
- If they ask about PRICING → explain it depends on scope, suggest a quick call to scope it properly
- If they ask QUESTIONS → answer specifically using their listing data, then bridge back to the meeting
- If they are BOOKING_READY → confirm enthusiastically, share your direct calendar scheduling link and invite them to pick a slot

HARD RULES:
- NEVER sound like a template or a sequence — this is a 1:1 human conversation
- NEVER use words like: leverage, synergy, transform, seamlessly, unlock, game-changer
- NEVER write more than 120 words
- ALWAYS reference something specific about their listing (ASIN, weakness, score)
- Include your Calendly link ONLY when the conversation has reached a natural booking point
- Sign off with just "— Yahya" (no "Best regards" or "Looking forward to hearing from you")

THEIR LISTING DATA:
{prospect_context}

CONVERSATION SO FAR:
{conversation_history}

REPLY CLASSIFICATION:
Category: {classification_category}
Confidence: {classification_confidence}
Reason: {classification_reason}
"""

class ConversationDrafter:
    def __init__(self):
        self.api_key = os.getenv("OPENROUTER_API_KEY", "")
        self.model = os.getenv("OPENROUTER_DRAFT_MODEL", "deepseek/deepseek-chat-v3-0324")

    async def draft_response(
        self,
        brand_data: Dict[str, Any],
        prospect_data: Optional[Dict[str, Any]],
        reply_text: str,
        conversation_context: List[Dict[str, Any]],
        classification: Dict[str, Any]
    ) -> str:
        """Generate an AI-drafted reply that addresses objections or queries naturally."""
        if not self.api_key:
            return "Hi there, Yahya here. Thanks for your note! Let's schedule a brief 15-minute sync to walk through your listing's Rufus visibility and go over next steps. Here is my booking calendar link: " + os.getenv("CALENDLY_URL", "https://calendly.com/optimusrufus/audit")

        # 1. Format prospect details context
        ctx_parts = [
            f"Brand: {brand_data.get('brand_name', 'Unknown')}",
            f"Contact First Name: {brand_data.get('contact_first_name', 'there')}",
            f"Category: {brand_data.get('category', 'consumer product')}",
            f"Anchor ASIN: {brand_data.get('anchor_asin', 'N/A')}",
        ]
        
        if prospect_data:
            ctx_parts.append(f"Rufus Score: {prospect_data.get('rufus_score', '?')}/100")
            ctx_parts.append(f"Rufus Summary: {prospect_data.get('rufus_summary', 'N/A')}")
            weaknesses = prospect_data.get("rufus_top_weaknesses", "")
            if weaknesses:
                try:
                    parsed = json.loads(weaknesses) if isinstance(weaknesses, str) else weaknesses
                    for w in (parsed or [])[:3]:
                        ctx_parts.append(f"  Weakness: [{w.get('axis','')}] {w.get('issue','')}")
                except Exception:
                    pass
        
        prospect_context = "\n".join(ctx_parts)
        
        # 2. Format conversation logs
        history_parts = []
        for msg in conversation_context[-6:]:
            direction = msg.get("direction", "outbound")
            body = msg.get("body", "")[:300]
            speaker = "Yahya" if direction == "outbound" else brand_data.get("contact_first_name", "Prospect")
            history_parts.append(f"{speaker}: {body}")
        
        history_parts.append(f"{brand_data.get('contact_first_name', 'Prospect')}: {reply_text}")
        conversation_history = "\n\n".join(history_parts)
        
        calendly_url = os.getenv("CALENDLY_URL", "https://calendly.com/optimusrufus/audit")
        
        system = REPLY_SYSTEM_PROMPT.format(
            prospect_context=prospect_context,
            conversation_history=conversation_history,
            classification_category=classification.get("category", "UNKNOWN"),
            classification_confidence=classification.get("confidence", 0),
            classification_reason=classification.get("reason", ""),
        )
        system += f"\n\nCalendly booking link (use when appropriate): {calendly_url}"

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
                        "max_tokens": 400,
                        "temperature": 0.8,
                        "messages": [
                            {"role": "system", "content": system},
                            {"role": "user", "content": f"Write your reply to this email from {brand_data.get('contact_first_name', 'the prospect')}:\n\n{reply_text}"},
                        ],
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                return (data["choices"][0]["message"]["content"] or "").strip()
        except Exception as e:
            logging.error(f"Error generating email response draft: {e}")
            return f"Hi {brand_data.get('contact_first_name', 'there')},\n\nThanks for reaching back out! I'd love to chat more about this. Do you have 10-15 minutes next week? Here's my direct booking link to pick a slot: {calendly_url}\n\n— Yahya"
