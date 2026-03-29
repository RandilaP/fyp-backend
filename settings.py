# get environment variables from .env file
from dotenv import load_dotenv
import os
load_dotenv()

# Supabase configuration
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Validate required environment variables
if not SUPABASE_URL:
    raise ValueError("SUPABASE_URL environment variable is not set. Please check your .env file.")
if not SUPABASE_KEY:
    raise ValueError("SUPABASE_KEY environment variable is not set. Please check your .env file.")

# JWT / Auth configuration
SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-production-to-a-long-random-string")
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
# Access token expiry in minutes (default 8 hours)
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "480"))

