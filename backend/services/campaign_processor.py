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


async def _dispatch_single_recipient(
    campaign_id: int,
    customer_id: int,
    comm_id: int,
    channel: str,
    message: str,
    sem: asyncio.Semaphore
) -> bool:
    """
    Dispatches a single message via channel service and updates communication status.
    Uses conditional updates so a delayed dispatch result never overwrites a receipt
    status (e.g. delivered, opened, clicked).
    """
    try:
        ok = await send_to_channel_service(
            campaign_id=campaign_id,
            customer_id=customer_id,
            channel=channel,
            message=message
        )
    except Exception:
        ok = False

    async with sem:
        conn = await get_connection()
        try:
            if ok:
                # Dispatch accepted by channel service. Set sent_at timestamp,
                # and set status to 'sent' unless a downstream receipt has already arrived
                # (delivered, opened, clicked, or failed).
                await conn.execute(
                    """
                    UPDATE communications
                    SET status = CASE
                            WHEN status IN ('delivered', 'opened', 'clicked', 'failed') THEN status
                            ELSE 'sent'
                        END,
                        sent_at = COALESCE(sent_at, CURRENT_TIMESTAMP)
                    WHERE id = $1
                    """,
                    comm_id
                )
            else:
                # Dispatch failed or rejected. Record failure.
                # Never overwrite an already-confirmed delivery receipt.
                await conn.execute(
                    """
                    UPDATE communications
                    SET status = 'failed'
                    WHERE id = $1
                      AND status NOT IN ('delivered', 'opened', 'clicked')
                    """,
                    comm_id
                )
            return ok
        finally:
            await release_connection(conn)


async def process_campaign(campaign_id: int, segment_id: int, channel: str, message: str):
    """
    Process campaign dispatch for all segment customers.

    Evaluates dispatch outcomes per recipient and updates campaign status:
    - 'sent': all recipient dispatches accepted
    - 'partially_failed': some dispatches accepted, some failed
    - 'failed': all dispatches failed or empty recipient list
    """
    conn = await get_connection()
    try:
        customers = await get_segment_customers(segment_id)

        # Empty recipient list: do not report successful delivery
        if not customers:
            await conn.execute("UPDATE campaigns SET status = 'failed' WHERE id = $1", campaign_id)
            return

        # Insert initial communication records in 'processing' state
        comm_entries = []
        for customer in customers:
            comm_id = await conn.fetchval(
                """
                INSERT INTO communications (campaign_id, customer_id, status)
                VALUES ($1, $2, 'processing') RETURNING id
                """,
                campaign_id, customer["id"]
            )
            comm_entries.append((customer["id"], comm_id))

        sem = asyncio.Semaphore(5)
        dispatch_tasks = [
            asyncio.create_task(
                _dispatch_single_recipient(
                    campaign_id=campaign_id,
                    customer_id=cust_id,
                    comm_id=c_id,
                    channel=channel,
                    message=message,
                    sem=sem
                )
            )
            for cust_id, c_id in comm_entries
        ]

        results = await asyncio.gather(*dispatch_tasks, return_exceptions=True)

        # Evaluate aggregate outcomes
        success_count = sum(1 for r in results if r is True)
        total_count = len(results)

        if success_count == total_count:
            final_status = "sent"
        elif success_count > 0:
            final_status = "partially_failed"
        else:
            final_status = "failed"

        await conn.execute("UPDATE campaigns SET status = $1 WHERE id = $2", final_status, campaign_id)

    except Exception as e:
        print("[CAMPAIGN PROCESSOR ERROR]:", str(e))
        try:
            await conn.execute("UPDATE campaigns SET status = 'failed' WHERE id = $1", campaign_id)
        except Exception:
            pass
    finally:
        await release_connection(conn)
