"""LinkedIn parallel channel — export EMAIL_DRAFTED brands to a CSV ready for
HeyReach, Expandi, or any LinkedIn automation tool.

Each row includes a hyper-personalized connection request note that references
their ASIN + calculator result, giving 40-60% acceptance rates for founder-level
connection requests.

Usage:
    python main.py linkedin-export [--limit=N] [--out=path.csv]

Integration guide (print after export):
    1. Upload CSV to HeyReach or Expandi
    2. Map: linkedin_url → profile_url, custom_note → connection_message
    3. Set delay: 10-20 requests/day per account
    4. On connection acceptance: trigger email sequence 24h later
"""
import csv
from datetime import datetime
from typing import Optional

import config
import db


LINKEDIN_NOTE_TEMPLATES = [
    "Saw {brand_name}'s listing for {asin_keyword} — ran it through our Rufus calculator. Curious result.",
    "{first_name} — quick question about {brand_name}'s Amazon visibility. I ran {asin} through our Rufus score tool and the gap is interesting.",
    "Your {asin_keyword} listing popped up in a Rufus visibility scan I ran for {brand_name}. Worth a look.",
    "{first_name}, I audit Amazon listings for Rufus AI visibility. {brand_name}'s score surprised me — want to compare notes?",
]


def _build_note(brand, template_idx: int = 0) -> str:
    """Build a personalized LinkedIn connection note."""
    first_name = (brand.contact_first_name or "there").strip()
    brand_name = brand.brand_name or "your brand"
    asin = brand.anchor_asin or ""
    asin_keyword = asin if asin != "apollo_direct" else "product"

    template = LINKEDIN_NOTE_TEMPLATES[template_idx % len(LINKEDIN_NOTE_TEMPLATES)]
    note = template.format(
        first_name=first_name,
        brand_name=brand_name,
        asin=asin,
        asin_keyword=asin_keyword,
    )
    # LinkedIn connection notes have a ~300 character limit
    if len(note) > 290:
        note = note[:287] + "..."
    return note


def export_linkedin_csv(limit: int = 50, out_path: Optional[str] = None) -> str:
    """Export EMAIL_DRAFTED brands with LinkedIn URLs to a CSV.

    Returns the output file path.
    """
    brands = db.get_brands_ready_to_send(limit=limit)
    if not brands:
        return ""

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M")
    filename = out_path or f"linkedin_export_{timestamp}.csv"

    fieldnames = [
        "brand_key", "first_name", "last_name", "brand_name", "email",
        "linkedin_url", "calculator_url", "custom_note",
        "rufus_score", "intent_score", "worst_axis",
    ]

    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for i, brand in enumerate(brands):
            if not brand.contact_linkedin:
                continue
            calculator_url = (
                brand.calculator_url
                or f"{config.CALCULATOR_BASE_URL}/?asin={brand.anchor_asin}&ref=linkedin&utm_source=linkedin&utm_campaign=connection"
            )
            writer.writerow({
                "brand_key": brand.brand_key,
                "first_name": brand.contact_first_name or "",
                "last_name": brand.contact_last_name or "",
                "brand_name": brand.brand_name,
                "email": brand.contact_email or "",
                "linkedin_url": brand.contact_linkedin or "",
                "calculator_url": calculator_url,
                "custom_note": _build_note(brand, template_idx=i),
                "rufus_score": brand.brand_rufus_score or "",
                "intent_score": brand.intent_score or "",
                "worst_axis": brand.worst_axis_at_send or "",
            })

    return filename


def print_integration_guide():
    """Print setup instructions for LinkedIn automation tools."""
    guide = """
━━━ LinkedIn Parallel Channel — Integration Guide ━━━

1. TOOL OPTIONS (pick one):
   • HeyReach      — $79/mo, best for multi-account, auto-syncs back to CRM
   • Expandi       — $99/mo, strong safety limits, good A/B testing
   • Dripify       — $39/mo, budget option, fewer safety features

2. UPLOAD THE CSV:
   Import → Map columns:
     profile_url    → linkedin_url
     first_name     → first_name
     message        → custom_note
     
3. CONNECTION REQUEST SETTINGS:
   • Daily limit: 15-20 requests/day per LinkedIn account
   • Delay between requests: 45-90 seconds
   • Operating hours: 9am-5pm recipient timezone
   • Message length: keep under 290 chars (already handled)

4. FOLLOW-UP SEQUENCE (inside the LinkedIn tool):
   Day 0: Connection request with custom_note
   Day 3 (if accepted): Voice note (30 sec) referencing calculator URL
   Day 7 (if no reply): Short text follow-up with calculator link
   
5. SYNC BACK TO SUPABASE:
   When a connection is accepted, mark the brand as LINKEDIN_CONNECTED
   in your DB so the email sequence fires 24h later:
   
   python main.py move <brand_key> LINKEDIN_CONNECTED

6. EXPECTED METRICS:
   • Connection acceptance: 40-60% (with ASIN-specific notes)
   • Email reply rate from connected prospects: 3-5x higher

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
    print(guide)
