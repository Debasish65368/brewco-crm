from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from core.auth import verify_clerk_token
from core.database import get_connection, release_connection
from schemas import CampaignCreate
from services.campaign_processor import process_campaign

router = APIRouter(tags=["campaigns"])


@router.post("/campaigns")
async def create_campaign(
    payload: CampaignCreate,
    background_tasks: BackgroundTasks,
    user=Depends(verify_clerk_token)
):
    conn = await get_connection()
    try:
        segment = await conn.fetchrow("SELECT * FROM segments WHERE id = $1", payload.segment_id)
        if not segment:
            raise HTTPException(status_code=404, detail="Segment not found")

        campaign_id = await conn.fetchval(
            """
            INSERT INTO campaigns (name, segment_id, message, channel, status)
            VALUES ($1,$2,$3,$4,'processing') RETURNING id
            """,
            payload.name, payload.segment_id, payload.message, payload.channel
        )
        background_tasks.add_task(process_campaign, campaign_id, payload.segment_id, payload.channel, payload.message)
        return {"success": True, "campaign_id": campaign_id, "status": "processing"}
    finally:
        await release_connection(conn)


@router.get("/campaigns")
async def get_campaigns(
    user=Depends(verify_clerk_token)
):
    conn = await get_connection()
    try:
        rows = await conn.fetch(
            """
            SELECT c.id, c.name, c.segment_id, c.message, c.channel, c.status, c.created_at, s.name AS segment_name
            FROM campaigns c JOIN segments s ON c.segment_id = s.id
            ORDER BY c.created_at DESC
            """
        )
        return [dict(row) for row in rows]
    finally:
        await release_connection(conn)


@router.delete("/campaigns/{campaign_id}")
async def delete_campaign(
    campaign_id: int,
    user=Depends(verify_clerk_token)
):
    conn = await get_connection()
    try:
        campaign = await conn.fetchrow("SELECT id FROM campaigns WHERE id = $1", campaign_id)
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")

        async with conn.transaction():
            await conn.execute("DELETE FROM communications WHERE campaign_id = $1", campaign_id)
            await conn.execute("DELETE FROM campaigns WHERE id = $1", campaign_id)

        return {"success": True, "campaign_id": campaign_id}
    finally:
        await release_connection(conn)


@router.get("/campaigns/{campaign_id}/stats")
async def campaign_stats(
    campaign_id: int,
    user=Depends(verify_clerk_token)
):
    conn = await get_connection()
    try:
        campaign = await conn.fetchrow("SELECT * FROM campaigns WHERE id = $1", campaign_id)
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")

        sent_count = await conn.fetchval("SELECT COUNT(*) FROM communications WHERE campaign_id = $1", campaign_id)
        delivered_count = await conn.fetchval("SELECT COUNT(*) FROM communications WHERE campaign_id = $1 AND delivered_at IS NOT NULL", campaign_id)
        opened_count = await conn.fetchval("SELECT COUNT(*) FROM communications WHERE campaign_id = $1 AND opened_at IS NOT NULL", campaign_id)
        clicked_count = await conn.fetchval("SELECT COUNT(*) FROM communications WHERE campaign_id = $1 AND clicked_at IS NOT NULL", campaign_id)
        failed_count = await conn.fetchval("SELECT COUNT(*) FROM communications WHERE campaign_id = $1 AND status = 'failed'", campaign_id)

        return {
            "campaign_id": campaign_id,
            "sent": sent_count,
            "delivered": delivered_count,
            "opened": opened_count,
            "clicked": clicked_count,
            "failed": failed_count
        }
    finally:
        await release_connection(conn)
