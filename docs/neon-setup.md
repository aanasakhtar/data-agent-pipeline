# Neon Setup (Manual — do this yourself, then report back)

Neon hosts the synthetic "customer source" Postgres database that Airbyte Cloud will
pull from, exactly as it would pull from a real customer's database.

## Steps

1. Go to https://neon.tech and sign up (GitHub or email — no credit card required for
   the free tier).
2. Create a new project. Any region is fine; name it e.g. `customer-platform-demo`.
3. Neon creates a default database (usually `neondb`) and gives you a **connection
   string** on the project dashboard — it looks like:
   ```
   postgresql://<user>:<password>@<endpoint>.neon.tech/neondb?sslmode=require
   ```
4. Copy that connection string.
5. Make sure the connection is **not** restricted to specific IPs (Neon's free tier
   defaults to open access, which is what Airbyte Cloud needs — Airbyte connects from
   its own infrastructure, not your machine).

## What to hand back to Claude

- The full connection string (or paste it directly into a local `.env` as
  `DATABASE_URL=...` — never commit it).

Once you have this, Claude can run `data-source/generator/load_to_postgres.py`
immediately — no further manual steps needed for this part.

## What Airbyte will need later (same info, different form)

When configuring the Postgres **source** in Airbyte Cloud (see `docs/airbyte-runbook.md`),
you'll enter the same connection details split into fields: host, port (5432), database
name, username, password, and SSL mode = require.
