-- PostgreSQL Schema for FX Trading Data Pipeline
-- Creates 6 tables for OHLC data, volatility metrics, correlations, and session tracking

-- 1. OHLC Candles Table (Hourly data, 1-year retention)
CREATE TABLE IF NOT EXISTS oanda_candles (
    id BIGSERIAL PRIMARY KEY,
    instrument VARCHAR(20) NOT NULL,
    time TIMESTAMP NOT NULL,
    granularity VARCHAR(5) NOT NULL DEFAULT 'H1',

    -- Bid prices
    open_bid DECIMAL(10,5),
    high_bid DECIMAL(10,5),
    low_bid DECIMAL(10,5),
    close_bid DECIMAL(10,5),

    -- Ask prices
    open_ask DECIMAL(10,5),
    high_ask DECIMAL(10,5),
    low_ask DECIMAL(10,5),
    close_ask DECIMAL(10,5),

    -- Mid prices (for convenience)
    open_mid DECIMAL(10,5),
    high_mid DECIMAL(10,5),
    low_mid DECIMAL(10,5),
    close_mid DECIMAL(10,5),

    -- Metadata
    volume INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT unique_candle UNIQUE(instrument, time, granularity)
);

-- 2. Volatility Metrics Table (Hourly calculations)
CREATE TABLE IF NOT EXISTS volatility_metrics (
    id BIGSERIAL PRIMARY KEY,
    instrument VARCHAR(20) NOT NULL,
    time TIMESTAMP NOT NULL,

    -- Volatility metrics
    volatility_20 DECIMAL(10,6),          -- 20-period Historical Volatility
    volatility_50 DECIMAL(10,6),          -- 50-period Historical Volatility

    -- Moving Averages
    sma_15 DECIMAL(10,5),                 -- 15-period SMA
    sma_30 DECIMAL(10,5),                 -- 30-period SMA
    sma_50 DECIMAL(10,5),                 -- 50-period SMA

    -- Bollinger Bands
    bb_upper DECIMAL(10,5),               -- Upper band
    bb_middle DECIMAL(10,5),              -- Middle band (SMA)
    bb_lower DECIMAL(10,5),               -- Lower band

    -- Other metrics
    atr DECIMAL(10,5),                    -- Average True Range (14-period)

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT unique_volatility UNIQUE(instrument, time)
);

-- 3. Correlation Matrix Table (Daily or less frequent)
CREATE TABLE IF NOT EXISTS correlation_matrix (
    id BIGSERIAL PRIMARY KEY,
    pair1 VARCHAR(20) NOT NULL,
    pair2 VARCHAR(20) NOT NULL,
    time TIMESTAMP NOT NULL,

    -- Correlation value (-1.0 to 1.0)
    correlation DECIMAL(5,3),

    -- Window size used for calculation
    window_size INT DEFAULT 100,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT unique_correlation UNIQUE(pair1, pair2, time),
    CONSTRAINT pair_order CHECK (pair1 < pair2)  -- Ensure consistent ordering
);

-- 4. Best Pairs Tracker Table (Derived from correlation matrix)
CREATE TABLE IF NOT EXISTS best_pairs_tracker (
    id BIGSERIAL PRIMARY KEY,
    time TIMESTAMP NOT NULL,

    pair1 VARCHAR(20) NOT NULL,
    pair2 VARCHAR(20) NOT NULL,
    correlation DECIMAL(5,3),

    -- Category based on correlation
    category VARCHAR(50),                  -- 'uncorrelated', 'negatively_correlated', 'hedging'
    reason TEXT,

    -- Ranking within category
    rank INT,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 5. Real-time Prices Audit Table (24-hour rolling buffer)
CREATE TABLE IF NOT EXISTS real_time_prices_audit (
    id BIGSERIAL PRIMARY KEY,
    instrument VARCHAR(20) NOT NULL,

    bid DECIMAL(10,5),
    ask DECIMAL(10,5),
    mid DECIMAL(10,5),

    timestamp TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_instrument_time (instrument, timestamp)
);

-- 6. Market Sessions Configuration Table (Static data)
CREATE TABLE IF NOT EXISTS market_sessions (
    id SERIAL PRIMARY KEY,
    session_name VARCHAR(50) NOT NULL UNIQUE,

    open_utc TIME NOT NULL,
    close_utc TIME NOT NULL,

    timezone VARCHAR(50),
    description TEXT,

    is_active BOOLEAN DEFAULT TRUE,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 7. Cron Job Execution Log
CREATE TABLE IF NOT EXISTS cron_job_log (
    id BIGSERIAL PRIMARY KEY,
    job_name VARCHAR(100) NOT NULL,

    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP,

    duration_seconds INT,
    status VARCHAR(20),                    -- 'success', 'failed', 'running'

    error_message TEXT,
    records_processed INT,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Insert default market sessions
INSERT INTO market_sessions (session_name, open_utc, close_utc, timezone, description, is_active)
VALUES
    ('Tokyo', '00:00:00'::time, '08:00:00'::time, 'Asia/Tokyo', 'Asian Session', TRUE),
    ('London', '08:00:00'::time, '16:00:00'::time, 'Europe/London', 'European Session', TRUE),
    ('NewYork', '13:00:00'::time, '21:00:00'::time, 'America/New_York', 'American Session', TRUE),
    ('Sydney', '22:00:00'::time, '06:00:00'::time, 'Australia/Sydney', 'Sydney Session', TRUE)
ON CONFLICT (session_name) DO NOTHING;

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_oanda_candles_instrument_time ON oanda_candles(instrument, time DESC);
CREATE INDEX IF NOT EXISTS idx_oanda_candles_time ON oanda_candles(time DESC);
CREATE INDEX IF NOT EXISTS idx_volatility_metrics_instrument_time ON volatility_metrics(instrument, time DESC);
CREATE INDEX IF NOT EXISTS idx_volatility_metrics_time ON volatility_metrics(time DESC);
CREATE INDEX IF NOT EXISTS idx_correlation_time ON correlation_matrix(time DESC);
CREATE INDEX IF NOT EXISTS idx_best_pairs_time ON best_pairs_tracker(time DESC);
CREATE INDEX IF NOT EXISTS idx_real_time_prices_instrument ON real_time_prices_audit(instrument);
CREATE INDEX IF NOT EXISTS idx_cron_job_log_name ON cron_job_log(job_name);

-- Create views for common queries
CREATE OR REPLACE VIEW v_latest_candles AS
SELECT DISTINCT ON (instrument)
    instrument,
    time,
    open_mid,
    high_mid,
    low_mid,
    close_mid,
    volume
FROM oanda_candles
ORDER BY instrument, time DESC;

CREATE OR REPLACE VIEW v_latest_volatility AS
SELECT DISTINCT ON (instrument)
    instrument,
    time,
    volatility_20,
    volatility_50,
    sma_15,
    sma_30,
    atr
FROM volatility_metrics
ORDER BY instrument, time DESC;

-- Grant permissions (optional - adjust as needed)
-- GRANT SELECT ON ALL TABLES IN SCHEMA public TO fx_read_user;
-- GRANT INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO fx_write_user;

-- Show table summary
SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
FROM pg_tables
WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
