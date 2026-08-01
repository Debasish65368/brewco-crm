from fastapi import HTTPException, Request
import jwt
from jwt import PyJWKClient

from core.config import CLERK_JWKS_URL, CLERK_ISSUER

_jwk_client = None


def get_jwk_client():
    global _jwk_client

    if _jwk_client is None:
        _jwk_client = PyJWKClient(CLERK_JWKS_URL)

    return _jwk_client


async def verify_clerk_token(request: Request):
    auth_header = request.headers.get("Authorization")

    if not auth_header:
        raise HTTPException(
            status_code=401,
            detail="Missing Authorization header"
        )

    if not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Invalid Authorization header"
        )

    token = auth_header.replace("Bearer ", "")

    try:
        signing_key = get_jwk_client().get_signing_key_from_jwt(token)

        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            issuer=CLERK_ISSUER if CLERK_ISSUER else None,
            options={
                "verify_aud": False
            }
        )

        return payload

    except Exception:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired Clerk token"
        )
