import os
from supabase import create_client, Client
from settings import SUPABASE_URL, SUPABASE_KEY

# Validate that configuration values are properly set
if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError(
        "Supabase configuration is invalid. "
        "Please ensure SUPABASE_URL and SUPABASE_KEY are set in your .env file."
    )

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
