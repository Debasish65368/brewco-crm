"""
Update customer churn-risk scores using the transparent heuristic service.

Fix 3 / Path B Implementation:
Instead of loading an unvalidated Logistic Regression model trained on
pseudo-labels, this script computes defensible behavioral churn-risk scores
via `services.churn_risk.calculate_churn_risk`.

Usage (Administrative batch task):
    python scripts/update_churn_scores.py
"""

import asyncio
import os
import sys
from datetime import datetime

# Add parent directory to path so we can import backend packages
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncpg
from core.config import DATABASE_URL
from services.churn_risk import calculate_churn_risk


async def update_scores(db_url: str = None):
    url = db_url or DATABASE_URL
    if not url:
        raise RuntimeError("DATABASE_URL not found or not configured.")

    conn = await asyncpg.connect(url)
    try:
        print("Connected to database. Fetching customers...")
        rows = await conn.fetch(
            """
            SELECT id, total_orders, total_spent, last_order_date, created_at
            FROM customers
            """
        )

        if not rows:
            print("No customers found.")
            return

        now = datetime.utcnow()
        updates = []

        for row in rows:
            customer_id = row["id"]
            score = calculate_churn_risk(
                total_orders=row["total_orders"],
                total_spent=row["total_spent"],
                last_order_date=row["last_order_date"],
                created_at=row["created_at"],
                now=now,
            )
            updates.append((score, customer_id))

        print(f"Updating heuristic churn scores for {len(updates)} customers...")

        await conn.executemany(
            """
            UPDATE customers
            SET churn_score = $1
            WHERE id = $2
            """,
            updates,
        )

        print("Heuristic churn-risk scores updated successfully!")

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(update_scores())
