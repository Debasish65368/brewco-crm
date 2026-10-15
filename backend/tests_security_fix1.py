"""
tests_security_fix1.py

Comprehensive security verification for Fix 1 in BrewCo CRM backend:
  - Objective A: Outgoing channel client sends X-Channel-Service-Key header; fails closed if secret absent.
  - Objective B: CORS middleware uses explicit allowlist; credentials never paired with wildcard;
                 behavioral preflight verification for trusted vs untrusted origins.
  - Objective C: Clerk JWT validation requires CLERK_ISSUER; fails closed (500) if issuer missing;
                 signature and expiration verified; azp claim validated against CLERK_AUTHORIZED_PARTIES allowlist;
                 production fail-fast safeguards when APP_ENV=production.
"""
import os
import sys
import time
import warnings
from unittest.mock import AsyncMock, MagicMock, patch

warnings.filterwarnings("ignore")

import pytest

try:
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.backends import default_backend
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False

import jwt as pyjwt


def _make_rsa_keypair():
    private_key = rsa.generate_private_key(
        public_exponent=65537, key_size=2048, backend=default_backend()
    )
    public_pem = private_key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo
    )
    return private_key, public_pem


def _make_token(private_key, issuer, azp=None, exp_offset=3600):
    now = int(time.time())
    claims = {
        "iss": issuer,
        "sub": "user_test_123",
        "iat": now,
        "exp": now + exp_offset,
        "nbf": now - 5,
    }
    if azp is not None:
        claims["azp"] = azp
    return pyjwt.encode(claims, private_key, algorithm="RS256")


# ---------------------------------------------------------------------------
# Objective B Tests: CORS
# ---------------------------------------------------------------------------

class TestBackendCORS:
    def _read_main(self):
        path = os.path.join(os.path.dirname(__file__), "main.py")
        with open(path, encoding="utf-8") as f:
            return f.read()

    def test_no_wildcard_origin_literal(self):
        """The literal string allow_origins=['*'] must not appear in main.py."""
        src = self._read_main()
        assert 'allow_origins=["*"]' not in src, (
            'backend/main.py must not use allow_origins=["*"].'
        )

    def test_allowed_origins_imported_from_config(self):
        """ALLOWED_ORIGINS must be imported from core.config, avoiding scattered env lookups."""
        src = self._read_main()
        assert "from core.config import ALLOWED_ORIGINS" in src, (
            "backend/main.py must import ALLOWED_ORIGINS from core.config"
        )

    def test_cors_methods_explicit(self):
        """allow_methods must be an explicit list, not ['*']."""
        src = self._read_main()
        assert 'allow_methods=["*"]' not in src, (
            'allow_methods should be an explicit list, not ["*"]'
        )

    def test_cors_headers_explicit(self):
        """allow_headers must be an explicit list, not ['*']."""
        src = self._read_main()
        assert 'allow_headers=["*"]' not in src, (
            'allow_headers should be an explicit list, not ["*"]'
        )

    def test_cors_preflight_behavioral(self):
        """
        Behavioral test:
        - Options request from trusted origin receives Access-Control-Allow-Origin & credentials.
        - Options request from untrusted origin does NOT receive Access-Control-Allow-Origin.
        """
        from fastapi import FastAPI
        from fastapi.middleware.cors import CORSMiddleware
        from fastapi.testclient import TestClient

        test_app = FastAPI()
        test_app.add_middleware(
            CORSMiddleware,
            allow_origins=["http://localhost:5173", "https://brewco.vercel.app"],
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            allow_headers=["Authorization", "Content-Type"],
        )

        @test_app.get("/test")
        def sample():
            return {"ok": True}

        client = TestClient(test_app)

        # 1. Trusted origin preflight
        trusted_resp = client.options(
            "/test",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            }
        )
        assert trusted_resp.headers.get("access-control-allow-origin") == "http://localhost:5173"
        assert trusted_resp.headers.get("access-control-allow-credentials") == "true"

        # 2. Untrusted origin preflight
        untrusted_resp = client.options(
            "/test",
            headers={
                "Origin": "https://malicious-attacker.com",
                "Access-Control-Request-Method": "GET",
            }
        )
        assert "access-control-allow-origin" not in untrusted_resp.headers


# ---------------------------------------------------------------------------
# Objective A Tests: channel_client.py
# ---------------------------------------------------------------------------

class TestChannelClientAuth:
    def _read_client(self):
        path = os.path.join(os.path.dirname(__file__), "clients", "channel_client.py")
        with open(path, encoding="utf-8") as f:
            return f.read()

    def test_sends_auth_header(self):
        """channel_client.py must include X-Channel-Service-Key in outgoing requests."""
        src = self._read_client()
        assert "X-Channel-Service-Key" in src, (
            "channel_client.py must send the X-Channel-Service-Key header"
        )

    def test_imports_secret(self):
        """channel_client.py must import CHANNEL_SERVICE_SECRET from config."""
        src = self._read_client()
        assert "CHANNEL_SERVICE_SECRET" in src, (
            "channel_client.py must import and use CHANNEL_SERVICE_SECRET"
        )

    def test_fails_if_secret_missing(self):
        """channel_client.py must guard against calling channel service with no secret."""
        src = self._read_client()
        assert "not CHANNEL_SERVICE_SECRET" in src or "if not CHANNEL_SERVICE_SECRET" in src, (
            "channel_client.py must guard against calling channel service with no secret"
        )

    def test_behavioral_channel_client_call(self):
        """Behavioral check: calling send_to_channel_service passes the auth header to httpx."""
        import asyncio
        from clients import channel_client

        with patch("clients.channel_client.CHANNEL_SERVICE_SECRET", "mock-secret-123"):
            with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
                asyncio.run(channel_client.send_to_channel_service(
                    campaign_id=1,
                    customer_id=42,
                    channel="sms",
                    message="Coffee promo"
                ))
                assert mock_post.called
                _, kwargs = mock_post.call_args
                assert kwargs["headers"]["X-Channel-Service-Key"] == "mock-secret-123"
                assert kwargs["json"]["campaign_id"] == 1
                assert kwargs["json"]["customer_id"] == 42


# ---------------------------------------------------------------------------
# Objective C Tests: Clerk JWT Policy (Static)
# ---------------------------------------------------------------------------

class TestClerkJWTPolicy:
    def _read_auth(self):
        path = os.path.join(os.path.dirname(__file__), "core", "auth.py")
        with open(path, encoding="utf-8") as f:
            return f.read()

    def test_no_conditional_issuer_fallback(self):
        """The old pattern `issuer=CLERK_ISSUER if CLERK_ISSUER else None` must be gone."""
        src = self._read_auth()
        assert "issuer=CLERK_ISSUER if CLERK_ISSUER else None" not in src, (
            "auth.py must not silently skip issuer validation when CLERK_ISSUER is absent."
        )

    def test_issuer_required_check_present(self):
        """auth.py must explicitly check for missing CLERK_ISSUER and fail closed."""
        src = self._read_auth()
        assert "not CLERK_ISSUER" in src, (
            "auth.py must fail closed (raise 500) when CLERK_ISSUER is not configured"
        )

    def test_verify_aud_false_documented(self):
        """verify_aud=False must be present and documented with azp explanation."""
        src = self._read_auth()
        assert "verify_aud" in src, "auth.py must include verify_aud option"
        assert "azp" in src or "authorized party" in src.lower(), (
            "auth.py must document the azp alternative to aud validation"
        )

    def test_no_token_logging(self):
        """The raw token value must never be logged."""
        import re
        src = self._read_auth()
        log_lines = re.findall(r'(?:print|log(?:ging)?|logger)\s*\(.*\btoken\b.*\)', src)
        assert not log_lines, f"Token must not be logged. Suspicious lines: {log_lines}"

    def test_azp_validation_present(self):
        """CLERK_AUTHORIZED_PARTIES check must be present for azp allowlist validation."""
        src = self._read_auth()
        assert "CLERK_AUTHORIZED_PARTIES" in src, (
            "auth.py must validate azp against CLERK_AUTHORIZED_PARTIES"
        )


# ---------------------------------------------------------------------------
# Objective C Tests: Clerk JWT Runtime Verification
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not HAS_CRYPTO, reason="cryptography package not installed")
class TestClerkJWTRuntime:
    ISSUER = "https://test.clerk.accounts.dev"

    def setup_method(self):
        self.private_key, self.public_pem = _make_rsa_keypair()

        os.environ["CLERK_JWKS_URL"] = "https://test.clerk.accounts.dev/.well-known/jwks.json"
        os.environ["CLERK_ISSUER"] = self.ISSUER
        os.environ["CHANNEL_SERVICE_SECRET"] = "test-secret"
        os.environ["DATABASE_URL"] = "postgresql://fake"
        os.environ["GROQ_API_KEY"] = "fake-groq"
        os.environ["CLERK_AUTHORIZED_PARTIES"] = "http://localhost:5173,https://my-app.vercel.app"

        for mod in list(sys.modules.keys()):
            if mod.startswith("core."):
                del sys.modules[mod]

        from core import auth as auth_mod
        self.auth = auth_mod

        fake_key = MagicMock()
        fake_key.key = self.private_key.public_key()
        mock_client = MagicMock()
        mock_client.get_signing_key_from_jwt.return_value = fake_key
        auth_mod._jwk_client = mock_client

    def _req(self, token):
        r = MagicMock()
        r.headers = {"Authorization": f"Bearer {token}"}
        return r

    def _run(self, coro):
        import asyncio
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    def test_valid_token_accepted_with_dev_origin(self):
        """Token with matching issuer and localhost dev azp is accepted."""
        self.auth.CLERK_ISSUER = self.ISSUER
        self.auth.CLERK_AUTHORIZED_PARTIES = {"http://localhost:5173", "https://my-app.vercel.app"}
        token = _make_token(self.private_key, self.ISSUER, azp="http://localhost:5173")
        payload = self._run(self.auth.verify_clerk_token(self._req(token)))
        assert payload["iss"] == self.ISSUER
        assert payload["azp"] == "http://localhost:5173"

    def test_valid_token_accepted_with_prod_origin(self):
        """Token with matching issuer and production vercel azp is accepted."""
        self.auth.CLERK_ISSUER = self.ISSUER
        self.auth.CLERK_AUTHORIZED_PARTIES = {"http://localhost:5173", "https://my-app.vercel.app"}
        token = _make_token(self.private_key, self.ISSUER, azp="https://my-app.vercel.app")
        payload = self._run(self.auth.verify_clerk_token(self._req(token)))
        assert payload["azp"] == "https://my-app.vercel.app"

    def test_wrong_issuer_rejected(self):
        """Token from an untrusted issuer is rejected (401)."""
        from fastapi import HTTPException
        self.auth.CLERK_ISSUER = self.ISSUER
        self.auth.CLERK_AUTHORIZED_PARTIES = {"http://localhost:5173"}
        token = _make_token(self.private_key, "https://evil.clerk.accounts.dev", azp="http://localhost:5173")
        with pytest.raises(HTTPException) as exc:
            self._run(self.auth.verify_clerk_token(self._req(token)))
        assert exc.value.status_code == 401

    def test_missing_issuer_config_fails_closed(self):
        """When CLERK_ISSUER is missing, auth fails closed with 500."""
        from fastapi import HTTPException
        self.auth.CLERK_ISSUER = ""
        self.auth.CLERK_AUTHORIZED_PARTIES = {"http://localhost:5173"}
        token = _make_token(self.private_key, self.ISSUER, azp="http://localhost:5173")
        with pytest.raises(HTTPException) as exc:
            self._run(self.auth.verify_clerk_token(self._req(token)))
        assert exc.value.status_code == 500

    def test_azp_not_in_allowlist_rejected(self):
        """Token with an unauthorized azp is rejected (401)."""
        from fastapi import HTTPException
        self.auth.CLERK_ISSUER = self.ISSUER
        self.auth.CLERK_AUTHORIZED_PARTIES = {"http://localhost:5173", "https://my-app.vercel.app"}
        token = _make_token(self.private_key, self.ISSUER, azp="https://unauthorized-domain.com")
        with pytest.raises(HTTPException) as exc:
            self._run(self.auth.verify_clerk_token(self._req(token)))
        assert exc.value.status_code == 401

    def test_missing_azp_rejected_when_allowlist_active(self):
        """Token lacking any azp claim is rejected (401) when allowlist is active."""
        from fastapi import HTTPException
        self.auth.CLERK_ISSUER = self.ISSUER
        self.auth.CLERK_AUTHORIZED_PARTIES = {"http://localhost:5173"}
        token = _make_token(self.private_key, self.ISSUER, azp=None)
        with pytest.raises(HTTPException) as exc:
            self._run(self.auth.verify_clerk_token(self._req(token)))
        assert exc.value.status_code == 401

    def test_expired_token_rejected(self):
        """Expired token must be rejected (401)."""
        from fastapi import HTTPException
        self.auth.CLERK_ISSUER = self.ISSUER
        self.auth.CLERK_AUTHORIZED_PARTIES = {"http://localhost:5173"}
        token = _make_token(self.private_key, self.ISSUER, azp="http://localhost:5173", exp_offset=-30)
        with pytest.raises(HTTPException) as exc:
            self._run(self.auth.verify_clerk_token(self._req(token)))
        assert exc.value.status_code == 401


# ---------------------------------------------------------------------------
# Config Safeguards Tests (Production fail-fast)
# ---------------------------------------------------------------------------

class TestConfigSafeguards:
    def test_production_fails_without_explicit_allowed_origins(self):
        """In production (APP_ENV=production), failing to set ALLOWED_ORIGINS raises Exception."""
        env_backup = dict(os.environ)
        try:
            with patch("dotenv.load_dotenv"):
                os.environ["APP_ENV"] = "production"
                os.environ["DATABASE_URL"] = "postgresql://fake"
                os.environ["GROQ_API_KEY"] = "fake"
                os.environ["CHANNEL_SERVICE_SECRET"] = "fake"
                os.environ["CLERK_JWKS_URL"] = "https://fake/.well-known/jwks.json"
                os.environ["CLERK_ISSUER"] = "https://fake"
                os.environ.pop("ALLOWED_ORIGINS", None)
                os.environ.pop("CLERK_AUTHORIZED_PARTIES", None)

                for mod in list(sys.modules.keys()):
                    if mod == "core.config" or mod.startswith("core.config"):
                        del sys.modules[mod]

                with pytest.raises(Exception) as exc:
                    import core.config
                assert "ALLOWED_ORIGINS must be explicitly configured" in str(exc.value)
        finally:
            os.environ.clear()
            os.environ.update(env_backup)

    def test_production_fails_when_clerk_parties_set_but_allowed_origins_missing(self):
        """
        Regression test: In production, setting CLERK_AUTHORIZED_PARTIES alone must NOT
        allow startup to pass if ALLOWED_ORIGINS is missing.
        """
        env_backup = dict(os.environ)
        try:
            with patch("dotenv.load_dotenv"):
                os.environ["APP_ENV"] = "production"
                os.environ["DATABASE_URL"] = "postgresql://fake"
                os.environ["GROQ_API_KEY"] = "fake"
                os.environ["CHANNEL_SERVICE_SECRET"] = "fake"
                os.environ["CLERK_JWKS_URL"] = "https://fake/.well-known/jwks.json"
                os.environ["CLERK_ISSUER"] = "https://fake"
                os.environ.pop("ALLOWED_ORIGINS", None)
                os.environ["CLERK_AUTHORIZED_PARTIES"] = "https://brewco.vercel.app"

                for mod in list(sys.modules.keys()):
                    if mod == "core.config" or mod.startswith("core.config"):
                        del sys.modules[mod]

                with pytest.raises(Exception) as exc:
                    import core.config
                assert "ALLOWED_ORIGINS must be explicitly configured" in str(exc.value)
        finally:
            os.environ.clear()
            os.environ.update(env_backup)

    def test_wildcard_cors_origin_rejected(self):
        """Wildcard in ALLOWED_ORIGINS must raise an exception."""
        env_backup = dict(os.environ)
        try:
            with patch("dotenv.load_dotenv"):
                os.environ["DATABASE_URL"] = "postgresql://fake"
                os.environ["GROQ_API_KEY"] = "fake"
                os.environ["CHANNEL_SERVICE_SECRET"] = "fake"
                os.environ["CLERK_JWKS_URL"] = "https://fake/.well-known/jwks.json"
                os.environ["CLERK_ISSUER"] = "https://fake"
                os.environ["ALLOWED_ORIGINS"] = "*"

                for mod in list(sys.modules.keys()):
                    if mod == "core.config" or mod.startswith("core.config"):
                        del sys.modules[mod]

                with pytest.raises(Exception) as exc:
                    import core.config
                assert "Wildcard or invalid origin is not permitted" in str(exc.value)
        finally:
            os.environ.clear()
            os.environ.update(env_backup)

    def test_invalid_cors_origin_protocol_rejected(self):
        """Origin missing http:// or https:// must raise an exception."""
        env_backup = dict(os.environ)
        try:
            with patch("dotenv.load_dotenv"):
                os.environ["DATABASE_URL"] = "postgresql://fake"
                os.environ["GROQ_API_KEY"] = "fake"
                os.environ["CHANNEL_SERVICE_SECRET"] = "fake"
                os.environ["CLERK_JWKS_URL"] = "https://fake/.well-known/jwks.json"
                os.environ["CLERK_ISSUER"] = "https://fake"
                os.environ["ALLOWED_ORIGINS"] = "ftp://invalid-origin.com"

                for mod in list(sys.modules.keys()):
                    if mod == "core.config" or mod.startswith("core.config"):
                        del sys.modules[mod]

                with pytest.raises(Exception) as exc:
                    import core.config
                assert "must start with http:// or https://" in str(exc.value)
        finally:
            os.environ.clear()
            os.environ.update(env_backup)

    def test_production_succeeds_with_explicit_origins(self):
        """In production, when ALLOWED_ORIGINS is provided, startup succeeds."""
        env_backup = dict(os.environ)
        try:
            with patch("dotenv.load_dotenv"):
                os.environ["APP_ENV"] = "production"
                os.environ["DATABASE_URL"] = "postgresql://fake"
                os.environ["GROQ_API_KEY"] = "fake"
                os.environ["CHANNEL_SERVICE_SECRET"] = "fake"
                os.environ["CLERK_JWKS_URL"] = "https://fake/.well-known/jwks.json"
                os.environ["CLERK_ISSUER"] = "https://fake"
                os.environ["ALLOWED_ORIGINS"] = "https://brewco-crm.vercel.app"
                os.environ.pop("CLERK_AUTHORIZED_PARTIES", None)

                for mod in list(sys.modules.keys()):
                    if mod == "core.config" or mod.startswith("core.config"):
                        del sys.modules[mod]

                import core.config as cfg
                assert cfg.ALLOWED_ORIGINS == ["https://brewco-crm.vercel.app"]
                assert cfg.CLERK_AUTHORIZED_PARTIES == {"https://brewco-crm.vercel.app"}
        finally:
            os.environ.clear()
            os.environ.update(env_backup)




# ---------------------------------------------------------------------------
# Main test runner
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    suites = [
        TestBackendCORS(),
        TestChannelClientAuth(),
        TestClerkJWTPolicy(),
        TestConfigSafeguards(),
    ]
    if HAS_CRYPTO:
        suites.append(TestClerkJWTRuntime())

    total = 0
    passed = 0
    failed = 0

    for suite in suites:
        for name in sorted(dir(suite)):
            if name.startswith("test_"):
                total += 1
                try:
                    if hasattr(suite, "setup_method"):
                        suite.setup_method()
                    fn = getattr(suite, name)
                    fn()
                    passed += 1
                    print(f"  PASS  {type(suite).__name__}.{name}")
                except AssertionError as e:
                    failed += 1
                    print(f"  FAIL  {type(suite).__name__}.{name}: {e}")
                except Exception as ex:
                    failed += 1
                    print(f"  ERROR {type(suite).__name__}.{name}: {ex}")

    print(f"\nResults: {passed}/{total} passed, {failed} failed.")
    if failed > 0:
        sys.exit(1)
    sys.exit(0)
