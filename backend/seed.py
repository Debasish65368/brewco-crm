import os
import sys
import json
import random
import asyncio
from datetime import datetime, timedelta

import asyncpg
from dotenv import load_dotenv

load_dotenv()

# Add backend directory to sys.path so scripts can be imported cleanly
sys_backend_dir = os.path.dirname(os.path.abspath(__file__))
if sys_backend_dir not in sys.path:
    sys.path.insert(0, sys_backend_dir)

try:
    from scripts.reset_dev_db import (
        ALLOWED_LOCAL_HOSTS,
        ALLOWED_DEV_ENVIRONMENTS,
        validate_local_database_host,
        resolve_destructive_db_url,
    )
except ImportError:
    from backend.scripts.reset_dev_db import (
        ALLOWED_LOCAL_HOSTS,
        ALLOWED_DEV_ENVIRONMENTS,
        validate_local_database_host,
        resolve_destructive_db_url,
    )

try:
    from faker import Faker
    fake = Faker("en_IN")
except ImportError:
    Faker = None
    fake = None

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
    if fake is None:
        raise RuntimeError("Faker is required for synthetic data generation. Please install it with: pip install faker")
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


import sys

def check_seed_safeguards(argv=None, env=None, db_url=None):
    """
    Validates environment, confirmation flags, and database target before permitting synthetic data seeding.
    Fails closed on ambiguous or missing environment configurations.
    Requires DEV_DATABASE_URL and validates local loopback host.
    """
    env_dict = env if env is not None else os.environ
    args = argv if argv is not None else sys.argv

    # 1. Environment Guard (Fail-Closed on Ambiguous / Missing Environment)
    raw_env = env_dict.get("APP_ENV") or env_dict.get("ENVIRONMENT")
    if not raw_env:
        raise RuntimeError(
            "REFUSED: Environment is ambiguous. Neither APP_ENV nor ENVIRONMENT is explicitly set. "
            "Destructive operations require an explicitly configured development environment "
            "(e.g. APP_ENV='development')."
        )

    app_env = raw_env.strip().lower()
    if app_env in ("production", "prod"):
        raise RuntimeError(
            f"REFUSED: Seeding cannot run in production (APP_ENV={app_env!r}). "
            "Data loss prevention safeguard active."
        )

    if app_env not in ALLOWED_DEV_ENVIRONMENTS:
        raise RuntimeError(
            f"REFUSED: Environment {app_env!r} is not an authorized development environment. "
            "Destructive operations require APP_ENV='development'."
        )

    # 2. Explicit Confirmation Guard
    confirm_flag = "--confirm-reset" in args
    confirm_env = env_dict.get("CONFIRM_SEED_RESET", "").lower() in ("true", "1", "yes")

    if not (confirm_flag or confirm_env):
        raise RuntimeError(
            "REFUSED: Seeding requires explicit confirmation because it deletes all existing "
            "customers, orders, segments, campaigns, and communications. "
            "Pass '--confirm-reset' on the command line or set CONFIRM_SEED_RESET=true to proceed."
        )

    # 3. Dedicated Target & Local Host Validation
    return resolve_destructive_db_url(db_url=db_url, env=env_dict, caller_name="Data seeder")


async def seed_database(db_url: str = None, argv=None, env=None):
    target_url = check_seed_safeguards(argv=argv, env=env, db_url=db_url)

    print("Connecting to local development database for seeding...")
    conn = await asyncpg.connect(target_url)

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
    try:
        asyncio.run(seed_database())
    except RuntimeError as e:
        print(f"\n[ERROR] {e}\n", file=sys.stderr)
        sys.exit(1)
