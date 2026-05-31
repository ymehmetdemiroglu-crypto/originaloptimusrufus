"""Landing page API router — serves pre-researched prospect data for personalized pitch pages.

Routes:
  GET  /api/landing/{brand_key}        → Full prospect audit data for rendering
  POST /api/landing/{brand_key}/track  → Analytics event tracking
"""
import os
import hashlib
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

router = APIRouter(prefix="/api/landing", tags=["Landing Pages"])

import logging
from core.supabase import get_supabase


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class TrackingEvent(BaseModel):
    event_type: str  # 'page_view', 'section_view', 'chat_open', 'calendly_click', 'scroll_depth'
    event_data: dict = {}


class WeaknessItem(BaseModel):
    axis: str
    issue: str
    fix: str


class CompetitorItem(BaseModel):
    brand: str
    bullet_count: int
    image_count: int
    qa_count: int
    has_a_plus: bool
    rating: Optional[float] = None
    review_count: Optional[int] = None


class LandingPageData(BaseModel):
    brand_key: str
    brand_name: str
    contact_first_name: Optional[str] = None
    category: Optional[str] = None
    anchor_asin: Optional[str] = None
    listing_title: Optional[str] = None
    listing_bullets: list[str] = []
    
    # Scores
    rufus_score: Optional[int] = None
    rufus_citation_probability: Optional[str] = None
    intent_alignment_score: Optional[int] = None
    attribute_density_score: Optional[int] = None
    conversational_readability_score: Optional[int] = None
    qa_coverage_score: Optional[int] = None
    visual_structured_content_score: Optional[int] = None
    competitive_relativity_score: Optional[int] = None
    local_quality_score: Optional[int] = None
    client_quality_score: Optional[int] = None
    reachability_index: Optional[int] = None
    local_quality_breakdown: Optional[dict] = None
    
    # Analysis
    rufus_summary: Optional[str] = None
    weaknesses: list[WeaknessItem] = []
    weakness_signals: Optional[str] = None
    
    # Competitor context
    competitors: list[CompetitorItem] = []
    
    # Listing stats
    bullet_count: Optional[int] = None
    image_count: Optional[int] = None
    qa_count: Optional[int] = None
    has_a_plus: Optional[bool] = None
    listing_rating: Optional[float] = None
    listing_review_count: Optional[int] = None
    
    # Meta
    calendly_url: str = ""
    calculator_url: Optional[str] = None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/{brand_key}", response_model=LandingPageData)
async def get_landing_data(brand_key: str):
    """Return all pre-researched data for a prospect's personalized landing page."""
    sb = get_supabase()
    if not sb:
        raise HTTPException(status_code=503, detail="Database not configured")
    
    # Fetch brand
    brand_res = sb.table("brands").select("*").eq("brand_key", brand_key).limit(1).execute()
    if not brand_res.data:
        raise HTTPException(status_code=404, detail=f"Brand {brand_key} not found")
    brand = brand_res.data[0]
    
    # Fetch anchor prospect (listing data)
    anchor_asin = brand.get("anchor_asin")
    prospect = None
    if anchor_asin and anchor_asin != "apollo_direct":
        prospect_res = sb.table("prospects").select("*").eq("asin", anchor_asin).limit(1).execute()
        if prospect_res.data:
            prospect = prospect_res.data[0]
    
    # Fetch competitors
    competitors = []
    try:
        competitors_res = sb.table("competitors").select("*").eq("brand_key", brand_key).order("search_rank").limit(5).execute()
        for c in (competitors_res.data or []):
            competitors.append(CompetitorItem(
                brand=c.get("competitor_brand", "Unknown"),
                bullet_count=c.get("bullet_count", 0),
                image_count=c.get("image_count", 0),
                qa_count=c.get("qa_count", 0),
                has_a_plus=c.get("has_a_plus", False),
                rating=c.get("rating"),
                review_count=c.get("review_count"),
            ))
    except Exception:
        logging.exception(f"Failed to query competitors table from Supabase for brand {brand_key}. Falling back to empty list.")
    
    # Parse weaknesses from rufus_top_weaknesses JSON
    weaknesses = []
    if prospect and prospect.get("rufus_top_weaknesses"):
        try:
            import json
            raw = json.loads(prospect["rufus_top_weaknesses"])
            for w in (raw or []):
                weaknesses.append(WeaknessItem(
                    axis=w.get("axis", "Unknown"),
                    issue=w.get("issue", ""),
                    fix=w.get("fix", ""),
                ))
        except Exception:
            logging.exception(f"Failed to parse weaknesses for prospect ASIN {prospect.get('asin') if prospect else 'unknown'}")
    
    # Parse bullets from post_body
    listing_bullets = []
    if prospect and prospect.get("post_body"):
        # Split on newlines or bullet markers
        raw_body = prospect["post_body"]
        for line in raw_body.split("\n"):
            line = line.strip().lstrip("•-–").strip()
            if line and len(line) > 10:
                listing_bullets.append(line)
    
    # Calendly URL from env
    calendly_url = os.getenv("CALENDLY_URL", "https://calendly.com/optimusrufus/audit")
    
    return LandingPageData(
        brand_key=brand_key,
        brand_name=brand.get("brand_name", ""),
        contact_first_name=brand.get("contact_first_name"),
        category=brand.get("category") or (prospect.get("category") if prospect else None),
        anchor_asin=anchor_asin,
        listing_title=prospect.get("post_title") if prospect else None,
        listing_bullets=listing_bullets,
        
        rufus_score=prospect.get("rufus_score") if prospect else None,
        rufus_citation_probability=prospect.get("rufus_citation_probability") if prospect else None,
        intent_alignment_score=prospect.get("intent_alignment_score") if prospect else None,
        attribute_density_score=prospect.get("attribute_density_score") if prospect else None,
        conversational_readability_score=prospect.get("conversational_readability_score") if prospect else None,
        qa_coverage_score=prospect.get("qa_coverage_score") if prospect else None,
        visual_structured_content_score=prospect.get("visual_structured_content_score") if prospect else None,
        competitive_relativity_score=prospect.get("competitive_relativity_score") if prospect else None,
        
        local_quality_score=prospect.get("quality_score") if prospect else None,
        client_quality_score=brand.get("client_quality_score"),
        reachability_index=brand.get("reachability_index"),
        local_quality_breakdown=prospect.get("quality_breakdown") if prospect else None,
        
        rufus_summary=prospect.get("rufus_summary") if prospect else None,
        weaknesses=weaknesses,
        weakness_signals=brand.get("weakness_signals") or (prospect.get("weakness_signals") if prospect else None),
        
        competitors=competitors,
        
        bullet_count=prospect.get("bullet_count") if prospect else None,
        image_count=prospect.get("image_count") if prospect else None,
        qa_count=prospect.get("qa_count") if prospect else None,
        has_a_plus=prospect.get("has_a_plus") if prospect else None,
        listing_rating=prospect.get("listing_rating") if prospect else None,
        listing_review_count=prospect.get("listing_review_count") if prospect else None,
        
        calendly_url=calendly_url,
        calculator_url=brand.get("calculator_url"),
    )


@router.post("/{brand_key}/track")
async def track_event(brand_key: str, event: TrackingEvent, request: Request):
    """Track analytics events on the landing page."""
    sb = get_supabase()
    if not sb:
        return {"status": "ok", "tracked": False}
    
    # Hash IP for privacy
    client_ip = request.client.host if request.client else "unknown"
    ip_hash = hashlib.sha256(client_ip.encode()).hexdigest()[:16]
    
    try:
        sb.table("landing_analytics").insert({
            "brand_key": brand_key,
            "event_type": event.event_type,
            "event_data": event.event_data,
            "ip_hash": ip_hash,
            "user_agent": request.headers.get("user-agent", "")[:500],
        }).execute()
    except Exception:
        logging.exception(f"Failed to insert tracking event {event.event_type} for brand {brand_key}")
    
    return {"status": "ok", "tracked": True}
