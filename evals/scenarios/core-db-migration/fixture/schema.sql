-- Current production-shaped table (simplified)
CREATE TABLE customers (
  id            BIGINT PRIMARY KEY,
  full_name     TEXT NOT NULL,
  email         TEXT NOT NULL,
  created_at    TIMESTAMP NOT NULL,
  updated_at    TIMESTAMP NOT NULL
);

CREATE INDEX customers_full_name_idx ON customers (full_name);
