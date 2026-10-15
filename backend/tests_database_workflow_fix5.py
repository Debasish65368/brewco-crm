"""
Automated Behavioral and Static Verification Tests for Fix 5:
Correct DDL and Migration Workflow & Remote Database Protection.

Verifies:
1. DDL Ordering Defect Corrected:
   - `backend/scripts/reset_dev_db.sql` drops tables in reverse foreign-key dependency order.
   - Contains NO invalid `DELETE FROM` statements after `DROP TABLE`.
   - `backend/schema.sql` contains safe, repeatable DDL without DROP or DELETE.
   - `backend/scripts/reset_dev_db.sql` includes a preflight guard with `inet_server_addr()`
     that immediately refuses execution against remote PostgreSQL hosts.
2. Separation of Reset from Migrations:
   - Additive migration scripts (01 and 02) contain NO DROP, TRUNCATE, or DELETE statements.
   - Migrations do not import or invoke reset/seed logic.
   - Migrations re-raise exceptions on failure rather than silently suppressing errors.
3. No Reset on Application Startup:
   - FastAPI `lifespan` and `main.py` only manage connection pool and routes.
   - Startup logic executes zero DDL, resets, or migrations.
4. Fail-Closed Reset Safeguards (reset_dev_db.py):
   - Refuses when APP_ENV / ENVIRONMENT is missing or empty (fail-closed).
   - Refuses when APP_ENV or ENVIRONMENT is 'production' or 'prod' (even with confirmation).
   - Refuses when confirmation flag ('--confirm-destructive-reset') is absent.
   - Refuses when DEV_DATABASE_URL is missing (refuses fallback to DATABASE_URL).
   - Refuses remote database hosts (e.g. Neon, AWS) and asserts connect was NEVER called.
   - Allows execution only when in development, confirmed, and targeting a local loopback host.
   - Never exposes credentials in error messages.
5. Fail-Closed Seeding Safeguards (seed.py):
   - Refuses when APP_ENV / ENVIRONMENT is missing or empty (fail-closed).
   - Refuses when APP_ENV or ENVIRONMENT is 'production' or 'prod'.
   - Refuses when confirmation flag ('--confirm-reset') is absent.
   - Refuses when DEV_DATABASE_URL is missing (refuses fallback to DATABASE_URL).
   - Refuses remote database hosts before connect (asserting connect was never called).
   - Allows execution only when confirmed in development with a local loopback host.
6. 100% Offline:
   - Zero live database connections to Neon.
   - Uses static code analysis, environment mocks, and in-memory mock connection objects.
"""

import os
import re
import sys
import unittest
from unittest.mock import AsyncMock, patch

# Ensure backend directory is in sys.path
backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from scripts.reset_dev_db import (
    ALLOWED_DEV_ENVIRONMENTS,
    ALLOWED_LOCAL_HOSTS,
    check_reset_safeguards,
    reset_database,
    resolve_destructive_db_url,
    validate_local_database_host,
)
from seed import check_seed_safeguards, seed_database


class TestDDLOrderingAndSchemaCorrectness(unittest.TestCase):
    """Verifies that DDL and reset scripts maintain correct syntax, ordering, and table dependencies."""

    def setUp(self):
        self.backend_dir = os.path.dirname(os.path.abspath(__file__))
        self.schema_sql_path = os.path.join(self.backend_dir, "schema.sql")
        self.reset_sql_path = os.path.join(self.backend_dir, "scripts", "reset_dev_db.sql")

    def test_schema_sql_exists_and_is_non_destructive(self):
        """schema.sql must exist and contain safe, repeatable DDL without DROP or DELETE."""
        self.assertTrue(os.path.exists(self.schema_sql_path), "backend/schema.sql must exist.")

        with open(self.schema_sql_path, "r", encoding="utf-8") as f:
            code_lines = [l.strip().upper() for l in f if l.strip() and not l.strip().startswith("--")]
            content = "\n".join(code_lines)

        # Must not contain destructive statements
        self.assertNotIn("DROP TABLE", content, "schema.sql must not drop tables.")
        self.assertNotIn("DELETE FROM", content, "schema.sql must not delete data.")
        self.assertNotIn("TRUNCATE", content, "schema.sql must not truncate tables.")

        # Must contain all 5 required tables with IF NOT EXISTS
        for table in ["CUSTOMERS", "ORDERS", "SEGMENTS", "CAMPAIGNS", "COMMUNICATIONS"]:
            self.assertIn(
                f"CREATE TABLE IF NOT EXISTS {table}",
                content,
                f"schema.sql must create {table} with IF NOT EXISTS.",
            )

    def test_reset_sql_ordering_no_delete_after_drop(self):
        """reset_dev_db.sql must drop tables in reverse FK order and contain zero DELETE statements."""
        self.assertTrue(os.path.exists(self.reset_sql_path), "reset_dev_db.sql must exist.")

        with open(self.reset_sql_path, "r", encoding="utf-8") as f:
            lines = [line.strip().upper() for line in f if line.strip() and not line.strip().startswith("--")]

        # Filter DROP statements
        drop_statements = [l for l in lines if l.startswith("DROP TABLE")]
        delete_statements = [l for l in lines if l.startswith("DELETE FROM")]

        # 1. Zero DELETE statements after DROP
        self.assertEqual(
            len(delete_statements),
            0,
            "reset_dev_db.sql must NOT contain any DELETE statements (especially after DROP).",
        )

        # 2. Extract dropped table names
        dropped_tables = []
        for stmt in drop_statements:
            m = re.search(r"DROP TABLE (?:IF EXISTS )?(\w+)", stmt)
            if m:
                dropped_tables.append(m.group(1))

        # 3. Verify reverse foreign-key dependency order
        # communications -> campaigns -> segments -> orders -> customers
        self.assertIn("COMMUNICATIONS", dropped_tables)
        self.assertIn("CAMPAIGNS", dropped_tables)
        self.assertIn("SEGMENTS", dropped_tables)
        self.assertIn("ORDERS", dropped_tables)
        self.assertIn("CUSTOMERS", dropped_tables)

        comm_idx = dropped_tables.index("COMMUNICATIONS")
        camp_idx = dropped_tables.index("CAMPAIGNS")
        seg_idx = dropped_tables.index("SEGMENTS")
        ord_idx = dropped_tables.index("ORDERS")
        cust_idx = dropped_tables.index("CUSTOMERS")

        self.assertLess(comm_idx, camp_idx, "Child table COMMUNICATIONS must be dropped before parent CAMPAIGNS.")
        self.assertLess(comm_idx, cust_idx, "Child table COMMUNICATIONS must be dropped before parent CUSTOMERS.")
        self.assertLess(camp_idx, seg_idx, "Child table CAMPAIGNS must be dropped before parent SEGMENTS.")
        self.assertLess(ord_idx, cust_idx, "Child table ORDERS must be dropped before parent CUSTOMERS.")

    def test_reset_sql_contains_loopback_preflight_guard(self):
        """reset_dev_db.sql must contain a DO block rejecting NULL server address or remote hosts."""
        with open(self.reset_sql_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("DO $$", content, "reset_dev_db.sql must have a DO block preflight check.")
        self.assertIn("inet_server_addr()", content, "Preflight check must inspect inet_server_addr().")
        self.assertIn("server_ip IS NULL", content, "Preflight check must fail closed if server_ip IS NULL.")
        self.assertIn("127.0.0.1", content, "Preflight check must reference loopback 127.0.0.1.")
        self.assertIn("RAISE EXCEPTION", content, "Preflight check must raise exception on unverified/remote connection.")


class TestMigrationIsolationAndRepeatability(unittest.TestCase):
    """Verifies that migrations are additive, repeatable, and strictly isolated from reset operations."""

    def setUp(self):
        self.scripts_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scripts")
        self.mig01_path = os.path.join(self.scripts_dir, "01_add_churn_score_column.py")
        self.mig02_path = os.path.join(self.scripts_dir, "02_add_cluster_id_column.py")

    def test_migrations_are_purely_additive_no_destructive_keywords(self):
        """Migrations must only ADD columns and must never DROP, DELETE, or TRUNCATE."""
        for path in [self.mig01_path, self.mig02_path]:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read().upper()

            self.assertNotIn("DROP TABLE", content)
            self.assertNotIn("DELETE FROM", content)
            self.assertNotIn("TRUNCATE", content)
            self.assertIn("ADD COLUMN IF NOT EXISTS", content)

    def test_migrations_do_not_import_reset_or_seed(self):
        """Migrations must be completely independent of reset or seed modules."""
        for path in [self.mig01_path, self.mig02_path]:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()

            self.assertNotIn("import seed", content)
            self.assertNotIn("from seed", content)
            self.assertNotIn("reset_dev_db", content)

    def test_migrations_reraise_exceptions_on_failure(self):
        """Migrations must re-raise exceptions on failure rather than suppressing them."""
        for path in [self.mig01_path, self.mig02_path]:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()

            # Must contain except Exception and a raise
            self.assertIn("except Exception", content)
            self.assertIn("raise", content)


class TestApplicationStartupSafety(unittest.TestCase):
    """Verifies that application startup never triggers destructive resets, DDL, or migrations."""

    def test_lifespan_does_not_execute_ddl_or_resets(self):
        """backend/core/database.py lifespan must only initialize and close connection pool."""
        db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "core", "database.py")
        with open(db_path, "r", encoding="utf-8") as f:
            content = f.read().upper()

        self.assertNotIn("DROP TABLE", content)
        self.assertNotIn("DELETE FROM", content)
        self.assertNotIn("ALTER TABLE", content)
        self.assertNotIn("CREATE TABLE", content)
        self.assertNotIn("SEED", content)

    def test_main_does_not_execute_ddl_or_resets(self):
        """backend/main.py must not trigger DDL, seed, or reset scripts on import or startup."""
        main_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "main.py")
        with open(main_path, "r", encoding="utf-8") as f:
            content = f.read().upper()

        self.assertNotIn("DROP TABLE", content)
        self.assertNotIn("DELETE FROM", content)
        self.assertNotIn("SEED_DATABASE", content)
        self.assertNotIn("RESET_DATABASE", content)


class TestResetSafeguards(unittest.IsolatedAsyncioTestCase):
    """Verifies fail-closed safeguards for the development reset script."""

    def test_refuses_when_app_env_is_missing_or_empty(self):
        """Refuses to reset if APP_ENV and ENVIRONMENT are missing or empty (fail-closed)."""
        # Missing entirely
        with self.assertRaises(RuntimeError) as ctx1:
            check_reset_safeguards(
                argv=["reset_dev_db.py", "--confirm-destructive-reset"],
                env={},
            )
        self.assertIn("Environment is ambiguous", str(ctx1.exception))

        # Empty string
        with self.assertRaises(RuntimeError) as ctx2:
            check_reset_safeguards(
                argv=["reset_dev_db.py", "--confirm-destructive-reset"],
                env={"APP_ENV": "", "ENVIRONMENT": ""},
            )
        self.assertIn("Environment is ambiguous", str(ctx2.exception))

    def test_refuses_when_app_env_is_production(self):
        """Refuses to reset if APP_ENV is production, even with confirmation flag."""
        with self.assertRaises(RuntimeError) as ctx:
            check_reset_safeguards(
                argv=["reset_dev_db.py", "--confirm-destructive-reset"],
                env={
                    "APP_ENV": "production",
                    "CONFIRM_DESTRUCTIVE_RESET": "true",
                    "DEV_DATABASE_URL": "postgresql://postgres:postgres@localhost:5432/brewco_dev",
                },
            )
        self.assertIn("cannot run in production", str(ctx.exception))

    def test_refuses_when_environment_is_prod(self):
        """Refuses to reset if ENVIRONMENT is prod."""
        with self.assertRaises(RuntimeError) as ctx:
            check_reset_safeguards(
                argv=["reset_dev_db.py", "--confirm-destructive-reset"],
                env={
                    "ENVIRONMENT": "prod",
                    "DEV_DATABASE_URL": "postgresql://postgres:postgres@localhost:5432/brewco_dev",
                },
            )
        self.assertIn("cannot run in production", str(ctx.exception))

    def test_refuses_when_confirmation_missing_in_development(self):
        """Refuses to reset in development when neither flag nor env confirmation is provided."""
        with self.assertRaises(RuntimeError) as ctx:
            check_reset_safeguards(
                argv=["reset_dev_db.py"],
                env={
                    "APP_ENV": "development",
                    "DEV_DATABASE_URL": "postgresql://postgres:postgres@localhost:5432/brewco_dev",
                },
            )
        self.assertIn("requires explicit confirmation", str(ctx.exception))

    def test_refuses_when_dev_database_url_is_missing(self):
        """Refuses to reset if DEV_DATABASE_URL is missing, refusing to fall back to DATABASE_URL."""
        with self.assertRaises(RuntimeError) as ctx:
            check_reset_safeguards(
                argv=["reset_dev_db.py", "--confirm-destructive-reset"],
                env={
                    "APP_ENV": "development",
                    "DATABASE_URL": "postgresql://postgres:postgres@localhost:5432/brewco_dev",
                },
            )
        self.assertIn("requires a dedicated development database URL (DEV_DATABASE_URL)", str(ctx.exception))

    async def test_refuses_remote_database_target_before_connect(self):
        """Refuses remote database URLs before attempting any network connection."""
        remote_url = "postgresql://brewco_user:secret123@ep-misty-water-a17p778z-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require"

        with patch("scripts.reset_dev_db.asyncpg.connect", new_callable=AsyncMock) as mock_connect:
            with self.assertRaises(RuntimeError) as ctx:
                await reset_database(
                    argv=["reset_dev_db.py", "--confirm-destructive-reset"],
                    env={
                        "APP_ENV": "development",
                        "DEV_DATABASE_URL": remote_url,
                    },
                )

            # Assert connection was NEVER attempted
            mock_connect.assert_not_called()
            # Assert refusal explicitly mentions remote database host
            self.assertIn("cannot run against remote database host", str(ctx.exception))
            # Assert credentials were NOT leaked in the error
            self.assertNotIn("secret123", str(ctx.exception))

    def test_allows_execution_when_confirmed_in_development_with_local_url(self):
        """Permits execution when APP_ENV is development, confirmed, and DEV_DATABASE_URL is local."""
        validated_url = check_reset_safeguards(
            argv=["reset_dev_db.py", "--confirm-destructive-reset"],
            env={
                "APP_ENV": "development",
                "DEV_DATABASE_URL": "postgresql://postgres:postgres@localhost:5432/brewco_dev",
            },
        )
        self.assertEqual(validated_url, "postgresql://postgres:postgres@localhost:5432/brewco_dev")

    async def test_reset_database_executes_drops_in_order_when_authorized(self):
        """When authorized, executes drop statements in reverse dependency order against local DB."""
        mock_conn = AsyncMock()
        executed_stmts = []

        async def fake_execute(stmt):
            executed_stmts.append(stmt)

        mock_conn.execute.side_effect = fake_execute

        with patch("scripts.reset_dev_db.asyncpg.connect", return_value=mock_conn) as mock_connect:
            await reset_database(
                argv=["reset_dev_db.py", "--confirm-destructive-reset"],
                env={
                    "APP_ENV": "development",
                    "DEV_DATABASE_URL": "postgresql://postgres:postgres@127.0.0.1:5432/brewco_dev",
                },
            )
            mock_connect.assert_called_once_with("postgresql://postgres:postgres@127.0.0.1:5432/brewco_dev")

        self.assertEqual(len(executed_stmts), 5)
        self.assertIn("COMMUNICATIONS", executed_stmts[0].upper())
        self.assertIn("CAMPAIGNS", executed_stmts[1].upper())
        self.assertIn("SEGMENTS", executed_stmts[2].upper())
        self.assertIn("ORDERS", executed_stmts[3].upper())
        self.assertIn("CUSTOMERS", executed_stmts[4].upper())
        # Zero DELETE statements
        for stmt in executed_stmts:
            self.assertNotIn("DELETE", stmt.upper())


class TestSeedSafeguards(unittest.IsolatedAsyncioTestCase):
    """Verifies fail-closed safeguards for synthetic-data seeding."""

    def test_seed_refuses_when_app_env_missing_or_empty(self):
        """Refuses to seed if APP_ENV and ENVIRONMENT are missing or empty."""
        with self.assertRaises(RuntimeError) as ctx:
            check_seed_safeguards(
                argv=["seed.py", "--confirm-reset"],
                env={},
            )
        self.assertIn("Environment is ambiguous", str(ctx.exception))

    def test_seed_refuses_when_app_env_is_production(self):
        """Refuses to seed if APP_ENV is production."""
        with self.assertRaises(RuntimeError) as ctx:
            check_seed_safeguards(
                argv=["seed.py", "--confirm-reset"],
                env={
                    "APP_ENV": "production",
                    "CONFIRM_SEED_RESET": "true",
                    "DEV_DATABASE_URL": "postgresql://postgres:postgres@localhost:5432/brewco_dev",
                },
            )
        self.assertIn("cannot run in production", str(ctx.exception))

    def test_seed_refuses_when_confirmation_is_absent(self):
        """Refuses to seed in development without explicit confirmation."""
        with self.assertRaises(RuntimeError) as ctx:
            check_seed_safeguards(
                argv=["seed.py"],
                env={
                    "APP_ENV": "development",
                    "DEV_DATABASE_URL": "postgresql://postgres:postgres@localhost:5432/brewco_dev",
                },
            )
        self.assertIn("requires explicit confirmation", str(ctx.exception))

    def test_seed_refuses_when_dev_database_url_is_missing(self):
        """Refuses to seed if DEV_DATABASE_URL is missing, refusing to fall back to DATABASE_URL."""
        with self.assertRaises(RuntimeError) as ctx:
            check_seed_safeguards(
                argv=["seed.py", "--confirm-reset"],
                env={
                    "APP_ENV": "development",
                    "DATABASE_URL": "postgresql://postgres:postgres@localhost:5432/brewco_dev",
                },
            )
        self.assertIn("requires a dedicated development database URL (DEV_DATABASE_URL)", str(ctx.exception))

    async def test_seed_refuses_remote_database_target_before_connect(self):
        """Refuses remote database URLs before attempting any network connection in seeder."""
        remote_url = "postgresql://brewco_user:secret456@ep-misty-water-a17p778z-pooler.ap-southeast-1.aws.neon.tech/neondb"

        with patch("seed.asyncpg.connect", new_callable=AsyncMock) as mock_connect:
            with self.assertRaises(RuntimeError) as ctx:
                await seed_database(
                    argv=["seed.py", "--confirm-reset"],
                    env={
                        "APP_ENV": "development",
                        "DEV_DATABASE_URL": remote_url,
                    },
                )

            # Assert connection was NEVER attempted
            mock_connect.assert_not_called()
            self.assertIn("cannot run against remote database host", str(ctx.exception))
            self.assertNotIn("secret456", str(ctx.exception))

    def test_seed_permits_when_confirmed_in_development_with_local_url(self):
        """Allows seeding when in development, confirmed, and targeting local host."""
        validated_url = check_seed_safeguards(
            argv=["seed.py", "--confirm-reset"],
            env={
                "APP_ENV": "development",
                "DEV_DATABASE_URL": "postgresql://postgres:postgres@localhost:5432/brewco_dev",
            },
        )
        self.assertEqual(validated_url, "postgresql://postgres:postgres@localhost:5432/brewco_dev")

    async def test_seed_database_executes_when_authorized(self):
        """When authorized, executes seeder against local DB with mock data generation."""
        mock_conn = AsyncMock()
        executed_stmts = []

        async def fake_execute(stmt):
            executed_stmts.append(stmt)

        mock_conn.execute.side_effect = fake_execute
        mock_conn.fetchval.return_value = 100

        with patch("seed.asyncpg.connect", return_value=mock_conn) as mock_connect, \
             patch("seed.create_customers", new_callable=AsyncMock, return_value=[1, 2, 3]) as mock_cust, \
             patch("seed.create_orders", new_callable=AsyncMock) as mock_ord:
            await seed_database(
                argv=["seed.py", "--confirm-reset"],
                env={
                    "APP_ENV": "development",
                    "DEV_DATABASE_URL": "postgresql://postgres:postgres@localhost:5432/brewco_dev",
                },
            )
            mock_connect.assert_called_once_with("postgresql://postgres:postgres@localhost:5432/brewco_dev")
            mock_cust.assert_called_once_with(mock_conn)
            mock_ord.assert_called_once_with(mock_conn, [1, 2, 3])

        # Verify clear order (reverse dependency)
        delete_stmts = [s for s in executed_stmts if "DELETE FROM" in s.upper()]
        self.assertEqual(len(delete_stmts), 5)
        self.assertIn("COMMUNICATIONS", delete_stmts[0].upper())
        self.assertIn("CAMPAIGNS", delete_stmts[1].upper())
        self.assertIn("SEGMENTS", delete_stmts[2].upper())
        self.assertIn("ORDERS", delete_stmts[3].upper())
        self.assertIn("CUSTOMERS", delete_stmts[4].upper())


if __name__ == "__main__":
    unittest.main()
