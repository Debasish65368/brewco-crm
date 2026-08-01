import os
import json
import random
import asyncio
from datetime import datetime, timedelta

import asyncpg
from dotenv import load_dotenv
from faker import Faker

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

fake = Faker("en_IN")

INDIAN_CITIES = [
    "Delhi", "Mumbai", "Bangalore", "Hyderabad", "Chennai",
    "Kolkata", "Pune", "Ahmedabad", "Jaipur", "Lucknow",
    "Chandigarh", "Indore", "Surat", "Bhopal", "Patna",
    "Kochi", "Nagpur", "Kanpur", "Noida", "Gurgaon"
]

COFFEE_MENU = [
    {"name": "Espresso", "price": 120},
    {"name": "Americano", "price": 140},
    {"name": "Cappuccino", "price": 180},
    {"name": "Latte", "price": 200},
    {"name": "Mocha", "price": 220},
    {"name": "Cold Brew", "price": 240},
    {"name": "Flat White", "price": 210},
    {"name": "Macchiato", "price": 190},
    {"name": "Iced Latte", "price": 230},
    {"name": "Caramel Latte", "price": 250}
]


async def create_customers(conn):
    customer_ids = []

    for _ in range(100):
        name = fake.name()
        email = (
            name.lower()
            .replace(" ", ".")
            .replace("'", "")
            + str(random.randint(100, 999))
            + "@gmail.com"
        )
        phone = "9" + "".join(str(random.randint(0, 9)) for _ in range(9))
        city = random.choice(INDIAN_CITIES)
        last_order_date = datetime.now() - timedelta(days=random.randint(1, 180))

        customer_id = await conn.fetchval(
            """
            INSERT INTO customers (name, email, phone, city, total_orders, total_spent, last_order_date)
            VALUES ($1, $2, $3, $4, 0, 0, $5)
            RETURNING id
            """,
            name, email, phone, city, last_order_date
        )
        customer_ids.append(customer_id)

    print(f"Inserted {len(customer_ids)} customers")
    return customer_ids


async def create_orders(conn, customer_ids):
    customer_stats = {cid: {"orders": 0, "spent": 0} for cid in customer_ids}

    for _ in range(300):
        customer_id = random.choice(customer_ids)
        order_items = []
        total_amount = 0
        item_count = random.randint(1, 4)

        for _ in range(item_count):
            item = random.choice(COFFEE_MENU)
            quantity = random.randint(1, 3)
            subtotal = item["price"] * quantity
            total_amount += subtotal
            order_items.append({
                "name": item["name"],
                "price": item["price"],
                "quantity": quantity,
                "subtotal": subtotal
            })

        order_date = datetime.now() - timedelta(days=random.randint(1, 180))

        await conn.execute(
            """
            INSERT INTO orders (customer_id, amount, items, created_at)
            VALUES ($1, $2, $3, $4)
            """,
            customer_id, total_amount, json.dumps(order_items), order_date
        )

        customer_stats[customer_id]["orders"] += 1
        customer_stats[customer_id]["spent"] += total_amount

    for customer_id, stats in customer_stats.items():
        latest_order = await conn.fetchval(
            "SELECT MAX(created_at) FROM orders WHERE customer_id = $1",
            customer_id
        )
        await conn.execute(
            """
            UPDATE customers
            SET total_orders = $1, total_spent = $2, last_order_date = $3
            WHERE id = $4
            """,
            stats["orders"], stats["spent"], latest_order, customer_id
        )

    print("Inserted 300 orders")


async def seed_database():
    if not DATABASE_URL:
        raise Exception("DATABASE_URL not found")

    conn = await asyncpg.connect(DATABASE_URL)

    try:
        print("Connected to database")

        await conn.execute("DELETE FROM communications")
        await conn.execute("DELETE FROM campaigns")
        await conn.execute("DELETE FROM segments")
        await conn.execute("DELETE FROM orders")
        await conn.execute("DELETE FROM customers")

        print("Existing data cleared")

        customer_ids = await create_customers(conn)
        await create_orders(conn, customer_ids)

        customer_count = await conn.fetchval("SELECT COUNT(*) FROM customers")
        order_count = await conn.fetchval("SELECT COUNT(*) FROM orders")
        revenue = await conn.fetchval("SELECT COALESCE(SUM(amount), 0) FROM orders")

        print("\nSeed Complete!")
        print(f"Customers: {customer_count}")
        print(f"Orders: {order_count}")
        print(f"Revenue: Rs.{revenue}")

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(seed_database())
