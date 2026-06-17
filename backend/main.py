import os
import json
import asyncio
from datetime import datetime
from typing import List, Optional, Dict, Any

import asyncpg
import httpx

from dotenv import load_dotenv

from fastapi import (
    FastAPI,
    HTTPException,
    BackgroundTasks,
    Query
)

from fastapi.middleware.cors import CORSMiddleware

from pydantic import BaseModel, EmailStr

from groq import Groq

# =====================================================
# ENVIRONMENT
# =====================================================

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

CHANNEL_SERVICE_URL = os.getenv(
    "CHANNEL_SERVICE_URL",
    "http://localhost:8001/send"
)

CRM_RECEIPT_URL = os.getenv(
    "CRM_RECEIPT_URL",
    "http://localhost:8000/receipt"
)

if not DATABASE_URL:
    raise Exception("DATABASE_URL missing in .env")

if not os.getenv("GROQ_API_KEY"):
    raise Exception("GROQ_API_KEY missing in .env")


# =====================================================
# GEMINI CONFIG
# =====================================================

groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))


# =====================================================
# FASTAPI APP
# =====================================================

app = FastAPI(
    title="BrewCo CRM",
    version="1.0.0"
)


# =====================================================
# CORS
# =====================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =====================================================
# DATABASE POOL
# =====================================================

db_pool: Optional[asyncpg.Pool] = None


@app.on_event("startup")
async def startup():
    global db_pool
    db_pool = await asyncpg.create_pool(
        DATABASE_URL,
        min_size=1,
        max_size=10
    )
    print("Connected to PostgreSQL")


@app.on_event("shutdown")
async def shutdown():
    global db_pool
    if db_pool:
        await db_pool.close()
    print("Database pool closed")


# =====================================================
# DATABASE HELPER
# =====================================================

async def get_connection():
    if not db_pool:
        raise HTTPException(
            status_code=500,
            detail="Database not initialized"
        )
    return await db_pool.acquire()


# =====================================================
# CUSTOMER SCHEMAS
# =====================================================

class CustomerCreate(BaseModel):
    name: str
    email: EmailStr
    phone: str
    city: str
    total_orders: int = 0
    total_spent: float = 0
    last_order_date: Optional[datetime] = None


class CustomerBulkRequest(BaseModel):
    customers: List[CustomerCreate]


# =====================================================
# ORDER SCHEMAS
# =====================================================

class OrderCreate(BaseModel):
    customer_id: int
    amount: float
    items: List[Dict[str, Any]]
    created_at: Optional[datetime] = None


class OrderBulkRequest(BaseModel):
    orders: List[OrderCreate]


# =====================================================
# SEGMENT SCHEMAS
# =====================================================

class SegmentCreate(BaseModel):
    name: str
    description: Optional[str] = ""
    filter_json: Dict[str, Any]


class SegmentResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    filter_json: Dict[str, Any]
    customer_count: int
    created_at: datetime


# =====================================================
# CAMPAIGN SCHEMAS
# =====================================================

class CampaignCreate(BaseModel):
    name: str
    segment_id: int
    message: str
    channel: str


class CampaignResponse(BaseModel):
    id: int
    name: str
    segment_id: int
    message: str
    channel: str
    status: str
    created_at: datetime


# =====================================================
# COMMUNICATION SCHEMAS
# =====================================================

class CommunicationReceipt(BaseModel):
    campaign_id: int
    customer_id: int
    status: str


# =====================================================
# DASHBOARD SCHEMAS
# =====================================================

class DashboardStats(BaseModel):
    total_customers: int
    total_orders: int
    total_revenue: float
    total_campaigns: int
    delivered: int
    opened: int
    clicked: int


# =====================================================
# AI SCHEMAS
# =====================================================

class SegmentSuggestionRequest(BaseModel):
    prompt: str


class DraftMessageRequest(BaseModel):
    goal: str


class AISegmentResponse(BaseModel):
    filter_json: Dict[str, Any]


class AIDraftResponse(BaseModel):
    message: str


# =====================================================
# CUSTOMER FILTER SCHEMA
# =====================================================

class CustomerFilterQuery(BaseModel):
    city: Optional[str] = None
    min_spent: Optional[float] = None
    max_spent: Optional[float] = None
    min_orders: Optional[int] = None


# =====================================================
# SEGMENT FILTER HELPER
# =====================================================

def build_segment_sql(filter_json: Dict[str, Any]):
    clauses = []
    values = []

    if "city" in filter_json:
        clauses.append(f"city = ${len(values)+1}")
        values.append(filter_json["city"])

    if "min_spent" in filter_json:
        clauses.append(f"total_spent >= ${len(values)+1}")
        values.append(filter_json["min_spent"])

    if "max_spent" in filter_json:
        clauses.append(f"total_spent <= ${len(values)+1}")
        values.append(filter_json["max_spent"])

    if "min_orders" in filter_json:
        clauses.append(f"total_orders >= ${len(values)+1}")
        values.append(filter_json["min_orders"])

    if "last_order_before" in filter_json:
        clauses.append(f"last_order_date <= ${len(values)+1}")
        values.append(filter_json["last_order_before"])

    where_clause = " AND ".join(clauses)
    if not where_clause:
        where_clause = "TRUE"

    return where_clause, values


# =====================================================
# CHANNEL SERVICE HELPER
# =====================================================

async def send_to_channel_service(
    campaign_id: int,
    customer_id: int,
    channel: str,
    message: str
):
    payload = {
        "campaign_id": campaign_id,
        "customer_id": customer_id,
        "channel": channel,
        "message": message,
        "receipt_url": CRM_RECEIPT_URL
    }

    async with httpx.AsyncClient() as client:
        try:
            await client.post(
                CHANNEL_SERVICE_URL,
                json=payload,
                timeout=30
            )
        except Exception as e:
            print(f"Channel Service Error: {str(e)}")


# =====================================================
# GEMINI HELPERS
# =====================================================

async def generate_segment_filter(prompt: str):
    full_prompt = f"""
You are a CRM segmentation engine.

Convert this description into JSON.

Description:
{prompt}

Return ONLY valid JSON. No markdown. No explanation.

Example:
{{"min_spent": 500, "city": "Delhi"}}

Supported fields: min_spent, max_spent, min_orders, city, last_order_before
"""
    response = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": full_prompt}]
    )
    text = response.choices[0].message.content.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    text = text.strip()
    return json.loads(text)


async def generate_campaign_message(goal: str):
    prompt = f"""
You are a marketing expert for BrewCo coffee shop.

Create a short campaign message.

Campaign Goal:
{goal}

Requirements:
- Friendly and warm
- Coffee shop tone
- Under 200 characters
- Include a call to action
"""
    response = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content.strip()


# =====================================================
# POST /customers/bulk
# =====================================================

@app.post("/customers/bulk")
async def bulk_insert_customers(payload: CustomerBulkRequest):
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
        await db_pool.release(conn)


# =====================================================
# GET /customers
# =====================================================

@app.get("/customers")
async def get_customers(
    city: Optional[str] = Query(None),
    min_spent: Optional[float] = Query(None),
    max_spent: Optional[float] = Query(None),
    min_orders: Optional[int] = Query(None)
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
        await db_pool.release(conn)


# =====================================================
# POST /orders/bulk
# =====================================================

@app.post("/orders/bulk")
async def bulk_insert_orders(payload: OrderBulkRequest):
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
        await db_pool.release(conn)


# =====================================================
# POST /segments
# =====================================================

@app.post("/segments")
async def create_segment(payload: SegmentCreate):
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
        await db_pool.release(conn)


# =====================================================
# GET /segments
# =====================================================

@app.get("/segments")
async def get_segments():
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
        await db_pool.release(conn)


# =====================================================
# DELETE /segments/{id}
# =====================================================

@app.delete("/segments/{segment_id}")
async def delete_segment(segment_id: int):
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
        await db_pool.release(conn)


# =====================================================
# HELPER: GET CUSTOMERS INSIDE A SEGMENT
# =====================================================

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
        await db_pool.release(conn)


# =====================================================
# BACKGROUND CAMPAIGN SENDER
# =====================================================

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
        await db_pool.release(conn)


# =====================================================
# POST /campaigns
# =====================================================

@app.post("/campaigns")
async def create_campaign(payload: CampaignCreate, background_tasks: BackgroundTasks):
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
        await db_pool.release(conn)


# =====================================================
# GET /campaigns
# =====================================================

@app.get("/campaigns")
async def get_campaigns():
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
        await db_pool.release(conn)


# =====================================================
# DELETE /campaigns/{id}
# =====================================================

@app.delete("/campaigns/{campaign_id}")
async def delete_campaign(campaign_id: int):
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
        await db_pool.release(conn)


# =====================================================
# GET /campaigns/{id}/stats
# =====================================================

@app.get("/campaigns/{campaign_id}/stats")
async def campaign_stats(campaign_id: int):
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
        await db_pool.release(conn)


# =====================================================
# POST /receipt
# =====================================================

@app.post("/receipt")
async def receive_receipt(payload: CommunicationReceipt):
    conn = await get_connection()
    try:
        status = payload.status.lower()
        if status == "delivered":
            await conn.execute(
                "UPDATE communications SET status = 'delivered', delivered_at = CURRENT_TIMESTAMP WHERE campaign_id = $1 AND customer_id = $2",
                payload.campaign_id, payload.customer_id
            )
        elif status == "failed":
            await conn.execute(
                "UPDATE communications SET status = 'failed' WHERE campaign_id = $1 AND customer_id = $2",
                payload.campaign_id, payload.customer_id
            )
        elif status == "opened":
            await conn.execute(
                "UPDATE communications SET status = 'opened', opened_at = CURRENT_TIMESTAMP WHERE campaign_id = $1 AND customer_id = $2",
                payload.campaign_id, payload.customer_id
            )
        elif status == "clicked":
            await conn.execute(
                "UPDATE communications SET status = 'clicked', clicked_at = CURRENT_TIMESTAMP WHERE campaign_id = $1 AND customer_id = $2",
                payload.campaign_id, payload.customer_id
            )
        else:
            raise HTTPException(status_code=400, detail="Invalid status")

        return {"success": True, "campaign_id": payload.campaign_id, "customer_id": payload.customer_id, "status": status}
    finally:
        await db_pool.release(conn)


# =====================================================
# GET /dashboard/stats
# =====================================================

@app.get("/dashboard/stats")
async def dashboard_stats():
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
            "recent_campaigns": [dict(row) for row in recent_campaigns]
        }
    finally:
        await db_pool.release(conn)

# =====================================================
# GET /dashboard/revenue-trend
# =====================================================

@app.get("/dashboard/revenue-trend")
async def dashboard_revenue_trend():
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
        await db_pool.release(conn)

# =====================================================
# POST /ai/suggest-segment
# =====================================================

@app.post("/ai/suggest-segment")
async def ai_suggest_segment(payload: SegmentSuggestionRequest):
    try:
        filter_json = await generate_segment_filter(payload.prompt)
        return {"filter_json": filter_json}
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Gemini returned invalid JSON")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =====================================================
# POST /ai/draft-message
# =====================================================

@app.post("/ai/draft-message")
async def ai_draft_message(payload: DraftMessageRequest):
    try:
        message = await generate_campaign_message(payload.goal)
        return {"message": message}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =====================================================
# HEALTH CHECK
# =====================================================

@app.get("/")
async def root():
    return {"service": "BrewCo CRM", "status": "running", "version": "1.0.0"}


@app.get("/health")
async def health():
    return {"status": "healthy"}
