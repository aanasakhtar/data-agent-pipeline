# Deep Research: How Good Can This Get — Finding Real AI-Adoption Gaps

The ask: can this pipeline find genuine gaps in a customer's data around
*where AI is and isn't being used*, run deep cross-entity queries, build
real relationships, discover process, and assess overall performance —
not just answer a single KPI question. This is research into the state of
the art for exactly that job, plus one concrete proof-of-upgrade against
our own pilot data.

## Part 1 — What "as good as it gets" actually looks like today

Three distinct disciplines converge on this problem, and each has a mature
answer we should borrow from, on top of what `docs/competitive-landscape.md`
already found (NL-to-SQL engines, Palantir's Ontology):

### 1. Object-centric process mining — the "build relations, find process" piece

**[Celonis's Process Intelligence Graph](https://www.celonis.com/blog/celonis-process-intelligence-graph-provides-a-common-language-for-enterprise-process-performance)**
is the clearest answer to "how connected data becomes a process view."
Instead of a hand-declared schema of objects and relationships (which is
all `registry/ontology_objects.yml` currently is), Celonis *mines* a
knowledge graph directly from event logs across systems — it discovers
which objects (invoices, orders, tickets) actually interacted, in what
order, at what frequency, not just what a schema says is *possible*. Their
own framing: this becomes "a digital twin of how the business actually
runs," object-centric and system-agnostic.

The academic case for why this matters to AI agents specifically is made
directly in **["No AI Without PI!"](https://arxiv.org/pdf/2508.00116)**
(object-centric process mining as the enabler for generative/predictive/
prescriptive AI): pure LLM/data agents "lack understanding of how work
actually flows," can't "distinguish what systems claim happens versus
actual execution," and have "no conformance insights" — meaning they can't
detect deviations or bottlenecks without a discovered process model
underneath them. That is precisely the gap between our current
`operational-diagnosis` skill (a flat segment breakdown: rate by plan_tier)
and something that actually discovers process behavior.

**UiPath's task mining** adds the desktop/action-level layer Celonis
doesn't cover — literal clicks/keystrokes — which is closer to "where is a
human doing something an AI could do" than Celonis's system-log approach.
Not applicable to our synthetic dataset (no desktop telemetry exists), but
worth knowing this is a separate, complementary data source in a real
deployment.

### 2. Adversarial, verification-centric multi-agent diagnosis — the "trust" piece

Two 2026 papers on LLM-based root cause analysis validate the L7/L10 split
in our own architecture, and go further than what we've built:

- **[KRCA](https://arxiv.org/pdf/2607.01788)** (agentic RCA in
  hyper-scale microservices): a layered design — perception agents gather
  data, analysis agents generate hypotheses, **verification agents validate
  against actual system behavior**, with an iterative feedback loop where
  verification results inform the *next* round of analysis, not just a
  pass/fail gate at the end. Our current L10 does the pass/fail gate; we
  don't yet close the loop by feeding a rejection's specific reason back
  into a targeted re-analysis (the CLaiMB doc's own "targeted retry"
  concept — this is real precedent for building it, not just following
  the spec.)
- **[Reasoning about Multi-hop Fault Propagation with LLM Agents](https://conf.researchr.org/details/forge-2026/forge-2026-papers/15/)**
  and Microsoft Research's **[Exploring LLM-Based Agents for RCA](https://arxiv.org/html/2403.04123v1)**
  both flag the same failure mode: LLMs "are not able to dynamically
  collect additional diagnostic information" and are "susceptible to
  hallucinations" when reasoning chains get long. The fix both point to is
  exactly what CLaiMB's L10 and our `evidence-current-state` skill already
  do — ground every claim in a re-executable query against real data,
  never let the model assert a number from memory.

### 3. AI-maturity/adoption-gap scoring — the "how much AI isn't being used" piece

This is the part our L8 (`ai-opportunity-assessment`) currently under-models.
Gartner's AI Maturity Model scores organizations across **7 dimensions**
(strategy, value, organization, people & culture, governance, engineering,
data) — our current `AIOpportunityRecord` only scores *task*
characteristics (repeatability, determinism, etc.), with no dimension for
whether the *organization* is actually positioned to adopt a fix even if
the task is a good fit. The market data backs up why this matters: there's
a documented **49-point gap between 80% of enterprises embedding an agent
somewhere and only 31% running one in production**, and only **8.4% say
their data is trustworthy enough for production AI** — meaning most
real-world "AI opportunity" assessments fail not on task-suitability but on
organizational/data readiness, which is exactly the dimension we're
currently missing. The academic **[AI Transformation Gap Index (AITG)](https://arxiv.org/pdf/2603.13278)**
formalizes this at industry/firm level (opportunity, disruption risk, and
value creation as three separate scored axes) — a more rigorous structure
than our current single `ai_fit` string field.

## Part 2 — Proof: applying this to our own pilot data, right now

Ran a real object-centric-style case-trace query against `dev.duckdb`
(no cost, ~1 second) instead of the flat segment breakdown from
`docs/claimb-pilot-run.md`: classify every completed order + its linked
ticket lifecycle into a discovered process variant.

| Variant | Orders | % of completed | Avg resolution time |
| --- | --- | --- | --- |
| V1 — straight-through (no ticket) | 873 | 90.09% | n/a |
| V2 — resolved well (CSAT ≥ 4) | 45 | 4.64% | 2,671 hrs |
| **V4 — unresolved risk** | **40** | **4.13%** | n/a (still open) |
| V3 — resolved poorly (CSAT < 3) | 6 | 0.62% | 8,833 hrs |
| V2b — resolved, neutral CSAT | 5 | 0.52% | 11,359 hrs |

**This found something the flat rate metric hid.** `docs/claimb-pilot-run.md`
reported one number (90.47% straight-through) and one diagnosis that turned
out to be noise (the plan-tier segment difference). This case-trace pass
surfaces **V4: 40 orders (4.13%) marked "completed" while their linked
support ticket is still open or in progress** — a real, directly measured
process gap (orders being closed out while a customer issue is
unresolved), not a hypothesis. It also flags the two multi-hundred-day
average resolution times as *probably* a synthetic-data generation artifact
rather than a real pattern — stated as a caveat, not asserted either way.
Full record: `artifacts/diagnostics/process_variant_analysis.json`.

This is a concrete, working demonstration of the "No AI Without PI"
argument: the process-variant view found a real, actionable gap; the
flat-rate view didn't.

## Part 3 — Gap analysis: where we stand vs. state of the art

| Capability | State of the art | This repo today | Gap |
| --- | --- | --- | --- |
| Relationship discovery | Mined from event logs (Celonis PI Graph) | Hand-declared in `registry/ontology_objects.yml` | We declare what's possible; we don't yet discover what actually happened, in what order, how often |
| Process/case analysis | Full process discovery, variant mining, conformance checking | One-off case-trace query, run manually (Part 2 above) | Real but not systematized as a reusable skill step yet |
| Verification loop | Iterative: rejection reason feeds targeted re-analysis (KRCA) | Pass/fail gate; retry loop described in the CLaiMB spec but not actually implemented in `.claude/skills/verification-adversarial-review/` | The retry loop is designed, not built |
| AI-opportunity scoring | Multi-dimensional: task fit + org readiness + data trust (Gartner 7-category, AITG) | Task-characteristics only (`AIOpportunityRecord.task_characteristics`) | Missing an organizational/data-readiness axis entirely |
| Cross-entity deep queries | Object-centric graph traversal across arbitrary object types | Fixed joins per metric, defined per `MetricContract` | Works for known metrics; doesn't generalize to "explore what's connected to what" on demand |

## Part 4 — Recommended next slice (not yet built)

In priority order, each buildable free/local against this same dataset:

1. **Turn Part 2's one-off query into a real skill step.** Add a
   "process-variant discovery" step to `.claude/skills/operational-diagnosis/SKILL.md`
   as a standard diagnostic family, not a one-off — it already proved more
   useful than the segment-breakdown families currently listed there.
2. **Add an organizational-readiness dimension to L8.** Extend
   `AIOpportunityRecord.task_characteristics` with a parallel
   `data_readiness`/`org_readiness` score (borrowing Gartner's
   strategy/governance/data categories), so a task can be a great technical
   fit but still correctly score low overall if the surrounding data/org
   isn't ready — matching what the market data says actually blocks AI
   adoption.
3. **Close the verification retry loop for real.** Currently
   `verification-adversarial-review` describes a `REJECT` → retry pattern
   but nothing in this repo has ever exercised it. Deliberately inject one
   bad artifact and run the actual retry, per KRCA's iterative-feedback
   pattern, to prove the loop (not just the intent) works.
4. **Generalize relationship traversal beyond fixed MetricContracts.** A
   true object-centric layer would let a skill ask "what's connected to
   Order X" and get an answer from the ontology graph, not require a new
   hand-written JOIN per question. Worth prototyping once there's a second
   real metric to test generalization against — one metric isn't enough
   signal to design a general traversal API around yet.

## Sources

- [Celonis Process Intelligence Graph](https://www.celonis.com/blog/celonis-process-intelligence-graph-provides-a-common-language-for-enterprise-process-performance)
- ["No AI Without PI!" — Object-Centric Process Mining as AI Enabler (arXiv 2508.00116)](https://arxiv.org/pdf/2508.00116)
- [KRCA: Agentic RCA in hyper-scale microservices (arXiv 2607.01788)](https://arxiv.org/pdf/2607.01788)
- [Reasoning about Multi-hop Fault Propagation with LLM Agents (FORGE 2026)](https://conf.researchr.org/details/forge-2026/forge-2026-papers/15/)
- [Exploring LLM-Based Agents for Root Cause Analysis (Microsoft Research / arXiv 2403.04123)](https://arxiv.org/html/2403.04123v1)
- [Gartner AI Maturity Model and Roadmap Toolkit](https://www.gartner.com/en/chief-information-officer/research/ai-maturity-model-toolkit)
- [The AI Transformation Gap Index (AITG) (arXiv 2603.13278)](https://arxiv.org/pdf/2603.13278)
- [Enterprise AI Agent Adoption market data — 49-point production gap](https://www.digitalapplied.com/blog/ai-agent-adoption-2026-enterprise-data-points)
- [Enterprise AI Agents Face a Data Trust Problem](https://techedgeai.com/enterprise-ai-adoption-is-outpacing-the-data-foundations-behind-it/)
- [Celonis vs UiPath process/task mining comparison](https://scribe.com/library/celonis-vs-uipath)
