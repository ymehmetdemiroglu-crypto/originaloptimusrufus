"""
Production-grade Async Amazon Selling Partner API (SP-API) Client.
Handles both Backend listing data (Listings Items API) and Customer-Visible listing data (Catalog Items API).
Includes automatic LWA (Login with Amazon) access token refresh, caching, and rate limiting.
"""

import httpx
import os
import time
import logging
import asyncio
from typing import Dict, Any, Optional, List

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SPAPIClient")

class SPTokenBucketLimiter:
    """Token bucket rate limiter to adhere to SP-API guidelines."""
    def __init__(self, rate: float, capacity: int):
        self.rate = rate
        self.capacity = capacity
        self.tokens = float(capacity)
        self.last_update = time.monotonic()
        self.lock = asyncio.Lock()

    async def consume(self):
        async with self.lock:
            now = time.monotonic()
            elapsed = now - self.last_update
            self.tokens = min(float(self.capacity), self.tokens + elapsed * self.rate)
            self.last_update = now
            
            if self.tokens < 1.0:
                wait_time = (1.0 - self.tokens) / self.rate
                logger.warning(f"SP-API Rate limit reached. Backing off for {wait_time:.2f} seconds...")
                await asyncio.sleep(wait_time)
                self.tokens = 0.0
            else:
                self.tokens -= 1.0

class AmazonSPAPIClient:
    """
    Asynchronous Amazon SP-API Client utilizing direct LWA OAuth integration.
    Simplifies setup by avoiding complex AWS IAM Signatures, using Amazon's recommended LWA-Only flow.
    """
    
    REGIONS = {
        "US": {"endpoint": "https://sellingpartnerapi-na.amazon.com", "lwa_url": "https://api.amazon.com/auth/o2/token"},
        "EU": {"endpoint": "https://sellingpartnerapi-eu.amazon.com", "lwa_url": "https://api.amazon.com/auth/o2/token"},
        "FE": {"endpoint": "https://sellingpartnerapi-fe.amazon.com", "lwa_url": "https://api.amazon.com/auth/o2/token"},
    }

    def __init__(self):
        self.client_id = os.getenv("LWA_CLIENT_ID")
        self.client_secret = os.getenv("LWA_CLIENT_SECRET")
        self.refresh_token = os.getenv("SP_API_REFRESH_TOKEN")
        self.seller_id = os.getenv("AMAZON_SELLER_ID")
        self.region = os.getenv("SP_API_REGION", "US").upper()
        
        region_config = self.REGIONS.get(self.region, self.REGIONS["US"])
        self.base_url = region_config["endpoint"]
        self.lwa_url = region_config["lwa_url"]
        
        # Token caches
        self.access_token: Optional[str] = None
        self.token_expiry: float = 0.0
        
        # Rate limiters matching Amazon SP-API limits
        # Listings Items API has a standard transaction limit of 5 requests per second
        self.listings_limiter = SPTokenBucketLimiter(rate=5.0, capacity=5)
        # Catalog Items API has a strict transaction limit of 2 requests per second
        self.catalog_limiter = SPTokenBucketLimiter(rate=2.0, capacity=2)

    def is_configured(self) -> bool:
        """Check if all necessary credentials are present in the environment."""
        return all([self.client_id, self.client_secret, self.refresh_token, self.seller_id])

    async def _get_access_token(self, client: httpx.AsyncClient) -> str:
        """Retrieves or refreshes the Login with Amazon (LWA) access token."""
        now = time.time()
        # If token is still valid (with a 5-minute safety buffer), return it
        if self.access_token and now < self.token_expiry - 300:
            return self.access_token

        if not self.client_id or not self.client_secret or not self.refresh_token:
            raise ValueError("LWA Client ID, Client Secret, or SP-API Refresh Token is missing in environment variables.")

        logger.info("Refreshing Amazon LWA Access Token...")
        payload = {
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token,
            "client_id": self.client_id,
            "client_secret": self.client_secret
        }
        
        response = await client.post(self.lwa_url, data=payload, timeout=10.0)
        if response.status_code != 200:
            logger.error(f"Failed to refresh LWA token: {response.text}")
            raise HTTPException(status_code=500, detail="Failed to authenticate with Amazon LWA service.")
            
        data = response.json()
        self.access_token = data["access_token"]
        # Token is valid for 3600 seconds (1 hour)
        self.token_expiry = now + int(data.get("expires_in", 3600))
        logger.info("Amazon LWA Access Token refreshed successfully.")
        return self.access_token

    async def _request(self, method: str, path: str, params: Optional[Dict[str, Any]] = None, json_data: Optional[Dict[str, Any]] = None, limiter: Optional[SPTokenBucketLimiter] = None) -> Dict[str, Any]:
        """Executes an authorized HTTP request to the SP-API endpoint."""
        if limiter:
            await limiter.consume()

        async with httpx.AsyncClient() as client:
            try:
                access_token = await self._get_access_token(client)
                headers = {
                    "x-amz-access-token": access_token,
                    "Accept": "application/json",
                    "Content-Type": "application/json"
                }
                
                url = f"{self.base_url}{path}"
                logger.info(f"SP-API Call: {method} {path}")
                
                response = await client.request(
                    method=method,
                    url=url,
                    headers=headers,
                    params=params,
                    json=json_data,
                    timeout=15.0
                )
                
                if response.status_code == 429:
                    logger.warning("SP-API returned 429 (Too Many Requests). Retrying after brief delay...")
                    await asyncio.sleep(2.0)
                    return await self._request(method, path, params, json_data, limiter)
                    
                if response.status_code not in [200, 201]:
                    logger.error(f"SP-API Error response [{response.status_code}]: {response.text}")
                    return {"error": response.status_code, "message": response.text}
                    
                return response.json()
            except Exception as e:
                logger.error(f"Network error calling SP-API: {e}")
                return {"error": "network_failure", "message": str(e)}

    async def get_backend_listing(self, sku: str) -> Dict[str, Any]:
        """
        Pull full backend attributes for a client's own listing.
        Uses Listings Items API: GET /listings/2021-08-01/items/{sellerId}/{sku}
        Required Role: Product Listing Category
        """
        if not self.is_configured():
            logger.warning("SP-API credentials not configured. Returning simulation placeholder.")
            return {"error": "unconfigured", "message": "Credentials missing"}

        path = f"/listings/2021-08-01/items/{self.seller_id}/{sku}"
        params = {
            "marketplaceIds": "ATVPDKIKX0DER",  # Default to US Marketplace ID
            "includedData": "attributes,summaries,issues,offers"
        }
        
        response = await self._request("GET", path, params=params, limiter=self.listings_limiter)
        return response

    async def get_visible_listing(self, asin: str) -> Dict[str, Any]:
        """
        Pull customer-visible listing text (Title, Bullets, Description, Images, Brand).
        Uses Catalog Items API: GET /catalog/2022-04-01/items/{asin}
        Works for client or competitor listings.
        Required Role: Amazon Shopping Cart / Catalog Product Search
        """
        if not self.is_configured():
            logger.warning("SP-API credentials not configured. Returning simulation placeholder.")
            return {"error": "unconfigured", "message": "Credentials missing"}

        path = f"/catalog/2022-04-01/items/{asin}"
        params = {
            "marketplaceIds": "ATVPDKIKX0DER",  # Default to US Marketplace ID
            "includedData": "attributes,summaries,images,classifications"
        }
        
        response = await self._request("GET", path, params=params, limiter=self.catalog_limiter)
        return response

    def parse_backend_attributes(self, sp_api_response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract backend attributes crucial for mapping COSMO relationship models.
        COSMO leverages: materials, target gender, generic keywords, target audience, body parts, etc.
        """
        attributes = sp_api_response.get("attributes", {})
        
        # Safe extraction helper
        def get_value(attr_key: str) -> str:
            items = attributes.get(attr_key, [])
            if not items:
                return ""
            return items[0].get("value", "")
            
        def get_list(attr_key: str) -> List[str]:
            items = attributes.get(attr_key, [])
            return [item.get("value", "") for item in items if "value" in item]

        return {
            "title": get_value("item_name"),
            "bullets": get_list("bullet_point"),
            "description": get_value("product_description"),
            "brand": get_value("brand"),
            "manufacturer": get_value("manufacturer"),
            "materials": get_list("material"),
            "color": get_value("color"),
            "size": get_value("size"),
            "target_audience": get_list("target_audience_keywords") or get_list("target_gender"),
            "intended_use": get_list("intended_use_keywords"),
            "generic_keywords": get_list("generic_keyword"),  # CRITICAL: Backend search terms
            "subject_matter": get_list("subject_matter"),
            "body_parts": get_list("body_area_keywords")
        }

    def parse_visible_attributes(self, sp_api_response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract visible attributes that Rufus retrieves during RAG queries.
        """
        # Catalog items API returns attributes under attributes or summaries
        summaries = sp_api_response.get("summaries", [{}])[0]
        attributes = sp_api_response.get("attributes", {})
        
        def get_value(attr_key: str) -> str:
            items = attributes.get(attr_key, [])
            if not items:
                return ""
            return items[0].get("value", "")
            
        def get_list(attr_key: str) -> List[str]:
            items = attributes.get(attr_key, [])
            return [item.get("value", "") for item in items if "value" in item]

        bullets = get_list("bullet_point") or summaries.get("features", [])
        title = get_value("item_name") or summaries.get("itemName", "")
        description = get_value("product_description") or summaries.get("productDescription", "")
        
        images = []
        for img_set in summaries.get("images", []):
            for img in img_set.get("images", []):
                if "link" in img:
                    images.append(img["link"])
                    
        return {
            "title": title,
            "bullets": bullets,
            "description": description,
            "brand": summaries.get("brandName", ""),
            "images": images,
            "category": summaries.get("classificationId", "")
        }

# Global reusable client instance
spapi_client = AmazonSPAPIClient()
