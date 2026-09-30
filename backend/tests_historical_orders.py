import asyncio
import os
import asyncpg
from datetime import datetime
from dotenv import load_dotenv

async def test_historical_orders():
    load_dotenv('backend/.env')
    db_url = os.getenv('DATABASE_URL')
    
    # initialize pool
    import core.database as db
    db.db_pool = await asyncpg.create_pool(db_url)
    
    conn = await asyncpg.connect(db_url)
    
    customer_id = await conn.fetchval('''
        INSERT INTO customers (name, email, phone, city, total_orders, total_spent, last_order_date)
        VALUES ('Test Customer', 'test@historical.com', '555-0000', 'TestCity', 0, 0, NULL)
        RETURNING id
    ''')
    
    try:
        from routers.orders import bulk_insert_orders
        from schemas import OrderBulkRequest, OrderCreate
        
        async def check_date():
            row = await conn.fetchrow('SELECT last_order_date FROM customers WHERE id = $1', customer_id)
            return row['last_order_date']

        async def send_order(created_at, items=None):
            req = OrderBulkRequest(orders=[
                OrderCreate(customer_id=customer_id, amount=10, items=[], created_at=created_at)
            ])
            res = await bulk_insert_orders(req, user="mock")
            if not res.get("success"):
                raise Exception("API Failed")

        print("Running historical order tests...")

        # Case D: first order from NULL
        dt1 = datetime(2025, 2, 10, 12, 0, 0)
        await send_order(dt1)
        res = await check_date()
        print(f"[PASS] Case D (first order from NULL) | Expected: {dt1}, Got: {res}")
        if res.date() != dt1.date(): raise Exception("Mismatch Case D")

        # Case A / E: historical order imported today
        dt2 = datetime(2025, 3, 1, 12, 0, 0)
        await send_order(dt2)
        res = await check_date()
        print(f"[PASS] Case A/E (historical order today) | Expected: {dt2}, Got: {res}")
        if res.date() != dt2.date(): raise Exception("Mismatch Case A/E")
        
        # Case C: older order doesn't move date backwards
        dt3 = datetime(2025, 1, 15, 12, 0, 0)
        await send_order(dt3)
        res = await check_date()
        print(f"[PASS] Case C (older order no backwards move) | Expected: {dt2}, Got: {res}")
        if res.date() != dt2.date(): raise Exception("Mismatch Case C")
        
        # Case B: multiple historical orders in random order
        req = OrderBulkRequest(orders=[
            OrderCreate(customer_id=customer_id, amount=10, items=[], created_at=datetime(2024, 1, 1, 12, 0, 0)),
            OrderCreate(customer_id=customer_id, amount=10, items=[], created_at=datetime(2025, 5, 20, 12, 0, 0)),
            OrderCreate(customer_id=customer_id, amount=10, items=[], created_at=datetime(2025, 4, 15, 12, 0, 0))
        ])
        await bulk_insert_orders(req, user="mock")
        res = await check_date()
        expected_multi = datetime(2025, 5, 20, 12, 0, 0)
        print(f"[PASS] Case B (multiple orders) | Expected: {expected_multi}, Got: {res}")
        if res.date() != expected_multi.date(): raise Exception("Mismatch Case B")
        
        print("All historical order tests passed.")
        
    finally:
        await conn.execute('DELETE FROM orders WHERE customer_id = $1', customer_id)
        await conn.execute('DELETE FROM customers WHERE id = $1', customer_id)
        await conn.close()
        await db.db_pool.close()

if __name__ == "__main__":
    asyncio.run(test_historical_orders())
