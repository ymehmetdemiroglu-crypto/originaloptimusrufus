import asyncio
import logging
from typing import Iterable

import httpx
import requests

import config

APOLLO_BASE_URL = "https://api.apollo.io/api/v1"
_logger = logging.getLogger("acquisition_tool.apollo")


def _is_target_title(title: str | None) -> bool:
    """
    Hard gate: returns True only for founder/owner/CEO-level titles.
    Apollo's title search is fuzzy and returns Directors, Managers, etc.
    This filter prevents non-decision-makers from reaching the send queue.

    Logic: accept if ANY founder keyword matches, THEN reject if any
    middle-management keyword appears and no founder keyword overrides it.
    Founder keywords take precedence so "Managing Director" and
    "Founder & CEO" pass even though "director" is in the exclude list.
    """
    if not title:
        return False
    t = title.lower()

    # Fast accept: if a founder-level keyword is present, let it through
    # (handles "Founder & CEO", "Managing Director", "Chief Executive Officer")
    if any(kw in t for kw in config.APOLLO_FOUNDER_TITLE_KEYWORDS):
        return True

    # Reject titles that only have mid-management signals
    if any(exc in t for exc in config.APOLLO_TITLE_EXCLUDE_KEYWORDS):
        return False

    return False  # no founder keyword at all — reject

def _get_headers():
    return {
        "Content-Type": "application/json",
        "Cache-Control": "no-cache",
        "x-api-key": config.APOLLO_API_KEY
    }

def enrich_brand(brand_name=None, domain=None):
    """
    Search for target decision makers at a specific brand or domain.
    Returns the first verified match, or None.
    """
    if not config.APOLLO_API_KEY:
        _logger.warning("APOLLO_API_KEY is missing. Skipping enrichment.")
        return None

    url = f"{APOLLO_BASE_URL}/mixed_people/api_search"
    payload = {
        "person_titles": config.APOLLO_TARGET_TITLES,
        "person_seniorities": ["founder", "owner", "c_suite"],
        "organization_num_employees_ranges": config.APOLLO_NUM_EMPLOYEES_RANGES,
        "contact_email_status": ["verified"],
        "person_locations": config.APOLLO_PERSON_LOCATIONS,
        "page": 1,
        "per_page": 10
    }
    
    if domain:
        payload["q_organization_domains"] = domain
    elif brand_name:
        payload["q_organization_names"] = [brand_name]
    else:
        return None

    try:
        for page in range(1, 4):
            payload["page"] = page
            response = requests.post(url, headers=_get_headers(), json=payload, timeout=30.0)
            response.raise_for_status()
            data = response.json()
            
            people = data.get("people", [])
            if not people:
                people = data.get("contacts", [])

            for person in people:
                title = (person.get("title") or "")
                if _is_target_title(title):
                    return person
        return None
    except requests.exceptions.HTTPError as e:
        _logger.error(f"Error enriching {domain or brand_name}: {e}")
        _logger.error(f"Response text: {e.response.text}")
        return None
    except Exception as e:
        _logger.error(f"Error enriching {domain or brand_name}: {e}")
        return None

def get_person(person_id):
    """Fetch full profile for a person using people/match endpoint."""
    if not config.APOLLO_API_KEY:
        return None
        
    url = f"{APOLLO_BASE_URL}/people/match"
    payload = {
        "id": person_id
    }
    
    try:
        response = requests.post(url, headers=_get_headers(), json=payload, timeout=30.0)
        response.raise_for_status()
        data = response.json()
        return data.get("person")
    except Exception as e:
        _logger.error(f"Error fetching person {person_id}: {e}")
        return None

def bulk_match(people: list[dict]) -> list[dict]:
    """
    Enrich up to 10 people per call via /people/bulk_match.
    Each dict should have: id (Apollo person id), first_name, organization_name.
    Returns list of matched person objects that have an email.
    Automatically batches input into chunks of 10.
    """
    if not config.APOLLO_API_KEY:
        _logger.warning("APOLLO_API_KEY is missing. Skipping bulk match.")
        return []

    url = f"{APOLLO_BASE_URL}/people/bulk_match"
    results = []

    for i in range(0, len(people), 10):
        batch = people[i:i + 10]
        payload = {
            "details": [
                {k: v for k, v in p.items() if k in ("id", "first_name", "last_name", "organization_name", "domain", "email", "linkedin_url") and v}
                for p in batch
            ],
            "reveal_personal_emails": False,
        }
        try:
            resp = requests.post(url, headers=_get_headers(), json=payload, timeout=30.0)
            resp.raise_for_status()
            data = resp.json()
            matched = data.get("matches", [])
            for person in matched:
                if person and person.get("email"):
                    results.append(person)
        except requests.exceptions.HTTPError as e:
            _logger.error(f"bulk_match batch {i//10 + 1} error: {e}")
            if e.response is not None:
                _logger.error(f"Response: {e.response.text[:300]}")
        except Exception as e:
            _logger.error(f"bulk_match batch {i//10 + 1} error: {e}")

    return results


def create_contact(
    email: str,
    first_name: str,
    last_name: str,
    title: str,
    organization_name: str,
    website_url: str = "",
    typed_custom_fields: dict | None = None,
) -> str | None:
    """Create a contact in Apollo. Returns the new contact ID or None on failure."""
    if not config.APOLLO_API_KEY:
        return None
    url = f"{APOLLO_BASE_URL}/contacts"
    payload: dict = {
        "first_name": first_name,
        "last_name": last_name,
        "email": email,
        "title": title,
        "organization_name": organization_name,
        "run_dedupe": True,
    }
    if website_url:
        payload["website_url"] = website_url
    if typed_custom_fields:
        payload["typed_custom_fields"] = typed_custom_fields
    try:
        resp = requests.post(url, headers=_get_headers(), json=payload, timeout=30.0)
        resp.raise_for_status()
        return resp.json().get("contact", {}).get("id")
    except requests.exceptions.HTTPError as e:
        _logger.error(f"create_contact error ({email}): {e} — {e.response.text[:200]}")
        return None
    except Exception as e:
        _logger.error(f"create_contact error ({email}): {e}")
        return None


def add_to_sequence(sequence_id: str, contact_id: str, send_from_id: str) -> bool:
    """Enroll a contact in an Apollo sequence. Returns True on success."""
    if not config.APOLLO_API_KEY:
        return False
    url = f"{APOLLO_BASE_URL}/emailer_campaigns/{sequence_id}/add_contact_ids"
    payload = {
        "emailer_campaign_id": sequence_id,
        "contact_ids": [contact_id],
        "send_email_from_email_account_id": send_from_id,
        "sequence_active_in_other_campaigns": False,
        "sequence_finished_in_other_campaigns": False,
    }
    try:
        resp = requests.post(url, headers=_get_headers(), json=payload, timeout=30.0)
        resp.raise_for_status()
        return True
    except requests.exceptions.HTTPError as e:
        _logger.error(f"add_to_sequence error ({contact_id}): {e} — {e.response.text[:200]}")
        return False
    except Exception as e:
        _logger.error(f"add_to_sequence error ({contact_id}): {e}")
        return False


def search_prospects(category, limit=20, page=1):
    """
    Search Apollo directly for prospects in a specific category.
    Mimics the /prospect Funnel B.
    """
    if not config.APOLLO_API_KEY:
        _logger.warning("APOLLO_API_KEY is missing. Skipping prospect search.")
        return []

    url = f"{APOLLO_BASE_URL}/mixed_people/api_search"

    # Resolve the niche to Apollo's controlled-vocab tags + industry filter.
    # Sending a multi-word niche as a literal q_organization_keyword_tag (or as
    # q_keywords) returns near-zero matches because Apollo treats both as strict
    # matches against a short tag vocabulary / org name+description text. Instead:
    #   - q_organization_keyword_tags: broad bucket Apollo actually tags ("skincare", "supplements", …)
    #   - organization_industries: hard filter so off-vertical orgs can't slip through
    # The literal niche term is then re-applied at the Amazon ASIN-backfill step,
    # which is the real relevance gate (no listing → SKIP_NO_LISTING).
    mapping = config.resolve_apollo_niche(category)

    payload = {
        "person_titles": config.APOLLO_TARGET_TITLES,
        "person_seniorities": ["founder", "owner", "c_suite"],
        "contact_email_status": ["verified"],
        "organization_num_employees_ranges": config.APOLLO_NUM_EMPLOYEES_RANGES,
        "person_locations": config.APOLLO_PERSON_LOCATIONS,
        "page": page,
        "per_page": min(limit, 100)
    }
    if mapping.get("tags"):
        payload["q_organization_keyword_tags"] = mapping["tags"]
    if mapping.get("industries"):
        payload["organization_industries"] = mapping["industries"]

    try:
        response = requests.post(url, headers=_get_headers(), json=payload, timeout=30.0)
        response.raise_for_status()
        data = response.json()

        people = data.get("people", [])
        if not people:
            people = data.get("contacts", [])

        # Filter to founder/owner/CEO-level only before returning
        people = [p for p in people if _is_target_title(p.get("title"))]
        return people[:limit]
    except requests.exceptions.HTTPError as e:
        _logger.error(f"Error searching prospects for {category}: {e}")
        _logger.error(f"Response text: {e.response.text}")
        return []
    except Exception as e:
        _logger.error(f"Error searching prospects for {category}: {e}")
        return []


# ---------------------------------------------------------------------------
# Async variants — used by the streaming pipeline orchestrator
# ---------------------------------------------------------------------------

def _bulk_match_payload(batch: list[dict]) -> dict:
    return {
        "details": [
            {
                k: v
                for k, v in p.items()
                if k in ("id", "first_name", "last_name", "organization_name", "domain", "email", "linkedin_url")
                and v
            }
            for p in batch
        ],
        "reveal_personal_emails": False,
    }


async def bulk_match_async(
    people: list[dict],
    client: httpx.AsyncClient | None = None,
    semaphore: asyncio.Semaphore | None = None,
) -> list[dict]:
    """Async, fan-out version of bulk_match. Shards into 10-person calls and fires
    them concurrently under the provided semaphore (defaults to MAX_APOLLO_CONCURRENCY)."""
    if not config.APOLLO_API_KEY or not people:
        return []

    sem = semaphore or asyncio.Semaphore(config.MAX_APOLLO_CONCURRENCY)
    owns_client = client is None
    if owns_client:
        client = httpx.AsyncClient(timeout=config.APOLLO_REQUEST_TIMEOUT_S)

    url = f"{APOLLO_BASE_URL}/people/bulk_match"
    headers = _get_headers()

    async def _one(batch: list[dict]) -> list[dict]:
        async with sem:
            try:
                resp = await client.post(url, headers=headers, json=_bulk_match_payload(batch))
                resp.raise_for_status()
                data = resp.json()
                return [m for m in data.get("matches", []) if m and m.get("email")]
            except httpx.HTTPStatusError as e:
                _logger.error(f"bulk_match_async HTTP error: {e} — {e.response.text[:200]}")
                return []
            except Exception as e:
                _logger.error(f"bulk_match_async error: {e}")
                return []

    try:
        chunks = [people[i : i + 10] for i in range(0, len(people), 10)]
        results = await asyncio.gather(*(_one(c) for c in chunks))
    finally:
        if owns_client:
            await client.aclose()

    out: list[dict] = []
    for r in results:
        out.extend(r)
    return out


async def enrich_brand_async(
    brand_name: str | None = None,
    domain: str | None = None,
    client: httpx.AsyncClient | None = None,
    semaphore: asyncio.Semaphore | None = None,
) -> dict | None:
    """Async equivalent of enrich_brand — single-brand search with the same target-title gate."""
    if not config.APOLLO_API_KEY:
        return None
    if not (brand_name or domain):
        return None

    sem = semaphore or asyncio.Semaphore(config.MAX_APOLLO_CONCURRENCY)

    payload = {
        "person_titles": config.APOLLO_TARGET_TITLES,
        "person_seniorities": ["founder", "owner", "c_suite"],
        "organization_num_employees_ranges": config.APOLLO_NUM_EMPLOYEES_RANGES,
        "contact_email_status": ["verified"],
        "person_locations": config.APOLLO_PERSON_LOCATIONS,
        "page": 1,
        "per_page": 10,
    }
    if domain:
        payload["q_organization_domains"] = domain
    else:
        payload["q_organization_names"] = [brand_name]

    url = f"{APOLLO_BASE_URL}/mixed_people/api_search"

    async def _do(c: httpx.AsyncClient) -> dict | None:
        try:
            async with sem:
                resp = await c.post(url, headers=_get_headers(), json=payload)
                resp.raise_for_status()
                data = resp.json()
        except Exception as e:
            _logger.error(f"enrich_brand_async error ({domain or brand_name}): {e}")
            return None
        people = data.get("people") or data.get("contacts") or []
        for person in people:
            if _is_target_title(person.get("title") or ""):
                return person
        return None

    if client is None:
        async with httpx.AsyncClient(timeout=config.APOLLO_REQUEST_TIMEOUT_S) as c:
            return await _do(c)
    return await _do(client)


async def enrich_brands_async(
    brands: Iterable[tuple[str | None, str | None]],
    semaphore: asyncio.Semaphore | None = None,
) -> list[dict | None]:
    """Run enrich_brand_async over many (brand_name, domain) pairs concurrently.

    Returns results aligned with input order; caller maps to brand_keys.
    """
    sem = semaphore or asyncio.Semaphore(config.MAX_APOLLO_CONCURRENCY)
    async with httpx.AsyncClient(timeout=config.APOLLO_REQUEST_TIMEOUT_S) as client:
        tasks = [
            enrich_brand_async(brand_name=bn, domain=dom, client=client, semaphore=sem)
            for bn, dom in brands
        ]
        return await asyncio.gather(*tasks)
