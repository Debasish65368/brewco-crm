import asyncio
import json

from fastapi import HTTPException

from core.database import get_connection, release_connection
from services.segment_filters import build_segment_sql
from clients.channel_client import send_to_channel_service


async def get_segment_customers(segment_id: int):
    conn = await get_connection()
    try:
        segment = await conn.fetchrow("SELECT * FROM segments WHERE id = $1", segment_id)
        if not segment:
            raise HTTPException(status_code=404, detail="Segment not found")

        filter_json = segment["filter_json"]
        if isinstance(filter_json, str):
            filter_json = json.loads(filter_json)

        where_clause, values = build_segment_sql(filter_json)
        query = f"SELECT * FROM customers WHERE {where_clause}"
        rows = await conn.fetch(query, *values)
        return [dict(row) for row in rows]
    finally:
        await release_connection(conn)


async def process_campaign(campaign_id: int, segment_id: int, channel: str, message: str):
    conn = await get_connection()
    try:
        customers = await get_segment_customers(segment_id)
        for customer in customers:
            await conn.fetchval(
                """
                INSERT INTO communications (campaign_id, customer_id, status, sent_at)
                VALUES ($1, $2, 'sent', CURRENT_TIMESTAMP) RETURNING id
                """,
                campaign_id, customer["id"]
            )
            asyncio.create_task(
                send_to_channel_service(
                    campaign_id=campaign_id,
                    customer_id=customer["id"],
                    channel=channel,
                    message=message
                )
            )
        await conn.execute("UPDATE campaigns SET status = 'sent' WHERE id = $1", campaign_id)
    except Exception as e:
        print("Campaign Error:", str(e))
        await conn.execute("UPDATE campaigns SET status = 'failed' WHERE id = $1", campaign_id)
    finally:
        await release_connection(conn)
