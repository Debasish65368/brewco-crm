from fastapi import HTTPException, Request
import jwt
from jwt import PyJWKClient

from core.config import CLERK_JWKS_URL, CLERK_ISSUER, CLERK_AUTHORIZED_PARTIES

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

    token = auth_header[len("Bearer "):]

    # Fail closed: issuer must be configured.
    # Without CLERK_ISSUER, jwt.decode would skip issuer validation entirely,
    # allowing tokens from any Clerk instance to be accepted.
    if not CLERK_ISSUER:
        raise HTTPException(
            status_code=500,
            detail="Server misconfiguration: CLERK_ISSUER is not set"
        )

    try:
        signing_key = get_jwk_client().get_signing_key_from_jwt(token)

        # Audience: Clerk session tokens do not carry a per-service `aud` claim
        # suitable for backend validation in this single-tenant configuration.
        # verify_aud=False is intentional and documented here.
        #
        # Authorized-party (azp): Clerk sets the `azp` claim to the frontend
        # origin that requested the token (the browser's Origin header at
        # sign-in time, e.g. "http://localhost:5173" or the Vercel URL).
        # When CLERK_AUTHORIZED_PARTIES is configured (comma-separated list of
        # allowed frontend origins), the azp claim is validated against that
        # allowlist, rejecting tokens obtained from unauthorized frontends.
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            issuer=CLERK_ISSUER,
            options={
                "verify_aud": False,
            }
        )

        # azp allowlist check — active only when CLERK_AUTHORIZED_PARTIES is set.
        # In production, set this to the deployed frontend origin(s).
        # Example: "https://brewco.vercel.app,http://localhost:5173"
        if CLERK_AUTHORIZED_PARTIES:
            azp = payload.get("azp", "")
            if azp not in CLERK_AUTHORIZED_PARTIES:
                raise HTTPException(
                    status_code=401,
                    detail="Token authorized party not in allowlist"
                )

        return payload

    except HTTPException:
        raise
    except Exception:
        # Do NOT log the token or payload — they contain sensitive claims.
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired Clerk token"
        )
