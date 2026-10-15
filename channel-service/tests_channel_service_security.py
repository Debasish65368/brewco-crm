"""
tests_channel_service_security.py

Verifies the security boundaries for the channel-service /send endpoint:
  - Missing auth header is rejected (401) before scheduling background tasks
  - Wrong secret is rejected (403) before scheduling background tasks
  - Correct secret is accepted (200 queued) and schedules background task
  - Empty string secret is rejected (401/403)
  - Unconfigured secret fails closed (500) and never makes /send accessible
  - Server-to-server security: No CORSMiddleware registered, no wildcard origins with credentials
"""
import os
import sys
import warnings
from unittest.mock import AsyncMock, patch

# Suppress deprecation warnings from test frameworks/libraries
warnings.filterwarnings("ignore")

from fastapi.testclient import TestClient


def _load_app(secret: str):
    """Import (or re-import) the channel-service app with the given secret."""
    os.environ["CHANNEL_SERVICE_SECRET"] = secret
    if "main" in sys.modules:
        del sys.modules["main"]
    import main as m
    return m.app


class TestSendAuth:
    def setup_method(self):
        self.secret = "test-channel-secret-abc"
        self.app = _load_app(self.secret)
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.payload = {
            "campaign_id": 1,
            "customer_id": 1,
            "channel": "email",
            "message": "Hello"
        }

    def test_missing_auth_header_returns_401(self):
        """No X-Channel-Service-Key header -> rejected before scheduling delivery."""
        import main
        with patch.object(main, "simulate_message_lifecycle", new_callable=AsyncMock) as mock_sim:
            resp = self.client.post("/send", json=self.payload)
            assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"
            mock_sim.assert_not_called()

    def test_wrong_secret_returns_403(self):
        """Incorrect secret -> rejected before scheduling delivery."""
        import main
        with patch.object(main, "simulate_message_lifecycle", new_callable=AsyncMock) as mock_sim:
            resp = self.client.post(
                "/send",
                json=self.payload,
                headers={"X-Channel-Service-Key": "totally-wrong-secret"}
            )
            assert resp.status_code == 403, f"Expected 403, got {resp.status_code}"
            mock_sim.assert_not_called()

    def test_correct_secret_is_accepted(self):
        """Correct secret -> request is accepted, queued, and task scheduled."""
        import main
        with patch.object(main, "simulate_message_lifecycle", new_callable=AsyncMock) as mock_sim:
            resp = self.client.post(
                "/send",
                json=self.payload,
                headers={"X-Channel-Service-Key": self.secret}
            )
            assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
            data = resp.json()
            assert data["status"] == "queued"
            assert data["success"] is True
            mock_sim.assert_called_once_with(
                self.payload["campaign_id"],
                self.payload["customer_id"],
                self.payload["channel"],
                self.payload["message"]
            )

    def test_empty_string_secret_returns_403(self):
        """An empty string as secret must not pass comparison and not schedule task."""
        import main
        with patch.object(main, "simulate_message_lifecycle", new_callable=AsyncMock) as mock_sim:
            resp = self.client.post(
                "/send",
                json=self.payload,
                headers={"X-Channel-Service-Key": ""}
            )
            assert resp.status_code in (401, 403), (
                f"Expected 401 or 403 for empty key, got {resp.status_code}"
            )
            mock_sim.assert_not_called()


class TestSendAuthUnconfiguredSecret:
    def setup_method(self):
        """Load app with NO secret configured."""
        self.app = _load_app("")
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.payload = {
            "campaign_id": 1,
            "customer_id": 1,
            "channel": "email",
            "message": "Hello"
        }

    def test_no_secret_configured_returns_500_not_200(self):
        """
        When CHANNEL_SERVICE_SECRET is not configured, /send must NEVER become
        publicly accessible. Any request - even with a header - must fail closed (500).
        """
        import main
        with patch.object(main, "simulate_message_lifecycle", new_callable=AsyncMock) as mock_sim:
            resp = self.client.post(
                "/send",
                json=self.payload,
                headers={"X-Channel-Service-Key": "any-value"}
            )
            assert resp.status_code == 500, (
                f"/send must fail closed (500) when secret is unconfigured, got {resp.status_code}"
            )
            mock_sim.assert_not_called()

    def test_no_secret_no_header_returns_500(self):
        """No secret + no header -> still 500 (fails closed on missing config first)."""
        import main
        with patch.object(main, "simulate_message_lifecycle", new_callable=AsyncMock) as mock_sim:
            resp = self.client.post("/send", json=self.payload)
            assert resp.status_code == 500, (
                f"/send must fail closed (500) when secret is unconfigured, got {resp.status_code}"
            )
            mock_sim.assert_not_called()


class TestCORSConfiguration:
    def setup_method(self):
        self.app = _load_app("some-secret")

    def test_no_cors_middleware_registered(self):
        """
        The channel service is server-to-server. No CORSMiddleware should be
        registered at all - removing it is the correct posture.
        """
        user_middleware_classes = [m.cls.__name__ for m in self.app.user_middleware]
        assert "CORSMiddleware" not in user_middleware_classes, (
            "CORSMiddleware should NOT be registered on the channel service. "
            "It is a server-to-server API; browser CORS is not needed."
        )

    def test_wildcard_with_credentials_never_present(self):
        """Belt-and-suspenders: confirm no middleware exposes allow_origins=* + credentials."""
        from fastapi.middleware.cors import CORSMiddleware as CM
        for m in self.app.user_middleware:
            if m.cls is CM:
                kwargs = m.kwargs
                origins = kwargs.get("allow_origins", [])
                creds = kwargs.get("allow_credentials", False)
                assert not ("*" in origins and creds), (
                    "Wildcard CORS combined with allow_credentials=True is invalid "
                    "and must never appear."
                )


if __name__ == "__main__":
    suite = [
        TestSendAuth(),
        TestSendAuthUnconfiguredSecret(),
        TestCORSConfiguration(),
    ]
    total = 0
    passed = 0
    failed = 0

    for s in suite:
        for name in sorted(dir(s)):
            if name.startswith("test_"):
                total += 1
                try:
                    s.setup_method()
                    fn = getattr(s, name)
                    fn()
                    passed += 1
                    print(f"  PASS  {type(s).__name__}.{name}")
                except AssertionError as e:
                    failed += 1
                    print(f"  FAIL  {type(s).__name__}.{name}: {e}")
                except Exception as ex:
                    failed += 1
                    print(f"  ERROR {type(s).__name__}.{name}: {ex}")

    print(f"\nResults: {passed}/{total} passed, {failed} failed.")
    if failed > 0:
        sys.exit(1)
    sys.exit(0)
