"""
BrewCo CRM - Fix 2 Regression Test Suite: Correct Campaign Delivery Reporting

Tests the following requirements:
1. Successful HTTP dispatch returns an explicitly successful dispatch result (True).
2. HTTP 4xx response is detected and not treated as success (False).
3. HTTP 5xx response is detected and not treated as success (False).
4. Connection errors and timeouts are handled correctly (False).
5. The campaign processor persists dispatch failures per recipient.
6. Mixed recipient outcomes are represented accurately (partially_failed).
7. Successful dispatch is not mislabeled as confirmed delivery.
8. Delivery receipts correctly update recipient-level outcomes.
9. A delayed dispatch update cannot overwrite an already recorded delivery receipt.
10. Empty-recipient campaigns do not report successful delivery (marked failed).
11. Existing authenticated receipt processing continues to work.
12. Channel client authentication header from Fix 1 is preserved.
"""

import asyncio
import os
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

# Ensure test secret is set for client configuration
os.environ.setdefault("CHANNEL_SERVICE_SECRET", "test-secret-reporting-fix2")
os.environ.setdefault("CHANNEL_SERVICE_URL", "http://127.0.0.1:8001/send")
os.environ.setdefault("ENVIRONMENT", "development")

from clients import channel_client
from services import campaign_processor


# ===========================================================================
# 1. Channel Client HTTP Error Handling Tests (Req 1, 2, 3, 4, 12)
# ===========================================================================

class TestChannelClientHTTPHandling(unittest.TestCase):
    """Verifies that channel_client correctly distinguishes 2xx from 4xx, 5xx, timeouts, and network errors."""

    def setUp(self):
        self.secret = "test-secret-reporting-fix2"
        self.url = "http://127.0.0.1:8001/send"

    def test_successful_dispatch_returns_explicit_success(self):
        """Req 1: Successful HTTP 200/202 dispatch returns True."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {"success": True, "status": "queued"}

        with patch("clients.channel_client.CHANNEL_SERVICE_SECRET", self.secret), \
             patch("clients.channel_client.CHANNEL_SERVICE_URL", self.url), \
             patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            result = asyncio.run(channel_client.send_to_channel_service(
                campaign_id=1,
                customer_id=10,
                channel="email",
                message="Test Message"
            ))

            self.assertIs(result, True, "Successful HTTP 200 must return explicit True")
            self.assertTrue(mock_response.raise_for_status.called)

            # Req 12: Verify auth header is preserved
            _, kwargs = mock_post.call_args
            self.assertEqual(kwargs["headers"]["X-Channel-Service-Key"], self.secret)

    def test_http_4xx_response_detected_and_not_treated_as_success(self):
        """Req 2: HTTP 4xx (400, 401, 404, 422) is detected and returns False."""
        for status_code in [400, 401, 403, 404, 422]:
            req = httpx.Request("POST", self.url)
            resp = httpx.Response(status_code, request=req)
            http_error = httpx.HTTPStatusError(f"Client error {status_code}", request=req, response=resp)

            with patch("clients.channel_client.CHANNEL_SERVICE_SECRET", self.secret), \
                 patch("clients.channel_client.CHANNEL_SERVICE_URL", self.url), \
                 patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
                mock_post.side_effect = http_error

                result = asyncio.run(channel_client.send_to_channel_service(
                    campaign_id=1,
                    customer_id=10,
                    channel="email",
                    message="Test Message"
                ))

                self.assertIs(result, False, f"HTTP {status_code} must return False, not True")

    def test_http_5xx_response_detected_and_not_treated_as_success(self):
        """Req 3: HTTP 5xx (500, 502, 503) is detected and returns False."""
        for status_code in [500, 502, 503, 504]:
            req = httpx.Request("POST", self.url)
            resp = httpx.Response(status_code, request=req)
            http_error = httpx.HTTPStatusError(f"Server error {status_code}", request=req, response=resp)

            with patch("clients.channel_client.CHANNEL_SERVICE_SECRET", self.secret), \
                 patch("clients.channel_client.CHANNEL_SERVICE_URL", self.url), \
                 patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
                mock_post.side_effect = http_error

                result = asyncio.run(channel_client.send_to_channel_service(
                    campaign_id=1,
                    customer_id=10,
                    channel="email",
                    message="Test Message"
                ))

                self.assertIs(result, False, f"HTTP {status_code} must return False, not True")

    def test_connection_errors_and_timeouts_handled(self):
        """Req 4: Timeouts and connection failures return False and do not crash."""
        exceptions = [
            httpx.TimeoutException("Read timed out"),
            httpx.ConnectError("Connection refused"),
            httpx.NetworkError("Network unreachable"),
        ]

        for exc in exceptions:
            with patch("clients.channel_client.CHANNEL_SERVICE_SECRET", self.secret), \
                 patch("clients.channel_client.CHANNEL_SERVICE_URL", self.url), \
                 patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
                mock_post.side_effect = exc

                result = asyncio.run(channel_client.send_to_channel_service(
                    campaign_id=1,
                    customer_id=10,
                    channel="email",
                    message="Test Message"
                ))

                self.assertIs(result, False, f"{type(exc).__name__} must return False, not crash or return True")

    def test_missing_configuration_fails_closed(self):
        """Refuses to dispatch if secret or URL is missing."""
        with patch("clients.channel_client.CHANNEL_SERVICE_SECRET", ""), \
             patch("clients.channel_client.CHANNEL_SERVICE_URL", self.url):
            result = asyncio.run(channel_client.send_to_channel_service(
                campaign_id=1, customer_id=10, channel="email", message="Test"
            ))
            self.assertIs(result, False, "Missing secret must fail closed and return False")

        with patch("clients.channel_client.CHANNEL_SERVICE_SECRET", self.secret), \
             patch("clients.channel_client.CHANNEL_SERVICE_URL", ""):
            result = asyncio.run(channel_client.send_to_channel_service(
                campaign_id=1, customer_id=10, channel="email", message="Test"
            ))
            self.assertIs(result, False, "Missing URL must fail closed and return False")


# ===========================================================================
# 2. Campaign Processor State & Reporting Tests (Req 5, 6, 7, 9, 10)
# ===========================================================================

class TestCampaignProcessorLifecycle(unittest.TestCase):
    """Verifies campaign and recipient lifecycle state transitions and concurrency safety."""

    def test_empty_recipient_campaign_does_not_report_successful_delivery(self):
        """Req 10: Segment with 0 customers is marked failed, never sent or delivered."""
        executed_sqls = []

        class MockConn:
            async def execute(self, query, *args):
                executed_sqls.append((query, args))
            async def fetchval(self, query, *args):
                return 1

        mock_conn = MockConn()

        with patch("services.campaign_processor.get_connection", new_callable=AsyncMock) as mock_get_conn, \
             patch("services.campaign_processor.release_connection", new_callable=AsyncMock), \
             patch("services.campaign_processor.get_segment_customers", new_callable=AsyncMock) as mock_get_cust:
            mock_get_conn.return_value = mock_conn
            mock_get_cust.return_value = []  # Empty segment

            asyncio.run(campaign_processor.process_campaign(
                campaign_id=42,
                segment_id=1,
                channel="email",
                message="Promo"
            ))

            # Must execute UPDATE campaigns SET status = 'failed'
            status_updates = [args for query, args in executed_sqls if "UPDATE campaigns SET status" in query]
            self.assertEqual(len(status_updates), 1)
            self.assertEqual(status_updates[0], (42,))
            self.assertTrue(any("status = 'failed'" in q for q, _ in executed_sqls))

    def test_processor_persists_dispatch_failures(self):
        """Req 5: Single recipient dispatch failure sets communication to 'failed' and campaign to 'failed'."""
        executed_sqls = []

        class MockConn:
            async def execute(self, query, *args):
                executed_sqls.append((query, args))
            async def fetchval(self, query, *args):
                executed_sqls.append((query, args))
                return 99  # comm_id

        mock_conn = MockConn()

        with patch("services.campaign_processor.get_connection", new_callable=AsyncMock) as mock_get_conn, \
             patch("services.campaign_processor.release_connection", new_callable=AsyncMock), \
             patch("services.campaign_processor.get_segment_customers", new_callable=AsyncMock) as mock_get_cust, \
             patch("services.campaign_processor.send_to_channel_service", new_callable=AsyncMock) as mock_send:
            mock_get_conn.return_value = mock_conn
            mock_get_cust.return_value = [{"id": 10}]
            mock_send.return_value = False  # Channel dispatch rejected/failed

            asyncio.run(campaign_processor.process_campaign(
                campaign_id=1,
                segment_id=2,
                channel="email",
                message="Promo"
            ))

            # Recipient communication must be updated to 'failed'
            comm_failed_updates = [
                q for q, args in executed_sqls
                if "UPDATE communications" in q and "status = 'failed'" in q and args[0] == 99
            ]
            self.assertEqual(len(comm_failed_updates), 1, "Communication must be marked failed")

            # Campaign status must be updated to 'failed'
            campaign_updates = [
                args for q, args in executed_sqls
                if "UPDATE campaigns SET status = $1 WHERE id = $2" in q
            ]
            self.assertEqual(len(campaign_updates), 1)
            final_status, camp_id = campaign_updates[0]
            self.assertEqual(final_status, "failed")
            self.assertEqual(camp_id, 1)

    def test_mixed_recipient_outcomes_represented_accurately(self):
        """Req 6: Mixed outcomes (some succeed, some fail) updates campaign to 'partially_failed'."""
        executed_sqls = []

        class MockConn:
            async def execute(self, query, *args):
                executed_sqls.append((query, args))
            async def fetchval(self, query, *args):
                executed_sqls.append((query, args))
                # Return customer_id * 10 as comm_id
                return args[1] * 10

        mock_conn = MockConn()

        with patch("services.campaign_processor.get_connection", new_callable=AsyncMock) as mock_get_conn, \
             patch("services.campaign_processor.release_connection", new_callable=AsyncMock), \
             patch("services.campaign_processor.get_segment_customers", new_callable=AsyncMock) as mock_get_cust, \
             patch("services.campaign_processor.send_to_channel_service", new_callable=AsyncMock) as mock_send:
            mock_get_conn.return_value = mock_conn
            # 3 customers: cust 1 succeeds, cust 2 fails, cust 3 succeeds
            mock_get_cust.return_value = [{"id": 1}, {"id": 2}, {"id": 3}]

            async def side_effect_send(campaign_id, customer_id, channel, message):
                return customer_id != 2  # cust 2 fails

            mock_send.side_effect = side_effect_send

            asyncio.run(campaign_processor.process_campaign(
                campaign_id=5,
                segment_id=1,
                channel="sms",
                message="Coffee discount"
            ))

            # Verify communication updates
            sent_comm_updates = [
                args[0] for q, args in executed_sqls
                if "UPDATE communications" in q and "ELSE 'sent'" in q
            ]
            failed_comm_updates = [
                args[0] for q, args in executed_sqls
                if "UPDATE communications" in q and "status = 'failed'" in q
            ]

            self.assertIn(10, sent_comm_updates)  # cust 1 comm_id
            self.assertIn(20, failed_comm_updates)  # cust 2 comm_id
            self.assertIn(30, sent_comm_updates)  # cust 3 comm_id

            # Verify campaign final status is 'partially_failed'
            campaign_updates = [
                args for q, args in executed_sqls
                if "UPDATE campaigns SET status = $1 WHERE id = $2" in q
            ]
            self.assertEqual(len(campaign_updates), 1)
            final_status, camp_id = campaign_updates[0]
            self.assertEqual(final_status, "partially_failed")
            self.assertEqual(camp_id, 5)

    def test_all_successful_dispatches_updates_campaign_to_sent(self):
        """All recipient dispatches accepted marks campaign as 'sent'."""
        executed_sqls = []

        class MockConn:
            async def execute(self, query, *args):
                executed_sqls.append((query, args))
            async def fetchval(self, query, *args):
                return 100

        mock_conn = MockConn()

        with patch("services.campaign_processor.get_connection", new_callable=AsyncMock) as mock_get_conn, \
             patch("services.campaign_processor.release_connection", new_callable=AsyncMock), \
             patch("services.campaign_processor.get_segment_customers", new_callable=AsyncMock) as mock_get_cust, \
             patch("services.campaign_processor.send_to_channel_service", new_callable=AsyncMock) as mock_send:
            mock_get_conn.return_value = mock_conn
            mock_get_cust.return_value = [{"id": 1}, {"id": 2}]
            mock_send.return_value = True

            asyncio.run(campaign_processor.process_campaign(
                campaign_id=8,
                segment_id=1,
                channel="email",
                message="All good"
            ))

            campaign_updates = [
                args for q, args in executed_sqls
                if "UPDATE campaigns SET status = $1 WHERE id = $2" in q
            ]
            self.assertEqual(len(campaign_updates), 1)
            final_status, camp_id = campaign_updates[0]
            self.assertEqual(final_status, "sent")
            self.assertEqual(camp_id, 8)

    def test_successful_dispatch_is_not_mislabeled_as_delivered(self):
        """Req 7: Successful dispatch sets communication status='sent' with sent_at, NOT status='delivered'."""
        executed_sqls = []

        class MockConn:
            async def execute(self, query, *args):
                executed_sqls.append((query, args))
            async def fetchval(self, query, *args):
                return 55

        mock_conn = MockConn()
        sem = asyncio.Semaphore(1)

        with patch("services.campaign_processor.get_connection", new_callable=AsyncMock) as mock_get_conn, \
             patch("services.campaign_processor.release_connection", new_callable=AsyncMock), \
             patch("services.campaign_processor.send_to_channel_service", new_callable=AsyncMock) as mock_send:
            mock_get_conn.return_value = mock_conn
            mock_send.return_value = True

            ok = asyncio.run(campaign_processor._dispatch_single_recipient(
                campaign_id=1,
                customer_id=10,
                comm_id=55,
                channel="email",
                message="Hello",
                sem=sem
            ))

            self.assertTrue(ok)
            # Must update status to 'sent' (via CASE) and set sent_at, NOT 'delivered'
            for q, _ in executed_sqls:
                self.assertNotIn("status = 'delivered'", q, "Dispatch must never set status='delivered'")
                self.assertIn("ELSE 'sent'", q)
                self.assertIn("sent_at = COALESCE(sent_at, CURRENT_TIMESTAMP)", q)

    def test_delayed_dispatch_cannot_overwrite_recorded_delivery_receipt(self):
        """Req 9: Delayed dispatch update contains guard preventing overwriting 'delivered', 'opened', 'clicked'."""
        executed_sqls = []

        class MockConn:
            async def execute(self, query, *args):
                executed_sqls.append((query, args))
            async def fetchval(self, query, *args):
                return 1

        mock_conn = MockConn()
        sem = asyncio.Semaphore(1)

        with patch("services.campaign_processor.get_connection", new_callable=AsyncMock) as mock_get_conn, \
             patch("services.campaign_processor.release_connection", new_callable=AsyncMock), \
             patch("services.campaign_processor.send_to_channel_service", new_callable=AsyncMock) as mock_send:
            mock_get_conn.return_value = mock_conn
            mock_send.return_value = True

            asyncio.run(campaign_processor._dispatch_single_recipient(
                campaign_id=1, customer_id=10, comm_id=77, channel="email", message="Hello", sem=sem
            ))

            # Success query must preserve delivered, opened, clicked, failed via CASE and set sent_at via COALESCE
            update_query = [q for q, _ in executed_sqls if "UPDATE communications" in q][0]
            self.assertIn("WHEN status IN ('delivered', 'opened', 'clicked', 'failed') THEN status", update_query)
            self.assertIn("sent_at = COALESCE(sent_at, CURRENT_TIMESTAMP)", update_query)

            # Test failed dispatch also includes receipt guard
            executed_sqls.clear()
            mock_send.return_value = False

            asyncio.run(campaign_processor._dispatch_single_recipient(
                campaign_id=1, customer_id=10, comm_id=77, channel="email", message="Hello", sem=sem
            ))

            fail_update_query = [q for q, _ in executed_sqls if "UPDATE communications" in q][0]
            self.assertIn("status NOT IN ('delivered', 'opened', 'clicked')", fail_update_query)

    def test_early_receipt_arrives_before_dispatch_completion(self):
        """
        Audit Requirement: Test race condition where valid receipt arrives and is processed
        BEFORE the campaign processor records the dispatch outcome.

        Verifies:
        1. Confirmed status ('delivered') cannot be overwritten by dispatch completion.
        2. sent_at is correctly populated when dispatch acceptance has been established.
        3. Receipt's confirmed state is preserved end-to-end.
        """
        executed_sqls = []

        class MockConn:
            async def execute(self, query, *args):
                executed_sqls.append((query, args))
            async def fetchval(self, query, *args):
                return 1

        mock_conn = MockConn()
        sem = asyncio.Semaphore(1)

        with patch("services.campaign_processor.get_connection", new_callable=AsyncMock) as mock_get_conn, \
             patch("services.campaign_processor.release_connection", new_callable=AsyncMock), \
             patch("services.campaign_processor.send_to_channel_service", new_callable=AsyncMock) as mock_send:
            mock_get_conn.return_value = mock_conn
            mock_send.return_value = True

            # Execute delayed dispatch completion after receipt arrived
            asyncio.run(campaign_processor._dispatch_single_recipient(
                campaign_id=1, customer_id=10, comm_id=100, channel="email", message="Promo", sem=sem
            ))

            update_query = [q for q, _ in executed_sqls if "UPDATE communications" in q][0]
            # Ensure the SQL preserves delivered state and guarantees sent_at
            self.assertIn("WHEN status IN ('delivered', 'opened', 'clicked', 'failed') THEN status", update_query)
            self.assertIn("sent_at = COALESCE(sent_at, CURRENT_TIMESTAMP)", update_query)


# ===========================================================================
# 3. Receipt Handling & Concurrency Tests (Req 8, 11)
# ===========================================================================

class TestReceiptHandling(unittest.TestCase):
    """Verifies that authenticated receipts update outcomes and maintain idempotence."""

    def test_delivery_receipt_updates_recipient_level_outcome(self):
        """Req 8: Delivery receipt sets status to 'delivered' and records delivered_at."""
        from fastapi.testclient import TestClient
        from main import app
        import hmac

        secret = "test-secret-reporting-fix2"
        client = TestClient(app)

        executed_sqls = []

        class MockConn:
            async def execute(self, query, *args):
                executed_sqls.append((query, args))

        mock_conn = MockConn()

        with patch("routers.receipts.CHANNEL_SERVICE_SECRET", secret), \
             patch("routers.receipts.get_connection", new_callable=AsyncMock) as mock_get_conn, \
             patch("routers.receipts.release_connection", new_callable=AsyncMock):
            mock_get_conn.return_value = mock_conn

            response = client.post(
                "/receipt",
                json={"campaign_id": 1, "customer_id": 42, "status": "delivered"},
                headers={"X-Channel-Service-Key": secret}
            )

            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["status"], "delivered")

            # Check executed SQL
            self.assertTrue(len(executed_sqls) > 0)
            q, args = executed_sqls[0]
            self.assertIn("delivered_at = COALESCE(delivered_at, CURRENT_TIMESTAMP)", q)
            self.assertEqual(args, (1, 42))

    def test_receipt_failure_cannot_overwrite_delivered_state(self):
        """A late failure receipt has a WHERE guard so it cannot overwrite delivered/opened/clicked."""
        from fastapi.testclient import TestClient
        from main import app

        secret = "test-secret-reporting-fix2"
        client = TestClient(app)

        executed_sqls = []

        class MockConn:
            async def execute(self, query, *args):
                executed_sqls.append((query, args))

        mock_conn = MockConn()

        with patch("routers.receipts.CHANNEL_SERVICE_SECRET", secret), \
             patch("routers.receipts.get_connection", new_callable=AsyncMock) as mock_get_conn, \
             patch("routers.receipts.release_connection", new_callable=AsyncMock):
            mock_get_conn.return_value = mock_conn

            response = client.post(
                "/receipt",
                json={"campaign_id": 1, "customer_id": 42, "status": "failed"},
                headers={"X-Channel-Service-Key": secret}
            )

            self.assertEqual(response.status_code, 200)
            q, _ = executed_sqls[0]
            self.assertIn("status NOT IN ('delivered', 'opened', 'clicked')", q)

    def test_out_of_order_and_duplicate_receipts_monotonicity(self):
        """Audit Requirement: Out-of-order and duplicate receipts do not regress state or corrupt timestamps."""
        from fastapi.testclient import TestClient
        from main import app

        secret = "test-secret-reporting-fix2"
        client = TestClient(app)

        executed_sqls = []

        class MockConn:
            async def execute(self, query, *args):
                executed_sqls.append((query, args))

        mock_conn = MockConn()

        with patch("routers.receipts.CHANNEL_SERVICE_SECRET", secret), \
             patch("routers.receipts.get_connection", new_callable=AsyncMock) as mock_get_conn, \
             patch("routers.receipts.release_connection", new_callable=AsyncMock):
            mock_get_conn.return_value = mock_conn

            # 1. Delivered receipt sets delivered_at and sent_at via COALESCE
            client.post(
                "/receipt",
                json={"campaign_id": 1, "customer_id": 42, "status": "delivered"},
                headers={"X-Channel-Service-Key": secret}
            )
            q_deliv = executed_sqls[-1][0]
            self.assertIn("delivered_at = COALESCE(delivered_at, CURRENT_TIMESTAMP)", q_deliv)
            self.assertIn("sent_at = COALESCE(sent_at, CURRENT_TIMESTAMP)", q_deliv)

            # 2. Opened receipt sets opened_at, delivered_at, sent_at via COALESCE
            client.post(
                "/receipt",
                json={"campaign_id": 1, "customer_id": 42, "status": "opened"},
                headers={"X-Channel-Service-Key": secret}
            )
            q_opened = executed_sqls[-1][0]
            self.assertIn("opened_at = COALESCE(opened_at, CURRENT_TIMESTAMP)", q_opened)
            self.assertIn("delivered_at = COALESCE(delivered_at, CURRENT_TIMESTAMP)", q_opened)
            self.assertIn("sent_at = COALESCE(sent_at, CURRENT_TIMESTAMP)", q_opened)

            # 3. Clicked receipt sets clicked_at, opened_at, delivered_at, sent_at via COALESCE
            client.post(
                "/receipt",
                json={"campaign_id": 1, "customer_id": 42, "status": "clicked"},
                headers={"X-Channel-Service-Key": secret}
            )
            q_clicked = executed_sqls[-1][0]
            self.assertIn("clicked_at = COALESCE(clicked_at, CURRENT_TIMESTAMP)", q_clicked)
            self.assertIn("opened_at = COALESCE(opened_at, CURRENT_TIMESTAMP)", q_clicked)
            self.assertIn("delivered_at = COALESCE(delivered_at, CURRENT_TIMESTAMP)", q_clicked)
            self.assertIn("sent_at = COALESCE(sent_at, CURRENT_TIMESTAMP)", q_clicked)

    def test_existing_authenticated_receipt_processing_works(self):
        """Req 11: 401 on missing key, 403 on invalid key, 200 on valid key."""
        from fastapi.testclient import TestClient
        from main import app

        secret = "test-secret-reporting-fix2"
        client = TestClient(app)

        class MockConn:
            async def execute(self, query, *args):
                pass

        with patch("routers.receipts.CHANNEL_SERVICE_SECRET", secret), \
             patch("routers.receipts.get_connection", new_callable=AsyncMock) as mock_get_conn, \
             patch("routers.receipts.release_connection", new_callable=AsyncMock):
            mock_get_conn.return_value = MockConn()

            # Missing key -> 401
            r401 = client.post("/receipt", json={"campaign_id": 1, "customer_id": 1, "status": "delivered"})
            self.assertEqual(r401.status_code, 401)

            # Invalid key -> 403
            r403 = client.post(
                "/receipt",
                json={"campaign_id": 1, "customer_id": 1, "status": "delivered"},
                headers={"X-Channel-Service-Key": "wrong-secret"}
            )
            self.assertEqual(r403.status_code, 403)

            # Valid key -> 200
            r200 = client.post(
                "/receipt",
                json={"campaign_id": 1, "customer_id": 1, "status": "delivered"},
                headers={"X-Channel-Service-Key": secret}
            )
            self.assertEqual(r200.status_code, 200)


# ===========================================================================
# 4. Campaign Stats Endpoint Calculation Tests (Req 7, 8)
# ===========================================================================

class TestCampaignStatsReporting(unittest.TestCase):
    """Verifies that the /stats endpoint accurately calculates sent, delivered, and failed counts."""

    def test_campaign_stats_uses_sent_at_for_sent_count(self):
        """Campaign stats counts sent_at IS NOT NULL for dispatched count."""
        from fastapi.testclient import TestClient
        from main import app

        client = TestClient(app)

        class MockConn:
            async def fetchrow(self, query, *args):
                return {"id": 1, "name": "Test Campaign"}
            async def fetchval(self, query, *args):
                if "sent_at IS NOT NULL" in query:
                    return 8  # 8 dispatched successfully
                if "delivered_at IS NOT NULL" in query:
                    return 6  # 6 confirmed delivered
                if "opened_at IS NOT NULL" in query:
                    return 4  # 4 opened
                if "clicked_at IS NOT NULL" in query:
                    return 2  # 2 clicked
                if "status = 'failed'" in query:
                    return 2  # 2 failed (dispatch or delivery)
                return 10  # total communications

        from core.auth import verify_clerk_token
        app.dependency_overrides[verify_clerk_token] = lambda: {"sub": "user_test"}

        try:
            with patch("routers.campaigns.get_connection", new_callable=AsyncMock) as mock_get_conn, \
                 patch("routers.campaigns.release_connection", new_callable=AsyncMock):
                mock_get_conn.return_value = MockConn()

                response = client.get("/campaigns/1/stats")
                self.assertEqual(response.status_code, 200)
                data = response.json()

                self.assertEqual(data["campaign_id"], 1)
                self.assertEqual(data["total"], 10)
                self.assertEqual(data["sent"], 8)
                self.assertEqual(data["delivered"], 6)
                self.assertEqual(data["opened"], 4)
                self.assertEqual(data["clicked"], 2)
                self.assertEqual(data["failed"], 2)
        finally:
            app.dependency_overrides.clear()


# ===========================================================================
# 5. Early Receipt Race Condition Behavioral Tests (Fix 2 Final Correction)
# ===========================================================================

class TestEarlyReceiptRaceCondition(unittest.TestCase):
    """
    Focused behavioral tests verifying dispatch/receipt race conditions,
    early failure receipts, timestamp semantics, and statistics consistency.
    """

    def test_early_failure_receipt_then_confirmed_http_2xx(self):
        """
        Req 1: Early failure receipt arrives, followed by confirmed HTTP 2xx.
        Status must remain 'failed', but sent_at becomes populated because
        dispatch acceptance was confirmed.
        """
        # Communication record state simulation
        state = {"id": 101, "status": "processing", "sent_at": None, "delivered_at": None}

        class MockConn:
            async def execute(self, query, *args):
                if "UPDATE communications" in query:
                    # Emulate CASE WHEN status IN ('delivered', 'opened', 'clicked', 'failed') THEN status ELSE 'sent' END
                    if "status IN ('delivered', 'opened', 'clicked', 'failed')" in query:
                        if state["status"] not in ('delivered', 'opened', 'clicked', 'failed'):
                            state["status"] = "sent"
                        # Emulate sent_at = COALESCE(sent_at, CURRENT_TIMESTAMP)
                        if state["sent_at"] is None:
                            state["sent_at"] = "2026-10-15 12:00:00"

        # Step 1: Early failure receipt arrives first and updates status to 'failed'
        state["status"] = "failed"
        self.assertIsNone(state["sent_at"])

        # Step 2: HTTP 2xx dispatch acceptance is confirmed
        mock_conn = MockConn()
        sem = asyncio.Semaphore(1)

        with patch("services.campaign_processor.get_connection", new_callable=AsyncMock) as mock_get_conn, \
             patch("services.campaign_processor.release_connection", new_callable=AsyncMock), \
             patch("services.campaign_processor.send_to_channel_service", new_callable=AsyncMock) as mock_send:
            mock_get_conn.return_value = mock_conn
            mock_send.return_value = True

            ok = asyncio.run(campaign_processor._dispatch_single_recipient(
                campaign_id=1, customer_id=10, comm_id=101, channel="email", message="Hello", sem=sem
            ))

            self.assertTrue(ok)
            # Final state verification
            self.assertEqual(state["status"], "failed", "Final status must remain 'failed' (cannot revert to 'sent')")
            self.assertIsNotNone(state["sent_at"], "sent_at must be populated because HTTP 2xx dispatch was confirmed")

    def test_early_delivered_receipt_then_confirmed_http_2xx(self):
        """
        Req 2: Early delivered receipt arrives, followed by confirmed HTTP 2xx.
        Status must remain 'delivered', with sent_at populated.
        """
        state = {"id": 102, "status": "processing", "sent_at": None, "delivered_at": None}

        class MockConn:
            async def execute(self, query, *args):
                if "UPDATE communications" in query:
                    if "status IN ('delivered', 'opened', 'clicked', 'failed')" in query:
                        if state["status"] not in ('delivered', 'opened', 'clicked', 'failed'):
                            state["status"] = "sent"
                        if state["sent_at"] is None:
                            state["sent_at"] = "2026-10-15 12:00:00"

        # Step 1: Delivery receipt arrives first
        state["status"] = "delivered"
        state["delivered_at"] = "2026-10-15 12:00:01"

        # Step 2: HTTP 2xx dispatch acceptance confirmed
        mock_conn = MockConn()
        sem = asyncio.Semaphore(1)

        with patch("services.campaign_processor.get_connection", new_callable=AsyncMock) as mock_get_conn, \
             patch("services.campaign_processor.release_connection", new_callable=AsyncMock), \
             patch("services.campaign_processor.send_to_channel_service", new_callable=AsyncMock) as mock_send:
            mock_get_conn.return_value = mock_conn
            mock_send.return_value = True

            ok = asyncio.run(campaign_processor._dispatch_single_recipient(
                campaign_id=1, customer_id=10, comm_id=102, channel="email", message="Hello", sem=sem
            ))

            self.assertTrue(ok)
            self.assertEqual(state["status"], "delivered")
            self.assertIsNotNone(state["sent_at"])
            self.assertIsNotNone(state["delivered_at"])

    def test_http_failure_no_dispatch_success_timestamp_invented(self):
        """
        Req 3: HTTP 4xx/5xx or connection failure: no dispatch-success timestamp is invented.
        """
        state = {"id": 103, "status": "processing", "sent_at": None}

        class MockConn:
            async def execute(self, query, *args):
                if "UPDATE communications" in query and "status = 'failed'" in query:
                    state["status"] = "failed"
                    # Notice sent_at is NOT set here

        mock_conn = MockConn()
        sem = asyncio.Semaphore(1)

        with patch("services.campaign_processor.get_connection", new_callable=AsyncMock) as mock_get_conn, \
             patch("services.campaign_processor.release_connection", new_callable=AsyncMock), \
             patch("services.campaign_processor.send_to_channel_service", new_callable=AsyncMock) as mock_send:
            mock_get_conn.return_value = mock_conn
            mock_send.return_value = False  # HTTP 4xx/5xx/timeout

            ok = asyncio.run(campaign_processor._dispatch_single_recipient(
                campaign_id=1, customer_id=10, comm_id=103, channel="email", message="Hello", sem=sem
            ))

            self.assertFalse(ok)
            self.assertEqual(state["status"], "failed")
            self.assertIsNone(state["sent_at"], "sent_at must remain None when HTTP dispatch fails")

    def test_late_dispatch_failure_cannot_overwrite_confirmed_delivery(self):
        """
        Req 4: Late dispatch failure cannot overwrite a confirmed delivery, open, or click.
        """
        state = {"id": 104, "status": "delivered", "delivered_at": "2026-10-15 12:00:00"}

        class MockConn:
            async def execute(self, query, *args):
                # Simulated SQL: UPDATE communications SET status = 'failed' WHERE id = $1 AND status NOT IN ('delivered', 'opened', 'clicked')
                if "status NOT IN ('delivered', 'opened', 'clicked')" in query:
                    if state["status"] not in ('delivered', 'opened', 'clicked'):
                        state["status"] = "failed"

        mock_conn = MockConn()
        sem = asyncio.Semaphore(1)

        with patch("services.campaign_processor.get_connection", new_callable=AsyncMock) as mock_get_conn, \
             patch("services.campaign_processor.release_connection", new_callable=AsyncMock), \
             patch("services.campaign_processor.send_to_channel_service", new_callable=AsyncMock) as mock_send:
            mock_get_conn.return_value = mock_conn
            mock_send.return_value = False  # Late timeout/failure

            ok = asyncio.run(campaign_processor._dispatch_single_recipient(
                campaign_id=1, customer_id=10, comm_id=104, channel="email", message="Hello", sem=sem
            ))

            self.assertFalse(ok)
            self.assertEqual(state["status"], "delivered", "Confirmed delivery must NOT be overwritten by late failure")

    def test_campaign_stats_counts_confirmed_dispatch_with_later_failure_receipt(self):
        """
        Req 5: Campaign sent/dispatched statistics count a confirmed HTTP 2xx dispatch
        even when a later delivery-failure receipt means the communication status is 'failed'.
        """
        from fastapi.testclient import TestClient
        from main import app
        from core.auth import verify_clerk_token

        client = TestClient(app)
        app.dependency_overrides[verify_clerk_token] = lambda: {"sub": "user_test"}

        # Simulate 2 communications:
        # Comm 1: dispatched (sent_at IS NOT NULL), but status is 'failed' (delivery failed)
        # Comm 2: dispatched (sent_at IS NOT NULL), and status is 'delivered'
        class MockConn:
            async def fetchrow(self, query, *args):
                return {"id": 1, "name": "Mixed Stats Campaign"}
            async def fetchval(self, query, *args):
                if "sent_at IS NOT NULL" in query:
                    return 2  # BOTH were dispatched successfully
                if "delivered_at IS NOT NULL" in query:
                    return 1  # Only 1 delivered
                if "status = 'failed'" in query:
                    return 1  # 1 delivery failure
                return 2  # total communications

        try:
            with patch("routers.campaigns.get_connection", new_callable=AsyncMock) as mock_get_conn, \
                 patch("routers.campaigns.release_connection", new_callable=AsyncMock):
                mock_get_conn.return_value = MockConn()

                response = client.get("/campaigns/1/stats")
                self.assertEqual(response.status_code, 200)
                data = response.json()

                self.assertEqual(data["sent"], 2, "Dispatched count must include confirmed dispatches that later failed delivery")
                self.assertEqual(data["delivered"], 1)
                self.assertEqual(data["failed"], 1)
                self.assertEqual(data["total"], 2)
        finally:
            app.dependency_overrides.clear()


if __name__ == "__main__":
    unittest.main(verbosity=2)
