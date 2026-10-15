"""
Defensible Heuristic Churn-Risk Scoring Service for BrewCo CRM.

Fix 3 / Path B Implementation:
Because the BrewCo CRM dataset does not contain observed ground-truth churn
events (e.g. cancellation logs, account deactivations, or empirical inactivity
horizons), fitting a supervised classifier (such as Logistic Regression) to
pseudo-labels creates circular logic with no true generalization or predictive validity.

This module provides a transparent, deterministic, and bounded heuristic
churn-risk index based on observable customer purchasing behavior.

Methodology:
1. Recency Risk (R) - 50% weight:
   Measures days elapsed since the customer's last order relative to a chosen
   90-day prototype dormancy cutoff.
   R = min(days_since_last_order / 90.0, 1.0)
   - When last_order_date is missing:
     * If created_at is available and registration tenure <= 30 days, scales
       by tenure / 90.0 to treat new sign-ups fairly rather than assuming dormancy.
     * If tenure > 30 days or registration date is unknown, defaults to 1.0 (dormant).

2. Frequency Risk (F) - 30% weight:
   Measures purchase habituation. Repeat visits reduce risk in this heuristic:
   F = 1.0 / (1.0 + total_orders)
   - 0 orders:   1.00 (no purchase habit)
   - 1 order:    0.50
   - 2 orders:   0.33
   - 5 orders:   0.17
   - 10+ orders: <0.09

3. Monetary Risk (M) - 20% weight:
   Measures cumulative economic engagement:
   M = 1.0 / (1.0 + total_spent / 1000.0)
   - ₹0 spent:      1.00
   - ₹500 spent:    0.67
   - ₹1,000 spent:  0.50
   - ₹5,000+ spent: <0.17

Parameter Evidential Status:
   The 90-day recency horizon, 50/30/20 component weighting, and ₹1,000 monetary
   scaling are chosen heuristic parameters for this prototype. They have NOT been
   statistically calibrated or fitted against observed BrewCo customer churn outcomes.

Composite Churn-Risk Score:
   Score = (0.50 * R) + (0.30 * F) + (0.20 * M)
   Strictly bounded within [0.0, 1.0], rounded to 4 decimal places.

Interpretation:
   This score is a relative behavioral risk indicator, NOT an empirically
   validated or calibrated probability of churn.
   - Low Risk:      [0.00, 0.40)
   - Moderate Risk: [0.40, 0.70]
   - High Risk:     (0.70, 1.00] ("At Risk" threshold in CRM frontend)
"""

from datetime import date, datetime, timezone
from typing import Any, Dict, Optional, Union
import math


# Default weights (sum to 1.0)
RECENCY_WEIGHT = 0.50
FREQUENCY_WEIGHT = 0.30
MONETARY_WEIGHT = 0.20

# Dormancy horizon in days
RECENCY_MAX_DAYS = 90.0

# Monetary normalization scale in currency units
MONETARY_SCALE = 1000.0

# High-risk threshold for UI classification
HIGH_RISK_THRESHOLD = 0.70


def _parse_datetime(val: Any) -> Optional[datetime]:
    """Safely converts various date/datetime inputs to a naive datetime."""
    if val is None:
        return None
    if isinstance(val, datetime):
        # Convert timezone-aware to naive UTC for safe arithmetic
        if val.tzinfo is not None:
            return val.astimezone(timezone.utc).replace(tzinfo=None)
        return val
    if isinstance(val, date):
        return datetime(val.year, val.month, val.day)
    if isinstance(val, str):
        val_str = val.strip()
        if not val_str:
            return None
        try:
            # Handle ISO format strings
            dt = datetime.fromisoformat(val_str.replace("Z", "+00:00"))
            if dt.tzinfo is not None:
                return dt.astimezone(timezone.utc).replace(tzinfo=None)
            return dt
        except ValueError:
            return None
    return None


def calculate_churn_risk(
    total_orders: Optional[Union[int, float]] = 0,
    total_spent: Optional[Union[int, float]] = 0.0,
    last_order_date: Optional[Union[datetime, date, str]] = None,
    created_at: Optional[Union[datetime, date, str]] = None,
    now: Optional[Union[datetime, date, str]] = None,
) -> float:
    """
    Computes a deterministic, bounded heuristic churn-risk score in [0.0, 1.0].

    Parameters:
        total_orders: Total completed orders by the customer (>= 0).
        total_spent: Cumulative monetary spend (>= 0.0).
        last_order_date: Datetime of the most recent completed order.
        created_at: Datetime when customer registered/was created.
        now: Reference evaluation datetime (defaults to datetime.utcnow()).

    Returns:
        float: Bounded churn-risk score in [0.0, 1.0], rounded to 4 decimal places.
    """
    breakdown = calculate_churn_risk_breakdown(
        total_orders=total_orders,
        total_spent=total_spent,
        last_order_date=last_order_date,
        created_at=created_at,
        now=now,
    )
    return breakdown["score"]


def calculate_churn_risk_breakdown(
    total_orders: Optional[Union[int, float]] = 0,
    total_spent: Optional[Union[int, float]] = 0.0,
    last_order_date: Optional[Union[datetime, date, str]] = None,
    created_at: Optional[Union[datetime, date, str]] = None,
    now: Optional[Union[datetime, date, str]] = None,
) -> Dict[str, Any]:
    """
    Calculates the churn-risk score and returns an interpretable breakdown
    of all component factors.
    """
    ref_now = _parse_datetime(now) or datetime.now(timezone.utc).replace(tzinfo=None)

    # 1. Clean and validate total_orders
    try:
        clean_orders = float(total_orders or 0)
        if math.isnan(clean_orders) or math.isinf(clean_orders) or clean_orders < 0:
            clean_orders = 0.0
    except (TypeError, ValueError):
        clean_orders = 0.0

    # 2. Clean and validate total_spent
    try:
        clean_spent = float(total_spent or 0.0)
        if math.isnan(clean_spent) or math.isinf(clean_spent) or clean_spent < 0:
            clean_spent = 0.0
    except (TypeError, ValueError):
        clean_spent = 0.0

    # 3. Clean and evaluate dates
    clean_last_order = _parse_datetime(last_order_date)
    clean_created_at = _parse_datetime(created_at)

    # 4. Calculate Recency Risk (R)
    days_since_last_order: Optional[int] = None
    account_tenure_days: Optional[int] = None

    if clean_created_at is not None:
        delta_created = (ref_now - clean_created_at).total_seconds() / 86400.0
        account_tenure_days = max(0, int(delta_created))

    if clean_last_order is not None:
        delta_seconds = (ref_now - clean_last_order).total_seconds()
        # Clamp future dates (due to server clock skew) to 0 days
        days = max(0.0, delta_seconds / 86400.0)
        days_since_last_order = int(days)
        recency_risk = min(days / RECENCY_MAX_DAYS, 1.0)
    elif clean_orders > 0:
        # Orders exist but date is missing: default to max recency risk
        recency_risk = 1.0
    else:
        # Zero orders (new or dormant registration)
        if account_tenure_days is not None:
            # If account is <= 30 days old, scale recency risk by tenure so new sign-ups
            # are not penalized as dormant churners immediately
            recency_risk = min(account_tenure_days / RECENCY_MAX_DAYS, 1.0)
        else:
            # Completely missing dates and zero orders: baseline unengaged prospect
            recency_risk = 1.0

    # 5. Calculate Frequency Risk (F)
    frequency_risk = 1.0 / (1.0 + clean_orders)

    # 6. Calculate Monetary Risk (M)
    monetary_risk = 1.0 / (1.0 + (clean_spent / MONETARY_SCALE))

    # 7. Compute Composite Score
    raw_score = (
        (RECENCY_WEIGHT * recency_risk)
        + (FREQUENCY_WEIGHT * frequency_risk)
        + (MONETARY_WEIGHT * monetary_risk)
    )

    # Strictly clamp to [0.0, 1.0]
    final_score = round(max(0.0, min(1.0, raw_score)), 4)

    # Risk category classification
    if final_score > HIGH_RISK_THRESHOLD:
        risk_tier = "high"
    elif final_score >= 0.40:
        risk_tier = "moderate"
    else:
        risk_tier = "low"

    return {
        "score": final_score,
        "risk_tier": risk_tier,
        "is_at_risk": final_score > HIGH_RISK_THRESHOLD,
        "components": {
            "recency_risk": round(recency_risk, 4),
            "frequency_risk": round(frequency_risk, 4),
            "monetary_risk": round(monetary_risk, 4),
        },
        "features": {
            "total_orders": int(clean_orders),
            "total_spent": clean_spent,
            "days_since_last_order": days_since_last_order,
            "account_tenure_days": account_tenure_days,
        },
        "weights": {
            "recency": RECENCY_WEIGHT,
            "frequency": FREQUENCY_WEIGHT,
            "monetary": MONETARY_WEIGHT,
        },
        "notes": (
            "Provisional heuristic risk indicator with uncalibrated prototype parameters "
            "(90-day horizon, 50/30/20 weights, ₹1,000 scale). Not an empirical probability "
            "or validated prediction of customer churn."
        ),
    }
