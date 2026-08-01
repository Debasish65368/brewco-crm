import json

from fastapi import APIRouter, Depends, HTTPException

from core.auth import verify_clerk_token
from core.database import get_connection, release_connection
from schemas import SegmentCreate
from services.segment_filters import build_segment_sql

router = APIRouter(tags=["segments"])


@router.post("/segments")
async def create_segment(
    payload: SegmentCreate,
    user=Depends(verify_clerk_token)
):
    conn = await get_connection()
    try:
        where_clause, values = build_segment_sql(payload.filter_json)
        count_query = f"SELECT COUNT(*) FROM customers WHERE {where_clause}"
        customer_count = await conn.fetchval(count_query, *values)

        segment_id = await conn.fetchval(
            """
            INSERT INTO segments (name, description, filter_json, customer_count)
            VALUES ($1,$2,$3,$4) RETURNING id
            """,
            payload.name, payload.description, json.dumps(payload.filter_json), customer_count
        )
        return {"success": True, "segment_id": segment_id, "customer_count": customer_count}
    finally:
        await release_connection(conn)


@router.get("/segments")
async def get_segments(
    user=Depends(verify_clerk_token)
):
    conn = await get_connection()
    try:
        rows = await conn.fetch("SELECT * FROM segments ORDER BY created_at DESC")
        result = []
        for row in rows:
            item = dict(row)
            if isinstance(item["filter_json"], str):
                item["filter_json"] = json.loads(item["filter_json"])
            result.append(item)
        return result
    finally:
        await release_connection(conn)


@router.delete("/segments/{segment_id}")
async def delete_segment(
    segment_id: int,
    user=Depends(verify_clerk_token)
):
    conn = await get_connection()
    try:
        segment = await conn.fetchrow("SELECT id FROM segments WHERE id = $1", segment_id)
        if not segment:
            raise HTTPException(status_code=404, detail="Segment not found")

        campaign_count = await conn.fetchval("SELECT COUNT(*) FROM campaigns WHERE segment_id = $1", segment_id)
        if campaign_count:
            raise HTTPException(
                status_code=409,
                detail="Segment is used by one or more campaigns and cannot be deleted"
            )

        await conn.execute("DELETE FROM segments WHERE id = $1", segment_id)
        return {"success": True, "segment_id": segment_id}
    finally:
        await release_connection(conn)
