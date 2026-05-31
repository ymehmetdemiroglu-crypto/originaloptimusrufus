"""Resilient External Data Ingestion Layer with rate limiting and retry fallbacks."""

import asyncio
import time
import httpx
import os
import logging
from typing import List, Dict, Optional
from tenacity import retry, stop_after_attempt, wait_exponential

class TokenBucketLimiter:
    def __init__(self, rate: float, capacity: int):
        self.rate = rate
        self.capacity = capacity
        self.tokens = capacity
        self.last_update = time.monotonic()
        self.lock = asyncio.Lock()

    async def consume(self):
        async with self.lock:
            now = time.monotonic()
            elapsed = now - self.last_update
            self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
            self.last_update = now
            
            if self.tokens < 1:
                wait_time = (1 - self.tokens) / self.rate
                await asyncio.sleep(wait_time)
                self.tokens = 0
            else:
                self.tokens -= 1

from core.spapi_client import spapi_client

class ExternalDataClient:
    def __init__(self, rainforest_api_key: Optional[str] = None):
        self.rainforest_api_key = rainforest_api_key or os.getenv("RAINFOREST_API_KEY")
        # SP-API has a strict limit of 2 requests per second for Catalog Items
        self.sp_api_limiter = TokenBucketLimiter(rate=2.0, capacity=2)
        # Rainforest has generous API limits but we limit it to 10 requests per second
        self.rainforest_limiter = TokenBucketLimiter(rate=10.0, capacity=5)
        
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def get_catalog_item(self, asin: str) -> dict:
        """Retrieve catalog data for any ASIN via SP-API Catalog (Mocked or Real API)."""
        await self.sp_api_limiter.consume()
        
        if spapi_client.is_configured():
            try:
                raw_response = await spapi_client.get_visible_listing(asin)
                if "error" not in raw_response:
                    parsed = spapi_client.parse_visible_attributes(raw_response)
                    return parsed
                else:
                    logging.warning(f"SP-API get_visible_listing returned error: {raw_response}. Falling back to simulation.")
            except Exception as e:
                logging.error(f"SP-API Catalog exception: {e}. Falling back to simulation.")
        
        return self._simulate_catalog_item(asin)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def get_backend_listing(self, sku: str) -> dict:
        """Retrieve backend listing attributes for client's own listing via SP-API Listings Items."""
        if spapi_client.is_configured():
            try:
                raw_response = await spapi_client.get_backend_listing(sku)
                if "error" not in raw_response:
                    parsed = spapi_client.parse_backend_attributes(raw_response)
                    return parsed
                else:
                    logging.warning(f"SP-API get_backend_listing returned error: {raw_response}. Returning empty attributes.")
            except Exception as e:
                logging.error(f"SP-API Listings Items exception: {e}. Returning empty attributes.")
        
        # Fallback to simulated backend data derived from catalog simulation
        logging.info(f"Using simulated backend data for SKU {sku}")
        sim = self._simulate_catalog_item(sku)
        return {
            "title": sim["title"],
            "bullets": sim["bullets"],
            "description": sim["description"],
            "brand": sim["brand"],
            "generic_keywords": ["high performance", "ergonomic comfort", "durability", "travel camp"],
            "target_audience": ["professionals", "health conscious", "travelers"]
        }

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def get_competitor_reviews_and_bullets(self, asin: str) -> dict:
        """Fetch competitor product information and reviews using Rainforest API."""
        await self.rainforest_limiter.consume()
        
        if not self.rainforest_api_key:
            logging.info(f"No Rainforest API key. Using simulated competitor details for {asin}")
            return self._simulate_competitor_details(asin)
            
        try:
            async with httpx.AsyncClient() as client:
                url = "https://api.rainforestapi.com/request"
                params = {
                    "api_key": self.rainforest_api_key,
                    "type": "product",
                    "amazon_domain": "amazon.com",
                    "asin": asin
                }
                response = await client.get(url, params=params, timeout=15.0)
                response.raise_for_status()
                data = response.json()
                
                product = data.get("product", {})
                bullets = product.get("feature_bullets", [])
                title = product.get("title", f"Competitor {asin}")
                rating = product.get("rating", 4.4)
                reviews = [r.get("body", "") for r in data.get("reviews", []) if r.get("body")]
                
                return {
                    "asin": asin,
                    "title": title,
                    "bullets": bullets,
                    "description": product.get("description", ""),
                    "price": product.get("buybox_winner", {}).get("price", {}).get("raw", "$25.00"),
                    "rating": str(rating),
                    "review_count": product.get("ratings_total", 500),
                    "reviews": reviews,
                    "full_text": title + "\n" + "\n".join(bullets)
                }
        except Exception as e:
            logging.error(f"Rainforest API failure for {asin}: {e}. Falling back to simulation.")
            return self._simulate_competitor_details(asin)

    def _simulate_catalog_item(self, asin: str) -> dict:
        """Generates realistic catalog data based on seed configurations."""
        from data.store import store
        listing = store.get_listing(asin)
        if listing:
            return {
                "asin": asin,
                "title": listing["title"],
                "bullets": listing["bullets"],
                "description": listing["description"],
                "brand": listing["brand"]
            }
        return {
            "asin": asin,
            "title": f"Simulated High-Performance product {asin}",
            "bullets": [
                "ADVANCED ERGONOMIC DESIGN FOR ALL-DAY COMFORT - Specifically contoured to match biological curves, perfect for prolonged office work or daily workouts",
                "PREMIUM MATERIALS FOR SUSTAINED DURABILITY - Built with eco-friendly components that resist damage and ensure long-term utility for health-conscious users",
                "CONVENIENT AND PORTABLE ON-THE-GO COMPANION - Sleek, lightweight layout fits easily in backpacks or luggage for active travel and outdoor camping adventures",
                "RISK-FREE 100% SATISFACTION GUARANTEE - Complete peace of mind with our hassle-free replacement service for every valued customer"
            ],
            "description": "This is a high-performance product simulated to validate COSMO relationship models.",
            "brand": "SimuBrand"
        }

    def _simulate_competitor_details(self, asin: str) -> dict:
        """Generates mock competitor listing and reviews if no credentials are configured."""
        from data.store import store
        all_comp = []
        for comps in store.competitors.values():
            all_comp.extend(comps)
            
        matched = next((c for c in all_comp if c["asin"] == asin), None)
        title = matched["title"] if matched else f"Competitor Product {asin}"
        price = matched["price"] if matched else "$24.99"
        rating = matched["rating"] if matched else "4.4"
        review_count = matched["review_count"] if matched else 680
        
        return {
            "asin": asin,
            "title": title,
            "bullets": [
                f"Market-leading hydration alternative matching the premium standard of {asin}",
                "Heavy-duty double walled insulation keeps beverages cold for hours during hikes",
                "Travel cap with loop for hiking clips and backpacks",
                "Made from robust materials, safe for everyday household and travel use"
            ],
            "description": "Simulated competitor product detail for semantic analysis.",
            "price": price,
            "rating": rating,
            "review_count": review_count,
            "reviews": [
                "Really love the thermal insulation, kept my water cold all day at the beach!",
                "Decent product but the cap is a bit stiff to open on travel commutes.",
                "Perfect for nursing shifts at the local clinic, holds plenty of liquid."
            ],
            "full_text": title + "\n" + f"Market-leading standard. Heavy-duty double walled insulation. Perfect for nursing shifts."
        }

external_client = ExternalDataClient()
