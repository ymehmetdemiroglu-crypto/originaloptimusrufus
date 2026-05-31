import sys
import os

# Ensure we can import from the current directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from apify_client import ApifyClient
import config
import db
from amazon_scraper import _fetch_listing_detail, _to_prospect

def main():
    db.init_db()
    conn = db._conn()
    brands = conn.execute("SELECT * FROM brands WHERE anchor_asin = 'apollo_direct'").fetchall()
    
    if not brands:
        print("No brands needing ASIN backfill found.")
        return
        
    print(f"Found {len(brands)} brands needing ASIN research on Amazon.")
    client = ApifyClient(config.APIFY_TOKEN)
    
    # Batch 1: Search all brands in one call
    print("Batching search requests...")
    search_inputs = []
    brand_map = {} # search_kw -> brand_key
    
    for b in brands:
        search_kw = f"{b['brand_name']} {b['category']}".strip()
        brand_map[search_kw.lower()] = dict(b)
        search_inputs.append({
            "keyword": search_kw,
            "domainCode": config.AMAZON_DOMAIN.replace("amazon.", ""),
            "sortBy": "relevanceblender",
            "page": 1,
        })
    
    print(f"Calling Amazon Search Actor with {len(search_inputs)} keywords (this is a single fast call)...")
    try:
        run = client.actor(config.APIFY_AMAZON_SEARCH_ACTOR_ID).call(run_input={"input": search_inputs})
        raw_search = list(client.dataset(run["defaultDatasetId"]).iterate_items())
    except Exception as e:
        print(f"Search API Error: {e}")
        return
        
    print(f"Search returned {len(raw_search)} total items. Mapping to brands...")
    
    asin_to_brand = {}
    urls_to_fetch = []
    asins_to_fetch = []
    
    for item in raw_search:
        kw = item.get("keyword") or item.get("searchQuery")
        item_asin = item.get("asin") or item.get("ASIN")
        if not item_asin: continue
        
        matched_b = None
        if kw and kw.lower() in brand_map:
            matched_b = brand_map[kw.lower()]
        else:
            item_brand = (item.get("brand") or item.get("manufacturer") or "").lower()
            for skw, b in brand_map.items():
                b_name = b['brand_name'].lower()
                if (b_name and (b_name in item_brand or item_brand in b_name)) and skw in brand_map:
                    matched_b = b
                    break
        
        if matched_b and matched_b['brand_key'] not in [b['brand_key'] for b in asin_to_brand.values()]:
            asin_to_brand[item_asin] = matched_b
            asins_to_fetch.append(item_asin)
            urls_to_fetch.append(f"https://www.{config.AMAZON_DOMAIN}/dp/{item_asin}")
            # remove from map so we only get 1 ASIN per brand
            if kw and kw.lower() in brand_map:
                del brand_map[kw.lower()]
            else:
                for skw, b in list(brand_map.items()):
                    if b['brand_key'] == matched_b['brand_key']:
                        del brand_map[skw]
    
    print(f"Found {len(asins_to_fetch)} ASINs to detail.")
    if not asins_to_fetch:
        print("Could not map any ASINs.")
        return
        
    print(f"Batching {len(asins_to_fetch)} detail requests in a single call...")
    run_input = {
        "urls": urls_to_fetch,
        "domainCode": config.AMAZON_DOMAIN.replace("amazon.", ""),
    }
    
    try:
        run2 = client.actor(config.APIFY_AMAZON_DETAIL_ACTOR_ID).call(run_input=run_input)
        detail_items = list(client.dataset(run2["defaultDatasetId"]).iterate_items())
    except Exception as e:
        print(f"Detail API Error: {e}")
        return
        
    print(f"Detail returned {len(detail_items)} items. Updating database...")
    for item in detail_items:
        asin = item.get("asin") or item.get("ASIN")
        if not asin or asin not in asin_to_brand:
            continue
            
        b = asin_to_brand[asin]
        p = _to_prospect(item, b['category'])
        if p:
            db.upsert_listing(p)
            conn.execute("UPDATE brands SET anchor_asin = ? WHERE brand_key = ?", (asin, b['brand_key']))
            print(f"  -> Updated brand {b['brand_name']} -> ASIN {asin}")
            
    conn.commit()
    print("All done!")

if __name__ == '__main__':
    main()
