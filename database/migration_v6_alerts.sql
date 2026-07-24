-- Migration v6: Price-drop alerts table
-- Apply with:
--   python -c "
--   import os; from dotenv import load_dotenv; import psycopg2
--   load_dotenv()
--   conn = psycopg2.connect(host=os.getenv('DB_HOST','localhost'), port=int(os.getenv('DB_PORT','5432')), dbname=os.getenv('DB_NAME','pc_comparison'), user=os.getenv('DB_USER','postgres'), password=os.getenv('DB_PASSWORD',''))
--   conn.autocommit = True
--   cur = conn.cursor()
--   cur.execute(open('database/migration_v6_alerts.sql').read())
--   print('Done!')
--   conn.close()
--   "

CREATE TABLE IF NOT EXISTS alerts (
    id               SERIAL PRIMARY KEY,
    device_id        TEXT        NOT NULL,   -- client-generated UUID, stored in localStorage
    product_id       INTEGER     NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    target_price     NUMERIC     NOT NULL,   -- alert fires when current price <= this
    triggered        BOOLEAN     NOT NULL DEFAULT FALSE,
    last_notified_at TIMESTAMPTZ,            -- when the alert last fired
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (device_id, product_id)           -- one alert per device per product
);

-- Index for fast lookup by device and for scheduler evaluation
CREATE INDEX IF NOT EXISTS idx_alerts_device_id   ON alerts (device_id);
CREATE INDEX IF NOT EXISTS idx_alerts_product_id  ON alerts (product_id);
CREATE INDEX IF NOT EXISTS idx_alerts_triggered   ON alerts (triggered) WHERE triggered = FALSE;

COMMENT ON TABLE alerts IS
    'User price-drop alerts. No auth system — keyed by client-generated device_id stored in localStorage. '
    'The scheduler evaluates untriggered alerts after each scrape cycle.';
