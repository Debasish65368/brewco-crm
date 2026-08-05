import asyncio
import sys
import os

# Add parent directory to path so we can import core.config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncpg
from core.config import DATABASE_URL

async def run_migration():
    if not DATABASE_URL:
        raise Exception("DATABASE_URL not found")
        
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        print("Connected to database")
        await conn.execute(
            "ALTER TABLE customers ADD COLUMN IF NOT EXISTS churn_score FLOAT DEFAULT 0.0;"
        )
        print("Migration successful: added churn_score column.")
    except Exception as e:
        print(f"Migration failed: {e}")
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(run_migration())
