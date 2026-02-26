ALTER TABLE NIFTY_OC_HISTORICAL 
MODIFY COLUMN ce_volume BIGINT,
MODIFY COLUMN pe_volume BIGINT,
MODIFY COLUMN ce_oi BIGINT,
MODIFY COLUMN pe_oi BIGINT;

SELECT * FROM analyzer_db.nifty_oc_historical;
Delete  FROM analyzer_db.nifty_oc_historical;
TRUNCATE TABLE analyzer_db.nifty_oc_historical;

ALTER TABLE NIFTY_OC_HISTORICAL 
ADD COLUMN OI_Diff INT AS (CE_OI - PE_OI) VIRTUAL;

ALTER TABLE NIFTY_OC_HISTORICAL 
ADD COLUMN ce_signal VARCHAR(50), 
ADD COLUMN pe_signal VARCHAR(50);

SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'NIFTY_OC_HISTORICAL'
  AND table_schema = 'analyzer_db'; -- Optional: Use if you have multiple schemas
  
SELECT * FROM analyzer_db.nifty_oc_historical 
WHERE Strike_price = 25450 
AND time IN ("09:15:00", "09:18:00");

SELECT * FROM analyzer_db.nifty_oc_historical 
WHERE Strike_price = 25450;


SELECT *
FROM analyzer_db.nifty_oc_historical 
WHERE time BETWEEN "09:15:00" AND "10:30:00" AND Strike_price = 24450
GROUP BY ce_oi;

SELECT * FROM analyzer_db.nifty_oc_historical 
GROUP BY Strike_price;
