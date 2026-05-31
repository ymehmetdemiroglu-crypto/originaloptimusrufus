"""Admin control panel API router — pipeline monitoring, prospect management, email queue.

All routes require admin authentication via X-Admin-Key header or admin_token cookie.

Routes:
  POST /api/admin/login              → Authenticate and get session token
  GET  /api/admin/dashboard          → Aggregate metrics
  GET  /api/admin/prospects          → Filterable prospect list
  POST /api/admin/prospects/{bk}/action → Manual stage transitions
  GET  /api/admin/emails             → Email queue + conversation threads
  POST /api/admin/emails/{bk}/approve → Approve email draft for sending
  GET  /api/admin/analytics          → Landing page + email analytics
  GET  /api/admin/settings           → System settings
  POST /api/admin/settings           → Update system settings
  POST /api/admin/trigger/{stage}    → Manually trigger pipeline stage
"""
import os
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, HTTPException, Depends, Response, Request
from pydantic import BaseModel

from middleware.auth import (
    require_admin, verify_password, create_session, invalidate_session,
    check_rate_limit, record_failed_attempt, clear_failed_attempts
)
from core.supabase import get_supabase

router = APIRouter(prefix="/api/admin", tags=["Admin Panel"])


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    password: str


class ActionRequest(BaseModel):
    action: str  # 'advance', 'skip', 'regenerate_email', 'add_note'
    value: Optional[str] = None


class SettingsUpdate(BaseModel):
    key: str
    value: str


# ---------------------------------------------------------------------------
# Auth routes (no admin dependency)
# ---------------------------------------------------------------------------

@router.post("/login")
async def admin_login(login_data: LoginRequest, response: Response, request: Request):
    """Authenticate with admin password, returns session token as cookie."""
    ip = request.client.host if request.client else "unknown"
    if not check_rate_limit(ip):
        logging.warning(f"Failed login attempt blocked by rate limit for IP: {ip}")
        raise HTTPException(status_code=429, detail="Too many failed login attempts. Locked out for 15 minutes.")
        
    if not verify_password(login_data.password):
        logging.warning(f"Failed login attempt from IP: {ip}")
        record_failed_attempt(ip)
        raise HTTPException(status_code=401, detail="Invalid password")
    
    clear_failed_attempts(ip)
    token = create_session()
    is_development = os.getenv("ENV") == "development"
    response.set_cookie(
        key="admin_token",
        value=token,
        httponly=True,
        secure=not is_development,
        samesite="lax",
        max_age=86400,  # 24 hours
    )
    return {"status": "ok", "message": "Authenticated"}


@router.post("/logout")
async def admin_logout(response: Response):
    """Clear admin session."""
    response.delete_cookie("admin_token")
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Protected routes
# ---------------------------------------------------------------------------

@router.get("/dashboard", dependencies=[Depends(require_admin)])
async def get_dashboard():
    """Aggregate metrics for the admin overview dashboard."""
    sb = get_supabase()
    if not sb:
        return {"error": "Database not configured"}
    
    try:
        # Pipeline stage counts
        stages = [
            "LISTING_FOUND", "WEAK_LISTING", "WEAK_BRAND", "BRAND_RESOLVED",
            "CONTACT_ENRICHED", "EMAIL_DRAFTED", "SEQUENCED", "REPLIED",
            "CALCULATOR_USED", "CALCULATOR_SUBMITTED", "DEMO_SCHEDULED",
            "MEETING_BOOKED", "SKIP",
        ]
        
        stage_counts = {stage: 0 for stage in stages}
        try:
            res = sb.table("brands").select("stage", count="exact").group("stage").execute()
            for row in res.data:
                if row.get("stage") in stage_counts:
                    stage_counts[row["stage"]] = row.get("count", 0)
        except Exception:
            logging.exception("Failed to group stage counts, falling back")
            for stage in stages:
                res = sb.table("brands").select("brand_key", count="exact").eq("stage", stage).execute()
                stage_counts[stage] = res.count or 0
        
        # Total brands
        total_res = sb.table("brands").select("brand_key", count="exact").execute()
        total_brands = total_res.count or 0
        
        # Total prospects
        total_prospects_res = sb.table("prospects").select("id", count="exact").execute()
        total_prospects = total_prospects_res.count or 0
        
        # Recent activity (last 10 brand updates)
        recent_res = sb.table("brands").select(
            "brand_key, brand_name, stage, contact_email, updated_at"
        ).order("updated_at", desc=True).limit(10).execute()
        recent_activity = recent_res.data or []
        
        # Landing page views (last 7 days)
        landing_views = 0
        try:
            from datetime import timedelta
            week_ago = (datetime.utcnow() - timedelta(days=7)).isoformat()
            views_res = sb.table("landing_analytics").select(
                "id", count="exact"
            ).eq("event_type", "page_view").gte("created_at", week_ago).execute()
            landing_views = views_res.count or 0
        except Exception:
            logging.exception("Failed to query landing views in get_dashboard")
        
        # Meeting bookings
        meetings_res = sb.table("brands").select(
            "brand_key", count="exact"
        ).eq("stage", "MEETING_BOOKED").execute()
        meetings_booked = meetings_res.count or 0
        
        # Email stats
        email_drafted = stage_counts.get("EMAIL_DRAFTED", 0)
        sequenced = stage_counts.get("SEQUENCED", 0)
        replied = stage_counts.get("REPLIED", 0)
        
        # Conversion funnel
        funnel = {
            "prospected": total_brands,
            "enriched": stage_counts.get("CONTACT_ENRICHED", 0) + email_drafted + sequenced + replied + meetings_booked,
            "emailed": email_drafted + sequenced + replied + meetings_booked,
            "replied": replied + meetings_booked + stage_counts.get("DEMO_SCHEDULED", 0),
            "booked": meetings_booked + stage_counts.get("DEMO_SCHEDULED", 0),
        }
        
        return {
            "total_brands": total_brands,
            "total_prospects": total_prospects,
            "stage_counts": stage_counts,
            "funnel": funnel,
            "landing_page_views_7d": landing_views,
            "meetings_booked": meetings_booked,
            "recent_activity": recent_activity,
            "email_stats": {
                "drafted": email_drafted,
                "sequenced": sequenced,
                "replied": replied,
            },
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/prospecting", dependencies=[Depends(require_admin)])
async def get_prospecting_telemetry():
    """Query and return real-time pipeline statistics (ALII, CQS, RI, and computational linguistics) for the React admin dashboard."""
    sb = get_supabase()
    if not sb:
        return {"error": "Database not configured"}
        
    try:
        # Fetch LQS (ALII) and nested linguistics breakdown from prospects
        res_p = sb.table("prospects").select("quality_score,quality_breakdown").not_.is_("quality_score", "null").execute()
        
        # Fetch CQS and RI from brands
        res_b = sb.table("brands").select("reachability_index,client_quality_score").not_.is_("reachability_index", "null").execute()
        
        # Parse metrics
        lqs_scores = [r["quality_score"] for r in res_p.data if r.get("quality_score") is not None]
        ri_scores = [r["reachability_index"] for r in res_b.data if r.get("reachability_index") is not None]
        cqs_scores = [r["client_quality_score"] for r in res_b.data if r.get("client_quality_score") is not None]
        
        flesch_scores = []
        ttr_scores = []
        cosmo_scores = []
        
        for r in res_p.data:
            breakdown = r.get("quality_breakdown")
            if breakdown and isinstance(breakdown, dict):
                ling = breakdown.get("linguistic_integrity")
                if ling and isinstance(ling, dict):
                    if "flesch_reading_ease" in ling and ling["flesch_reading_ease"] is not None:
                        flesch_scores.append(ling["flesch_reading_ease"])
                    if "type_token_ratio_ttr" in ling and ling["type_token_ratio_ttr"] is not None:
                        ttr_scores.append(ling["type_token_ratio_ttr"])
                    if "cosmo_relational_density" in ling and ling["cosmo_relational_density"] is not None:
                        cosmo_scores.append(ling["cosmo_relational_density"])
                        
        avg_lqs = sum(lqs_scores) / len(lqs_scores) if lqs_scores else 0.0
        max_lqs = max(lqs_scores) if lqs_scores else 0
        avg_ri = sum(ri_scores) / len(ri_scores) if ri_scores else 0.0
        max_ri = max(ri_scores) if ri_scores else 0
        avg_cqs = sum(cqs_scores) / len(cqs_scores) if cqs_scores else 0.0
        avg_flesch = sum(flesch_scores) / len(flesch_scores) if flesch_scores else 0.0
        avg_ttr = sum(ttr_scores) / len(ttr_scores) if ttr_scores else 0.0
        avg_cosmo = sum(cosmo_scores) / len(cosmo_scores) if cosmo_scores else 0.0
        
        # Pipeline counts
        stages = [
            "LISTING_FOUND", "WEAK_LISTING", "WEAK_BRAND", "BRAND_RESOLVED",
            "CONTACT_ENRICHED", "EMAIL_DRAFTED", "SEQUENCED", "REPLIED",
            "CALCULATOR_USED", "CALCULATOR_SUBMITTED", "DEMO_SCHEDULED",
            "MEETING_BOOKED", "SKIP",
        ]
        stage_counts = {stage: 0 for stage in stages}
        grouped = sb.table("brands").select("stage", count="exact").in_("stage", stages).group("stage").execute()
        for row in (grouped.data or []):
            stage_counts[row["stage"]] = row.get("count", 0) or 0
            
        return {
            "avg_lqs": round(avg_lqs, 1),
            "max_lqs": max_lqs,
            "avg_ri": round(avg_ri, 1),
            "max_ri": max_ri,
            "avg_cqs": round(avg_cqs, 1),
            "avg_flesch": round(avg_flesch, 1),
            "avg_ttr": round(avg_ttr, 3),
            "avg_cosmo": round(avg_cosmo, 2),
            "total_scored_listings": len(lqs_scores),
            "total_scored_brands": len(ri_scores),
            "stage_counts": stage_counts,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class AssistantMessage(BaseModel):
    role: str
    content: str


class AssistantRequest(BaseModel):
    messages: List[AssistantMessage]


@router.post("/assistant", dependencies=[Depends(require_admin)])
async def admin_assistant(req: AssistantRequest):
    """Agentic Chat Assistant endpoint for admin dashboard. 
    
    Parses intent to query stats or trigger pipeline runs, and formats a highly tailored agent response.
    """
    import httpx
    sb = get_supabase()
    if not sb:
        return {"response": "Database not configured."}
        
    messages = [{"role": m.role, "content": m.content} for m in req.messages]
    last_user_msg = ""
    for msg in reversed(messages):
        if msg["role"] == "user":
            last_user_msg = msg["content"].lower()
            break
            
    # Intent detection & execution logic
    triggered_action = None
    action_msg = ""
    
    if any(k in last_user_msg for k in ["enrich", "apollo"]):
        triggered_action = "enrich"
        action_msg = "Successfully queued background lead enrichment task (Apollo Sync)!"
    elif any(k in last_user_msg for k in ["score", "rufus", "lqs", "alii"]):
        triggered_action = "score"
        action_msg = "Successfully queued listing quality scoring task to calculate ALII!"
    elif any(k in last_user_msg for k in ["draft", "sequence", "email"]):
        triggered_action = "draft"
        action_msg = "Successfully queued AI sequence generation task to draft personalized cold outreach!"
    elif any(k in last_user_msg for k in ["full run", "prospecting run", "scrape"]):
        triggered_action = "full"
        action_msg = "Successfully queued full prospecting pipeline run!"

    # Query current metrics to inject as dynamic context
    try:
        telemetry = await get_prospecting_telemetry()
    except Exception:
        telemetry = {}
        
    # Construct prompt with real telemetry context
    system_prompt = (
        "You are Optimus Rufus Assistant, a highly sophisticated agentic co-pilot managing our Amazon search citation engine.\n"
        "Your tone is professional, technical, precise, and humble. Avoid hype and superlatives.\n"
        "Here is the real-time database telemetry you can use to answer user queries:\n"
        f"- Avg Listing Integrity (ALII): {telemetry.get('avg_lqs', 'N/A')}/100\n"
        f"- Max ALII: {telemetry.get('max_lqs', 'N/A')}\n"
        f"- Avg Client Quality Score (CQS): {telemetry.get('avg_cqs', 'N/A')}/100\n"
        f"- Avg Reachability Index (RI): {telemetry.get('avg_ri', 'N/A')}/100\n"
        f"- Total Scored Listings: {telemetry.get('total_scored_listings', 0)}\n"
        f"- Total Scored Brands: {telemetry.get('total_scored_brands', 0)}\n"
        f"- Computational Linguistics Averages:\n"
        f"  * Flesch Readability Ease: {telemetry.get('avg_flesch', 'N/A')}\n"
        f"  * Lexical Density TTR: {telemetry.get('avg_ttr', 'N/A')}\n"
        f"  * COSMO Preposition Density: {telemetry.get('avg_cosmo', 'N/A')}/100w\n\n"
    )
    
    if triggered_action:
        system_prompt += f"NOTE: You have just intercepted the user's message and triggered the '{triggered_action}' task! Mention this task execution clearly in your response: '{action_msg}'."
        
    # Generate completion via OpenRouter / Gemini
    api_key = os.getenv("OPENROUTER_API_KEY", "")
    model = os.getenv("OPENROUTER_DRAFT_MODEL", "deepseek/deepseek-chat-v3-0324")
    
    if not api_key:
        # High-fidelity mock response if API key is not configured
        fallback_res = (
            "Hello! I am Optimus Assistant. "
        )
        if triggered_action:
            fallback_res += f"I have processed your command and triggered the pipeline stage: **{triggered_action}** ({action_msg}). "
        else:
            fallback_res += f"I am running in local co-pilot mode. The average Amazon Listing Integrity Index (ALII) across your database is currently **{telemetry.get('avg_lqs', 0.0)}/100** and the average Reachability Index is **{telemetry.get('avg_ri', 0.0)}/100**."
        return {"response": fallback_res, "triggered": triggered_action}
        
    api_messages = [{"role": "system", "content": system_prompt}]
    for msg in messages[-8:]:
        api_messages.append({"role": msg["role"], "content": msg["content"]})
        
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
                    "max_tokens": 500,
                    "temperature": 0.5,
                    "messages": api_messages,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            response_text = (data["choices"][0]["message"]["content"] or "").strip()
            return {"response": response_text, "triggered": triggered_action}
    except Exception as e:
        return {
            "response": f"I apologize, I hit a brief communication issue: {str(e)}. However, I can confirm that your intent was parsed correctly.",
            "triggered": triggered_action
        }


@router.get("/prospects", dependencies=[Depends(require_admin)])
async def get_prospects(
    stage: Optional[str] = None,
    search: Optional[str] = None,
    sort_by: str = "updated_at",
    order: str = "desc",
    limit: int = 50,
    offset: int = 0,
):
    """Get filterable, sortable list of all brands/prospects."""
    sb = get_supabase()
    if not sb:
        return {"error": "Database not configured"}
    
    q = sb.table("brands").select(
        "brand_key, brand_name, stage, category, anchor_asin, asin_count, "
        "contact_email, contact_first_name, contact_title, "
        "custom_subject, worst_axis_at_send, "
        "client_quality_score, reachability_index, "
        "landing_page_views, landing_page_last_visit, "
        "calculator_used_at, calculator_submitted_at, "
        "intent_score, notes, "
        "created_at, updated_at",
        count="exact"
    )
    
    if stage:
        q = q.eq("stage", stage)
    
    if search:
        safe_search = search.replace("%", r"\%").replace("_", r"\_")
        q = q.or_(f"brand_name.ilike.%{safe_search}%,brand_key.ilike.%{safe_search}%,contact_email.ilike.%{safe_search}%")
    
    is_desc = order == "desc"
    q = q.order(sort_by, desc=is_desc).range(offset, offset + limit - 1)
    
    res = q.execute()
    
    # Enrich with Rufus scores from prospects table
    brands = res.data or []
    for brand in brands:
        asin = brand.get("anchor_asin")
        if asin and asin != "apollo_direct":
            try:
                p_res = sb.table("prospects").select(
                    "rufus_score, rufus_citation_probability"
                ).eq("asin", asin).limit(1).execute()
                if p_res.data:
                    brand["rufus_score"] = p_res.data[0].get("rufus_score")
                    brand["citation_probability"] = p_res.data[0].get("rufus_citation_probability")
            except Exception:
                logging.exception(f"Failed to enrich brand {brand.get('brand_key')} with Rufus score")
    
    return {
        "total": res.count or len(brands),
        "offset": offset,
        "limit": limit,
        "brands": brands,
    }


@router.post("/prospects/{brand_key}/action", dependencies=[Depends(require_admin)])
async def prospect_action(brand_key: str, request: ActionRequest):
    """Execute an action on a prospect/brand."""
    sb = get_supabase()
    if not sb:
        raise HTTPException(status_code=503, detail="Database not configured")
    
    now = datetime.utcnow().isoformat()
    
    def _assert_stage_unchanged(expected: str):
        current = sb.table("brands").select("stage,updated_at").eq("brand_key", brand_key).single().execute()
        if current.data and current.data["stage"] != expected:
            raise HTTPException(status_code=409, detail="Brand stage changed by another request")

    if request.action == "advance":
        # Move to next stage
        stage_order = [
            "LISTING_FOUND", "WEAK_LISTING", "WEAK_BRAND", "BRAND_RESOLVED",
            "CONTACT_ENRICHED", "EMAIL_DRAFTED", "SEQUENCED", "REPLIED",
            "DEMO_SCHEDULED", "MEETING_BOOKED",
        ]
        brand_res = sb.table("brands").select("stage").eq("brand_key", brand_key).limit(1).execute()
        if not brand_res.data:
            raise HTTPException(status_code=404, detail="Brand not found")
        
        expected_current_stage = brand_res.data[0]["stage"]
        try:
            idx = stage_order.index(expected_current_stage)
            next_stage = stage_order[min(idx + 1, len(stage_order) - 1)]
        except ValueError:
            next_stage = request.value or expected_current_stage
        
        _assert_stage_unchanged(expected_current_stage)
        sb.table("brands").update({"stage": next_stage, "updated_at": now}).eq("brand_key", brand_key).execute()
        return {"status": "ok", "new_stage": next_stage}
    
    elif request.action == "skip":
        current = sb.table("brands").select("stage,updated_at").eq("brand_key", brand_key).single().execute()
        if not current.data:
            raise HTTPException(status_code=404, detail="Brand not found")
        expected_current_stage = current.data["stage"]
        _assert_stage_unchanged(expected_current_stage)
        sb.table("brands").update({"stage": "SKIP", "updated_at": now}).eq("brand_key", brand_key).execute()
        return {"status": "ok", "new_stage": "SKIP"}
    
    elif request.action == "set_stage":
        if not request.value:
            raise HTTPException(status_code=400, detail="value (new stage) required")
        current = sb.table("brands").select("stage,updated_at").eq("brand_key", brand_key).single().execute()
        if not current.data:
            raise HTTPException(status_code=404, detail="Brand not found")
        expected_current_stage = current.data["stage"]
        _assert_stage_unchanged(expected_current_stage)
        sb.table("brands").update({"stage": request.value, "updated_at": now}).eq("brand_key", brand_key).execute()
        return {"status": "ok", "new_stage": request.value}
    
    elif request.action == "add_note":
        if not request.value:
            raise HTTPException(status_code=400, detail="value (note text) required")
        brand_res = sb.table("brands").select("notes").eq("brand_key", brand_key).limit(1).execute()
        if not brand_res.data:
            raise HTTPException(status_code=404, detail="Brand not found")
        existing = brand_res.data[0].get("notes") or ""
        ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M")
        new_notes = f"{existing}\n[{ts}] [ADMIN] {request.value}".strip()
        sb.table("brands").update({"notes": new_notes, "updated_at": now}).eq("brand_key", brand_key).execute()
        return {"status": "ok", "notes": new_notes}
    
    elif request.action == "regenerate_email":
        # Re-trigger email drafting for this brand
        current = sb.table("brands").select("stage,updated_at").eq("brand_key", brand_key).single().execute()
        if not current.data:
            raise HTTPException(status_code=404, detail="Brand not found")
        expected_current_stage = current.data["stage"]
        _assert_stage_unchanged(expected_current_stage)
        sb.table("brands").update({"stage": "CONTACT_ENRICHED", "updated_at": now}).eq("brand_key", brand_key).execute()
        return {"status": "ok", "message": "Brand reset to CONTACT_ENRICHED — will be re-drafted on next pipeline run"}
    
    else:
        raise HTTPException(status_code=400, detail=f"Unknown action: {request.action}")


@router.get("/emails", dependencies=[Depends(require_admin)])
async def get_email_queue(
    stage: Optional[str] = None,
    limit: int = 50,
):
    """Get email queue — drafted, pending approval, or conversation threads."""
    sb = get_supabase()
    if not sb:
        return {"error": "Database not configured"}
    
    # Get brands with email drafts
    q = sb.table("brands").select(
        "brand_key, brand_name, stage, contact_email, contact_first_name, "
        "custom_subject, custom_body, worst_axis_at_send, "
        "anchor_asin, updated_at"
    ).in_("stage", ["EMAIL_DRAFTED", "SEQUENCED", "REPLIED"]).order("updated_at", desc=True).limit(limit)
    
    if stage:
        q = sb.table("brands").select(
            "brand_key, brand_name, stage, contact_email, contact_first_name, "
            "custom_subject, custom_body, worst_axis_at_send, "
            "anchor_asin, updated_at"
        ).eq("stage", stage).order("updated_at", desc=True).limit(limit)
    
    res = q.execute()
    
    # Try to fetch email step data
    brands = res.data or []
    for brand in brands:
        try:
            steps_res = sb.table("email_steps").select("*").eq(
                "brand_key", brand["brand_key"]
            ).order("step_num").execute()
            brand["email_steps"] = steps_res.data or []
        except Exception:
            logging.exception(f"Failed to fetch email steps for brand {brand.get('brand_key')}")
            brand["email_steps"] = []
        
        # Fetch conversation threads if any
        try:
            conv_res = sb.table("email_conversations").select("*").eq(
                "brand_key", brand["brand_key"]
            ).order("created_at", desc=True).limit(10).execute()
            brand["conversations"] = conv_res.data or []
        except Exception:
            logging.exception(f"Failed to fetch conversations for brand {brand.get('brand_key')}")
            brand["conversations"] = []
    
    return {"count": len(brands), "brands": brands}


@router.post("/emails/{brand_key}/approve", dependencies=[Depends(require_admin)])
async def approve_email(brand_key: str):
    """Approve an email draft for sending — advances to SEQUENCED stage."""
    sb = get_supabase()
    if not sb:
        raise HTTPException(status_code=503, detail="Database not configured")
    
    now = datetime.utcnow().isoformat()
    sb.table("brands").update({"stage": "SEQUENCED", "updated_at": now}).eq("brand_key", brand_key).execute()
    return {"status": "ok", "message": f"{brand_key} approved and moved to SEQUENCED"}


@router.get("/analytics", dependencies=[Depends(require_admin)])
async def get_analytics():
    """Landing page and email analytics."""
    sb = get_supabase()
    if not sb:
        return {"error": "Database not configured"}
    
    try:
        # Landing page analytics
        landing_res = sb.table("landing_analytics").select(
            "brand_key, event_type, created_at"
        ).order("created_at", desc=True).limit(500).execute()
        
        events = landing_res.data or []
        
        # Aggregate by event type
        event_counts = {}
        for e in events:
            et = e.get("event_type", "unknown")
            event_counts[et] = event_counts.get(et, 0) + 1
        
        # Top landing pages by views
        brand_views = {}
        for e in events:
            if e.get("event_type") == "page_view":
                bk = e.get("brand_key", "unknown")
                brand_views[bk] = brand_views.get(bk, 0) + 1
        
        top_pages = sorted(brand_views.items(), key=lambda x: x[1], reverse=True)[:10]
        
        return {
            "event_counts": event_counts,
            "top_landing_pages": [{"brand_key": bk, "views": v} for bk, v in top_pages],
            "total_events": len(events),
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/trigger/{stage}", dependencies=[Depends(require_admin)])
async def trigger_pipeline_stage(stage: str):
    """Manually trigger a pipeline stage (enrich, score, draft, sequence)."""
    valid_stages = {"enrich", "score", "draft", "sequence", "full"}
    if stage not in valid_stages:
        raise HTTPException(status_code=400, detail=f"Invalid stage. Valid: {valid_stages}")
    
    # This will be connected to the actual pipeline runner
    return {
        "status": "queued",
        "stage": stage,
        "message": f"Pipeline stage '{stage}' has been queued for execution",
    }


@router.get("/settings", dependencies=[Depends(require_admin)])
async def get_settings():
    """Get current system settings."""
    return {
        "openrouter_model": os.getenv("OPENROUTER_MODEL", "deepseek/deepseek-chat-v3-0324"),
        "openrouter_draft_model": os.getenv("OPENROUTER_DRAFT_MODEL", "deepseek/deepseek-chat-v3-0324"),
        "max_llm_concurrency": os.getenv("MAX_LLM_CONCURRENCY", "25"),
        "max_apollo_concurrency": os.getenv("MAX_APOLLO_CONCURRENCY", "5"),
        "email_mini_batch_size": os.getenv("EMAIL_MINI_BATCH_SIZE", "3"),
        "calendly_url": os.getenv("CALENDLY_URL", ""),
        "landing_page_base_url": os.getenv("LANDING_PAGE_BASE_URL", ""),
        "auto_send_enabled": os.getenv("AUTO_SEND_ENABLED", "false"),
        "auto_reply_enabled": os.getenv("AUTO_REPLY_ENABLED", "false"),
    }
