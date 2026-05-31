"""In-memory data store with seed data and JSON file-based local persistence."""

from datetime import datetime, timedelta
from typing import List, Dict, Optional
import random
import threading
import json
import os
import logging
import asyncio

class DataStore:
    def __init__(self):
        self.lock = threading.Lock()
        self.listings: Dict[str, dict] = {}
        self.competitors: Dict[str, List[dict]] = {}
        self.jobs: List[dict] = []
        self.clients: List[dict] = []
        self.traffic_history: Dict[str, List[dict]] = {}
        self._dirty = False
        self._flush_task = None
        
        # Load persisted state first. If none exists, seed standard initial data.
        if not self._load():
            self._seed()
        else:
            # Seed/Update clients always to ensure config consistency
            self.clients = [
                {"id": "c-101", "name": "HydroMax Brands", "tier": "Enterprise", "listings": 342, "asins": 128, "usage": 78, "mrr": 8500, "status": "active", "last_active": "2 min ago"},
                {"id": "c-102", "name": "Matcha Co", "tier": "Growth", "listings": 89, "asins": 34, "usage": 45, "mrr": 3200, "status": "active", "last_active": "15 min ago"},
                {"id": "c-103", "name": "ErgoSeating", "tier": "Growth", "listings": 156, "asins": 52, "usage": 62, "mrr": 4800, "status": "active", "last_active": "1 hour ago"},
                {"id": "c-104", "name": "SoundWave Audio", "tier": "Starter", "listings": 67, "asins": 22, "usage": 34, "mrr": 1500, "status": "paused", "last_active": "3 days ago"},
                {"id": "c-105", "name": "GreenLife Organics", "tier": "Enterprise", "listings": 210, "asins": 78, "usage": 91, "mrr": 9200, "status": "active", "last_active": "5 min ago"},
                {"id": "c-106", "name": "FitGear Pro", "tier": "Growth", "listings": 124, "asins": 41, "usage": 55, "mrr": 4100, "status": "active", "last_active": "32 min ago"},
            ]

    def _save(self):
        """Debounced save: schedule a flush 5 seconds later if none pending."""
        self._dirty = True
        if self._flush_task is not None:
            return
        try:
            loop = asyncio.get_event_loop()
            self._flush_task = loop.call_later(5.0, lambda: asyncio.create_task(asyncio.to_thread(self._flush_sync)))
        except RuntimeError:
            # No event loop running (e.g., during import); flush immediately
            self._flush_sync()

    def _flush_sync(self):
        """Synchronous flush to disk inside the store lock."""
        try:
            with self.lock:
                if not self._dirty:
                    return
                data = {
                    "listings": self.listings,
                    "competitors": self.competitors,
                    "jobs": self.jobs,
                    "traffic_history": self.traffic_history
                }
                dir_path = os.path.dirname(os.path.abspath(__file__))
                file_path = os.path.join(dir_path, "store_data.json")
                with open(file_path, "w") as f:
                    json.dump(data, f, indent=2)
                self._dirty = False
        except Exception:
            logging.exception("Failed to serialize data store to JSON")
        finally:
            self._flush_task = None

    def _load(self) -> bool:
        """Load data store from local JSON file if it exists, returning True if successful."""
        try:
            dir_path = os.path.dirname(os.path.abspath(__file__))
            file_path = os.path.join(dir_path, "store_data.json")
            if os.path.exists(file_path):
                with open(file_path, "r") as f:
                    data = json.load(f)
                self.listings = data.get("listings", {})
                self.competitors = data.get("competitors", {})
                self.jobs = data.get("jobs", [])
                self.traffic_history = data.get("traffic_history", {})
                return True
        except Exception:
            logging.exception("Failed to deserialize data store from JSON")
        return False

    def _seed(self):
        # Seed clients
        self.clients = [
            {"id": "c-101", "name": "HydroMax Brands", "tier": "Enterprise", "listings": 342, "asins": 128, "usage": 78, "mrr": 8500, "status": "active", "last_active": "2 min ago"},
            {"id": "c-102", "name": "Matcha Co", "tier": "Growth", "listings": 89, "asins": 34, "usage": 45, "mrr": 3200, "status": "active", "last_active": "15 min ago"},
            {"id": "c-103", "name": "ErgoSeating", "tier": "Growth", "listings": 156, "asins": 52, "usage": 62, "mrr": 4800, "status": "active", "last_active": "1 hour ago"},
            {"id": "c-104", "name": "SoundWave Audio", "tier": "Starter", "listings": 67, "asins": 22, "usage": 34, "mrr": 1500, "status": "paused", "last_active": "3 days ago"},
            {"id": "c-105", "name": "GreenLife Organics", "tier": "Enterprise", "listings": 210, "asins": 78, "usage": 91, "mrr": 9200, "status": "active", "last_active": "5 min ago"},
            {"id": "c-106", "name": "FitGear Pro", "tier": "Growth", "listings": 124, "asins": 41, "usage": 55, "mrr": 4100, "status": "active", "last_active": "32 min ago"},
        ]

        # Seed listings
        self.listings = {
            "B08N5WRWNW": {
                "asin": "B08N5WRWNW",
                "title": "Stainless Steel Water Bottle 32oz - Insulated Vacuum Flask for Gym, Travel, and Office - Keeps Drinks Cold 24hrs, Hot 12hrs - Leak-Proof, BPA-Free",
                "bullets": [
                    "TRIPLE-WALL VACUUM INSULATION KEEPS BEVERAGES COLD FOR 24 HOURS - Advanced copper-coated technology maintains ice-cold temperatures all day during workouts, commutes, and outdoor adventures without condensation",
                    "PERFECT FOR GYM ENTHUSIASTS AND OUTDOOR ADVENTURERS - The 32oz capacity and sweat-proof design fit standard car cup holders and bike bottle cages, making hydration effortless during hiking, cycling, and fitness training",
                    "LEAK-PROOF LID WITH CARRY HANDLE FOR ON-THE-GO CONVENIENCE - The secure twist cap prevents spills in gym bags and backpacks while the integrated loop allows easy attachment to hiking gear or stroller handles",
                    "BPA-FREE STAINLESS STEEL CONSTRUCTION FOR SAFE DAILY USE - Made from premium 18/8 food-grade steel with no plastic lining, ensuring pure taste and peace of mind for health-conscious users and families",
                ],
                "description": "Premium insulated water bottle designed for active lifestyles...",
                "brand": "HydroMax",
                "client_id": "c-101",
            },
            "B07ZPKBL6P": {
                "asin": "B07ZPKBL6P",
                "title": "Organic Matcha Green Tea Powder - Ceremonial Grade from Japan - 4oz Bag for Latte, Smoothie, and Baking",
                "bullets": [
                    "CEREMONIAL GRADE MATCHA HARVESTED FROM UJI, JAPAN - Shade-grown for 3 weeks before stone-ground processing, delivering vibrant green color, smooth umami flavor, and sustained energy without jitters",
                    "IDEAL FOR HEALTH-CONSCIOUS PROFESSIONALS AND YOGA PRACTITIONERS - Each serving provides 137x the antioxidants of brewed green tea, supporting mental clarity and calm focus during meditation and busy workdays",
                    "VERSATILE CULINARY GRADE FOR LATTES, SMOOTHIES, AND BAKING - Finely milled powder dissolves easily in hot or cold liquids, perfect for creating cafe-quality matcha lattes at home or adding nutrient boost to morning shakes",
                    "USDA ORGANIC CERTIFIED WITH THIRD-PARTY LAB TESTING - Every batch tested for heavy metals and pesticides, packaged in resealable foil bags to preserve freshness for matcha lovers who demand purity",
                ],
                "description": "Authentic Japanese ceremonial grade matcha green tea powder...",
                "brand": "Matcha Co",
                "client_id": "c-102",
            },
        }

        # Seed competitors per ASIN
        self.competitors["B08N5WRWNW"] = [
            {"asin": "B0ABC123", "title": "Insulated Water Bottle 40oz - Hydro Flask Alternative for Hiking", "full_text": "Double wall vacuum insulated stainless steel water bottle keeps drinks ice cold for 24 hours or piping hot for 12 hours. Premium travel flask designed for outdoor hiking, backpacking, camping, and athletic sports. Durable BPA-free powder-coated finish with leak-proof cap.", "price": "$29.99", "rating": "4.5", "review_count": 1240},
            {"asin": "B0DEF456", "title": "Travel Mug Stainless Steel - Keeps Coffee Hot 8 Hours", "full_text": "Sleek travel mug constructed with food-grade 18/8 stainless steel and vacuum insulation. Ideal commuter coffee mug that keeps beverages hot for 8 hours or cold for 16 hours. Features a leak-proof leak-lock flip lid and textured rubber grip.", "price": "$24.99", "rating": "4.3", "review_count": 890},
            {"asin": "B0GHI789", "title": "Sports Water Bottle with Straw - BPA Free Gym Bottle 32oz", "full_text": "Vibrant sports water bottle with high-flow straw lid for easy one-handed sipping. Durable plastic construction that is 100% BPA-free and leakproof. Features volume markings, silicon grip sleeve, and carry loop perfect for gym, fitness, cycling, and running.", "price": "$18.99", "rating": "4.6", "review_count": 2100},
            {"asin": "B0JKL012", "title": "Collapsible Water Bottle for Travel - Silicone Foldable 20oz", "full_text": "Ultra-portable foldable silicone water bottle for travel, hiking, and outdoor sports. Made from flexible food-grade BPA-free silicone. Collapses down to 1/3 of its full size to save space in backpacks. Features an alloy carabiner for easy attachment.", "price": "$15.99", "rating": "4.1", "review_count": 560},
            {"asin": "B0MNO345", "title": "Glass Water Bottle with Sleeve - Eco Friendly 24oz", "full_text": "Premium borosilicate glass water bottle with protective silicone sleeve and eco-friendly bamboo lid. Reusable, non-toxic, chemical-free glass ensures crisp, clean taste. Wide mouth opening is perfect for adding ice cubes or fruit infusions.", "price": "$22.99", "rating": "4.4", "review_count": 780},
        ]

        # Seed jobs
        self.jobs = [
            {"id": "job-9281", "asin": "B08N5WRWNW", "client_id": "c-101", "status": "completed", "stage": "publish", "progress": 100, "started": "08:55", "eta": "09:12", "readiness_before": 58, "readiness_after": 79, "date": "2026-05-18"},
            {"id": "job-9280", "asin": "B07ZPKBL6P", "client_id": "c-102", "status": "completed", "stage": "publish", "progress": 100, "started": "08:42", "eta": "09:01", "readiness_before": 44, "readiness_after": 71, "date": "2026-05-17"},
            {"id": "job-9279", "asin": "B09QXT8B7L", "client_id": "c-103", "status": "processing", "stage": "cosmo_mapping", "progress": 65, "started": "09:08", "eta": "09:18", "readiness_before": 51, "readiness_after": None, "date": "2026-05-17"},
            {"id": "job-9278", "asin": "B0B2QGDR6R", "client_id": "c-104", "status": "failed", "stage": "optimization", "progress": 34, "started": "08:30", "eta": None, "readiness_before": 62, "readiness_after": None, "date": "2026-05-16"},
        ]
        
        self.traffic_history = {}
        self._seed_traffic_history()
        self._save()

    def _seed_traffic_history(self):
        end_date = datetime.now()
        start_date = end_date - timedelta(days=60)
        
        self.traffic_history["B08N5WRWNW"] = []
        self.traffic_history["B0ABC123"] = []
        self.traffic_history["B07ZPKBL6P"] = []
        self.traffic_history["B0DEF456"] = []
        
        local_random = random.Random(42)
        
        for d in range(61):
            current_date = (start_date + timedelta(days=d)).strftime("%Y-%m-%d")
            
            control_cr = 0.041 + local_random.normalvariate(0, 0.001)
            c_sessions = int(local_random.normalvariate(800, 30))
            c_orders = int(c_sessions * control_cr)
            self.traffic_history["B0ABC123"].append({
                "date": current_date,
                "sessions": c_sessions,
                "orders": c_orders
            })
            
            is_post = d >= 45
            treatment_cr_base = 0.053 if is_post else 0.0415
            treatment_cr = treatment_cr_base + local_random.normalvariate(0, 0.001)
            
            t_sessions = int(local_random.normalvariate(850, 40))
            t_orders = int(t_sessions * treatment_cr)
            self.traffic_history["B08N5WRWNW"].append({
                "date": current_date,
                "sessions": t_sessions,
                "orders": t_orders
            })
            
            m_is_post = d >= 45
            m_cr_base = 0.060 if m_is_post else 0.049
            m_cr = m_cr_base + local_random.normalvariate(0, 0.001)
            m_sessions = int(local_random.normalvariate(500, 20))
            m_orders = int(m_sessions * m_cr)
            self.traffic_history["B07ZPKBL6P"].append({
                "date": current_date,
                "sessions": m_sessions,
                "orders": m_orders
            })
            
            mc_cr = 0.048 + local_random.normalvariate(0, 0.001)
            mc_sessions = int(local_random.normalvariate(480, 15))
            mc_orders = int(mc_sessions * mc_cr)
            self.traffic_history["B0DEF456"].append({
                "date": current_date,
                "sessions": mc_sessions,
                "orders": mc_orders
            })

    def get_listing(self, asin: str) -> Optional[dict]:
        return self.listings.get(asin)

    def set_listing(self, asin: str, listing: dict):
        with self.lock:
            self.listings[asin] = listing
            self._save()

    def get_competitors(self, asin: str) -> List[dict]:
        return self.competitors.get(asin, [])

    def get_jobs(self) -> List[dict]:
        return self.jobs

    def get_clients(self) -> List[dict]:
        return self.clients

    def add_job(self, job: dict):
        with self.lock:
            self.jobs.insert(0, job)
            self._save()

    def get_traffic_history(self, asin: str, days: int = 30) -> List[dict]:
        history = self.traffic_history.get(asin, [])
        return history[-days:] if history else []

    def set_traffic_history(self, asin: str, history: List[dict]):
        with self.lock:
            self.traffic_history[asin] = history
            self._save()

store = DataStore()
