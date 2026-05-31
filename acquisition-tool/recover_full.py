import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from apify_client import ApifyClient
import config
import db
from amazon_scraper import _to_prospect

client = ApifyClient(config.APIFY_TOKEN)

search_run = client.run('n6VZLqLAtepqTfjq3').get()
search_items = list(client.dataset(search_run['defaultDatasetId']).iterate_items())

detail_run = client.run('JqrCUpRRKHk7St7jf').get()
detail_items = list(client.dataset(detail_run['defaultDatasetId']).iterate_items())

db.init_db()

with db._conn() as conn:
    brands = conn.execute("SELECT * FROM brands WHERE anchor_asin = 'apollo_direct'").fetchall()

brand_map = {}
for b in brands:
    search_kw = f"{b['brand_name']} {b['category']}".strip().lower()
    brand_map[search_kw] = dict(b)

asin_to_brand = {}
for item in search_items:
    kw = item.get('keyword') or item.get('searchQuery')
    item_asin = item.get('asin') or item.get('ASIN')
    if not item_asin: continue
    
    matched_b = None
    if kw and kw.lower() in brand_map:
        matched_b = brand_map[kw.lower()]
    else:
        item_brand = (item.get('brand') or item.get('manufacturer') or '').lower()
        for skw, b in brand_map.items():
            b_name = b['brand_name'].lower()
            if b_name and (b_name in item_brand or item_brand in b_name):
                matched_b = b
                break
                
    if matched_b and matched_b['brand_key'] not in [b['brand_key'] for b in asin_to_brand.values()]:
        asin_to_brand[item_asin] = matched_b

print(f"Mapped {len(asin_to_brand)} ASINs to brands")

saved = 0
for item in detail_items:
    asin = item.get('asin') or item.get('ASIN')
    b = asin_to_brand.get(asin)
    if not b: continue
    
    p = _to_prospect(item, b['category'])
    if p:
        db.upsert_listing(p)
        with db._conn() as conn:
            conn.execute("UPDATE brands SET anchor_asin = ? WHERE brand_key = ?", (asin, b['brand_key']))
            conn.commit()
        saved += 1

print(f"Saved {saved} brands!")
