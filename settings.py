# get environment variables from .env file
from dotenv import load_dotenv
import os
load_dotenv()

# Supabase configuration
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# JWT / Auth configuration
SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-production-to-a-long-random-string")
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
# Access token expire minutes (default 15 minutes)
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "15"))

