"""Reply Intelligence — classify inbound replies and auto-route them.

Categories:
  INTERESTED      → mark DEMO_SCHEDULED, alert Yahya
  OBJECTION       → generate objection-handling draft
  NOT_NOW         → snooze 90 days, nurture sequence
  UNSUBSCRIBE     → mark SKIP, log reason
  WRONG_PERSON    → find correct contact via Apollo, restart enrichment
  COMPETITOR      → mark SKIP, tag as competitor
  NOISE           → auto-archive, no action

Uses OpenRouter/Deepseek for classification (cheap, fast).
"""
import json
from datetime import datetime, timedelta
from typing import Optional

import httpx

import config
import db


CLASSIFICATION_PROMPT = """You are an expert B2B sales reply classifier. Read the email reply and classify it into EXACTLY ONE category.

Categories:
- BOOKING_READY: Prospect explicitly asks to book a call, wants a calendar link, says "send me the link", or agrees to meet at a specific time ("let's meet Tuesday at 2pm"). This is a highly critical signal.
- INTERESTED: Prospect wants to learn more, asks questions, asks about pricing, requests info/audit report, says "sounds good", or shows buying interest, but hasn't explicitly asked for a call link or scheduled meeting yet.
- OBJECTION: Prospect raises a concern (price too high, not the right time, already have a solution, need to check with team, etc.) but hasn't shut the door.
- NOT_NOW: Prospect is polite but says timing is wrong ("maybe next quarter", "reach out in 3 months", "too busy right now"). Different from OBJECTION because no specific concern is raised.
- UNSUBSCRIBE: Prospect asks to stop emailing, says "remove me", "unsubscribe", or is angry/hostile.
- WRONG_PERSON: Prospect says they're not the right contact, suggests someone else, or says they left the company.
- COMPETITOR: Prospect is from a competing agency, tries to sell something back, or is clearly not a prospect.
- NOISE: Out-of-office, automated reply, "received your email", "thank you", delivery failure, or gibberish.

Output ONLY a JSON object in this exact format:
{
  "category": "BOOKING_READY|INTERESTED|OBJECTION|NOT_NOW|UNSUBSCRIBE|WRONG_PERSON|COMPETITOR|NOISE",
  "confidence": 0.0-1.0,
  "reason": "one-sentence explanation",
  "suggested_action": "one-sentence recommended next step"
}

No preamble, no markdown, no commentary. Just the JSON object."""


OPENROUTER_CHAT_URL = f"{config.OPENROUTER_BASE_URL}/chat/completions"


def _openrouter_headers() -> dict:
    return {
        "Authorization": f"Bearer {config.OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }


def classify_reply(reply_text: str) -> dict:
    """Classify a single reply. Returns {category, confidence, reason, suggested_action}."""
    if not reply_text or not config.OPENROUTER_API_KEY:
        return {
            "category": "NOISE",
            "confidence": 1.0,
            "reason": "Empty reply or missing API key",
            "suggested_action": "Manual review required",
        }

    payload = {
        "model": config.OPENROUTER_DRAFT_MODEL,
        "max_tokens": 300,
        "temperature": 0.2,
        "messages": [
            {"role": "system", "content": CLASSIFICATION_PROMPT},
            {"role": "user", "content": f"Reply to classify:\n\n{reply_text[:2000]}"},
        ],
    }

    try:
        resp = httpx.post(OPENROUTER_CHAT_URL, headers=_openrouter_headers(), json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        raw = (data["choices"][0]["message"]["content"] or "").strip()
        # Strip markdown fences if present
        raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        result = json.loads(raw)
    except Exception as e:
        return {
            "category": "NOISE",
            "confidence": 0.0,
            "reason": f"Classification failed: {e}",
            "suggested_action": "Manual review required",
        }

    # Normalize category
    cat = (result.get("category") or "NOISE").upper().strip()
    valid = {"BOOKING_READY", "INTERESTED", "OBJECTION", "NOT_NOW", "UNSUBSCRIBE", "WRONG_PERSON", "COMPETITOR", "NOISE"}
    if cat not in valid:
        cat = "NOISE"

    return {
        "category": cat,
        "confidence": float(result.get("confidence", 0.5)),
        "reason": result.get("reason", ""),
        "suggested_action": result.get("suggested_action", ""),
    }


def apply_action(brand_key: str, classification: dict, reply_text: str, console=None) -> str:
    """Apply auto-action based on classification. Returns the new stage."""
    cat = classification["category"]
    now = datetime.utcnow().isoformat()

    if cat == "BOOKING_READY":
        db.update_brand_stage(brand_key, "DEMO_SCHEDULED")
        db.add_note_to_brand(brand_key, f"[AUTO] Reply classified as BOOKING_READY. Direct booking link requested. Reply: {reply_text[:200]}")
        # TODO: send Slack/email alert to Yahya to schedule immediate onboarding
        if console:
            console.print(f"  [green]→ DEMO_SCHEDULED[/green] (booking ready!)")
        return "DEMO_SCHEDULED"

    elif cat == "INTERESTED":
        db.update_brand_stage(brand_key, "DEMO_SCHEDULED")
        db.add_note_to_brand(brand_key, f"[AUTO] Reply classified as INTERESTED. Action: alert sent. Reply: {reply_text[:200]}")
        # TODO: send Slack/email alert to Yahya
        if console:
            console.print(f"  [green]→ DEMO_SCHEDULED[/green] (interested)")
        return "DEMO_SCHEDULED"

    elif cat == "OBJECTION":
        db.update_brand_stage(brand_key, "REPLIED")
        db.add_note_to_brand(brand_key, f"[AUTO] Reply classified as OBJECTION. Suggested: {classification.get('suggested_action', '')}. Reply: {reply_text[:200]}")
        if console:
            console.print(f"  [yellow]→ REPLIED[/yellow] (objection — draft handling recommended)")
        return "REPLIED"

    elif cat == "NOT_NOW":
        snooze_until = (datetime.utcnow() + timedelta(days=90)).isoformat()
        db.update_brand_stage(brand_key, "REPLIED")
        db.add_note_to_brand(brand_key, f"[AUTO] Reply classified as NOT_NOW. Snoozed until {snooze_until[:10]}. Reply: {reply_text[:200]}")
        if console:
            console.print(f"  [blue]→ REPLIED[/blue] (not now — snoozed 90 days)")
        return "REPLIED"

    elif cat == "UNSUBSCRIBE":
        db.update_brand_stage(brand_key, "SKIP")
        db.add_note_to_brand(brand_key, f"[AUTO] Reply classified as UNSUBSCRIBE. Removed from sequence. Reply: {reply_text[:200]}")
        if console:
            console.print(f"  [red]→ SKIP[/red] (unsubscribe)")
        return "SKIP"

    elif cat == "WRONG_PERSON":
        db.update_brand_stage(brand_key, "BRAND_RESOLVED")
        db.add_note_to_brand(brand_key, f"[AUTO] Reply classified as WRONG_PERSON. Cleared contact; re-enrichment needed. Reply: {reply_text[:200]}")
        # Clear contact data so re-enrichment can find the right person
        db.set_brand_enrichment(brand_key, contact_email=None, contact_first_name=None,
                                contact_last_name=None, contact_title=None)
        if console:
            console.print(f"  [yellow]→ BRAND_RESOLVED[/yellow] (wrong person — re-enrichment queued)")
        return "BRAND_RESOLVED"

    elif cat == "COMPETITOR":
        db.update_brand_stage(brand_key, "SKIP")
        db.add_note_to_brand(brand_key, f"[AUTO] Reply classified as COMPETITOR. Tagged and skipped. Reply: {reply_text[:200]}")
        if console:
            console.print(f"  [red]→ SKIP[/red] (competitor)")
        return "SKIP"

    else:  # NOISE
        db.add_note_to_brand(brand_key, f"[AUTO] Reply classified as NOISE. Auto-archived. Reply: {reply_text[:200]}")
        if console:
            console.print(f"  [dim]→ NOISE (auto-archived)[/dim]")
        return "NOISE"


def process_reply(brand_key: str, reply_text: str, console=None) -> dict:
    """Classify a reply and apply the appropriate auto-action."""
    classification = classify_reply(reply_text)
    new_stage = apply_action(brand_key, classification, reply_text, console=console)
    classification["new_stage"] = new_stage
    return classification
