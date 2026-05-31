"""Centralized Settings Configuration for FastAPI Backend."""

import os
from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    # API Configurations
    PROJECT_NAME: str = "Rufus/COSMO Optimization Engine"
    API_VERSION: str = "1.2.0"
    DISABLE_HTTPS_REDIRECT: bool = False
    
    # CORS Configurations
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",  # For rufus-calculator
        "http://127.0.0.1:5173",
    ]
    
    # Vector Caching & Models
    CACHE_TTL_SECONDS: float = 300.0
    DEFAULT_EMBEDDING_DIMENSIONS: int = 3072
    TRUNCATED_EMBEDDING_DIMENSIONS: int = 768
    
    # Causal Model Baseline Assumptions
    TREATMENT_PRE_CONVERSION_RATE: float = 0.0415
    TREATMENT_POST_CONVERSION_RATE: float = 0.053
    CONTROL_PRE_CONVERSION_RATE: float = 0.041
    CONTROL_POST_CONVERSION_RATE: float = 0.041
    
    # Scraper & Scopes
    WEAKNESS_THRESHOLD: int = 3
    AMAZON_MAX_ASINS_PER_BRAND: int = 1
    
    # Paths & Directory Locations
    BASE_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    DATABASE_PATH: str = os.path.join(BASE_DIR, "core", "embedding_cache.db")

    class Config:
        env_prefix = "RUFUS_"
        env_file = ".env"
        extra = "allow"

settings = Settings()
