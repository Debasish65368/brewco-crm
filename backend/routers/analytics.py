import json
import logging
import asyncpg
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException

from core.auth import verify_clerk_token
from core.database import get_connection, release_connection
from clients.ai_client import generate_analytics_sql, generate_sql_summary
from services.sql_guard import validate_sql

router = APIRouter(prefix="/analytics", tags=["analytics"])
logger = logging.getLogger(__name__)

class AnalyticsQueryRequest(BaseModel):
    question: str

@router.post("/query")
async def query_analytics(
    payload: AnalyticsQueryRequest,
    user=Depends(verify_clerk_token)
):
    try:
        sql = await generate_analytics_sql(payload.question)
    except Exception as e:
        logger.error(f"Error generating SQL: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate SQL from AI.")

    is_valid, reason = validate_sql(sql)
    if not is_valid:
        raise HTTPException(status_code=400, detail=f"Generated SQL is invalid or unsafe: {reason}")
        
    if "LIMIT " not in sql.upper():
        sql += " LIMIT 100"

    conn = None
    try:
        conn = await get_connection()
        records = await conn.fetch(sql)
        # convert dates to isoformat string or let fastapi handle it? fastapi handles datetime serialization.
        results = [dict(record) for record in records]
    except asyncpg.PostgresError as e:
        logger.error(f"Postgres execution error: {e}")
        raise HTTPException(status_code=400, detail=f"Database execution error: {e}")
    except Exception as e:
        logger.error(f"Database error: {e}")
        raise HTTPException(status_code=500, detail="An error occurred while executing the query.")
    finally:
        if conn:
            await release_connection(conn)

    summary = None
    if results:
        try:
            summary = await generate_sql_summary(payload.question, results)
        except Exception as e:
            logger.warning(f"Error generating summary: {e}")
            summary = "Summary generation failed."
    else:
        summary = "No results found."

    return {
        "sql": sql,
        "results": results,
        "summary": summary
    }
