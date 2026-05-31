"""High-volume Apollo prospect discovery — parallel search across all niches.

Fan out Apollo people search across every entry in APOLLO_NICHE_TAG_MAP
concurrently (bounded by MAX_APOLLO_CONCURRENCY semaphore), deduplicate
against the existing DB, bulk-match missing emails, and insert verified
contacts at CONTACT_ENRICHED.

Target: 500+ raw contacts per run, 100+ new enriched brands per week.

Usage:
    python main.py mass-prospect [--niches=beauty,pet] [--per-niche=25]
"""
import asyncio

import httpx

import apollo_api
import config
import db


APOLLO_SEARCH_URL = "https://api.apollo.io/api/v1/mixed_people/api_search"


def _get_existing_brand_keys():
    """Return the set of brand_keys already in the brands table."""
    res = db._sb().table("brands").select("brand_key").execute()
    return {r["brand_key"] for r in res.data}


def _person_to_brand_key(person):
    """Derive the brand_key from an Apollo person dict (same formula as main.py)."""
    org = person.get("organization") or {}
    org_name = org.get("name") or ""
    return "".join(c.lower() for c in org_name if c.isalnum())


def _dedup_against_db(people, existing_keys):
    """Filter out people whose brand_key is already in the DB."""
    seen = set()
    result = []
    for p in people:
        bk = _person_to_brand_key(p)
        if not bk or bk in existing_keys or bk in seen:
            continue
        seen.add(bk)
        result.append(p)
    return result


async def _search_one_niche(niche, per_niche, sem, client):
    """Fetch up to per_niche verified founder contacts for one niche via Apollo."""
    mapping = config.resolve_apollo_niche(niche)
    payload = {
        "person_titles": config.APOLLO_TARGET_TITLES,
        "person_seniorities": ["founder", "owner", "c_suite"],
        "contact_email_status": ["verified"],
        "organization_num_employees_ranges": config.APOLLO_NUM_EMPLOYEES_RANGES,
        "person_locations": config.APOLLO_PERSON_LOCATIONS,
        "page": 1,
        "per_page": min(per_niche, 100),
    }
    if mapping.get("tags"):
        payload["q_organization_keyword_tags"] = mapping["tags"]
    if mapping.get("industries"):
        payload["organization_industries"] = mapping["industries"]

    headers = apollo_api._get_headers()
    collected = []

    async with sem:
        try:
            resp = await client.post(APOLLO_SEARCH_URL, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            people = data.get("people") or data.get("contacts") or []
            for p in people:
                if apollo_api._is_target_title(p.get("title")):
                    collected.append(p)
                if len(collected) >= per_niche:
                    break
        except httpx.HTTPStatusError as e:
            print(f"[mass_prospect] HTTP error for niche '{niche}': {e} — {e.response.text[:200]}")
        except Exception as e:
            print(f"[mass_prospect] Error for niche '{niche}': {e}")

    return collected


async def run_mass_prospect_async(niches=None, per_niche=None, console=None):
    """Async core: fan out across all niches, dedup, bulk-match, insert. Returns count inserted."""
    if niches is None:
        niches = list(config.APOLLO_NICHE_TAG_MAP.keys())
    if per_niche is None:
        per_niche = config.MASS_PROSPECT_PER_NICHE

    if console:
        console.print(f"[dim]Searching {len(niches)} niches × {per_niche} contacts each…[/dim]")

    sem = asyncio.Semaphore(config.MAX_APOLLO_CONCURRENCY)
    async with httpx.AsyncClient(timeout=config.APOLLO_REQUEST_TIMEOUT_S) as client:
        tasks = [_search_one_niche(niche, per_niche, sem, client) for niche in niches]
        results = await asyncio.gather(*tasks)

    raw_people = []
    for niche, people in zip(niches, results):
        if console and people:
            console.print(f"[dim]  {niche}: {len(people)} candidates[/dim]")
        raw_people.extend(people)

    if console:
        console.print(f"[dim]{len(raw_people)} total raw candidates across all niches[/dim]")

    # Deduplicate against DB and within this batch
    existing_keys = _get_existing_brand_keys()
    unique_people = _dedup_against_db(raw_people, existing_keys)

    if console:
        console.print(f"[dim]{len(unique_people)} new (not in DB) after dedup[/dim]")

    if not unique_people:
        return 0

    # Bulk-match contacts missing emails
    need_email = [p for p in unique_people if not p.get("email")]
    have_email = [p for p in unique_people if p.get("email")]

    if need_email:
        if console:
            console.print(f"[dim]Bulk-matching {len(need_email)} contacts missing emails…[/dim]")
        bulk_payload = [
            {
                "id": p.get("id", ""),
                "first_name": p.get("first_name", ""),
                "last_name": p.get("last_name", ""),
                "organization_name": (p.get("organization") or {}).get("name", ""),
            }
            for p in need_email
        ]
        matched = await apollo_api.bulk_match_async(bulk_payload)
        matched_by_id = {m.get("id"): m for m in matched if m.get("email")}
        for p in need_email:
            pid = p.get("id", "")
            if pid in matched_by_id:
                p.update(matched_by_id[pid])
        have_email.extend(need_email)
        if console:
            console.print(f"[dim]  → bulk_match resolved {len(matched_by_id)} emails[/dim]")

    # Insert into DB
    inserted = 0
    for p in have_email:
        email = p.get("email")
        EMAIL_STATUSES_ALLOWED = {"verified"}
        if not email or p.get("email_status") not in EMAIL_STATUSES_ALLOWED:
            continue
        org = p.get("organization") or {}
        org_name = org.get("name")
        domain = org.get("primary_domain") or org.get("website_url")
        if not org_name or not domain:
            continue
        if any(b.lower() in org_name.lower() for b in config.AMAZON_BRAND_BLOCKLIST):
            continue
        if "amazon.com" in domain.lower():
            continue

        brand_key = "".join(c.lower() for c in org_name if c.isalnum())
        ok = db.insert_apollo_brand(
            brand_key=brand_key,
            brand_name=org_name,
            domain=domain,
            contact_email=email,
            contact_first_name=p.get("first_name"),
            contact_last_name=p.get("last_name"),
            contact_title=p.get("title"),
            category=None,
            contact_linkedin=p.get("linkedin_url"),
            apollo_person_id=p.get("id"),
            apollo_organization_id=org.get("id"),
        )
        if ok:
            if console:
                console.print(f"  [green]✓[/green] {org_name} ({email})")
            inserted += 1

    return inserted


def run_mass_prospect(niches=None, per_niche=None, console=None):
    """Synchronous entry point for main.py."""
    db.init_db()
    return asyncio.run(run_mass_prospect_async(niches=niches, per_niche=per_niche, console=console))
