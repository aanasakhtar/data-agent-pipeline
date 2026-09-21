# Architecture Upgrades — What We Borrowed and Applied

Direct follow-through on `docs/competitive-landscape.md`'s recommendation:
don't rebuild L1-L6's semantic/evidence machinery from scratch when mature
patterns already exist — borrow the patterns, keep our own execution layer
(dbt on DuckDB, zero cost). Three concrete additions, each traced to a real
product:

## 1. Semantic model (`registry/semantic_model.yml`) — from Wren AI's MDL

Before: each `MetricContract` hardcoded its own `gold_fields` and inline SQL
joins, so every new metric re-derived "what a Customer/Order/SupportTicket
is" from scratch. Wren AI's MDL principle — "encode your domain knowledge
once, map high-level concepts to underlying tables/columns" — is now a
single file. `Customer`, `Order`, `SupportTicket` are defined once, with
their physical mapping and a `metrics:` section for reusable, standardized
definitions like `order_straight_through_rate`.

## 2. Verified Query Repository (`registry/verified_queries/`) — from Snowflake Cortex Analyst

Before: L6 (evidence-current-state) re-derived and re-ran a query with no
record that it had ever been checked before; L10 verified it fresh every
single run with no memory of past verifications. Cortex Analyst's Verified
Query Repository pattern (name/question/sql/verified_at/verified_by) is now
`registry/verified_queries/order_straight_through_rate.yml`, seeded with the
two queries this repo's pilot run (`docs/claimb-pilot-run.md`) already
proved correct. `kpi-metric-resolution` and `evidence-current-state` now
check this file first; `verification-adversarial-review` writes to it on a
`PASS`. This is also, functionally, the start of CLaiMB's own "golden
evaluation set" (architecture doc section 14.1) — every verified query
becomes a regression test for free.

## 3. Ontology object/link graph (`registry/ontology_objects.yml`) — from Palantir AIP

Before: relationships (Order→SupportTicket, Order→Customer, etc.) existed
only implicitly, inside whatever JOIN a skill happened to write. Palantir
AIP's rule — agents traverse ontology-exposed objects and link types, never
raw tables directly — is now an explicit object/link registry. It also
records what's deliberately *not* modeled (no Actor/Agent type, no
Document/Text type) so a skill can't quietly assume a relationship exists
that the synthetic schema doesn't actually support.

## What changed in the skills

- `.claude/skills/kpi-metric-resolution/SKILL.md` — now resolves terms
  through the semantic model and reuses verified queries before writing new
  SQL from scratch.
- `.claude/skills/evidence-current-state/SKILL.md` — now checks the
  verified query repository before re-deriving a query.
- `.claude/skills/verification-adversarial-review/SKILL.md` — now writes a
  newly-verified query into the repository on `PASS`, so verification's cost
  (see `docs/claimb-idea-fit.md` section 3) buys something durable instead
  of being paid fresh every run.

## Effect on the earlier cost question

This directly narrows the open cost question from `docs/claimb-idea-fit.md`:
once a query is verified once, L6 and L10 on a *repeat* run of the same
metric are cheap lookups against a YAML file instead of full re-derivation
and re-verification. The real cost is concentrated in the *first* time a
metric is measured — which is exactly where a vertical-slice pilot (already
done, see `docs/claimb-pilot-run.md`) should focus when costing this out for real.

## What's still not done

- `registry/metric_registry/order_straight_through_rate.json` has been
  updated to point at both new registries (`semantic_model_ref`,
  `verified_query_ref`) but the actual retrieval logic (a skill reading
  `semantic_model.yml`/`verified_queries/*.yml` programmatically rather than
  a human/Claude reading it by eye) is still manual — there's no MDL-style
  compiler or a Cortex-Analyst-style API here, just plain files a skill is
  instructed to consult. That's the right amount of machinery for a
  free, local pilot; a real implementation would want this enforced in
  code, not just in a skill's instructions.
