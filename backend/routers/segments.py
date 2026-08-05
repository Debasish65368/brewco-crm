import json

from fastapi import APIRouter, Depends, HTTPException

from core.auth import verify_clerk_token
from core.database import get_connection, release_connection
from schemas import SegmentCreate
from services.segment_filters import build_segment_sql

router = APIRouter(tags=["segments"])

def assign_cluster_labels(clusters):
    if not clusters:
        return clusters
        
    unassigned = list(clusters)
    
    if unassigned:
        loyal = max(unassigned, key=lambda c: float(c['avg_orders']) * float(c['avg_spent']))
        loyal['label'] = "Loyal High-Value"
        unassigned.remove(loyal)
        
    if unassigned:
        at_risk = max(unassigned, key=lambda c: float(c['avg_recency']))
        at_risk['label'] = "At Risk"
        unassigned.remove(at_risk)
        
    if unassigned:
        new_occ = min(unassigned, key=lambda c: float(c['avg_orders']))
        new_occ['label'] = "New/Occasional"
        unassigned.remove(new_occ)
        
    if unassigned:
        big_spender = max(unassigned, key=lambda c: float(c['avg_spent']))
        big_spender['label'] = "High Spenders"
        unassigned.remove(big_spender)
        
    for i, c in enumerate(unassigned):
        c['label'] = f"Standard Group {i+1}" if len(unassigned) > 1 else "Standard Group"
        
    return clusters



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


@router.get("/segments/discovered")
async def get_discovered_segments(user=Depends(verify_clerk_token)):
    conn = await get_connection()
    try:
        rows = await conn.fetch('''
            SELECT 
                cluster_id as id,
                COUNT(*) as customer_count,
                AVG(total_orders) as avg_orders,
                AVG(total_spent) as avg_spent,
                AVG(COALESCE(EXTRACT(DAY FROM (CURRENT_TIMESTAMP - last_order_date)), 999)) as avg_recency
            FROM customers 
            WHERE cluster_id IS NOT NULL 
            GROUP BY cluster_id
        ''')
        clusters = [dict(row) for row in rows]
        clusters = assign_cluster_labels(clusters)
        
        for c in clusters:
            c['avg_orders'] = round(float(c['avg_orders']), 1)
            c['avg_spent'] = round(float(c['avg_spent']), 2)
            c['avg_recency'] = round(float(c['avg_recency']), 1)
            
        return clusters
    finally:
        await release_connection(conn)


@router.post("/segments/discovered/{cluster_id}/convert")
async def convert_cluster_to_segment(
    cluster_id: int,
    payload: SegmentCreate,
    user=Depends(verify_clerk_token)
):
    """
    Note: cluster_id is not a stable identity across retrains.
    If train_rfm_clusters.py is rerun in the future, cluster numbering can shift 
    and a previously-converted segment's filter_json (cluster_id) may end up 
    matching a different group of customers than originally intended. 
    This is a known limitation.
    """
    conn = await get_connection()
    try:
        filter_json = {"cluster_id": cluster_id}
        
        where_clause, values = build_segment_sql(filter_json)
        count_query = f"SELECT COUNT(*) FROM customers WHERE {where_clause}"
        customer_count = await conn.fetchval(count_query, *values)

        segment_id = await conn.fetchval(
            """
            INSERT INTO segments (name, description, filter_json, customer_count)
            VALUES ($1,$2,$3,$4) RETURNING id
            """,
            payload.name, payload.description, json.dumps(filter_json), customer_count
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
