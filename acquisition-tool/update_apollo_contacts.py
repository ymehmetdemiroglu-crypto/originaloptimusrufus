"""
Patch custom fields (custom_subject_1..5, custom_body_1..5) on existing
Apollo contacts for all SEQUENCED brands that have an apollo_contact_id.
"""
import sys
import sqlite3
import time
import requests
import config

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

APOLLO_BASE_URL = "https://api.apollo.io/api/v1"


def _headers():
    return {"x-api-key": config.APOLLO_API_KEY, "Content-Type": "application/json"}


def patch_contact(contact_id: str, typed_custom_fields: dict) -> bool:
    url = f"{APOLLO_BASE_URL}/contacts/{contact_id}"
    try:
        resp = requests.patch(
            url,
            headers=_headers(),
            json={"typed_custom_fields": typed_custom_fields},
        )
        resp.raise_for_status()
        return True
    except requests.exceptions.HTTPError as e:
        print(f"  ERROR {contact_id}: {e} — {e.response.text[:200]}")
        return False
    except Exception as e:
        print(f"  ERROR {contact_id}: {e}")
        return False


def main():
    con = sqlite3.connect("data/prospects.db")
    con.row_factory = sqlite3.Row

    brands = con.execute(
        """
        SELECT b.brand_key, b.brand_name, b.contact_email, b.apollo_contact_id,
               b.custom_subject, b.custom_body, b.email_teardown, b.category
        FROM brands b
        WHERE b.apollo_contact_id IS NOT NULL
          AND b.apollo_contact_id != ''
        ORDER BY b.updated_at DESC
        """
    ).fetchall()

    print(f"Brands with apollo_contact_id: {len(brands)}")
    ok = 0
    fail = 0

    for b in brands:
        brand_key = b["brand_key"]
        contact_id = b["apollo_contact_id"]

        # Load step emails
        steps = con.execute(
            "SELECT step_num, subject, body FROM brand_step_emails WHERE brand_key = ? ORDER BY step_num",
            (brand_key,),
        ).fetchall()

        if not steps:
            print(f"  SKIP {brand_key} — no step emails in DB")
            continue

        custom = {}
        for s in steps:
            custom[f"custom_subject_{s['step_num']}"] = s["subject"] or ""
            custom[f"custom_body_{s['step_num']}"] = s["body"] or ""

        # Back-compat fields
        if b["custom_subject"]:
            custom["custom_subject"] = b["custom_subject"]
        if b["custom_body"]:
            custom["custom_body"] = b["custom_body"]
        if b["email_teardown"]:
            custom["weakness_teardown"] = b["email_teardown"]
        if b["category"]:
            custom["custom_category"] = b["category"]

        success = patch_contact(contact_id, custom)
        if success:
            print(f"  ok  {brand_key}  ({contact_id[:12]}...)")
            ok += 1
        else:
            fail += 1

        time.sleep(0.3)  # stay within Apollo rate limit

    con.close()
    print(f"\nDone: {ok} updated, {fail} failed")


if __name__ == "__main__":
    main()
