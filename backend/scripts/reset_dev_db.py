"""
BrewCo CRM — Development-Only Destructive Reset Script.

WARNING:
This script drops all CRM tables and permanently destroys all data.
It must NEVER be run in production or against remote/persistent databases.

Safety Boundaries:
1. Environment Guard (Fail-Closed):
   Refuses execution if APP_ENV or ENVIRONMENT is missing, empty, production,
   or any ambiguous state. Must be explicitly configured as development ('development', 'dev', 'local', 'test').
2. Dedicated Target Guard:
   Refuses to silently fall back to DATABASE_URL. Requires DEV_DATABASE_URL explicitly
   designated for development resets.
3. Local Host Allowlist Guard:
   Strictly enforces loopback hosts (localhost, 127.0.0.1, ::1). Rejects remote database
   hosts (e.g. Neon, AWS, Render) before attempting to connect.
4. Confirmation Guard:
   Requires explicit opt-in via '--confirm-destructive-reset' CLI flag
   or 'CONFIRM_DESTRUCTIVE_RESET=true' environment variable.
5. Credential Sanitization:
   Never prints database URLs or credentials in errors or logs.
6. Correct DDL Ordering:
   Drops tables in reverse foreign-key dependency order (communications -> campaigns ->
   segments -> orders -> customers) with CASCADE. Zero post-drop DELETE statements.

Usage:
    python scripts/reset_dev_db.py --confirm-destructive-reset
"""

import asyncio
import os
import sys
import urllib.parse

import asyncpg

# Add parent directory to path so we can import core packages if needed
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ALLOWED_LOCAL_HOSTS = {
    "localhost",
    "127.0.0.1",
    "::1",
    "[::1]",
}

ALLOWED_DEV_ENVIRONMENTS = {
    "development",
    "dev",
    "local",
    "test",
}


def validate_local_database_host(url: str, caller_name: str = "Destructive reset") -> str:
    """
    Validates that a database connection URL targets an allowlisted local host.
    Returns the validated hostname.
    Never exposes passwords, tokens, or full connection strings in errors.
    """
    if not url or not isinstance(url, str):
        raise RuntimeError(f"REFUSED: {caller_name} received an empty or invalid database connection string.")

    try:
        parsed = urllib.parse.urlsplit(url)
    except Exception:
        raise RuntimeError(f"REFUSED: {caller_name} received a malformed database URL.")

    hostname = (parsed.hostname or "").strip().lower()
    if not hostname:
        raise RuntimeError(
            f"REFUSED: {caller_name} could not determine database host from connection string. "
            "Host must be explicitly one of: localhost, 127.0.0.1, ::1."
        )

    if hostname not in ALLOWED_LOCAL_HOSTS:
        raise RuntimeError(
            f"REFUSED: {caller_name} cannot run against remote database host {hostname!r}. "
            "Destructive development operations are strictly restricted to local hosts "
            "(localhost, 127.0.0.1, ::1) to prevent accidental remote database destruction."
        )

    return hostname


def resolve_destructive_db_url(
    db_url: str = None,
    env: dict = None,
    caller_name: str = "Destructive reset",
) -> str:
    """
    Resolves the target database URL for destructive operations.
    Requires DEV_DATABASE_URL (or explicit programmatic db_url).
    Refuses to silently fall back to general DATABASE_URL to protect remote databases.
    """
    env_dict = env if env is not None else os.environ

    if db_url:
        target_url = db_url
    elif env_dict.get("DEV_DATABASE_URL"):
        target_url = env_dict.get("DEV_DATABASE_URL")
    else:
        raise RuntimeError(
            f"REFUSED: {caller_name} requires a dedicated development database URL (DEV_DATABASE_URL). "
            "To prevent accidental remote database destruction, destructive scripts will not silently fall back "
            "to the general DATABASE_URL. Please set DEV_DATABASE_URL with a local database "
            "(e.g. postgresql://postgres:postgres@localhost:5432/brewco_dev)."
        )

    validate_local_database_host(target_url, caller_name=caller_name)
    return target_url


def check_reset_safeguards(argv=None, env=None, db_url=None):
    """
    Validates environment, confirmation, and database target before permitting reset.
    Fails closed on ambiguous or missing environment configurations.
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
            f"REFUSED: Destructive reset cannot run in production (APP_ENV={app_env!r}). "
            "Data loss prevention safeguard active."
        )

    if app_env not in ALLOWED_DEV_ENVIRONMENTS:
        raise RuntimeError(
            f"REFUSED: Environment {app_env!r} is not an authorized development environment. "
            "Destructive operations require APP_ENV='development'."
        )

    # 2. Explicit Confirmation Guard
    confirm_flag = "--confirm-destructive-reset" in args
    confirm_env = env_dict.get("CONFIRM_DESTRUCTIVE_RESET", "").lower() in ("true", "1", "yes")

    if not (confirm_flag or confirm_env):
        raise RuntimeError(
            "REFUSED: Destructive database reset requires explicit confirmation. "
            "Pass '--confirm-destructive-reset' on the command line or set "
            "CONFIRM_DESTRUCTIVE_RESET=true in your environment."
        )

    # 3. Database URL & Local Host Validation
    return resolve_destructive_db_url(db_url=db_url, env=env_dict, caller_name="Destructive reset")


async def reset_database(db_url: str = None, argv=None, env=None):
    """Executes destructive table drop in reverse dependency order after all safeguards pass."""
    target_url = check_reset_safeguards(argv=argv, env=env, db_url=db_url)

    print("Connecting to local development database for reset...")
    conn = await asyncpg.connect(target_url)
    try:
        # Tables dropped in reverse foreign-key dependency order
        drop_statements = [
            "DROP TABLE IF EXISTS communications CASCADE;",
            "DROP TABLE IF EXISTS campaigns CASCADE;",
            "DROP TABLE IF EXISTS segments CASCADE;",
            "DROP TABLE IF EXISTS orders CASCADE;",
            "DROP TABLE IF EXISTS customers CASCADE;",
        ]
        for stmt in drop_statements:
            await conn.execute(stmt)

        print("Development database reset complete: All tables dropped cleanly.")
    finally:
        await conn.close()


if __name__ == "__main__":
    try:
        asyncio.run(reset_database())
    except RuntimeError as e:
        print(f"\n[ERROR] {e}\n", file=sys.stderr)
        sys.exit(1)
