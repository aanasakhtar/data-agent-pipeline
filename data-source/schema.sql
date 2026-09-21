-- Synthetic "customer source system" schema.
-- This is what a real customer's operational Postgres database might look like —
-- Airbyte connects to this exactly as it would connect to a real customer.

CREATE TABLE IF NOT EXISTS customers (
    customer_id     INTEGER PRIMARY KEY,
    first_name      TEXT NOT NULL,
    last_name       TEXT NOT NULL,
    email           TEXT NOT NULL UNIQUE,
    phone           TEXT,
    company         TEXT,
    country         TEXT NOT NULL,
    plan_tier       TEXT NOT NULL CHECK (plan_tier IN ('free', 'pro', 'enterprise')),
    status          TEXT NOT NULL CHECK (status IN ('active', 'churned')),
    signup_date     DATE NOT NULL,
    created_at      TIMESTAMP NOT NULL DEFAULT now(),
    updated_at      TIMESTAMP NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS products (
    product_id      INTEGER PRIMARY KEY,
    product_name    TEXT NOT NULL,
    category        TEXT NOT NULL,
    unit_price      NUMERIC(10, 2) NOT NULL,
    created_at      TIMESTAMP NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS orders (
    order_id        INTEGER PRIMARY KEY,
    customer_id     INTEGER NOT NULL REFERENCES customers(customer_id),
    order_date      TIMESTAMP NOT NULL,
    status          TEXT NOT NULL CHECK (status IN ('pending', 'completed', 'cancelled', 'refunded')),
    order_total     NUMERIC(10, 2) NOT NULL,
    created_at      TIMESTAMP NOT NULL DEFAULT now(),
    updated_at      TIMESTAMP NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS order_items (
    order_item_id   INTEGER PRIMARY KEY,
    order_id        INTEGER NOT NULL REFERENCES orders(order_id),
    product_id      INTEGER NOT NULL REFERENCES products(product_id),
    quantity        INTEGER NOT NULL CHECK (quantity > 0),
    unit_price      NUMERIC(10, 2) NOT NULL,
    line_total      NUMERIC(10, 2) NOT NULL
);

CREATE TABLE IF NOT EXISTS support_tickets (
    ticket_id       INTEGER PRIMARY KEY,
    customer_id     INTEGER NOT NULL REFERENCES customers(customer_id),
    order_id        INTEGER REFERENCES orders(order_id),
    priority        TEXT NOT NULL CHECK (priority IN ('low', 'medium', 'high')),
    status          TEXT NOT NULL CHECK (status IN ('open', 'in_progress', 'closed')),
    category        TEXT NOT NULL,
    csat_score      INTEGER CHECK (csat_score BETWEEN 1 AND 5),
    created_at      TIMESTAMP NOT NULL,
    resolved_at     TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_orders_customer_id ON orders(customer_id);
CREATE INDEX IF NOT EXISTS idx_order_items_order_id ON order_items(order_id);
CREATE INDEX IF NOT EXISTS idx_order_items_product_id ON order_items(product_id);
CREATE INDEX IF NOT EXISTS idx_support_tickets_customer_id ON support_tickets(customer_id);
