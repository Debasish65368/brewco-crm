-- =============================================================================
-- BrewCo CRM — Development-Only Destructive Reset Script
-- =============================================================================
-- WARNING: This script drops all CRM tables and permanently destroys all data.
-- NEVER execute this against a production or persistent database.
--
-- Note on DDL ordering:
-- Tables are dropped with CASCADE in reverse foreign-key dependency order
-- (communications -> campaigns -> segments -> orders -> customers).
-- No DELETE statements are executed after tables are dropped.
-- Preflight Safeguard:
-- The script validates via inet_server_addr() that it is connected to a verified local
-- loopback host (127.0.0.1 / ::1) over TCP and aborts immediately if executed
-- against a remote host or if the server address is NULL (unverified).
--
-- Usage:
--   psql $DEV_DATABASE_URL < backend/scripts/reset_dev_db.sql
-- =============================================================================

-- Preflight guard: Refuse execution if server address cannot be verified or is not local loopback
DO $$
DECLARE
    server_ip inet;
BEGIN
    server_ip := inet_server_addr();
    IF server_ip IS NULL OR (server_ip != '127.0.0.1'::inet AND server_ip != '::1'::inet) THEN
        RAISE EXCEPTION 'REFUSED: Direct SQL reset requires verified local loopback connection (127.0.0.1 or ::1). Detected server address: %. Destructive reset cannot proceed.', COALESCE(server_ip::text, 'NULL (unverified)');
    END IF;
END $$;

DROP TABLE IF EXISTS communications CASCADE;
DROP TABLE IF EXISTS campaigns CASCADE;
DROP TABLE IF EXISTS segments CASCADE;
DROP TABLE IF EXISTS orders CASCADE;
DROP TABLE IF EXISTS customers CASCADE;
