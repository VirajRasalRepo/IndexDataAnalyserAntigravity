DROP TABLE IF EXISTS MARKET_WATCH_WIDE;

CREATE TABLE MARKET_WATCH_WIDE (
    id INT AUTO_INCREMENT PRIMARY KEY,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    india_vix DECIMAL(10, 2),
    nifty_50 DECIMAL(10, 2),
    
    -- Heavyweights with Weightages in column names
    reliance_n9_5_s11_5 DECIMAL(10, 2),
    hdfc_bank_n10_s12 DECIMAL(10, 2),
    icici_bank_n7_5_s9 DECIMAL(10, 2),
    infosys_n5_5_s6_5 DECIMAL(10, 2),
     tcs_n4_s4_8 DECIMAL(10, 2),
    itc_n4_5_s5 DECIMAL(10, 2),
   
    lAt_n3_8_s4_2 DECIMAL(10, 2)
);
select * from analyzer_db.market_watch_wide;
Delete  FROM analyzer_db.market_watch_wide;
TRUNCATE TABLE analyzer_db.market_watch_wide;