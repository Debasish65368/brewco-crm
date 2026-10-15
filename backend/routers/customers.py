import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from core.auth import verify_clerk_token
from core.database import get_connection, release_connection
from schemas import CustomerBulkRequest
from services.churn_risk import calculate_churn_risk

router = APIRouter(tags=["customers"])
logger = logging.getLogger(__name__)


@router.post("/customers/bulk")
async def bulk_insert_customers(
    payload: CustomerBulkRequest,
    user=Depends(verify_clerk_token)
):
    if not payload.customers:
        return {"success": True, "inserted": 0, "skipped": 0, "attempted": 0}

    conn = await get_connection()
    try:
        inserted = 0
        skipped = 0
        async with conn.transaction():
            for customer in payload.customers:
                new_id = await conn.fetchval(
                    """
                    INSERT INTO customers (name, email, phone, city, total_orders, total_spent, last_order_date)
                    VALUES ($1,$2,$3,$4,$5,$6,$7)
                    ON CONFLICT(email) DO NOTHING
                    RETURNING id
                    """,
                    customer.name, customer.email, customer.phone, customer.city,
                    customer.total_orders, customer.total_spent, customer.last_order_date
                )
                if new_id is not None:
                    inserted += 1
                else:
                    skipped += 1

        return {
            "success": True,
            "inserted": inserted,
            "skipped": skipped,
            "attempted": len(payload.customers),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Bulk customer insert error: {e}")
        raise HTTPException(
            status_code=500,
            detail="Bulk customer import failed due to an unexpected database error."
        )
    finally:
        await release_connection(conn)


@router.get("/customers")
async def get_customers(
    city: Optional[str] = Query(None),
    min_spent: Optional[float] = Query(None),
    max_spent: Optional[float] = Query(None),
    min_orders: Optional[int] = Query(None),
    user=Depends(verify_clerk_token)
):
    conn = await get_connection()
    try:
        query = "SELECT * FROM customers"
        conditions = []
        values = []

        if city:
            conditions.append(f"city = ${len(values)+1}")
            values.append(city)
        if min_spent is not None:
            conditions.append(f"total_spent >= ${len(values)+1}")
            values.append(min_spent)
        if max_spent is not None:
            conditions.append(f"total_spent <= ${len(values)+1}")
            values.append(max_spent)
        if min_orders is not None:
            conditions.append(f"total_orders >= ${len(values)+1}")
            values.append(min_orders)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY created_at DESC"

        rows = await conn.fetch(query, *values)
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        customers = []
        for row in rows:
            c = dict(row)
            # Ensure clients receive current heuristic churn-risk score rather than
            # stale persisted outputs from the retired Logistic Regression model
            c["churn_score"] = calculate_churn_risk(
                total_orders=c.get("total_orders"),
                total_spent=c.get("total_spent"),
                last_order_date=c.get("last_order_date"),
                created_at=c.get("created_at"),
                now=now,
            )
            customers.append(c)
        return customers
    finally:
        await release_connection(conn)
