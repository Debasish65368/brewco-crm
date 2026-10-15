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

CHANNEL_SERVICE_SECRET = os.getenv("CHANNEL_SERVICE_SECRET", "")

CLERK_JWKS_URL = os.getenv("CLERK_JWKS_URL")
CLERK_ISSUER = os.getenv("CLERK_ISSUER")

# ---------------------------------------------------------------------------
# Frontend origin & Clerk authorized-party (azp) configuration
# ---------------------------------------------------------------------------

def _validate_origin(origin: str, var_name: str) -> None:
    if not origin or origin == "*" or "*" in origin:
        raise Exception(f"Wildcard or invalid origin is not permitted in {var_name}: {origin!r}")
    if not (origin.startswith("http://") or origin.startswith("https://")):
        raise Exception(f"Invalid origin in {var_name}: {origin!r} (must start with http:// or https://)")
    if origin.endswith("/"):
        raise Exception(f"Invalid origin in {var_name}: {origin!r} (must not contain a trailing slash)")

# ALLOWED_ORIGINS: Comma-separated list of allowed frontend origins for CORS.
# Defaults to local development origin.
_raw_origins = os.getenv("ALLOWED_ORIGINS")
if _raw_origins is not None:
    ALLOWED_ORIGINS = [o.strip() for o in _raw_origins.split(",") if o.strip()]
else:
    ALLOWED_ORIGINS = ["http://localhost:5173"]

for o in ALLOWED_ORIGINS:
    _validate_origin(o, "ALLOWED_ORIGINS")

# CLERK_AUTHORIZED_PARTIES: Set of allowed frontend origins for Clerk token `azp` validation.
# Defaults to ALLOWED_ORIGINS so authorized CORS origins are also accepted azp parties.
# Can be explicitly overridden with CLERK_AUTHORIZED_PARTIES=origin1,origin2.
_raw_parties = os.getenv("CLERK_AUTHORIZED_PARTIES")
if _raw_parties is not None:
    CLERK_AUTHORIZED_PARTIES = {p.strip() for p in _raw_parties.split(",") if p.strip()}
else:
    CLERK_AUTHORIZED_PARTIES = set(ALLOWED_ORIGINS)

for p in CLERK_AUTHORIZED_PARTIES:
    _validate_origin(p, "CLERK_AUTHORIZED_PARTIES")

if not CLERK_JWKS_URL:
    raise Exception("CLERK_JWKS_URL missing in .env")

if not DATABASE_URL:
    raise Exception("DATABASE_URL missing in .env")

if not GROQ_API_KEY:
    raise Exception("GROQ_API_KEY missing in .env")

if not CHANNEL_SERVICE_SECRET:
    raise Exception("CHANNEL_SERVICE_SECRET missing in .env")

if not CLERK_ISSUER:
    raise Exception("CLERK_ISSUER missing in .env")

# In production, require explicit CORS allowlist; cannot pass solely on CLERK_AUTHORIZED_PARTIES
APP_ENV = os.getenv("APP_ENV", os.getenv("ENVIRONMENT", "development")).lower()
if APP_ENV in ("production", "prod"):
    if not os.getenv("ALLOWED_ORIGINS"):
        raise Exception(
            "In production (APP_ENV=production), ALLOWED_ORIGINS must be explicitly configured "
            "with a comma-separated list of trusted frontend origins."
        )
    if not ALLOWED_ORIGINS:
        raise Exception("In production, ALLOWED_ORIGINS must not be empty.")
    if not CLERK_AUTHORIZED_PARTIES:
        raise Exception("In production, CLERK_AUTHORIZED_PARTIES must not be empty.")
