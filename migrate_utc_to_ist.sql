-- ============================================================
-- One-time migration: Convert existing UTC timestamps to IST
-- Run this ONCE on both VM and local MySQL databases
-- ============================================================

USE analyzer_db;

-- market_feed_realtime: timestamp column stored as UTC → add 5:30
-- This is the main table affected since it uses CURRENT_TIMESTAMP / NOW(3)
UPDATE market_feed_realtime
SET timestamp = DATE_ADD(timestamp, INTERVAL 330 MINUTE)
WHERE timestamp IS NOT NULL;

SELECT
    'market_feed_realtime' as table_name,
    COUNT(*) as rows_updated,
    MIN(timestamp) as earliest,
    MAX(timestamp) as latest
FROM market_feed_realtime;

-- Verify: timestamps should now be in IST range (09:15 - 15:30 for market hours)
SELECT 'Migration complete. Verify timestamps are in IST (09:xx - 15:xx for market data).' as Status;
