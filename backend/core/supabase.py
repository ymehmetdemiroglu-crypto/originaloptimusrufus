import os
import logging

_supabase_client = None

def get_supabase():
    """Returns the singleton Supabase client instance, initializing it if needed."""
    global _supabase_client
    if _supabase_client is None:
        try:
            from supabase import create_client
            url = os.getenv("SUPABASE_URL", "")
            key = os.getenv("SUPABASE_KEY", "")
            if url and key:
                _supabase_client = create_client(url, key)
            else:
                logging.warning("SUPABASE_URL or SUPABASE_KEY not configured in env")
        except Exception:
            logging.exception("Failed to initialize Supabase client")
    return _supabase_client
