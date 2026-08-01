import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

CHANNEL_SERVICE_URL = os.getenv(
    "CHANNEL_SERVICE_URL",
    "http://localhost:8001/send"
)

CRM_RECEIPT_URL = os.getenv(
    "CRM_RECEIPT_URL",
    "http://localhost:8000/receipt"
)

CLERK_JWKS_URL = os.getenv("CLERK_JWKS_URL")
CLERK_ISSUER = os.getenv("CLERK_ISSUER")

if not CLERK_JWKS_URL:
    raise Exception("CLERK_JWKS_URL missing in .env")

if not DATABASE_URL:
    raise Exception("DATABASE_URL missing in .env")

if not GROQ_API_KEY:
    raise Exception("GROQ_API_KEY missing in .env")
