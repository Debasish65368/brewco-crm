import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from core.auth import verify_clerk_token
from core.database import get_connection, release_connection
from schemas import OrderBulkRequest

router = APIRouter(tags=["orders"])
logger = logging.getLogger(__name__)


@router.post("/orders/bulk")
async def bulk_insert_orders(
    payload: OrderBulkRequest,
    user=Depends(verify_clerk_token)
):
    if not payload.orders:
        return {"success": True, "inserted": 0, "attempted": 0}

    conn = await get_connection()
    try:
        inserted = 0
        async with conn.transaction():
            for order in payload.orders:
                # 1. Verify target customer exists before inserting order
                customer_exists = await conn.fetchval(
                    "SELECT id FROM customers WHERE id = $1", order.customer_id
                )
                if customer_exists is None:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Customer with id {order.customer_id} does not exist."
                    )

                # 2. Insert order
                await conn.execute(
                    """
                    INSERT INTO orders (customer_id, amount, items, created_at)
                    VALUES ($1,$2,$3, COALESCE($4, CURRENT_TIMESTAMP))
                    """,
                    order.customer_id, order.amount, json.dumps(order.items), order.created_at
                )

                # 3. Update customer aggregate metrics within the same transaction
                await conn.execute(
                    """
                    UPDATE customers SET total_orders = total_orders + 1,
                    total_spent = total_spent + $1,
                    last_order_date = GREATEST(last_order_date, COALESCE($3, CURRENT_TIMESTAMP))
                    WHERE id = $2
                    """,
                    order.amount, order.customer_id, order.created_at
                )
                inserted += 1

        return {
            "success": True,
            "inserted": inserted,
            "attempted": len(payload.orders),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Bulk order insert error: {e}")
        raise HTTPException(
            status_code=500,
            detail="Bulk order import failed due to an unexpected database error."
        )
    finally:
        await release_connection(conn)
