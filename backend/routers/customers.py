from typing import Optional

from fastapi import APIRouter, Depends, Query

from core.auth import verify_clerk_token
from core.database import get_connection, release_connection
from schemas import CustomerBulkRequest

router = APIRouter(tags=["customers"])


@router.post("/customers/bulk")
async def bulk_insert_customers(
    payload: CustomerBulkRequest,
    user=Depends(verify_clerk_token)
):
    conn = await get_connection()
    try:
        inserted = 0
        for customer in payload.customers:
            await conn.execute(
                """
                INSERT INTO customers (name, email, phone, city, total_orders, total_spent, last_order_date)
                VALUES ($1,$2,$3,$4,$5,$6,$7)
                ON CONFLICT(email) DO NOTHING
                """,
                customer.name, customer.email, customer.phone, customer.city,
                customer.total_orders, customer.total_spent, customer.last_order_date
            )
            inserted += 1
        return {"success": True, "inserted": inserted}
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
        return [dict(row) for row in rows]
    finally:
        await release_connection(conn)
