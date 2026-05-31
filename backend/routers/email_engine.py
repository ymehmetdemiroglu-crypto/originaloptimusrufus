"""AI Email Engine router — conversational reply handling + AI-drafted responses.

Routes:
  POST /api/email-engine/classify         → Classify an inbound reply
  POST /api/email-engine/draft-reply      → Generate AI reply for a brand
  POST /api/email-engine/send-reply       → Send approved reply
  GET  /api/email-engine/conversations/{bk} → Full conversation thread
"""
import os
import json
import asyncio
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from middleware.auth import require_admin
from email_integration.conversation_drafter import ConversationDrafter

router = APIRouter(prefix="/api/email-engine", tags=["Email Engine"])

# Instantiate conversational email builder
drafter = ConversationDrafter()

import logging
from core.supabase import get_supabase


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class ClassifyRequest(BaseModel):
    brand_key: str
    reply_text: str


class DraftReplyRequest(BaseModel):
    brand_key: str
    reply_text: str  # The inbound reply to respond to
    conversation_context: list[dict] = []  # Prior messages in thread


class SendReplyRequest(BaseModel):
    brand_key: str
    reply_body: str
    subject: Optional[str] = None


# ---------------------------------------------------------------------------
# Conversational AI Drafter
# ---------------------------------------------------------------------------

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


async def _classify_reply(reply_text: str) -> dict:
    """Classify an inbound reply using OpenRouter."""
    import httpx
    
    api_key = os.getenv("OPENROUTER_API_KEY", "")
    model = os.getenv("OPENROUTER_DRAFT_MODEL", "deepseek/deepseek-chat-v3-0324")
    
    if not api_key:
        return {"category": "NOISE", "confidence": 0.0, "reason": "API key not configured"}
    
    classification_prompt = """You are an expert B2B sales reply classifier. Read the email reply and classify it into EXACTLY ONE category.

Categories:
- INTERESTED: Wants to learn more, asks about pricing, requests a call/demo, shows buying intent.
- OBJECTION: Raises a concern but hasn't shut the door.
- NOT_NOW: Timing is wrong, polite decline.
- BOOKING_READY: Explicitly wants to schedule a meeting/call.
- UNSUBSCRIBE: Asks to stop emailing, hostile.
- WRONG_PERSON: Not the right contact.
- COMPETITOR: From a competing agency.
- NOISE: Out-of-office, auto-reply, gibberish.

Output ONLY a JSON object:
{"category": "...", "confidence": 0.0-1.0, "reason": "one-sentence", "suggested_action": "one-sentence"}"""
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "max_tokens": 300,
                    "temperature": 0.2,
                    "messages": [
                        {"role": "system", "content": classification_prompt},
                        {"role": "user", "content": f"Reply to classify:\n\n{reply_text[:2000]}"},
                    ],
                },
            )
            resp.raise_for_status()
            data = resp.json()
            raw = (data["choices"][0]["message"]["content"] or "").strip()
            raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            result = json.loads(raw)
            
            cat = (result.get("category") or "NOISE").upper().strip()
            valid = {"INTERESTED", "OBJECTION", "NOT_NOW", "BOOKING_READY", "UNSUBSCRIBE", "WRONG_PERSON", "COMPETITOR", "NOISE"}
            if cat not in valid:
                cat = "NOISE"
            
            return {
                "category": cat,
                "confidence": float(result.get("confidence", 0.5)),
                "reason": result.get("reason", ""),
                "suggested_action": result.get("suggested_action", ""),
            }
    except Exception as e:
        return {"category": "NOISE", "confidence": 0.0, "reason": f"Classification failed: {e}"}


async def _generate_reply(
    brand_data: dict,
    prospect_data: Optional[dict],
    reply_text: str,
    conversation_context: list[dict],
    classification: dict,
) -> str:
    """Generate an AI reply that feels like a real human conversation."""
    import httpx
    
    api_key = os.getenv("OPENROUTER_API_KEY", "")
    model = os.getenv("OPENROUTER_DRAFT_MODEL", "deepseek/deepseek-chat-v3-0324")
    
    if not api_key:
        return ""
    
    # Build prospect context
    ctx_parts = [
        f"Brand: {brand_data.get('brand_name', 'Unknown')}",
        f"Contact: {brand_data.get('contact_first_name', 'there')}",
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
                logging.exception(f"Failed to parse weaknesses JSON for prospect ASIN {prospect_data.get('asin') if prospect_data else 'unknown'}")
    
    prospect_context = "\n".join(ctx_parts)
    
    # Build conversation history
    history_parts = []
    for msg in conversation_context[-6:]:
        direction = msg.get("direction", "outbound")
        body = msg.get("body", "")[:300]
        history_parts.append(f"{'Yahya' if direction == 'outbound' else brand_data.get('contact_first_name', 'Prospect')}: {body}")
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
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
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
    except Exception:
        logging.exception("Failed to generate reply using OpenRouter")
        return ""


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/classify", dependencies=[Depends(require_admin)])
async def classify_reply(request: ClassifyRequest):
    """Classify an inbound reply."""
    classification = await _classify_reply(request.reply_text)
    
    # Save to Supabase
    sb = get_supabase()
    if sb:
        try:
            sb.table("email_conversations").insert({
                "brand_key": request.brand_key,
                "direction": "inbound",
                "body": request.reply_text,
                "classification": classification,
                "status": "received",
            }).execute()
        except Exception:
            logging.exception(f"Failed to save inbound classification to email_conversations for brand {request.brand_key}")
    
    return classification


@router.post("/draft-reply", dependencies=[Depends(require_admin)])
async def draft_reply(request: DraftReplyRequest):
    """Generate an AI reply draft for an inbound message."""
    sb = get_supabase()
    if not sb:
        raise HTTPException(status_code=503, detail="Database not configured")
    
    # Fetch brand data
    brand_res = sb.table("brands").select("*").eq("brand_key", request.brand_key).limit(1).execute()
    if not brand_res.data:
        raise HTTPException(status_code=404, detail="Brand not found")
    brand_data = brand_res.data[0]
    
    # Fetch prospect data
    prospect_data = None
    asin = brand_data.get("anchor_asin")
    if asin and asin != "apollo_direct":
        p_res = sb.table("prospects").select("*").eq("asin", asin).limit(1).execute()
        if p_res.data:
            prospect_data = p_res.data[0]
    
    # Classify the reply
    classification = await _classify_reply(request.reply_text)
    
    # Generate AI reply using modular ConversationDrafter
    draft = await drafter.draft_response(
        brand_data=brand_data,
        prospect_data=prospect_data,
        reply_text=request.reply_text,
        conversation_context=request.conversation_context,
        classification=classification,
    )
    
    # Save conversation entries
    try:
        # Save inbound
        sb.table("email_conversations").insert({
            "brand_key": request.brand_key,
            "direction": "inbound",
            "body": request.reply_text,
            "classification": classification,
            "status": "received",
        }).execute()
        
        # Save AI draft
        if draft:
            sb.table("email_conversations").insert({
                "brand_key": request.brand_key,
                "direction": "outbound",
                "body": draft,
                "ai_draft": draft,
                "status": "pending",
            }).execute()
    except Exception:
        logging.exception(f"Failed to save conversation entries to email_conversations for brand {request.brand_key}")
    
    return {
        "brand_key": request.brand_key,
        "classification": classification,
        "draft_reply": draft,
        "status": "pending_approval",
    }


@router.post("/send-reply", dependencies=[Depends(require_admin)])
async def send_reply(request: SendReplyRequest):
    """Send an approved reply (placeholder — connect to SMTP or Apollo)."""
    sb = get_supabase()
    
    # For now, just mark as sent in DB
    if sb:
        try:
            sb.table("email_conversations").insert({
                "brand_key": request.brand_key,
                "direction": "outbound",
                "subject": request.subject,
                "body": request.reply_body,
                "status": "sent",
                "sent_at": datetime.utcnow().isoformat(),
            }).execute()
        except Exception:
            logging.exception(f"Failed to save sent email event to email_conversations for brand {request.brand_key}")
    
    # TODO: Connect to SMTP or Apollo API for actual sending
    
    return {
        "status": "sent",
        "brand_key": request.brand_key,
        "message": "Reply marked as sent. Connect SMTP for actual delivery.",
    }


@router.get("/conversations/{brand_key}", dependencies=[Depends(require_admin)])
async def get_conversations(brand_key: str):
    """Get full email conversation thread for a brand."""
    sb = get_supabase()
    if not sb:
        return {"brand_key": brand_key, "messages": []}
    
    try:
        res = sb.table("email_conversations").select("*").eq(
            "brand_key", brand_key
        ).order("created_at").execute()
        
        # Also fetch email step drafts
        steps = []
        try:
            steps_res = sb.table("email_steps").select("*").eq(
                "brand_key", brand_key
            ).order("step_num").execute()
            steps = steps_res.data or []
        except Exception:
            logging.exception(f"Failed to fetch sequence steps in get_conversations for brand {brand_key}")
        
        return {
            "brand_key": brand_key,
            "messages": res.data or [],
            "sequence_steps": steps,
        }
    except Exception as e:
        return {"brand_key": brand_key, "messages": [], "error": str(e)}
