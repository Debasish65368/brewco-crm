import json

from fastapi import APIRouter, Depends

from core.auth import verify_clerk_token
from core.database import get_connection, release_connection
from schemas import OrderBulkRequest

router = APIRouter(tags=["orders"])


@router.post("/orders/bulk")
async def bulk_insert_orders(
    payload: OrderBulkRequest,
    user=Depends(verify_clerk_token)
):
    conn = await get_connection()
    try:
        inserted = 0
        for order in payload.orders:
            await conn.execute(
                """
                INSERT INTO orders (customer_id, amount, items, created_at)
                VALUES ($1,$2,$3, COALESCE($4, CURRENT_TIMESTAMP))
                """,
                order.customer_id, order.amount, json.dumps(order.items), order.created_at
            )
            await conn.execute(
                """
                UPDATE customers SET total_orders = total_orders + 1,
                total_spent = total_spent + $1, last_order_date = CURRENT_TIMESTAMP
                WHERE id = $2
                """,
                order.amount, order.customer_id
            )
            inserted += 1
        return {"success": True, "inserted": inserted}
    finally:
        await release_connection(conn)
