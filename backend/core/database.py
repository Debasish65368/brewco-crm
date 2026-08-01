from contextlib import asynccontextmanager
from typing import Optional

import asyncpg
from fastapi import HTTPException

from core.config import DATABASE_URL

db_pool: Optional[asyncpg.Pool] = None


@asynccontextmanager
async def lifespan(app):
    global db_pool
    db_pool = await asyncpg.create_pool(
        DATABASE_URL,
        min_size=1,
        max_size=10
    )
    print("Connected to PostgreSQL")

    yield

    if db_pool:
        await db_pool.close()
    print("Database pool closed")


async def get_connection():
    if not db_pool:
        raise HTTPException(
            status_code=500,
            detail="Database not initialized"
        )
    return await db_pool.acquire()


async def release_connection(conn):
    await db_pool.release(conn)
