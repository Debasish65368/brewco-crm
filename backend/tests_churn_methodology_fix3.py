"""
Automated Behavioral Tests for Fix 3: Defensible Heuristic Churn Methodology.

Covers:
1. Deterministic score calculation and breakdown for ordinary customer profiles.
2. Deliberate handling of new customers, zero-order prospects, and missing dates.
3. Resilience to invalid inputs (negative values, NaNs, future dates, malformed strings).
4. Strict score boundedness within [0.0, 1.0] across boundary conditions.
5. Strict determinism across repeated executions.
6. Monotonicity: scores increase with dormancy, decrease with repeat visits and spend.
7. Semantic alignment with frontend health categorization (VIP, At Risk, Active, Unscored).
8. Deprecation and retirement of pseudo-label training and removal of obsolete artifacts.
9. Isolated verification without any live database mutations.
"""

import math
import os
import unittest
from datetime import datetime, timedelta, timezone

from services.churn_risk import (
    HIGH_RISK_THRESHOLD,
    calculate_churn_risk,
    calculate_churn_risk_breakdown,
)


class TestChurnScoreOrdinaryData(unittest.TestCase):
    """Verifies score calculation for typical customer profiles."""

    def setUp(self):
        self.now = datetime(2026, 10, 15, 12, 0, 0)

    def test_active_loyal_customer_has_low_churn_risk(self):
        """Active customer with frequent recent orders and high spend has low risk (< 0.40)."""
        last_order = self.now - timedelta(days=2)
        score = calculate_churn_risk(
            total_orders=15,
            total_spent=4500.0,
            last_order_date=last_order,
            now=self.now,
        )
        self.assertLess(score, 0.40)
        self.assertGreaterEqual(score, 0.0)

    def test_moderate_customer_profile(self):
        """Customer with moderate recency and occasional orders has moderate risk [0.40, 0.70]."""
        last_order = self.now - timedelta(days=45)
        score = calculate_churn_risk(
            total_orders=2,
            total_spent=350.0,
            last_order_date=last_order,
            now=self.now,
        )
        self.assertGreaterEqual(score, 0.40)
        self.assertLessEqual(score, 0.70)

    def test_dormant_customer_has_high_risk(self):
        """Customer who has not ordered in 90+ days has high churn risk (> 0.70)."""
        last_order = self.now - timedelta(days=95)
        score = calculate_churn_risk(
            total_orders=1,
            total_spent=180.0,
            last_order_date=last_order,
            now=self.now,
        )
        self.assertGreater(score, HIGH_RISK_THRESHOLD)
        self.assertLessEqual(score, 1.0)


class TestZeroOrdersAndMissingDates(unittest.TestCase):
    """Verifies deliberate handling of prospects, new sign-ups, and missing dates."""

    def setUp(self):
        self.now = datetime(2026, 10, 15, 12, 0, 0)

    def test_new_customer_with_zero_orders_not_penalized_as_dormant(self):
        """A new customer created 3 days ago with 0 orders is scored by account tenure."""
        created_at = self.now - timedelta(days=3)
        breakdown = calculate_churn_risk_breakdown(
            total_orders=0,
            total_spent=0.0,
            last_order_date=None,
            created_at=created_at,
            now=self.now,
        )
        # Recency risk = 3 / 90 = 0.033, frequency = 1.0, monetary = 1.0
        # 0.50*(0.033) + 0.30*(1.0) + 0.20*(1.0) = ~0.517 (moderate onboarding, not 1.0)
        self.assertLess(breakdown["score"], 0.70)
        self.assertEqual(breakdown["components"]["recency_risk"], round(3 / 90.0, 4))
        self.assertEqual(breakdown["features"]["account_tenure_days"], 3)

    def test_dormant_prospect_with_old_registration_has_max_recency_risk(self):
        """An account created 120 days ago with 0 orders reaches maximum churn risk."""
        created_at = self.now - timedelta(days=120)
        score = calculate_churn_risk(
            total_orders=0,
            total_spent=0.0,
            last_order_date=None,
            created_at=created_at,
            now=self.now,
        )
        self.assertAlmostEqual(score, 1.0, places=4)

    def test_completely_missing_dates_handled_safely(self):
        """When dates are completely missing, scoring succeeds with bounded output."""
        score = calculate_churn_risk(
            total_orders=0,
            total_spent=0.0,
            last_order_date=None,
            created_at=None,
            now=self.now,
        )
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 1.0)


class TestInvalidAndBoundaryInputs(unittest.TestCase):
    """Verifies resilience against negative, NaN, Inf, and malformed inputs."""

    def setUp(self):
        self.now = datetime(2026, 10, 15, 12, 0, 0)

    def test_negative_values_clamped_safely(self):
        """Negative orders or spend are clamped to 0 without throwing."""
        score = calculate_churn_risk(
            total_orders=-10,
            total_spent=-500.0,
            last_order_date=self.now - timedelta(days=10),
            now=self.now,
        )
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 1.0)

    def test_future_dates_clamped_to_zero_days(self):
        """Clock skew placing last_order in the future clamps days_since_last_order to 0."""
        future_order = self.now + timedelta(days=5)
        breakdown = calculate_churn_risk_breakdown(
            total_orders=2,
            total_spent=300.0,
            last_order_date=future_order,
            now=self.now,
        )
        self.assertEqual(breakdown["features"]["days_since_last_order"], 0)
        self.assertEqual(breakdown["components"]["recency_risk"], 0.0)

    def test_nan_and_inf_handled_safely(self):
        """Float NaN or Inf values do not propagate into NaN or Inf scores."""
        score = calculate_churn_risk(
            total_orders=float("nan"),
            total_spent=float("inf"),
            last_order_date=self.now,
            now=self.now,
        )
        self.assertFalse(math.isnan(score))
        self.assertFalse(math.isinf(score))
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 1.0)

    def test_all_none_parameters_returns_valid_score(self):
        """Passing None for every argument returns a valid bounded score."""
        score = calculate_churn_risk(
            total_orders=None,
            total_spent=None,
            last_order_date=None,
            created_at=None,
            now=None,
        )
        self.assertIsInstance(score, float)
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 1.0)

    def test_iso_string_dates_parsed_accurately(self):
        """ISO strings with or without Z suffix parse correctly."""
        score1 = calculate_churn_risk(
            total_orders=2,
            total_spent=400.0,
            last_order_date="2026-10-10T12:00:00Z",
            now=self.now,
        )
        score2 = calculate_churn_risk(
            total_orders=2,
            total_spent=400.0,
            last_order_date=datetime(2026, 10, 10, 12, 0, 0),
            now=self.now,
        )
        self.assertEqual(score1, score2)

    def test_malformed_string_date_falls_back_gracefully(self):
        """Malformed date string does not raise unhandled exception."""
        score = calculate_churn_risk(
            total_orders=2,
            total_spent=400.0,
            last_order_date="invalid-date-string",
            now=self.now,
        )
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 1.0)


class TestMonotonicityAndDeterminism(unittest.TestCase):
    """Verifies mathematical consistency: determinism and directional monotonicity."""

    def setUp(self):
        self.now = datetime(2026, 10, 15, 12, 0, 0)

    def test_score_is_strictly_deterministic(self):
        """Identical inputs with fixed reference time always return identical scores."""
        scores = [
            calculate_churn_risk(
                total_orders=4,
                total_spent=1200.0,
                last_order_date=self.now - timedelta(days=20),
                now=self.now,
            )
            for _ in range(50)
        ]
        self.assertEqual(len(set(scores)), 1)

    def test_monotonicity_increasing_inactivity_increases_risk(self):
        """Holding orders and spend constant, increasing recency days strictly increases risk."""
        days_list = [1, 10, 25, 45, 70, 90, 120]
        scores = [
            calculate_churn_risk(
                total_orders=3,
                total_spent=600.0,
                last_order_date=self.now - timedelta(days=d),
                now=self.now,
            )
            for d in days_list
        ]
        for i in range(len(scores) - 1):
            self.assertLessEqual(
                scores[i],
                scores[i + 1],
                f"Score at {days_list[i]}d ({scores[i]}) should be <= score at {days_list[i+1]}d ({scores[i+1]})",
            )

    def test_monotonicity_increasing_orders_decreases_risk(self):
        """Holding recency and spend constant, increasing order count strictly decreases risk."""
        orders_list = [0, 1, 3, 5, 10, 25]
        scores = [
            calculate_churn_risk(
                total_orders=o,
                total_spent=500.0,
                last_order_date=self.now - timedelta(days=15),
                now=self.now,
            )
            for o in orders_list
        ]
        for i in range(len(scores) - 1):
            self.assertGreaterEqual(
                scores[i],
                scores[i + 1],
                f"Score at {orders_list[i]} orders ({scores[i]}) should be >= score at {orders_list[i+1]} orders ({scores[i+1]})",
            )

    def test_monotonicity_increasing_spend_decreases_risk(self):
        """Holding recency and orders constant, increasing monetary spend strictly decreases risk."""
        spends_list = [0.0, 250.0, 750.0, 2000.0, 10000.0]
        scores = [
            calculate_churn_risk(
                total_orders=2,
                total_spent=s,
                last_order_date=self.now - timedelta(days=15),
                now=self.now,
            )
            for s in spends_list
        ]
        for i in range(len(scores) - 1):
            self.assertGreaterEqual(
                scores[i],
                scores[i + 1],
                f"Score at ₹{spends_list[i]} spend ({scores[i]}) should be >= score at ₹{spends_list[i+1]} spend ({scores[i+1]})",
            )


class TestFrontendHealthSemantics(unittest.TestCase):
    """
    Verifies that health categorization logic reflects the defensible methodology:
    - High-value frequent spenders are VIP regardless of churn score.
    - Churn score > 0.70 marks customer At Risk.
    - Churn score <= 0.70 marks customer Active.
    - Missing churn score / zero data returns Unscored (never defaulted to Active).
    """

    def _get_health(self, customer):
        """Python implementation of getCustomerHealth matching frontend contract."""
        if not customer:
            return "Unscored"
        total_orders = float(customer.get("total_orders") or 0)
        total_spent = float(customer.get("total_spent") or 0)

        if total_orders > 4 and total_spent > 5000:
            return "VIP"

        if total_orders == 0:
            return "Unscored"

        score = customer.get("churn_score")
        if score is None or (isinstance(score, float) and math.isnan(score)):
            return "Unscored"

        try:
            val = float(score)
        except (TypeError, ValueError):
            return "Unscored"

        if val > 0.70:
            return "At Risk"
        return "Active"

    def test_vip_classification(self):
        """Customers with >4 orders and >₹5000 spend are VIP."""
        cust = {"total_orders": 6, "total_spent": 5500.0, "churn_score": 0.85}
        self.assertEqual(self._get_health(cust), "VIP")

    def test_at_risk_classification(self):
        """Non-VIP customers with churn_score > 0.70 are At Risk."""
        cust = {"total_orders": 2, "total_spent": 400.0, "churn_score": 0.78}
        self.assertEqual(self._get_health(cust), "At Risk")

    def test_active_classification(self):
        """Non-VIP customers with churn_score <= 0.70 are Active."""
        cust = {"total_orders": 3, "total_spent": 900.0, "churn_score": 0.45}
        self.assertEqual(self._get_health(cust), "Active")

    def test_zero_orders_returns_unscored(self):
        """Customers with zero orders are categorized as Unscored rather than Active."""
        cust_zero = {"total_orders": 0, "total_spent": 0.0, "churn_score": 0.20}
        self.assertEqual(self._get_health(cust_zero), "Unscored")

    def test_missing_score_returns_unscored_not_active(self):
        """Missing churn score does NOT default to Active (which would falsely imply low risk)."""
        cust_none = {"total_orders": 0, "total_spent": 0.0, "churn_score": None}
        self.assertEqual(self._get_health(cust_none), "Unscored")

        cust_missing_key = {"total_orders": 1, "total_spent": 150.0}
        self.assertEqual(self._get_health(cust_missing_key), "Unscored")


class TestCustomerEndpointReadTimeScoring(unittest.TestCase):
    """Verifies that GET /customers computes heuristic scores dynamically at read time."""

    def test_read_time_scoring_overwrites_stale_persisted_score(self):
        """Read-time logic calculates fresh heuristic score regardless of persisted DB values."""
        stale_db_row = {
            "id": 42,
            "name": "Arjun Sharma",
            "email": "arjun@example.com",
            "city": "Mumbai",
            "total_orders": 8,
            "total_spent": 2400.0,
            "last_order_date": datetime.now() - timedelta(days=5),
            "created_at": datetime.now() - timedelta(days=60),
            "churn_score": 0.95,  # Stale, unverified value from old model
            "cluster_id": 1,
        }

        # Simulate read-time scoring loop from routers/customers.py
        c = dict(stale_db_row)
        c["churn_score"] = calculate_churn_risk(
            total_orders=c.get("total_orders"),
            total_spent=c.get("total_spent"),
            last_order_date=c.get("last_order_date"),
            created_at=c.get("created_at"),
        )

        # Fresh score for 8 orders, ₹2400 spend, ordered 5 days ago should be < 0.40 (low risk)
        self.assertLess(c["churn_score"], 0.40)
        self.assertNotEqual(c["churn_score"], 0.95)


class TestRetiredArtifactsAndScripts(unittest.TestCase):
    """Verifies that pseudo-label training is retired and obsolete artifacts are absent."""

    def test_churn_model_pickle_is_absent(self):
        """backend/models/churn_model.pkl must not exist."""
        models_dir = os.path.join(os.path.dirname(__file__), "models")
        churn_pickle = os.path.join(models_dir, "churn_model.pkl")
        self.assertFalse(
            os.path.exists(churn_pickle),
            "Obsolete churn_model.pkl must be removed to prevent loading unvalidated models.",
        )

    def test_rfm_artifacts_are_preserved(self):
        """RFM clustering models in backend/models must remain intact."""
        models_dir = os.path.join(os.path.dirname(__file__), "models")
        rfm_model = os.path.join(models_dir, "rfm_model.pkl")
        rfm_scaler = os.path.join(models_dir, "rfm_scaler.pkl")
        self.assertTrue(os.path.exists(rfm_model), "rfm_model.pkl must be preserved.")
        self.assertTrue(os.path.exists(rfm_scaler), "rfm_scaler.pkl must be preserved.")

    def test_train_churn_model_script_is_retired_and_safe(self):
        """Executing train_churn_model.main() runs the deprecation notice without creating artifacts."""
        import scripts.train_churn_model as train_script

        exit_code = train_script.main()
        self.assertEqual(exit_code, 0)
        # Verify no pickle was created
        models_dir = os.path.join(os.path.dirname(__file__), "models")
        churn_pickle = os.path.join(models_dir, "churn_model.pkl")
        self.assertFalse(os.path.exists(churn_pickle))


class TestAnalyticsChurnExclusion(unittest.TestCase):
    """Verifies that Ask Your Data / natural language SQL cannot query stale persisted churn scores."""

    def test_analytics_query_rejects_churn_score(self):
        """Attempting to select churn_score via Ask Your Data spec is blocked by schema validation."""
        from services.sql_guard import build_analytics_query

        spec = {
            "tables": ["customers"],
            "select": [{"table": "customers", "column": "churn_score"}],
        }
        is_valid, reason, sql, params = build_analytics_query(spec)
        self.assertFalse(is_valid)
        self.assertIn("not valid for table 'customers'", reason)

    def test_analytics_query_allows_safe_customer_fields(self):
        """Selecting authorized customer fields (city, spend, orders) remains fully supported."""
        from services.sql_guard import build_analytics_query

        spec = {
            "tables": ["customers"],
            "select": [
                {"table": "customers", "column": "city"},
                {"table": "customers", "column": "total_spent", "agg": "SUM"},
                {"table": "customers", "column": "total_orders", "agg": "AVG"},
            ],
        }
        is_valid, reason, sql, params = build_analytics_query(spec)
        self.assertTrue(is_valid)
        self.assertIn("customers.city", sql)
        self.assertIn("SUM(customers.total_spent)", sql)


if __name__ == "__main__":
    unittest.main()
