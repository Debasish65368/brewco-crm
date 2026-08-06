from fastapi import APIRouter, Depends

from core.auth import verify_clerk_token
from core.database import get_connection, release_connection

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/stats")
async def dashboard_stats(
    user=Depends(verify_clerk_token)
):
    conn = await get_connection()
    try:
        total_customers = await conn.fetchval("SELECT COUNT(*) FROM customers")
        total_orders = await conn.fetchval("SELECT COUNT(*) FROM orders")
        total_revenue = await conn.fetchval("SELECT COALESCE(SUM(amount),0) FROM orders")
        total_campaigns = await conn.fetchval("SELECT COUNT(*) FROM campaigns")
        delivered = await conn.fetchval("SELECT COUNT(*) FROM communications WHERE delivered_at IS NOT NULL")
        opened = await conn.fetchval("SELECT COUNT(*) FROM communications WHERE opened_at IS NOT NULL")
        clicked = await conn.fetchval("SELECT COUNT(*) FROM communications WHERE clicked_at IS NOT NULL")
        sent = await conn.fetchval("SELECT COUNT(*) FROM communications")

        delivery_rate = round((delivered / sent) * 100, 2) if sent > 0 else 0
        open_rate = round((opened / delivered) * 100, 2) if delivered > 0 else 0
        click_rate = round((clicked / opened) * 100, 2) if opened > 0 else 0

        recent_campaigns = await conn.fetch(
            "SELECT id, name, channel, status, created_at FROM campaigns ORDER BY created_at DESC LIMIT 5"
        )

        recent_activity = await conn.fetch(
            """
            SELECT * FROM (
                SELECT 'customer-' || id AS unique_id, id, name, created_at, 'customer' AS type 
                FROM customers
                UNION ALL
                SELECT 'segment-' || id AS unique_id, id, name, created_at, 'segment' AS type 
                FROM segments
                UNION ALL
                SELECT 'campaign-' || id AS unique_id, id, name, created_at, 'campaign' AS type 
                FROM campaigns
            ) sub
            ORDER BY created_at DESC
            LIMIT 8
            """
        )

        return {
            "total_customers": total_customers,
            "total_orders": total_orders,
            "total_revenue": float(total_revenue),
            "total_campaigns": total_campaigns,
            "sent": sent,
            "delivered": delivered,
            "opened": opened,
            "clicked": clicked,
            "delivery_rate": delivery_rate,
            "open_rate": open_rate,
            "click_rate": click_rate,
            "recent_campaigns": [dict(row) for row in recent_campaigns],
            "recent_activity": [dict(row) for row in recent_activity]
        }
    finally:
        await release_connection(conn)


@router.get("/revenue-trend")
async def dashboard_revenue_trend(
    user=Depends(verify_clerk_token)
):
    conn = await get_connection()
    try:
        rows = await conn.fetch(
            """
            SELECT days.day::date AS date, COALESCE(SUM(o.amount), 0) AS revenue
            FROM generate_series(
                CURRENT_DATE - INTERVAL '29 days',
                CURRENT_DATE,
                INTERVAL '1 day'
            ) AS days(day)
            LEFT JOIN orders o ON DATE(o.created_at) = days.day::date
            GROUP BY days.day
            ORDER BY days.day
            """
        )

        return [
            {
                "date": row["date"].isoformat(),
                "revenue": float(row["revenue"])
            }
            for row in rows
        ]
    finally:
        await release_connection(conn)
