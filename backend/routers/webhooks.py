"""Webhooks router — receives events from Calendly and Apollo.

Routes:
  POST /api/webhooks/calendly  → Calendly booking events
  POST /api/webhooks/apollo    → Apollo sequence events (opens, clicks, replies)
"""
import os
import hmac
import hashlib
import time
import secrets
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from core.supabase import get_supabase

router = APIRouter(prefix="/api/webhooks", tags=["Webhooks"])

CALENDLY_WEBHOOK_SECRET = os.getenv("CALENDLY_WEBHOOK_SECRET", "")
APOLLO_WEBHOOK_SECRET = os.getenv("APOLLO_WEBHOOK_SECRET", "")


# ---------------------------------------------------------------------------
# Calendly webhook
# ---------------------------------------------------------------------------

@router.post("/calendly")
async def calendly_webhook(request: Request):
    """Handle Calendly booking events.
    
    Expected payload shape (Calendly v2 webhook):
    {
      "event": "invitee.created" | "invitee.canceled",
      "payload": {
        "event_type": {...},
        "invitee": {
          "email": "...",
          "name": "...",
          "questions_and_answers": [...]
        },
        "event": {
          "uuid": "...",
          "start_time": "...",
          "end_time": "..."
        }
      }
    }
    """
    if not CALENDLY_WEBHOOK_SECRET:
        raise HTTPException(status_code=501, detail="Webhook secret not configured")
    
    # Verify signature
    sig_header = request.headers.get("Calendly-Webhook-Signature", "")
    if not sig_header:
        logging.warning("Rejected Calendly webhook call: missing signature header")
        raise HTTPException(status_code=401, detail="Missing Calendly webhook signature")
    
    try:
        parts = sig_header.split(",")
        t_part = next(p for p in parts if p.startswith("t="))
        v1_part = next(p for p in parts if p.startswith("v1="))
        timestamp = t_part.split("=")[1]
        signature = v1_part.split("=")[1]
    except (StopIteration, IndexError):
        logging.warning("Rejected Calendly webhook call: invalid signature header format")
        raise HTTPException(status_code=400, detail="Invalid Calendly signature header format")
    
    # Prevent replay attacks (skew threshold of 5 minutes)
    try:
        t_val = float(timestamp)
        if abs(time.time() - t_val) > 300:
            logging.warning(f"Rejected Calendly webhook call: timestamp skew too large ({abs(time.time() - t_val)}s)")
            raise HTTPException(status_code=401, detail="Webhook signature timestamp is too old or in the future")
    except ValueError:
        logging.warning("Rejected Calendly webhook call: non-numeric timestamp")
        raise HTTPException(status_code=400, detail="Invalid timestamp in Calendly signature header")
        
    raw_body = await request.body()
    payload = f"{timestamp}.".encode() + raw_body
    expected = hmac.new(
        CALENDLY_WEBHOOK_SECRET.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()
    
    if not hmac.compare_digest(expected, signature):
        logging.warning("Rejected Calendly webhook call: signature mismatch")
        raise HTTPException(status_code=401, detail="Invalid webhook signature")
        
    body = await request.json()
    event_type = body.get("event", "")
    payload = body.get("payload", {})
    
    invitee = payload.get("invitee", {})
    invitee_email = invitee.get("email", "").lower().strip()
    invitee_name = invitee.get("name", "")
    
    event_data = payload.get("event", {})
    event_uuid = event_data.get("uuid", "")
    start_time = event_data.get("start_time", "")
    
    sb = get_supabase()
    if not sb:
        logging.error("Failed to process Calendly webhook: Supabase database client not configured")
        return {"status": "ok", "processed": False, "reason": "no database"}
    
    if event_type == "invitee.created":
        # Match invitee email to a brand in our system
        brand_key = None
        try:
            brand_res = sb.table("brands").select("brand_key, stage").eq(
                "contact_email", invitee_email
            ).limit(1).execute()
            
            if brand_res.data:
                brand_key = brand_res.data[0]["brand_key"]
                
                # Update brand stage
                sb.table("brands").update({
                    "stage": "MEETING_BOOKED",
                    "meeting_scheduled_at": start_time or datetime.utcnow().isoformat(),
                    "meeting_calendly_id": event_uuid,
                    "updated_at": datetime.utcnow().isoformat(),
                }).eq("brand_key", brand_key).execute()
        except Exception:
            logging.exception("Failed to update brand stage during Calendly webhook processing")
        
        # Save meeting record
        try:
            sb.table("meetings").upsert({
                "brand_key": brand_key,
                "calendly_event_id": event_uuid,
                "invitee_email": invitee_email,
                "invitee_name": invitee_name,
                "scheduled_at": start_time,
                "event_type": payload.get("event_type", {}).get("name", "Rufus Audit"),
                "status": "scheduled",
            }, on_conflict="calendly_event_id").execute()
        except Exception:
            logging.exception("Failed to upsert meeting record during Calendly webhook processing")
        
        return {
            "status": "ok",
            "event": "meeting_booked",
            "brand_key": brand_key,
            "invitee_email": invitee_email,
            "scheduled_at": start_time,
        }
    
    elif event_type == "invitee.canceled":
        # Update meeting status
        try:
            sb.table("meetings").update({
                "status": "cancelled",
            }).eq("calendly_event_id", event_uuid).execute()
            
            # Optionally revert brand stage
            meeting_res = sb.table("meetings").select("brand_key").eq(
                "calendly_event_id", event_uuid
            ).limit(1).execute()
            if meeting_res.data:
                brand_key = meeting_res.data[0].get("brand_key")
                if brand_key:
                    sb.table("brands").update({
                        "stage": "REPLIED",
                        "updated_at": datetime.utcnow().isoformat(),
                    }).eq("brand_key", brand_key).execute()
        except Exception:
            logging.exception("Failed to update meeting/brand cancel status during Calendly webhook processing")
        
        return {"status": "ok", "event": "meeting_cancelled"}
    
    return {"status": "ok", "event": event_type, "processed": False}


# ---------------------------------------------------------------------------
# Apollo webhook (sequence events)
# ---------------------------------------------------------------------------

@router.post("/apollo")
async def apollo_webhook(request: Request):
    """Handle Apollo sequence events — opens, clicks, replies.
    
    Note: Apollo's webhook format varies. This is a basic handler.
    """
    # Verify token if configured
    if APOLLO_WEBHOOK_SECRET:
        token = request.headers.get("X-Apollo-Token", "")
        if not token:
            auth_header = request.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                token = auth_header[7:]
        
        if not token or not secrets.compare_digest(token, APOLLO_WEBHOOK_SECRET):
            logging.warning("Rejected Apollo webhook call: unauthorized")
            raise HTTPException(status_code=401, detail="Unauthorized — invalid Apollo webhook token")
            
    body = await request.json()
    event_type = body.get("type", body.get("event", "unknown"))
    
    sb = get_supabase()
    if not sb:
        logging.error("Failed to process Apollo webhook: Supabase database client not configured")
        return {"status": "ok", "processed": False}
    
    # Log the event
    try:
        sb.table("landing_analytics").insert({
            "brand_key": body.get("brand_key", "apollo"),
            "event_type": f"apollo_{event_type}",
            "event_data": body,
        }).execute()
    except Exception:
        logging.exception("Failed to insert Apollo event into analytics database")
    
    return {"status": "ok", "event": event_type}
