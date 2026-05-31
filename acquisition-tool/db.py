from datetime import datetime
from typing import Optional

from supabase import create_client, Client

from models import Prospect, Brand
from config import SUPABASE_URL, SUPABASE_KEY
import resilience

import logging
import threading
_local = threading.local()
_ASIN_LOCK = threading.Lock()


def _sb() -> Client:
    if not hasattr(_local, "client"):
        _local.client = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _local.client


def close_supabase():
    if hasattr(_local, "client"):
        _local.client = None


def init_db():
    """No-op: tables live in Supabase. Kept for call-site compatibility."""
    pass


# ---------------------------------------------------------------------------
# Timestamp helper
# ---------------------------------------------------------------------------

def _dt(val) -> Optional[datetime]:
    if val is None:
        return None
    if isinstance(val, datetime):
        return val.replace(tzinfo=None)
    s = str(val)
    try:
        dt = datetime.fromisoformat(s)
        return dt.replace(tzinfo=None)
    except (ValueError, TypeError):
        pass
    clean = s.split("+")[0].split("Z")[0].replace("T", " ").strip()
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(clean, fmt)
        except (ValueError, TypeError):
            pass
    return None


# ---------------------------------------------------------------------------
# Row mappers
# ---------------------------------------------------------------------------

def _row_to_prospect(row: dict) -> Prospect:
    return Prospect(
        id=row["id"],
        username=row.get("username") or "",
        subreddit=row.get("subreddit") or "",
        post_title=row.get("post_title") or "",
        post_body=row.get("post_body") or "",
        post_url=row.get("post_url") or "",
        pain_summary=row.get("pain_summary"),
        rank_score=row.get("rank_score"),
        stage=row.get("stage") or "FOUND",
        outreach_msg=row.get("outreach_msg"),
        notes=row.get("notes"),
        messaged_at=_dt(row.get("messaged_at")),
        last_followup=_dt(row.get("last_followup")),
        next_followup=_dt(row.get("next_followup")),
        created_at=_dt(row.get("created_at")) or datetime.utcnow(),
        updated_at=_dt(row.get("updated_at")) or datetime.utcnow(),
        post_score=row.get("post_score") or 0,
        num_comments=row.get("num_comments") or 0,
        platform=row.get("platform"),
        followup_count=row.get("followup_count") or 0,
        source=row.get("source") or "reddit",
        asin=row.get("asin"),
        brand=row.get("brand"),
        category=row.get("category"),
        listing_price=row.get("listing_price"),
        listing_rating=row.get("listing_rating"),
        listing_review_count=row.get("listing_review_count"),
        bullet_count=row.get("bullet_count"),
        image_count=row.get("image_count"),
        has_a_plus=row.get("has_a_plus"),  # already bool or None from Supabase
        qa_count=row.get("qa_count"),
        weakness_score=row.get("weakness_score"),
        weakness_signals=row.get("weakness_signals"),
        quality_score=row.get("quality_score"),
        quality_signals=row.get("quality_signals"),
        quality_breakdown=row.get("quality_breakdown"),
        brand_key=row.get("brand_key"),
        domain=row.get("domain"),
        contact_email=row.get("contact_email"),
        contact_first_name=row.get("contact_first_name"),
        contact_last_name=row.get("contact_last_name"),
        contact_title=row.get("contact_title"),
        contact_linkedin=row.get("contact_linkedin"),
        apollo_person_id=row.get("apollo_person_id"),
        apollo_organization_id=row.get("apollo_organization_id"),
        apollo_contact_id=row.get("apollo_contact_id"),
        email_teardown=row.get("email_teardown"),
        pain_intensity=row.get("pain_intensity"),
        fit_score=row.get("fit_score"),
        urgency=row.get("urgency"),
        rufus_score=row.get("rufus_score"),
        intent_alignment_score=row.get("intent_alignment_score"),
        attribute_density_score=row.get("attribute_density_score"),
        conversational_readability_score=row.get("conversational_readability_score"),
        qa_coverage_score=row.get("qa_coverage_score"),
        rufus_citation_probability=row.get("rufus_citation_probability") or "",
        rufus_top_weaknesses=row.get("rufus_top_weaknesses") or "",
        rufus_summary=row.get("rufus_summary") or "",
        competitive_summary=row.get("competitive_summary"),
        visual_structured_content_score=row.get("visual_structured_content_score"),
        competitive_relativity_score=row.get("competitive_relativity_score"),
        seller_id=row.get("seller_id"),
        seller_domain=row.get("seller_domain"),
        seller_business_name=row.get("seller_business_name"),
        seller_country=row.get("seller_country"),
        seller_feedback_pct=row.get("seller_feedback_pct"),
    )



def _row_to_brand(row: dict) -> Brand:
    return Brand(
        brand_key=row["brand_key"],
        brand_name=row.get("brand_name") or "",
        anchor_asin=row.get("anchor_asin") or "",
        asin_count=row.get("asin_count") or 1,
        max_weakness_score=row.get("max_weakness_score"),
        weakness_signals=row.get("weakness_signals"),
        category=row.get("category"),
        stage=row.get("stage") or "WEAK_BRAND",
        domain=row.get("domain"),
        contact_email=row.get("contact_email"),
        contact_first_name=row.get("contact_first_name"),
        contact_last_name=row.get("contact_last_name"),
        contact_title=row.get("contact_title"),
        contact_linkedin=row.get("contact_linkedin"),
        apollo_person_id=row.get("apollo_person_id"),
        apollo_organization_id=row.get("apollo_organization_id"),
        apollo_contact_id=row.get("apollo_contact_id"),
        email_teardown=row.get("email_teardown"),
        notes=row.get("notes"),
        source=row.get("source") or "amazon_scrape",
        apollo_score=row.get("apollo_score"),
        custom_subject=row.get("custom_subject"),
        custom_body=row.get("custom_body"),
        worst_axis_at_send=row.get("worst_axis_at_send"),
        replied_at=_dt(row.get("replied_at")),
        calculator_url=row.get("calculator_url"),
        calculator_used_at=_dt(row.get("calculator_used_at")),
        calculator_submitted_at=_dt(row.get("calculator_submitted_at")),
        loom_url=row.get("loom_url"),
        loom_recorded_at=_dt(row.get("loom_recorded_at")),
        intent_score=row.get("intent_score"),
        intent_signals=row.get("intent_signals"),
        intent_summary=row.get("intent_summary"),
        client_quality_score=row.get("client_quality_score"),
        client_quality_signals=row.get("client_quality_signals"),
        client_quality_breakdown=row.get("client_quality_breakdown"),
        reachability_index=row.get("reachability_index"),
        created_at=_dt(row.get("created_at")) or datetime.utcnow(),
        updated_at=_dt(row.get("updated_at")) or datetime.utcnow(),
    )


# ---------------------------------------------------------------------------
# Prospect helpers
# ---------------------------------------------------------------------------

_EXISTING_ASIN_CACHE: Optional[set[str]] = None

def asin_exists(asin: str) -> bool:
    global _EXISTING_ASIN_CACHE
    with _ASIN_LOCK:
        if _EXISTING_ASIN_CACHE is None:
            try:
                res = _sb().table("prospects").select("asin").not_.is_("asin", "null").execute()
                _EXISTING_ASIN_CACHE = {r["asin"] for r in res.data if r.get("asin")}
            except Exception:
                logging.getLogger("acquisition_tool.db").exception("ASIN cache load failed")
                _EXISTING_ASIN_CACHE = set()
        return asin in _EXISTING_ASIN_CACHE


def asins_that_exist(asins: list[str]) -> set[str]:
    """Batch check which ASINs already exist in the DB."""
    if not asins:
        return set()
    try:
        res = _sb().table("prospects").select("asin").in_("asin", asins).execute()
        return {r["asin"] for r in res.data if r.get("asin")}
    except Exception:
        logging.getLogger("acquisition_tool.db").exception("ASIN batch check failed")
        return set()


@resilience.retry_call(max_attempts=3, exceptions=(Exception,))
def upsert_listing(p: Prospect) -> bool:
    """Insert or update a prospect row. Returns True if newly inserted."""
    now = datetime.utcnow().isoformat()
    existing = _sb().table("prospects").select("id").eq("id", p.id).limit(1).execute()

    if existing.data:
        update_payload = {
            "post_title": p.post_title,
            "post_body": p.post_body,
            "listing_price": p.listing_price,
            "listing_rating": p.listing_rating,
            "listing_review_count": p.listing_review_count,
            "bullet_count": p.bullet_count,
            "image_count": p.image_count,
            "has_a_plus": p.has_a_plus,
            "qa_count": p.qa_count,
            "brand": p.brand,
            "category": p.category,
            "brand_key": p.brand_key,
            "post_url": p.post_url,
            "updated_at": now,
        }
        for field in ("seller_id", "seller_domain", "seller_business_name", "seller_country", "seller_feedback_pct"):
            val = getattr(p, field, None)
            if val is not None:
                update_payload[field] = val
        _sb().table("prospects").update(update_payload).eq("id", p.id).execute()
        return False

    insert_payload = {
        "id": p.id,
        "username": p.username,
        "subreddit": p.subreddit,
        "post_title": p.post_title,
        "post_body": p.post_body,
        "post_url": p.post_url,
        "stage": p.stage,
        "source": p.source,
        "asin": p.asin,
        "brand": p.brand,
        "category": p.category,
        "listing_price": p.listing_price,
        "listing_rating": p.listing_rating,
        "listing_review_count": p.listing_review_count,
        "bullet_count": p.bullet_count,
        "image_count": p.image_count,
        "has_a_plus": p.has_a_plus,
        "qa_count": p.qa_count,
        "brand_key": p.brand_key,
        "created_at": now,
        "updated_at": now,
    }
    for field in ("seller_id", "seller_domain", "seller_business_name", "seller_country", "seller_feedback_pct"):
        val = getattr(p, field, None)
        if val is not None:
            insert_payload[field] = val

    _sb().table("prospects").insert(insert_payload).execute()
    if p.asin:
        with _ASIN_LOCK:
            if _EXISTING_ASIN_CACHE is not None:
                _EXISTING_ASIN_CACHE.add(p.asin)
    return True


@resilience.retry_call(max_attempts=3, exceptions=(Exception,))
def batch_upsert_listings(prospects: list) -> int:
    """Upsert a list of Prospect objects in one network call. Returns insert count (approx)."""
    if not prospects:
        return 0
    now = datetime.utcnow().isoformat()
    payload = []
    for p in prospects:
        item = {
            "id": p.id,
            "username": p.username,
            "subreddit": p.subreddit,
            "post_title": p.post_title,
            "post_body": p.post_body,
            "post_url": p.post_url,
            "stage": p.stage,
            "source": p.source,
            "asin": p.asin,
            "brand": p.brand,
            "category": p.category,
            "listing_price": p.listing_price,
            "listing_rating": p.listing_rating,
            "listing_review_count": p.listing_review_count,
            "bullet_count": p.bullet_count,
            "image_count": p.image_count,
            "has_a_plus": p.has_a_plus,
            "qa_count": p.qa_count,
            "brand_key": p.brand_key,
            "created_at": now,
            "updated_at": now,
        }
        for field in ("seller_id", "seller_domain", "seller_business_name", "seller_country", "seller_feedback_pct"):
            val = getattr(p, field, None)
            if val is not None:
                item[field] = val
        payload.append(item)
    _sb().table("prospects").upsert(payload, on_conflict="id").execute()
    with _ASIN_LOCK:
        if _EXISTING_ASIN_CACHE is not None:
            for p in prospects:
                if p.asin:
                    _EXISTING_ASIN_CACHE.add(p.asin)
    return len(payload)


def get_prospect(pid: str) -> Optional[Prospect]:
    res = _sb().table("prospects").select("*").eq("id", pid).limit(1).execute()
    return _row_to_prospect(res.data[0]) if res.data else None


def get_anchor_prospect(asin: str) -> Optional[Prospect]:
    res = _sb().table("prospects").select("*").eq("asin", asin).limit(1).execute()
    return _row_to_prospect(res.data[0]) if res.data else None


def list_prospects(stage: Optional[str] = None) -> list[Prospect]:
    q = _sb().table("prospects").select("*").order("created_at", desc=True)
    if stage:
        q = q.eq("stage", stage)
    res = q.execute()
    return [_row_to_prospect(r) for r in res.data]


def get_unscored_listings(limit: int = 100) -> list[Prospect]:
    """LISTING_FOUND rows that have no quality_score or weakness_score yet."""
    res = (
        _sb().table("prospects").select("*")
        .eq("stage", "LISTING_FOUND")
        .is_("quality_score", "null")
        .is_("weakness_score", "null")
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return [_row_to_prospect(r) for r in res.data]


def get_listings_needing_rufus_score(limit: int = 100) -> list[Prospect]:
    """WEAK_LISTING rows with no Rufus score yet."""
    res = (
        _sb().table("prospects").select("*")
        .eq("stage", "WEAK_LISTING")
        .is_("rufus_score", "null")
        .order("quality_score", desc=True)
        .order("weakness_score", desc=True)
        .limit(limit)
        .execute()
    )
    return [_row_to_prospect(r) for r in res.data]


def get_weak_listings_for_rollup() -> list[Prospect]:
    """WEAK_LISTING rows whose brand_key is not yet in the brands table."""
    bk_res = _sb().table("brands").select("brand_key").execute()
    existing_brand_keys = {r["brand_key"] for r in bk_res.data}

    res = (
        _sb().table("prospects").select("*")
        .eq("stage", "WEAK_LISTING")
        .not_.is_("brand_key", "null")
        .order("quality_score", desc=True)
        .order("weakness_score", desc=True)
        .execute()
    )
    return [
        _row_to_prospect(r) for r in res.data
        if r.get("brand_key") not in existing_brand_keys
    ]


def get_enriched_anchor_prospects(limit: int = 100) -> list[Prospect]:
    """Anchor ASINs of CONTACT_ENRICHED brands that still have no Rufus score."""
    bres = (
        _sb().table("brands").select("anchor_asin")
        .eq("stage", "CONTACT_ENRICHED")
        .execute()
    )
    anchor_asins = [
        r["anchor_asin"] for r in bres.data
        if r.get("anchor_asin") and r["anchor_asin"] != "apollo_direct"
    ]
    if not anchor_asins:
        return []

    res = (
        _sb().table("prospects").select("*")
        .in_("asin", anchor_asins)
        .is_("rufus_score", "null")
        .order("quality_score", desc=True)
        .order("weakness_score", desc=True)
        .limit(limit)
        .execute()
    )
    return [_row_to_prospect(r) for r in res.data]


@resilience.retry_call(max_attempts=3, exceptions=(Exception,))
def set_brand_rufus_score(brand_key: str, rufus_score: int):
    now = datetime.utcnow().isoformat()
    _sb().table("brands").update({
        "brand_rufus_score": rufus_score,
        "updated_at": now,
    }).eq("brand_key", brand_key).execute()


@resilience.retry_call(max_attempts=3, exceptions=(Exception,))
def set_rufus_score(
    prospect_id: str,
    rufus_score: int,
    intent_alignment_score: int,
    attribute_density_score: int,
    conversational_readability_score: int,
    qa_coverage_score: int,
    rufus_citation_probability: str,
    rufus_top_weaknesses: str,
    rufus_summary: str,
    visual_structured_content_score: Optional[int] = None,
    competitive_relativity_score: Optional[int] = None,
    competitive_summary: Optional[str] = None,
):
    now = datetime.utcnow().isoformat()
    update_payload = {
        "rufus_score": rufus_score,
        "intent_alignment_score": intent_alignment_score,
        "attribute_density_score": attribute_density_score,
        "conversational_readability_score": conversational_readability_score,
        "qa_coverage_score": qa_coverage_score,
        "rufus_citation_probability": rufus_citation_probability,
        "rufus_top_weaknesses": rufus_top_weaknesses,
        "rufus_summary": rufus_summary,
        "updated_at": now,
    }
    if visual_structured_content_score is not None:
        update_payload["visual_structured_content_score"] = visual_structured_content_score
    if competitive_relativity_score is not None:
        update_payload["competitive_relativity_score"] = competitive_relativity_score
    if competitive_summary is not None:
        update_payload["competitive_summary"] = competitive_summary
    _sb().table("prospects").update(update_payload).eq("id", prospect_id).execute()


def update_stage(prospect_id: str, stage: str):
    now = datetime.utcnow().isoformat()
    _sb().table("prospects").update({"stage": stage, "updated_at": now}).eq("id", prospect_id).execute()


def set_weakness_score(prospect_id: str, weakness_score: int, weakness_signals: str, new_stage: str):
    now = datetime.utcnow().isoformat()
    _sb().table("prospects").update({
        "weakness_score": weakness_score,
        "weakness_signals": weakness_signals,
        "stage": new_stage,
        "updated_at": now,
    }).eq("id", prospect_id).execute()


def set_listing_quality_score(
    prospect_id: str,
    quality_score: int,
    quality_signals: str,
    quality_breakdown: dict,
    stage: str,
):
    import json
    now = datetime.utcnow().isoformat()
    _sb().table("prospects").update({
        "quality_score": quality_score,
        "quality_signals": quality_signals,
        "quality_breakdown": json.dumps(quality_breakdown) if quality_breakdown else None,
        "stage": stage,
        "updated_at": now,
    }).eq("id", prospect_id).execute()


def set_client_quality_score(
    brand_key: str,
    client_quality_score: int,
    client_quality_signals: str,
    client_quality_breakdown: dict,
    reachability_index: int,
):
    import json
    now = datetime.utcnow().isoformat()
    _sb().table("brands").update({
        "client_quality_score": client_quality_score,
        "client_quality_signals": client_quality_signals,
        "client_quality_breakdown": json.dumps(client_quality_breakdown) if client_quality_breakdown else None,
        "reachability_index": reachability_index,
        "updated_at": now,
    }).eq("brand_key", brand_key).execute()


def add_note(prospect_id: str, note: str):
    now = datetime.utcnow().isoformat()
    res = _sb().table("prospects").select("notes").eq("id", prospect_id).limit(1).execute()
    if not res.data:
        return
    existing = res.data[0].get("notes") or ""
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M")
    new_notes = f"{existing}\n[{ts}] {note}".strip()
    _sb().table("prospects").update({"notes": new_notes, "updated_at": now}).eq("id", prospect_id).execute()


def add_note_to_brand(brand_key: str, note: str):
    now = datetime.utcnow().isoformat()
    res = _sb().table("brands").select("notes").eq("brand_key", brand_key).limit(1).execute()
    if not res.data:
        return
    existing = res.data[0].get("notes") or ""
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M")
    new_notes = f"{existing}\n[{ts}] {note}".strip()
    _sb().table("brands").update({"notes": new_notes, "updated_at": now}).eq("brand_key", brand_key).execute()


# ---------------------------------------------------------------------------
# Brand helpers
# ---------------------------------------------------------------------------

def upsert_brand(brand: Brand) -> bool:
    """Insert brand if brand_key doesn't exist. Returns True if newly inserted."""
    now = datetime.utcnow().isoformat()
    existing = (
        _sb().table("brands")
        .select("brand_key,asin_count,max_weakness_score")
        .eq("brand_key", brand.brand_key)
        .limit(1)
        .execute()
    )
    if existing.data:
        row = existing.data[0]
        _sb().table("brands").update({
            "asin_count": max(row.get("asin_count") or 1, brand.asin_count),
            "max_weakness_score": max(row.get("max_weakness_score") or 0, brand.max_weakness_score or 0),
            "weakness_signals": brand.weakness_signals,
            "updated_at": now,
        }).eq("brand_key", brand.brand_key).execute()
        return False

    _sb().table("brands").insert({
        "brand_key": brand.brand_key,
        "brand_name": brand.brand_name,
        "anchor_asin": brand.anchor_asin,
        "asin_count": brand.asin_count,
        "max_weakness_score": brand.max_weakness_score,
        "weakness_signals": brand.weakness_signals,
        "category": brand.category,
        "stage": brand.stage,
        "source": brand.source or "amazon_scrape",
        "created_at": now,
        "updated_at": now,
    }).execute()
    return True


def get_brand(brand_key: str) -> Optional[Brand]:
    res = _sb().table("brands").select("*").eq("brand_key", brand_key).limit(1).execute()
    return _row_to_brand(res.data[0]) if res.data else None


def get_brands_needing_enrichment(limit: int = 50) -> list[Brand]:
    res = (
        _sb().table("brands").select("*")
        .eq("stage", "WEAK_BRAND")
        .order("reachability_index", desc=True)
        .order("max_weakness_score", desc=True)
        .limit(limit)
        .execute()
    )
    return [_row_to_brand(r) for r in res.data]


def set_brand_enrichment(
    brand_key: str,
    domain: Optional[str] = None,
    contact_email: Optional[str] = None,
    contact_first_name: Optional[str] = None,
    contact_last_name: Optional[str] = None,
    contact_title: Optional[str] = None,
    apollo_person_id: Optional[str] = None,
    apollo_organization_id: Optional[str] = None,
    contact_linkedin: Optional[str] = None,
):
    now = datetime.utcnow().isoformat()
    _sb().table("brands").update({
        "domain": domain,
        "contact_email": contact_email,
        "contact_first_name": contact_first_name,
        "contact_last_name": contact_last_name,
        "contact_title": contact_title,
        "apollo_person_id": apollo_person_id,
        "apollo_organization_id": apollo_organization_id,
        "contact_linkedin": contact_linkedin,
        "updated_at": now,
    }).eq("brand_key", brand_key).execute()


def update_brand_stage(brand_key: str, stage: str):
    now = datetime.utcnow().isoformat()
    _sb().table("brands").update({"stage": stage, "updated_at": now}).eq("brand_key", brand_key).execute()


def get_brands_needing_email_draft(limit: int = 100) -> list[Brand]:
    """CONTACT_ENRICHED brands whose anchor has a Rufus score but no draft yet."""
    bres = _sb().table("brands").select("*").eq("stage", "CONTACT_ENRICHED").execute()
    ce_brands = bres.data

    direct_brands = [b for b in ce_brands if b.get("anchor_asin") == "apollo_direct"]
    asin_brands = [b for b in ce_brands if b.get("anchor_asin") != "apollo_direct"]

    result: list[Brand] = []
    seen: set[str] = set()

    if asin_brands:
        asin_list = [b["anchor_asin"] for b in asin_brands if b.get("anchor_asin")]
        if asin_list:
            pres = (
                _sb().table("prospects").select("asin,rufus_score")
                .in_("asin", asin_list)
                .not_.is_("rufus_score", "null")
                .execute()
            )
            asin_to_score = {r["asin"]: r["rufus_score"] for r in pres.data}
            qualifying = sorted(
                [b for b in asin_brands if b.get("anchor_asin") in asin_to_score],
                key=lambda b: asin_to_score.get(b["anchor_asin"], 0),
            )
            for b in qualifying:
                result.append(_row_to_brand(b))
                seen.add(b["brand_key"])

    for b in direct_brands:
        if b["brand_key"] not in seen:
            result.append(_row_to_brand(b))

    # Sort by reachability_index DESC (nulls last) to prioritize high-value prospects
    result.sort(
        key=lambda b: (b.reachability_index is not None, b.reachability_index or -999999),
        reverse=True
    )

    return result[:limit]


def insert_apollo_brand(
    brand_key: str,
    brand_name: str,
    domain: str,
    contact_email: str,
    contact_first_name: Optional[str] = None,
    contact_last_name: Optional[str] = None,
    contact_title: Optional[str] = None,
    category: Optional[str] = None,
    contact_linkedin: Optional[str] = None,
    apollo_person_id: Optional[str] = None,
    apollo_organization_id: Optional[str] = None,
    apollo_score: Optional[int] = None,
) -> bool:
    """Insert an Apollo-sourced brand at CONTACT_ENRICHED. Returns True if newly inserted."""
    existing = _sb().table("brands").select("brand_key").eq("brand_key", brand_key).limit(1).execute()
    if existing.data:
        return False
    now = datetime.utcnow().isoformat()
    _sb().table("brands").insert({
        "brand_key": brand_key,
        "brand_name": brand_name,
        "anchor_asin": "apollo_direct",
        "asin_count": 0,
        "category": category,
        "stage": "CONTACT_ENRICHED",
        "source": "apollo_search",
        "domain": domain,
        "contact_email": contact_email,
        "contact_first_name": contact_first_name,
        "contact_last_name": contact_last_name,
        "contact_title": contact_title,
        "contact_linkedin": contact_linkedin,
        "apollo_person_id": apollo_person_id,
        "apollo_organization_id": apollo_organization_id,
        "apollo_score": apollo_score,
        "created_at": now,
        "updated_at": now,
    }).execute()
    return True


def save_brand_custom_copy(
    brand_key: str,
    subject: str,
    body: str,
    worst_axis: str,
    teardown: str,
):
    now = datetime.utcnow().isoformat()
    _sb().table("brands").update({
        "custom_subject": subject,
        "custom_body": body,
        "worst_axis_at_send": worst_axis,
        "email_teardown": teardown,
        "updated_at": now,
    }).eq("brand_key", brand_key).execute()


def get_brands_by_stage(stage: str, limit: int = 100) -> list[Brand]:
    res = (
        _sb().table("brands").select("*")
        .eq("stage", stage)
        .order("updated_at", desc=True)
        .limit(limit)
        .execute()
    )
    return [_row_to_brand(r) for r in res.data]


def get_brands_ready_to_send(limit: int = 50) -> list[Brand]:
    """Return EMAIL_DRAFTED brands sorted by intent_score desc, then updated_at desc.

    Brands with no intent_score yet are treated as 0 so they still appear.
    """
    res = (
        _sb().table("brands").select("*")
        .eq("stage", "EMAIL_DRAFTED")
        .order("intent_score", desc=True, nullsfirst=False)
        .order("updated_at", desc=True)
        .limit(limit)
        .execute()
    )
    return [_row_to_brand(r) for r in res.data]


def set_intent_score(brand_key: str, intent_score: int, intent_signals: str, intent_summary: str):
    now = datetime.utcnow().isoformat()
    _sb().table("brands").update({
        "intent_score": intent_score,
        "intent_signals": intent_signals,
        "intent_summary": intent_summary,
        "updated_at": now,
    }).eq("brand_key", brand_key).execute()


def set_brand_apollo_contact(brand_key: str, apollo_contact_id: str):
    now = datetime.utcnow().isoformat()
    _sb().table("brands").update({
        "apollo_contact_id": apollo_contact_id,
        "updated_at": now,
    }).eq("brand_key", brand_key).execute()


def set_brand_replied(brand_key: str):
    now = datetime.utcnow().isoformat()
    _sb().table("brands").update({
        "stage": "REPLIED",
        "replied_at": now,
        "updated_at": now,
    }).eq("brand_key", brand_key).execute()


def set_brand_calculator_url(brand_key: str, calculator_url: str):
    """Store the personalized calculator URL on the brand row for tracking."""
    now = datetime.utcnow().isoformat()
    _sb().table("brands").update({
        "calculator_url": calculator_url,
        "updated_at": now,
    }).eq("brand_key", brand_key).execute()


def mark_calculator_used(brand_key: str):
    """Mark a brand as CALCULATOR_USED when they click through from cold email."""
    now = datetime.utcnow().isoformat()
    _sb().table("brands").update({
        "stage": "CALCULATOR_USED",
        "calculator_used_at": now,
        "updated_at": now,
    }).eq("brand_key", brand_key).execute()


def mark_calculator_submitted(brand_key: str):
    """Mark a brand as CALCULATOR_SUBMITTED when they complete the calculator."""
    now = datetime.utcnow().isoformat()
    _sb().table("brands").update({
        "stage": "CALCULATOR_SUBMITTED",
        "calculator_submitted_at": now,
        "updated_at": now,
    }).eq("brand_key", brand_key).execute()


@resilience.retry_call(max_attempts=3, exceptions=(Exception,))
def set_brand_loom_url(brand_key: str, loom_url: str):
    now = datetime.utcnow().isoformat()
    _sb().table("brands").update({
        "loom_url": loom_url,
        "loom_recorded_at": now,
        "updated_at": now,
    }).eq("brand_key", brand_key).execute()


def get_brands_needing_loom(limit: int = 25) -> list[Brand]:
    """Get brands in CALCULATOR_USED or REPLIED stages that do not have a recorded Loom yet."""
    res = (
        _sb().table("brands").select("*")
        .in_("stage", ["CALCULATOR_USED", "REPLIED"])
        .is_("loom_url", "null")
        .order("updated_at", desc=True)
        .limit(limit)
        .execute()
    )
    return [_row_to_brand(r) for r in res.data]


def get_reply_stats_by_axis() -> list:
    res = _sb().rpc("get_reply_stats_by_axis", {}).execute()
    return res.data if res.data else []


# ---------------------------------------------------------------------------
# Competitor helpers
# ---------------------------------------------------------------------------

def save_competitor(
    brand_key: str,
    competitor_asin: str,
    competitor_brand: str,
    search_rank: int,
    title: str,
    bullet_count: int,
    bullets: str,
    image_count: int,
    has_a_plus: bool,
    qa_count: int,
    rating: Optional[float],
    review_count: Optional[int],
    price: Optional[float],
):
    now = datetime.utcnow().isoformat()
    _sb().table("competitors").upsert({
        "brand_key": brand_key,
        "competitor_asin": competitor_asin,
        "competitor_brand": competitor_brand,
        "search_rank": search_rank,
        "title": title,
        "bullet_count": bullet_count,
        "bullets": bullets,
        "image_count": image_count,
        "has_a_plus": has_a_plus,
        "qa_count": qa_count,
        "rating": rating,
        "review_count": review_count,
        "price": price,
        "updated_at": now,
    }, on_conflict="brand_key,competitor_asin").execute()


def get_competitors(brand_key: str) -> list[dict]:
    res = (
        _sb().table("competitors")
        .select("*")
        .eq("brand_key", brand_key)
        .order("search_rank")
        .execute()
    )
    return res.data if res.data else []


def get_competitors_batch(brand_keys: list[str]) -> dict[str, list[dict]]:
    if not brand_keys:
        return {}
    res = (
        _sb().table("competitors")
        .select("*")
        .in_("brand_key", brand_keys)
        .order("search_rank")
        .execute()
    )
    result: dict[str, list[dict]] = {}
    for row in res.data:
        result.setdefault(row["brand_key"], []).append(row)
    return result


# ---------------------------------------------------------------------------
# brand_step_emails helpers
# ---------------------------------------------------------------------------

def save_brand_step_email(brand_key: str, step_num: int, subject: str, body: str, overlap: float):
    now = datetime.utcnow().isoformat()
    _sb().table("brand_step_emails").upsert({
        "brand_key": brand_key,
        "step_num": step_num,
        "subject": subject,
        "body": body,
        "overlap": overlap,
        "created_at": now,
    }, on_conflict="brand_key,step_num").execute()


def get_recent_brand_bodies(limit: int = 50, step_num: Optional[int] = None) -> list[str]:
    q = (
        _sb().table("brand_step_emails").select("body")
        .not_.is_("body", "null")
        .order("created_at", desc=True)
        .limit(limit)
    )
    if step_num is not None:
        q = q.eq("step_num", step_num)
    res = q.execute()
    return [r["body"] for r in res.data if r.get("body")]


def get_brand_step_emails(brand_key: str) -> dict[int, dict]:
    res = (
        _sb().table("brand_step_emails")
        .select("step_num,subject,body")
        .eq("brand_key", brand_key)
        .order("step_num")
        .execute()
    )
    return {
        r["step_num"]: {"subject": r.get("subject") or "", "body": r.get("body") or ""}
        for r in res.data
    }


def get_brand_step_emails_batch(brand_keys: list[str]) -> dict[str, dict[int, dict]]:
    """Fetch step emails for multiple brand_keys in a single call."""
    if not brand_keys:
        return {}
    res = (
        _sb().table("brand_step_emails")
        .select("brand_key,step_num,subject,body")
        .in_("brand_key", brand_keys)
        .execute()
    )
    result: dict[str, dict[int, dict]] = {}
    for r in res.data:
        result.setdefault(r["brand_key"], {})[r["step_num"]] = {
            "subject": r.get("subject") or "",
            "body": r.get("body") or "",
        }
    return result


# ---------------------------------------------------------------------------
# Dashboard / stats helpers
# ---------------------------------------------------------------------------

def get_pipeline_counts() -> dict[str, int]:
    res = _sb().rpc("get_pipeline_counts", {}).execute()
    return dict(res.data) if res.data else {}


def get_last_scrape() -> Optional[datetime]:
    res = _sb().rpc("get_last_scrape", {}).execute()
    if not res.data:
        return None
    return _dt(res.data)


def get_stats() -> dict:
    res = _sb().rpc("get_stats", {}).execute()
    return res.data if res.data else {"funnel": {"total": 0, "messaged": 0, "replied": 0, "demo": 0, "beta": 0, "paid": 0}}


def get_dashboard_advanced_metrics() -> dict:
    """Query and return real-time pipeline statistics (ALII, CQS, RI, and computational linguistics)."""
    try:
        # Fetch LQS (ALII) and nested linguistics breakdown from prospects
        res_p = _sb().table("prospects").select("quality_score,quality_breakdown").not_.is_("quality_score", "null").execute()
        
        # Fetch CQS and RI from brands
        res_b = _sb().table("brands").select("reachability_index,client_quality_score").not_.is_("reachability_index", "null").execute()
        
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
                        
        return {
            "avg_lqs": sum(lqs_scores) / len(lqs_scores) if lqs_scores else 0.0,
            "max_lqs": max(lqs_scores) if lqs_scores else 0,
            "avg_ri": sum(ri_scores) / len(ri_scores) if ri_scores else 0.0,
            "max_ri": max(ri_scores) if ri_scores else 0,
            "avg_cqs": sum(cqs_scores) / len(cqs_scores) if cqs_scores else 0.0,
            "avg_flesch": sum(flesch_scores) / len(flesch_scores) if flesch_scores else 0.0,
            "avg_ttr": sum(ttr_scores) / len(ttr_scores) if ttr_scores else 0.0,
            "avg_cosmo": sum(cosmo_scores) / len(cosmo_scores) if cosmo_scores else 0.0,
            "total_scored_listings": len(lqs_scores),
            "total_scored_brands": len(ri_scores),
        }
    except Exception as e:
        # Graceful fallback in case table or columns are not initialized/available
        return {
            "avg_lqs": 0.0, "max_lqs": 0, "avg_ri": 0.0, "max_ri": 0, "avg_cqs": 0.0,
            "avg_flesch": 0.0, "avg_ttr": 0.0, "avg_cosmo": 0.0,
            "total_scored_listings": 0, "total_scored_brands": 0,
            "error": str(e)
        }

