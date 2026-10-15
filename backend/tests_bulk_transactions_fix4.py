"""
Automated Behavioral Regression Tests for Fix 4: Bulk-Insert Counting and Transaction Safety.

Verifies:
1. Customer bulk import accurate counting with ON CONFLICT RETURNING id.
2. Skipping existing database duplicate emails without incrementing inserted.
3. Skipping intra-batch duplicate emails without inflating inserted count.
4. Mixed and all-duplicate batch reporting accurate inserted/skipped counts.
5. All-or-nothing rollback for unexpected customer import failures (no partial commits).
6. Order bulk import transaction enclosure: atomic order inserts and aggregate updates.
7. Atomic rollback when an intermediate order insert fails.
8. Atomic rollback when an intermediate customer aggregate update fails.
9. Multiple orders for the same customer updating aggregates accurately in sequence.
10. Nonexistent customer rejection (404) with complete rollback of earlier orders in batch.
11. Clean handling of empty customer and order batches without unnecessary writes.
12. 100% isolated: uses in-memory mock connection and transactions without live Neon DB writes.
"""

import copy
from datetime import datetime, timezone
import unittest
from unittest.mock import patch

from fastapi import HTTPException
from pydantic import EmailStr

from routers.customers import bulk_insert_customers
from routers.orders import bulk_insert_orders
from schemas import CustomerBulkRequest, CustomerCreate, OrderBulkRequest, OrderCreate


class MockAsyncpgTransaction:
    """Simulates an asyncpg connection transaction manager with realistic rollback/commit."""

    def __init__(self, conn):
        self.conn = conn

    async def __aenter__(self):
        self.conn.in_transaction = True
        self.conn.savepoint()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.conn.in_transaction = False
        if exc_type is not None:
            self.conn.rollback()
        else:
            self.conn.commit()


class MockAsyncpgConnection:
    """
    In-memory asyncpg connection simulation for customers and orders tables.
    Maintains relational state and supports atomic commit and rollback.
    """

    def __init__(self, initial_customers=None, initial_orders=None):
        self.customers = copy.deepcopy(initial_customers or {})
        self.orders = copy.deepcopy(initial_orders or {})
        self._snapshot = None
        self.in_transaction = False
        self.committed = False
        self.rolled_back = False

        # Fault injection hooks
        self.fail_on_customer_insert_idx = None
        self.fail_on_order_insert_idx = None
        self.fail_on_customer_update_idx = None

        self._customer_insert_calls = 0
        self._order_insert_calls = 0
        self._customer_update_calls = 0

    def transaction(self):
        return MockAsyncpgTransaction(self)

    def savepoint(self):
        self._snapshot = (copy.deepcopy(self.customers), copy.deepcopy(self.orders))
        self.committed = False
        self.rolled_back = False

    def commit(self):
        self._snapshot = None
        self.committed = True

    def rollback(self):
        if self._snapshot is not None:
            self.customers, self.orders = self._snapshot
            self._snapshot = None
        self.rolled_back = True

    async def fetchval(self, query, *args):
        query_strip = " ".join(query.split()).upper()

        # Check for customer existence check: SELECT id FROM customers WHERE id = $1
        if "SELECT ID FROM CUSTOMERS WHERE ID = $1" in query_strip:
            cust_id = args[0]
            if cust_id in self.customers:
                return cust_id
            return None

        # Check for INSERT INTO customers ... RETURNING id
        if "INSERT INTO CUSTOMERS" in query_strip and "RETURNING ID" in query_strip:
            if (
                self.fail_on_customer_insert_idx is not None
                and self._customer_insert_calls == self.fail_on_customer_insert_idx
            ):
                self._customer_insert_calls += 1
                raise RuntimeError("Simulated unexpected database failure during customer insert.")

            self._customer_insert_calls += 1
            name, email, phone, city, total_orders, total_spent, last_order_date = args

            # Check unique email conflict
            for c in self.customers.values():
                if c["email"].lower() == email.lower():
                    # ON CONFLICT DO NOTHING -> 0 rows returned
                    return None

            # Generate new customer ID
            new_id = (max(self.customers.keys()) + 1) if self.customers else 1
            self.customers[new_id] = {
                "id": new_id,
                "name": name,
                "email": email,
                "phone": phone,
                "city": city,
                "total_orders": total_orders or 0,
                "total_spent": float(total_spent or 0.0),
                "last_order_date": last_order_date,
            }
            return new_id

        raise NotImplementedError(f"MockAsyncpgConnection.fetchval unhandled: {query}")

    async def execute(self, query, *args):
        query_strip = " ".join(query.split()).upper()

        # INSERT INTO orders (customer_id, amount, items, created_at)
        if "INSERT INTO ORDERS" in query_strip:
            if (
                self.fail_on_order_insert_idx is not None
                and self._order_insert_calls == self.fail_on_order_insert_idx
            ):
                self._order_insert_calls += 1
                raise RuntimeError("Simulated unexpected database failure during order insert.")

            self._order_insert_calls += 1
            cust_id, amount, items, created_at = args
            new_order_id = (max(self.orders.keys()) + 1) if self.orders else 1
            self.orders[new_order_id] = {
                "id": new_order_id,
                "customer_id": cust_id,
                "amount": float(amount),
                "items": items,
                "created_at": created_at or datetime.now(timezone.utc).replace(tzinfo=None),
            }
            return "INSERT 0 1"

        # UPDATE customers SET total_orders = total_orders + 1, ... WHERE id = $2
        if "UPDATE CUSTOMERS SET TOTAL_ORDERS" in query_strip:
            if (
                self.fail_on_customer_update_idx is not None
                and self._customer_update_calls == self.fail_on_customer_update_idx
            ):
                self._customer_update_calls += 1
                raise RuntimeError("Simulated unexpected failure during customer aggregate update.")

            self._customer_update_calls += 1
            amount, cust_id, created_at = args
            if cust_id not in self.customers:
                return "UPDATE 0"

            c = self.customers[cust_id]
            c["total_orders"] += 1
            c["total_spent"] += float(amount)
            order_dt = created_at or datetime.now(timezone.utc).replace(tzinfo=None)
            if c["last_order_date"] is None:
                c["last_order_date"] = order_dt
            else:
                c["last_order_date"] = max(c["last_order_date"], order_dt)

            return "UPDATE 1"

        raise NotImplementedError(f"MockAsyncpgConnection.execute unhandled: {query}")


class TestCustomerBulkImportAccurateCounting(unittest.IsolatedAsyncioTestCase):
    """Behavioral tests verifying customer bulk-insert counting and conflict handling."""

    def setUp(self):
        self.initial_customers = {
            1: {
                "id": 1,
                "name": "Existing User",
                "email": "existing@brewco.com",
                "phone": "9876543210",
                "city": "Delhi",
                "total_orders": 2,
                "total_spent": 500.0,
                "last_order_date": datetime(2026, 1, 15),
            }
        }
        self.mock_conn = MockAsyncpgConnection(initial_customers=self.initial_customers)

    async def test_single_new_customer_increments_inserted_count(self):
        """A new unique customer is inserted and reported as inserted=1."""
        req = CustomerBulkRequest(
            customers=[
                CustomerCreate(
                    name="Aarav Patel",
                    email="aarav@brewco.com",
                    phone="9123456789",
                    city="Mumbai",
                )
            ]
        )
        with patch("routers.customers.get_connection", return_value=self.mock_conn), \
             patch("routers.customers.release_connection"):
            res = await bulk_insert_customers(req, user="mock")

        self.assertTrue(res["success"])
        self.assertEqual(res["inserted"], 1)
        self.assertEqual(res["skipped"], 0)
        self.assertEqual(res["attempted"], 1)
        self.assertTrue(self.mock_conn.committed)
        self.assertEqual(len(self.mock_conn.customers), 2)

    async def test_duplicate_email_already_in_db_skipped(self):
        """Customer with email matching an existing row is skipped; inserted count is 0."""
        req = CustomerBulkRequest(
            customers=[
                CustomerCreate(
                    name="Existing Imposter",
                    email="existing@brewco.com",  # Already in initial_customers
                    phone="9999999999",
                    city="Bangalore",
                )
            ]
        )
        with patch("routers.customers.get_connection", return_value=self.mock_conn), \
             patch("routers.customers.release_connection"):
            res = await bulk_insert_customers(req, user="mock")

        self.assertTrue(res["success"])
        self.assertEqual(res["inserted"], 0)
        self.assertEqual(res["skipped"], 1)
        self.assertEqual(res["attempted"], 1)
        self.assertEqual(len(self.mock_conn.customers), 1)

    async def test_duplicate_emails_within_same_batch_do_not_inflate_count(self):
        """Intra-batch duplicates only insert the first instance; subsequent instances are skipped."""
        req = CustomerBulkRequest(
            customers=[
                CustomerCreate(
                    name="Diya Sharma 1",
                    email="diya@brewco.com",
                    phone="9811111111",
                    city="Kolkata",
                ),
                CustomerCreate(
                    name="Diya Sharma 2",
                    email="diya@brewco.com",  # Duplicate within batch
                    phone="9822222222",
                    city="Kolkata",
                ),
            ]
        )
        with patch("routers.customers.get_connection", return_value=self.mock_conn), \
             patch("routers.customers.release_connection"):
            res = await bulk_insert_customers(req, user="mock")

        self.assertTrue(res["success"])
        self.assertEqual(res["inserted"], 1)
        self.assertEqual(res["skipped"], 1)
        self.assertEqual(res["attempted"], 2)
        # Database only has 1 initial + 1 inserted = 2 total
        self.assertEqual(len(self.mock_conn.customers), 2)

    async def test_all_duplicate_batch_reports_zero_inserted(self):
        """A batch containing only duplicates reports inserted=0 and skipped=total."""
        req = CustomerBulkRequest(
            customers=[
                CustomerCreate(
                    name="Existing Dupe 1",
                    email="existing@brewco.com",
                    phone="9000000001",
                    city="Pune",
                ),
                CustomerCreate(
                    name="Existing Dupe 2",
                    email="existing@brewco.com",
                    phone="9000000002",
                    city="Pune",
                ),
            ]
        )
        with patch("routers.customers.get_connection", return_value=self.mock_conn), \
             patch("routers.customers.release_connection"):
            res = await bulk_insert_customers(req, user="mock")

        self.assertTrue(res["success"])
        self.assertEqual(res["inserted"], 0)
        self.assertEqual(res["skipped"], 2)
        self.assertEqual(res["attempted"], 2)

    async def test_mixed_batch_reports_exact_counts(self):
        """A mixed batch of new, existing, and intra-batch duplicates reports exact counts."""
        req = CustomerBulkRequest(
            customers=[
                CustomerCreate(name="New 1", email="new1@brewco.com", phone="9001", city="Delhi"),
                CustomerCreate(name="Existing", email="existing@brewco.com", phone="9002", city="Delhi"),
                CustomerCreate(name="New 1 Dup", email="new1@brewco.com", phone="9003", city="Delhi"),
                CustomerCreate(name="New 2", email="new2@brewco.com", phone="9004", city="Delhi"),
            ]
        )
        with patch("routers.customers.get_connection", return_value=self.mock_conn), \
             patch("routers.customers.release_connection"):
            res = await bulk_insert_customers(req, user="mock")

        self.assertTrue(res["success"])
        self.assertEqual(res["inserted"], 2)  # new1 and new2
        self.assertEqual(res["skipped"], 2)   # existing and new1 dup
        self.assertEqual(res["attempted"], 4)
        self.assertEqual(len(self.mock_conn.customers), 3)

    async def test_empty_customer_batch_handled_cleanly(self):
        """Empty customer request returns immediately with 0s without database queries."""
        req = CustomerBulkRequest(customers=[])
        with patch("routers.customers.get_connection", return_value=self.mock_conn), \
             patch("routers.customers.release_connection"):
            res = await bulk_insert_customers(req, user="mock")

        self.assertTrue(res["success"])
        self.assertEqual(res["inserted"], 0)
        self.assertEqual(res["skipped"], 0)
        self.assertEqual(res["attempted"], 0)


class TestCustomerBulkImportTransactionRollback(unittest.IsolatedAsyncioTestCase):
    """Behavioral tests verifying all-or-nothing transaction rollback on unexpected errors."""

    def setUp(self):
        self.mock_conn = MockAsyncpgConnection()

    async def test_unexpected_failure_rolls_back_earlier_insertions(self):
        """When an unexpected error occurs partway through, earlier insertions in the batch are rolled back."""
        # Inject error on the 3rd customer insert
        self.mock_conn.fail_on_customer_insert_idx = 2

        req = CustomerBulkRequest(
            customers=[
                CustomerCreate(name="Cust 1", email="c1@brewco.com", phone="111", city="Delhi"),
                CustomerCreate(name="Cust 2", email="c2@brewco.com", phone="222", city="Delhi"),
                CustomerCreate(name="Cust 3", email="c3@brewco.com", phone="333", city="Delhi"),
            ]
        )

        with patch("routers.customers.get_connection", return_value=self.mock_conn), \
             patch("routers.customers.release_connection"):
            with self.assertRaises(HTTPException) as ctx:
                await bulk_insert_customers(req, user="mock")

        self.assertEqual(ctx.exception.status_code, 500)
        self.assertEqual(ctx.exception.detail, "Bulk customer import failed due to an unexpected database error.")
        self.assertNotIn("Simulated unexpected database failure", ctx.exception.detail)
        # Verify rollback occurred
        self.assertTrue(self.mock_conn.rolled_back)
        self.assertFalse(self.mock_conn.committed)
        # No customers should remain in the database
        self.assertEqual(len(self.mock_conn.customers), 0)


class TestOrderBulkImportTransactions(unittest.IsolatedAsyncioTestCase):
    """Behavioral tests verifying atomic transaction consistency for order bulk imports."""

    def setUp(self):
        self.initial_customers = {
            10: {
                "id": 10,
                "name": "Kavita Rao",
                "email": "kavita@brewco.com",
                "phone": "9812345678",
                "city": "Hyderabad",
                "total_orders": 1,
                "total_spent": 150.0,
                "last_order_date": datetime(2026, 2, 1, 10, 0, 0),
            }
        }
        self.mock_conn = MockAsyncpgConnection(initial_customers=self.initial_customers)

    async def test_successful_batch_inserts_orders_and_updates_aggregates(self):
        """Orders are inserted and customer aggregates are incremented atomically."""
        req = OrderBulkRequest(
            orders=[
                OrderCreate(
                    customer_id=10,
                    amount=200.0,
                    items=[{"name": "Cappuccino", "price": 200}],
                    created_at=datetime(2026, 3, 1, 12, 0, 0),
                ),
                OrderCreate(
                    customer_id=10,
                    amount=150.0,
                    items=[{"name": "Croissant", "price": 150}],
                    created_at=datetime(2026, 3, 2, 14, 0, 0),
                ),
            ]
        )

        with patch("routers.orders.get_connection", return_value=self.mock_conn), \
             patch("routers.orders.release_connection"):
            res = await bulk_insert_orders(req, user="mock")

        self.assertTrue(res["success"])
        self.assertEqual(res["inserted"], 2)
        self.assertEqual(res["attempted"], 2)
        self.assertTrue(self.mock_conn.committed)

        # Verify orders inserted
        self.assertEqual(len(self.mock_conn.orders), 2)

        # Verify customer aggregates: total_orders: 1+2=3, total_spent: 150+350=500.0
        cust = self.mock_conn.customers[10]
        self.assertEqual(cust["total_orders"], 3)
        self.assertEqual(cust["total_spent"], 500.0)
        self.assertEqual(cust["last_order_date"], datetime(2026, 3, 2, 14, 0, 0))

    async def test_error_during_order_insert_rolls_back_whole_batch(self):
        """If an intermediate order insert fails, earlier orders and updates are rolled back."""
        # Fail on 2nd order insert
        self.mock_conn.fail_on_order_insert_idx = 1

        req = OrderBulkRequest(
            orders=[
                OrderCreate(customer_id=10, amount=100.0, items=[]),
                OrderCreate(customer_id=10, amount=200.0, items=[]),
            ]
        )

        with patch("routers.orders.get_connection", return_value=self.mock_conn), \
             patch("routers.orders.release_connection"):
            with self.assertRaises(HTTPException) as ctx:
                await bulk_insert_orders(req, user="mock")

        self.assertEqual(ctx.exception.status_code, 500)
        self.assertEqual(ctx.exception.detail, "Bulk order import failed due to an unexpected database error.")
        self.assertNotIn("Simulated unexpected database failure", ctx.exception.detail)
        self.assertTrue(self.mock_conn.rolled_back)
        self.assertFalse(self.mock_conn.committed)

        # State reverted: 0 orders in database, customer 10 aggregates unchanged
        self.assertEqual(len(self.mock_conn.orders), 0)
        self.assertEqual(self.mock_conn.customers[10]["total_orders"], 1)
        self.assertEqual(self.mock_conn.customers[10]["total_spent"], 150.0)

    async def test_error_during_aggregate_update_rolls_back_batch(self):
        """If an aggregate update fails, the preceding order insert is rolled back."""
        # Fail on 1st customer update
        self.mock_conn.fail_on_customer_update_idx = 0

        req = OrderBulkRequest(
            orders=[
                OrderCreate(customer_id=10, amount=100.0, items=[]),
            ]
        )

        with patch("routers.orders.get_connection", return_value=self.mock_conn), \
             patch("routers.orders.release_connection"):
            with self.assertRaises(HTTPException) as ctx:
                await bulk_insert_orders(req, user="mock")

        self.assertEqual(ctx.exception.status_code, 500)
        self.assertEqual(ctx.exception.detail, "Bulk order import failed due to an unexpected database error.")
        self.assertNotIn("Simulated unexpected failure", ctx.exception.detail)
        self.assertTrue(self.mock_conn.rolled_back)
        self.assertEqual(len(self.mock_conn.orders), 0)
        self.assertEqual(self.mock_conn.customers[10]["total_orders"], 1)

    async def test_order_referencing_nonexistent_customer_rolls_back(self):
        """Orders referencing invalid customer ID raise 404 and roll back any prior batch inserts."""
        req = OrderBulkRequest(
            orders=[
                OrderCreate(customer_id=10, amount=100.0, items=[]),   # Valid customer
                OrderCreate(customer_id=99999, amount=50.0, items=[]), # Nonexistent customer
            ]
        )

        with patch("routers.orders.get_connection", return_value=self.mock_conn), \
             patch("routers.orders.release_connection"):
            with self.assertRaises(HTTPException) as ctx:
                await bulk_insert_orders(req, user="mock")

        # Confirm 404 is not masked by generic 500 handler
        self.assertEqual(ctx.exception.status_code, 404)
        self.assertNotEqual(ctx.exception.status_code, 500)
        self.assertEqual(ctx.exception.detail, "Customer with id 99999 does not exist.")
        self.assertTrue(self.mock_conn.rolled_back)

        # Earlier order 1 must be rolled back
        self.assertEqual(len(self.mock_conn.orders), 0)
        self.assertEqual(self.mock_conn.customers[10]["total_orders"], 1)
        self.assertEqual(self.mock_conn.customers[10]["total_spent"], 150.0)

    async def test_order_single_nonexistent_customer_raises_404_not_500(self):
        """Single nonexistent customer raises 404 directly without converting to 500."""
        req = OrderBulkRequest(
            orders=[
                OrderCreate(customer_id=88888, amount=50.0, items=[]),
            ]
        )

        with patch("routers.orders.get_connection", return_value=self.mock_conn), \
             patch("routers.orders.release_connection"):
            with self.assertRaises(HTTPException) as ctx:
                await bulk_insert_orders(req, user="mock")

        self.assertEqual(ctx.exception.status_code, 404)
        self.assertEqual(ctx.exception.detail, "Customer with id 88888 does not exist.")
        self.assertTrue(self.mock_conn.rolled_back)
        self.assertFalse(self.mock_conn.committed)
        self.assertEqual(len(self.mock_conn.orders), 0)

    async def test_empty_order_batch_handled_cleanly(self):
        """Empty order batch returns success=True and inserted=0 without writes."""
        req = OrderBulkRequest(orders=[])
        with patch("routers.orders.get_connection", return_value=self.mock_conn), \
             patch("routers.orders.release_connection"):
            res = await bulk_insert_orders(req, user="mock")

        self.assertTrue(res["success"])
        self.assertEqual(res["inserted"], 0)
        self.assertEqual(res["attempted"], 0)


if __name__ == "__main__":
    unittest.main()
