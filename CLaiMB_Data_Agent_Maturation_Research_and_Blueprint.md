# CLaiMB Data Agent — Maturation Research and Engineering Blueprint

## Executive assessment

The CLaiMB Data Agent should not be matured by adding more LLM layers. The current repository already has the important conceptual ingredients: a governed medallion foundation, a KPI contract, deterministic evidence, diagnostic reasoning, AI-suitability refusal, benchmark suppression, verification, and synthesis. The main maturity problem is that the reasoning chain is still primarily expressed as agent skills and documentation rather than as an executable runtime with enforceable isolation, typed contracts, reproducibility, and measured failure behavior.

The target should therefore be redefined from “100% flawless” to **bounded, measured, reproducible, and safely degrading**. A production-ready run should either produce a finding whose material claims are independently reproducible and provenance-complete, or stop at `NOT_MEASURABLE`, `LOW_CONFIDENCE`, `REJECT`, or `HUMAN_REVIEW`. The architecture itself already adopts this principle: no headline KPI without a MetricContract, no material number without provenance, no causal interpretation without evidence, no AI recommendation without a suitability assessment, and no producer-only verification.

This blueprint is based on the CLaiMB architecture, the current repository handoff and pilot artifacts, the maturation plan, and current public enterprise/academic evidence on process intelligence, semantic data agents, evaluation, AI risk management, and multi-agent verification.

---

## 1. What the current repository proves

The repository’s own handoff reports the following maturity state:

| Area | Current evidence | Meaning |
|---|---|---|
| L1 Bronze | 72/72 dbt tests; re-verified at 100x scale | Strong local data-foundation proof |
| L2 Silver | Typed/conformed entities and SCD2 tested | Strong local proof |
| L3 Gold | Business entities and metrics built; unavailable capabilities explicitly surfaced | Strong but bounded proof |
| L4 Intent | One end-to-end business context | Proven once |
| L5 KPI | One contract and reusable semantic/verified-query infrastructure | Proven once |
| L6 Evidence | Fresh re-execution and query-hash verification | Proven once with independent re-check |
| L7 Diagnosis | Signal/noise behavior demonstrated; process-variant analysis found a real gap in pilot data | Promising but not generalized |
| L8 AI Opportunity | Refusal path works; task suitability is modeled | Missing organizational/data-readiness dimension |
| L9 Benchmark | Suppression path works | Qualification logic not generalized |
| L10 Verification | Re-execution/arithmetic/provenance checks pass | Reject/retry path not exercised |
| L11 Synthesis | One finding produced from verified artifacts | Proven once |

The pilot produced 90.47% straight-through orders (873/965), correctly treated the observed plan-tier spread as low-confidence noise, returned `NO_AI_RECOMMENDATION`, suppressed an unqualified benchmark, and independently re-executed the evidence query before synthesis. citehttps://raw.githubusercontent.com/aanasakhtar/data-agent-pipeline/main/HANDOFF.md

The pilot also explicitly states what is not yet proved: only one metric has traversed the full chain, the reasoning layers have not been exercised as independent runtime invocations with measured token/cost/latency, and the verification retry loop has not been tested under a deliberate failure. citehttps://raw.githubusercontent.com/aanasakhtar/data-agent-pipeline/main/docs/claimb-pilot-run.md

A second repository analysis found a process-variant signal missed by the flat KPI view: 40 completed orders (4.13%) had linked support tickets that were still open or in progress. The same analysis identifies process discovery, iterative verification feedback, and organizational/data readiness as the major capability gaps. citehttps://raw.githubusercontent.com/aanasakhtar/data-agent-pipeline/main/docs/deep-research-ai-adoption-gaps.md

---

## 2. The core architectural problem to solve first

The strongest issue identified in the maturation plan is not an analytical limitation. It is an **enforcement problem**.

The CLaiMB architecture says that the orchestration layer should route typed artifacts, that the verifier should be isolated from producer reasoning, and that synthesis should not have source-data access. The current repository expresses these restrictions mostly through `.claude/skills/*/SKILL.md` instructions. The verification skill itself says it must independently re-derive claims, but the current model of execution is still compatible with one continuous Claude Code context that has already seen the producer’s answer.

That means an invariant such as “the verifier must not see the producer’s reasoning” is not yet a system property. It is a prompt rule.

### Required architectural change

Keep the logical 11-layer design, but make each L4–L11 invocation an **explicit runtime job**:

```text
Customer context
      |
      v
L4 Job -> BusinessFunctionContext
      |
      v
L5 Job -> MetricContract
      |
      v
L6 Deterministic Job -> EvidenceBundle
      |
      +---- Evidence Gate ----------------------+
      |                                           |
      v                                           |
L7 Job -> DiagnosticRecord                        |
      |                                           |
      v                                           |
L8 Job -> AIOpportunityRecord                     |
      |                                           |
      v                                           |
L9 Job -> BenchmarkRecord / FrameworkEvidence    |
      |                                           |
      +---- Release Verification Plane <---------+
                     |
                     v
              L10 Verify Job
                     |
          PASS / LOW / REJECT / HUMAN
                     |
                     v
               L11 Synthesis
```

The critical change is that **the model never owns the workflow state**. The orchestrator owns state, permissions, routing, retries, and release decisions.

---

## 3. What should remain deterministic vs. agentic

A common failure mode is to interpret “agentic architecture” as “put an LLM in every layer.” That would add cost and failure surface without increasing CLaiMB’s trustworthiness.

### Keep deterministic

- Bronze ingestion and source manifests
- Silver transformations
- Gold construction
- Metric computation
- Query execution
- Query hashing
- Arithmetic/value calculations
- Thresholds and minimum sample checks
- Provenance validation
- Schema validation
- Tenant scoping
- Permission enforcement
- Retry counters/state transitions
- Narrative numeric-integrity checking

### Use LLM reasoning where it adds value

- Business intent interpretation
- Semantic KPI resolution
- Hypothesis generation for diagnosis
- AI suitability assessment
- Framework/context retrieval and interpretation
- Executive wording
- Semantic contradiction analysis

The public enterprise pattern supports this separation. Snowflake uses verified natural-language/SQL pairs as trusted examples and evaluation ground truth; Databricks uses curated metadata, example SQL, semantic expressions, trusted assets, and benchmark questions; Microsoft Fabric describes explicit orchestration and source routing when multiple data sources are involved. citehttps://docs.snowflake.com/en/user-guide/views-semantic/verified-query-repositoryhttps://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-analyst-evaluationshttps://docs.databricks.com/aws/en/genie-agents/conceptshttps://learn.microsoft.com/en-us/fabric/data-science/data-agent-routing

---

## 4. The mature CLaiMB execution model

### 4.1 Every handoff is an artifact boundary

Each layer receives only a typed artifact and the minimum authorized context required for its responsibility.

Example:

```text
L5 input
  BusinessFunctionContext
  Gold semantic registry
  Framework definitions

L5 output
  MetricContract
```

L6 then consumes the `MetricContract` plus authorized Gold access. It should not receive the raw business conversation unless an explicit field is carried in the contract.

The verifier consumes the candidate record, the MetricContract, the evidence/source access needed to independently reproduce it, and the verifier policy. It does **not** receive the producer’s hidden reasoning trace, intermediate scratchpad, or “expected answer.”

### 4.2 Capability-scoped tools

The runtime should enforce permissions using:

```text
agent identity
+ tool allowlist
+ view/schema permissions
+ artifact permissions
+ output schema
```

The architecture already specifies these controls as the intended context-isolation mechanism. fileciteturn2file0L1250-L1288

### 4.3 Separate verifier execution context

For the local prototype, a fresh Python subprocess is enough to prove the principle. For production, L10 should run as an isolated worker/job with its own scoped credentials and no access to the producer session state.

The verifier should receive:

```json
{
  "record_under_test": "...",
  "metric_contract": "...",
  "source_reference": "...",
  "verification_policy": "..."
}
```

It should not receive:

```json
{
  "producer_reasoning": "...",
  "producer_chain_of_thought": "...",
  "expected_value": "..."
}
```

This is consistent with newer research on information-asymmetric checking. MARCH explicitly deprives its checker of the solver’s original output to reduce self-confirmation bias. The practical implication for CLaiMB is stronger than simply “use a second LLM”: **the second evaluator needs information asymmetry**. citehttps://arxiv.org/abs/2603.24579

---

## 5. Verification should become a control plane, not only L10 at the end

The existing architecture places L10 after L9. Keep that logical layer, but implement verification as a **cross-cutting plane**.

### Early deterministic gates

After L5:

- schema-valid MetricContract
- numerator/denominator present
- grain present
- direction present
- target semantics valid
- query template references approved semantic objects

After L6:

- query hash
- result-shape validation
- denominator/sample validation
- range checks
- data-quality checks
- source coverage
- reproducibility check

After L7/L8/L9:

- evidence IDs exist
- causal-status values are valid
- recommendation is linked to a real diagnostic
- benchmark has passed qualification or has explicit suppression
- no new number appears without evidence

### Final adversarial verification

L10 remains the final release authority and runs:

1. semantic contract compliance
2. independent query re-execution
3. arithmetic recomputation
4. data-quality verification
5. benchmark qualification
6. contradiction checking
7. provenance verification
8. synthesis integrity

This follows the existing CLaiMB verification specification. fileciteturn2file0L1077-L1129

It also matches current agent-reliability research. Microsoft’s AgentRx work treats agent trajectories as executable traces and uses guarded constraints to identify the first unrecoverable failure, rather than relying only on an end-of-run success label. KRCA similarly uses a staged diagnosis pipeline with verification feedback rather than a single monolithic reasoning step. citehttps://www.microsoft.com/en-us/research/blog/systematic-debugging-for-ai-agents-introducing-the-agentrx-framework/https://arxiv.org/abs/2607.01788

---

## 6. The most important analytical upgrade: from KPI analysis to process intelligence

CLaiMB’s current Gold ontology is hand-declared and its process-variant analysis has only been demonstrated once. That is the largest analytical gap if the Data Agent must operate across arbitrary business functions.

The correct direction is not “let the LLM inspect more tables.” It is to create an object/process representation that lets the Data Agent reason over:

```text
objects
  Customer
  Order
  Ticket
  Invoice
  Employee
  Claim
  Shipment
  Payment
  Document
  Contract
  ...

relationships
  belongs_to
  linked_to
  creates
  resolves
  approves
  blocks
  follows
  depends_on

events
  created
  submitted
  reviewed
  approved
  rejected
  escalated
  completed
  reopened
```

This is closely aligned with Celonis’s Object-Centric Data Model and Process Intelligence Graph, which connect multiple object types, events and relationships into a process-oriented digital twin. citehttps://www.celonis.com/news/article/celonis-process-intelligence-graph-provides-a-common-language-for-enterprise-process-performance

Academic work by Wil van der Aalst makes the same architectural argument: process intelligence is needed to connect enterprise-specific operational behavior with generative, predictive and prescriptive AI, because text-oriented AI alone does not expose the full structure of how work actually executes. citehttps://arxiv.org/abs/2508.00116

### What this means for CLaiMB

Do not add another LLM layer.

Instead, extend L3/L7 with reusable capabilities:

```text
object discovery
relationship discovery
case construction
variant discovery
conformance analysis
bottleneck analysis
handoff analysis
exception concentration
rework analysis
```

The L7 agent should call these deterministic/process-intelligence modules and reason over their outputs.

---

## 7. KPI resolution should become a formal semantic compiler

The current repository already has the right idea: `semantic_model.yml` acts as the shared source of business meaning, and `ontology_objects.yml` controls allowed relationships. The metric registry and verified-query repository then turn natural language into reusable measurement logic. citehttps://raw.githubusercontent.com/aanasakhtar/data-agent-pipeline/main/registry/semantic_model.ymlhttps://raw.githubusercontent.com/aanasakhtar/data-agent-pipeline/main/.claude/skills/kpi-metric-resolution/SKILL.md

Make this a formal compiler-like flow:

```text
User Goal
   ↓
Concept extraction
   ↓
Business process mapping
   ↓
Metric candidate(s)
   ↓
Semantic-object mapping
   ↓
Numerator / denominator
   ↓
Grain / time window / exclusions
   ↓
Target semantics
   ↓
Executable query
   ↓
Static contract validation
   ↓
MetricContract
```

The agent must be unable to skip from “goal” to “SQL.”

### KPI resolution failure states

The system should explicitly support:

```text
RESOLVED
RESOLVED_WITH_ASSUMPTION
AMBIGUOUS_NEEDS_INPUT
NOT_MEASURABLE
UNSUPPORTED_BY_AVAILABLE_DATA
```

This prevents the common agent failure where “automation” becomes whichever measurable proxy happens to be easiest to query.

---

## 8. Evidence should be the central product primitive

The strongest architectural idea in the CLaiMB design is the EvidenceBundle. Treat it as the principal object passed between agents.

A mature EvidenceBundle should be content-addressed and immutable:

```yaml
EvidenceBundle:
  evidence_id:
  run_id:
  metric_contract_id:
  source_snapshot_ids:
  gold_objects:
  observed_value:
  numerator:
  denominator:
  period:
  grain:
  distribution:
  trend:
  segment_results:
  query:
  query_hash:
  result_hash:
  execution_id:
  freshness:
  quality:
  caveats:
  provenance_chain:
```

The additional `numerator`, `denominator`, `result_hash`, `execution_id`, and `source_snapshot_ids` fields matter because “90.47%” by itself is not enough to reproduce or investigate a claim.

### Claim graph

The final finding should be traceable as:

```text
Finding
  ↓
VerifiedFindingRecord
  ↓
VerificationResult
  ↓
EvidenceBundle
  ↓
MetricContract
  ↓
Executable Query
  ↓
Gold Object / Process Trace
  ↓
Silver Transformation
  ↓
Bronze Snapshot
  ↓
Customer Source
```

The current architecture explicitly defines this provenance chain. fileciteturn2file0L1300-L1333

---

## 9. Diagnostic reasoning should use an evidence taxonomy

The current `causal_status` control is correct. Extend it into a reusable evidence taxonomy:

```text
OBSERVED
  directly computed/measured

ASSOCIATED
  statistically related but not causally established

HYPOTHESIS
  plausible explanation requiring more evidence

SUPPORTED
  multiple independent evidence paths support the explanation

UNVERIFIED
  claim exists but evidence is insufficient
```

A diagnostic module should output a structured causal packet:

```yaml
DiagnosticRecord:
  diagnostic_id:
  category:
  observation:
  affected_process_steps:
  affected_segments:
  evidence_ids:
  supporting_metrics:
  counterevidence_ids:
  interpretation:
  causal_status:
  confidence:
  recommended_next_test:
```

The `counterevidence_ids` field is important. It stops the system from treating evidence collection as a one-way search for support.

Microsoft’s research on LLM agents for root-cause analysis found that tool access enabling dynamic retrieval of incident diagnostics improved factual accuracy over reasoning-only baselines. That supports giving L7 explicit diagnostic tools rather than asking the model to reason from a static context dump. citehttps://www.microsoft.com/en-us/research/publication/exploring-llm-based-agents-for-root-cause-analysis/

---

## 10. AI Opportunity should be two-dimensional: task fit × adoption readiness

The repository already identifies this gap correctly: L8 currently evaluates task characteristics but not the organization/data readiness required to operationalize an AI intervention. citehttps://raw.githubusercontent.com/aanasakhtar/data-agent-pipeline/main/docs/deep-research-ai-adoption-gaps.md

The mature model should separate:

### A. Task / opportunity fit

```text
repeatability
structured inputs
objective evaluation
exception rate
judgment intensity
error consequence
workflow integration
existing automation
```

### B. Adoption readiness

```text
data readiness
system integration readiness
process standardization
human ownership
AI governance readiness
security/privacy constraints
change-management readiness
monitoring/evaluation capability
vendor/platform dependencies
```

This is where NIST AI RMF is useful as a governance overlay rather than as an AI-opportunity score itself. NIST organizes AI risk work around Govern, Map, Measure and Manage and explicitly notes that AI may not be the appropriate solution for every problem. citehttps://www.nist.gov/itl/ai-risk-management-framework/nist-ai-rmf-playbookhttps://airc.nist.gov/airmf-resources/playbook/manage/

### Recommended output

```yaml
AIOpportunityRecord:
  opportunity_id:
  linked_gaps:
  linked_diagnostics:
  process_step:

  task_fit:
    repeatability:
    data_availability:
    determinism:
    exception_rate:
    judgment_intensity:
    error_consequence:
    workflow_integration:
    evaluation_measurability:

  adoption_readiness:
    data_readiness:
    integration_readiness:
    process_readiness:
    governance_readiness:
    people_readiness:
    monitoring_readiness:

  ai_fit:
  readiness:
  risk_profile:
  autonomy_level:
  human_control_points:
  dependencies:
  expected_kpi_impact:
  recommendation_confidence:
```

The agent must retain `NO_AI_RECOMMENDATION` as a first-class valid outcome.

---

## 11. Framework strategy for cross-industry CLaiMB

CLaiMB should **not** create a universal business-process/KPI taxonomy from scratch. Use a small set of external frameworks as adapters around an internal canonical ontology.

### 11.1 APQC PCF — primary cross-industry backbone

APQC describes its PCF as a cross-industry process taxonomy used by hundreds of leading companies and designed to support process comparison, measurement and benchmarking. APQC’s current site exposes version 8.0 and provides definitions and key measures collections. APQC also publishes case studies showing use in organizations including IBM, Philips and Pearson. citeturn547012search0turn547012search7turn916071search1turn916071search2turn916071search6

**Use in CLaiMB:**

```text
BusinessFunction
  → APQC process node
  → internal canonical process node
  → available Gold objects/events
  → applicable KPI candidates
```

Important commercial nuance: APQC's benchmark datasets and some detailed resources may require membership/licensing. IBM's public case study explicitly describes licensing APQC benchmarks for client work. Therefore CLaiMB should treat the PCF taxonomy and public materials separately from any licensed benchmark corpus. citeturn916071search4

### 11.2 SCOR DS — supply-chain overlay

SCOR DS is highly useful for supply-chain use cases because its metric hierarchy explicitly distinguishes strategic metrics, diagnostic metrics and deeper diagnostic levels. Its performance model also connects metrics with processes, practices and maturity. ASCM currently describes SCOR DS as open-access, and public case material documents long-term enterprise use at Ericsson. citeturn850881search48turn850881search3turn916071search48

This is particularly valuable for CLaiMB because the structure:

```text
strategic KPI
  ↓
diagnostic KPI
  ↓
process step
  ↓
practice / technology
```

maps naturally onto L5 → L7 → L8.

### 11.3 NIST AI RMF — AI risk/governance overlay

NIST AI RMF is public and voluntary. Its four functions — Govern, Map, Measure and Manage — make it useful for L8’s readiness/risk logic and for customer-facing AI governance evidence. NIST publicly documents industry use cases, including Workday. citeturn850881search0turn916071search0turn916071search49

### 11.4 ISO/IEC 42001 — organization-level governance overlay

ISO/IEC 42001:2023 is an international standard for establishing, implementing, maintaining and continually improving an AI Management System. It is cross-industry and applicable to organizations developing, providing or using AI. The standard itself is commercially purchased, so CLaiMB should use it as a licensed reference rather than reproducing standard text inside an open registry. citeturn215536search2

### 11.5 ISO 22400 — manufacturing KPI overlay

ISO 22400 is appropriate as a manufacturing-specific KPI reference where the customer’s operating context requires it. It should remain an optional industry adapter rather than part of the universal core.

### 11.6 Frameworks not to make core dependencies

Gartner’s AI maturity model and newer academic constructs such as the 2026 AI Transformation Gap Index can be used as research inputs, but they should not become foundational dependencies for the production system until their definitions, licensing/access, applicability and empirical robustness are independently established. The AITG paper is an interesting research input, but it is a 2026 preprint and reports only limited retrospective validation with an explicit caveat against causal interpretation. citehttps://arxiv.org/abs/2603.13278

---

## 12. Enterprise architecture patterns worth borrowing

### Snowflake

Borrow:

- verified natural-language/SQL pairs
- semantic-model-first SQL generation
- evaluation sets derived from verified queries
- regression tracking
- latency measurement

Snowflake explicitly evaluates generated SQL against verified-query ground truth and removes selected evaluation queries from the temporary semantic view so that evaluation does not simply test memorization of the ground-truth examples. citehttps://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-analyst-evaluations

### Databricks

Borrow:

- curated metadata
- example SQL
- semantic expressions
- trusted assets
- benchmark questions
- explicit user testing
- agent mode for deeper multi-step analysis

Databricks documentation explicitly recommends annotated data, company-specific instructions, tested example SQL and benchmark questions, and supports trusted SQL assets whose underlying logic cannot be modified by the agent. citehttps://docs.databricks.com/aws/en/genie-agents/conceptshttps://docs.databricks.com/gcp/en/genie-agents/tune-qualityhttps://docs.databricks.com/aws/en/genie-agents/monitor

### Microsoft Fabric

Borrow:

- orchestrator-managed source routing
- source descriptions
- schema selection
- example queries
- observability of routing decisions

Microsoft explicitly notes that wrong source routing can produce incorrect or incomplete results when multiple sources are available, which is directly relevant to CLaiMB’s L4-L6 design. citehttps://learn.microsoft.com/en-us/fabric/data-science/data-agent-routing

### Celonis / Process Intelligence

Borrow:

- object-centric representation
- event/object relationships
- process variants
- operational knowledge layer
- process-level diagnostics

Do not attempt to reproduce Celonis wholesale. Use the pattern to strengthen CLaiMB’s process-analysis substrate. citehttps://www.celonis.com/news/article/celonis-process-intelligence-graph-provides-a-common-language-for-enterprise-process-performance

---

## 13. Financial value: implement it as a deterministic subsystem

The CLaiMB architecture already specifies fully loaded cost, addressable labor pool, goal gap, annual value unlock, and cash/capacity split. fileciteturn2file0L1335-L1390

This should not be performed by an LLM.

### Runtime model

```text
verified metric gap
      ↓
validated value assumptions
      ↓
pure calculation service
      ↓
ValueRecord
      ↓
independent arithmetic verification
```

Suggested record:

```yaml
ValueRecord:
  value_id:
  metric_gap_id:
  assumptions:
    salary_source:
    overhead_multiplier:
    headcount:
    pct_time_on_function:
    pct_automatable:
    realization_mode:
    realization_factor:
  addressable_labor_pool:
  gap_fraction:
  total_annual_unlock:
  cash_benefit:
  capacity_benefit:
  calculation_version:
  calculation_hash:
  provenance:
```

Critical invariant:

```text
cash benefit + capacity benefit = total unlock
```

but these should remain separately displayed to customers.

---

## 14. Reproducibility is a product capability, not just engineering hygiene

Every run should produce a `RunManifest`:

```yaml
RunManifest:
  run_id:
  customer_id:
  created_at:
  source_snapshot_ids:
  semantic_registry_version:
  metric_registry_version:
  framework_registry_version:
  diagnostic_registry_version:
  advisory_registry_version:
  code_commit_sha:
  dbt_manifest_hash:
  model_provider:
  model_version:
  prompt_bundle_version:
  tool_bundle_version:
  configuration_hash:
  random_seed:
  artifact_root:
  status:
```

A replay command should be conceptually:

```bash
claimb-agent replay --run <run_id>
```

with an expected outcome of equivalent structured artifacts under the pinned inputs and versions.

The goal is not necessarily byte-identical language from an LLM. The strong reproducibility target should apply to deterministic artifacts and material numeric outputs. Narrative text may vary while all factual fields remain stable.

---

## 15. Evaluation strategy

The repository’s maturation plan correctly calls for a golden set. Expand that idea into a layered evaluation harness.

### Proposed first golden set: 24 cases

```text
6 affirmative planted-gap cases
4 real-gap / non-AI cases
4 refusal / insufficient-evidence cases
3 ambiguous-goal cases
3 data-quality adversarial cases
2 benchmark traps
2 cross-source / relationship cases
```

Each case should contain:

```text
source data
business context
expected metric contract
expected current-state values
expected diagnostic facts
expected AI recommendation/refusal
expected benchmark disposition
expected verification disposition
expected financial value, when applicable
```

### Per-layer metrics

| Layer | Proposed evaluation metric |
|---|---|
| L1 | source coverage, snapshot integrity |
| L2 | transformation correctness, duplicate handling, drift detection |
| L3 | entity/trace reconstruction accuracy |
| L4 | intent/scope correctness |
| L5 | semantic KPI correctness, query-contract conformance |
| L6 | numeric exactness, reproducibility, provenance completeness |
| L7 | evidence-backed diagnostic precision; unsupported-causality rate |
| L8 | AI-fit precision; inappropriate-recommendation rate |
| L9 | benchmark qualification precision; suppression correctness |
| L10 | false-claim interception; false-acceptance rate; retry routing correctness |
| L11 | numeric integrity and factual fidelity |

### Model-evaluation separation

Use separate metrics for:

```text
SQL correctness
evidence correctness
reasoning correctness
recommendation correctness
narrative fidelity
```

This follows enterprise evaluation practice documented by Snowflake and Databricks, where correctness of the underlying query/result is evaluated separately from broader response quality. citehttps://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-analyst-evaluationshttps://docs.databricks.com/aws/en/genie-agents/monitor

---

## 16. Adversarial test suite

The verifier should be tested with synthetic corruption operators rather than only naturally occurring failures.

### Corruption operators

```text
wrong numerator
wrong denominator
wrong direction
wrong unit
wrong time window
wrong join relationship
one-row deletion
one-row duplication
stale source snapshot
query/result mismatch
provenance pointer corruption
benchmark cohort swap
causal_status inflation
AI recommendation detached from evidence
numeric mutation in synthesis
```

For every corruption, the harness should record:

```text
was corruption detected?
which verifier engine caught it?
was it routed to the correct producer?
was retry targeted?
was it fixed?
was it escalated after max retries?
```

This is much more valuable than a generic “hallucination benchmark” because it directly tests CLaiMB’s own invariants.

---

## 17. Targeted retry design

The retry system should be dependency-aware.

Example:

```text
L10 detects wrong numerator in EvidenceBundle
        ↓
REJECT(EVIDENCE_NUMERATOR_MISMATCH)
        ↓
route to L6 only
        ↓
new EvidenceBundle version
        ↓
re-run dependent L7/L8/L9 artifacts
        ↓
L10 re-verifies
```

Do not blindly restart the entire pipeline.

Use an artifact dependency graph:

```text
BusinessContext
      ↓
MetricContract
      ↓
EvidenceBundle
   ↙    ↓    ↘
  L7   L8    L9
    \   |   /
      Finding
```

A version change in `EvidenceBundle` invalidates downstream artifacts that depended on its hash, while leaving L4/L5 reusable.

This combines the CLaiMB plan’s targeted retry design with the iterative verification-feedback approach described in KRCA. citehttps://arxiv.org/abs/2607.01788

---

## 18. Observability and cost model

Record per job:

```yaml
ExecutionTelemetry:
  run_id:
  layer:
  invocation_id:
  model:
  input_tokens:
  output_tokens:
  tool_calls:
  query_latency_ms:
  llm_latency_ms:
  total_latency_ms:
  retry_count:
  status:
  failure_code:
```

Then calculate:

```text
cost_per_run
cost_per_finding
cost_per_rejected_candidate
cost_per_verified_finding
median latency
p95 latency
verification cost share
```

Do this before optimizing prompts. The repository’s own cost analysis correctly notes that verification/retry cost can multiply the total cost rather than simply add one extra model call. citehttps://raw.githubusercontent.com/aanasakhtar/data-agent-pipeline/main/docs/claimb-idea-fit.md

### Model routing

A reasonable first policy is:

```text
Deterministic stages      → no LLM
L4 semantic mapping       → low/medium model
L5 KPI resolution         → medium model + registry retrieval
L7 diagnosis              → stronger reasoning model
L8 AI suitability         → stronger reasoning model
L9 framework retrieval    → retrieval + medium model
L10 semantic verification → strongest model only when deterministic checks pass
L11 synthesis             → low/medium model
```

The exact model selection should be measured from real token/cost/latency data rather than decided theoretically.

---

## 19. Customer data boundary and tenancy

The current repo explicitly reports no multi-tenant/customer-isolation story yet. That is acceptable for a proof of concept but must become a precondition before real customer data is onboarded. citehttps://raw.githubusercontent.com/aanasakhtar/data-agent-pipeline/main/HANDOFF.md

### Minimum production boundary

```text
Customer A
  source connector A
  execution identity A
  schemas A
  artifacts A
  encryption key A

Customer B
  source connector B
  execution identity B
  schemas B
  artifacts B
  encryption key B
```

No agent should receive an arbitrary customer identifier from the prompt and then trust it as an access control. Customer scope should be established by the runtime identity/token and enforced at the data layer.

### Raw-data minimization

Default model context:

```text
aggregates
rates
distributions
pseudonymous IDs
process variants
schema metadata
```

Exceptional row-level access should require an explicit capability with logging and policy evaluation.

---

## 20. Customer onboarding: the product boundary

The maturation plan correctly identifies that a hard-coded `stg_customers`/`stg_orders` style schema would turn each new customer into bespoke engineering.

The mature onboarding path should therefore be:

```text
source discovery
    ↓
profile
    ↓
candidate semantic mapping
    ↓
human contract approval
    ↓
templated dbt / SQL generation
    ↓
validation
    ↓
Gold model
    ↓
metric availability assessment
```

The human approval step is not a weakness. It should be the same pattern CLaiMB uses elsewhere: the agent proposes the contract; the system refuses to proceed until the contract has passed a controlled approval gate.

Do not build generalized onboarding before seeing multiple customer schemas. The first 2–3 engagements can be intentionally service-assisted so that CLaiMB learns which mappings actually repeat.

---

## 21. Maturation roadmap

### Phase P0 — Make the architecture real

1. Add a Python orchestrator/state machine.
2. Define Pydantic contracts for every material artifact.
3. Make each L4-L11 invocation a separate runtime job with explicit payload construction.
4. Enforce tool and artifact permissions in code.
5. Split deterministic verification from adversarial semantic verification.
6. Run verifier in a fresh process/job with asymmetric information.
7. Add run IDs, content hashes, version manifests and replay.

**Exit condition:** the existing pilot can run through the real orchestrator; the verifier demonstrably cannot see producer reasoning or expected values.

### Phase P1 — Prove the affirmative path

1. Add planted-gap data generation.
2. Add customer target and role-roster fixtures.
3. Implement deterministic financial value service.
4. Run an affirmative end-to-end scenario.
5. Deliberately corrupt artifacts.
6. Prove targeted reject → retry → re-verification → escalation.
7. Instrument layer cost/latency.
8. Build the first 24-case golden set.

**Exit condition:** at least one affirmative finding is recovered with known expected KPI gap and known expected value, while corruption tests are intercepted and routed correctly.

### Phase P2 — Make it safe for real data

1. Tenant-scoped execution.
2. Source-level access control.
3. PII minimization/redaction.
4. Audit all tool/query/artifact access.
5. Data freshness contracts.
6. Registry versioning.
7. Organizational/data readiness in L8.
8. Customer-facing uncertainty and evidence display.

**Exit condition:** a realistic customer-shaped data package can run without raw-row leakage and every artifact is tenant-scoped and auditable.

### Phase P3 — Generalize analytical discovery

1. Object-centric process representation.
2. Automated process-variant discovery.
3. Relationship traversal API.
4. Reusable diagnostic modules.
5. Benchmark cohort qualification.
6. Industry-framework adapters.

**Exit condition:** the same reasoning chain can discover a new process pattern without requiring a new hard-coded JOIN for every analytical question.

### Phase P4 — Productize onboarding

1. Schema profiling.
2. Semantic mapping proposals.
3. Human approval UI.
4. Automated dbt/model generation.
5. Mapping regression tests.
6. Customer-specific semantic registry overlays.

**Exit condition:** new customer onboarding is configuration plus approval rather than bespoke engineering.

### Phase P5 — Closed-loop transformation measurement

1. Capture AI/workflow deployment telemetry.
2. Re-run baseline KPIs.
3. Compare post-deployment metrics.
4. Verify realized benefit.
5. Feed successful patterns back into the diagnostic/advisory registry.

The CLaiMB architecture already defines this closed loop. fileciteturn2file0L1420-L1446

---

## 22. Proposed repository target structure

This is a target layout, not a statement of the current repository tree.

```text
claimb-data-agent/
│
├── src/
│   └── claimb_agent/
│       ├── orchestrator/
│       │   ├── state_machine.py
│       │   ├── runtime.py
│       │   ├── routing.py
│       │   └── retries.py
│       │
│       ├── contracts/
│       │   ├── business_context.py
│       │   ├── metric_contract.py
│       │   ├── evidence_bundle.py
│       │   ├── diagnostic.py
│       │   ├── ai_opportunity.py
│       │   ├── benchmark.py
│       │   ├── verification.py
│       │   └── finding.py
│       │
│       ├── verification/
│       │   ├── deterministic.py
│       │   ├── semantic.py
│       │   ├── provenance.py
│       │   └── corruption.py
│       │
│       ├── process_intelligence/
│       │   ├── object_model.py
│       │   ├── relationship_traversal.py
│       │   ├── variants.py
│       │   └── diagnostics.py
│       │
│       ├── value/
│       │   └── calculator.py
│       │
│       ├── telemetry/
│       │   └── events.py
│       │
│       └── replay/
│           └── runner.py
│
├── skills/
│   └── ... existing L1-L11 skill content
│
├── registry/
│   ├── metric_registry/
│   ├── semantic_model/
│   ├── process_ontology/
│   ├── framework_registry/
│   ├── diagnostic_modules/
│   ├── advisory_catalog/
│   └── benchmark_sources/
│
├── evals/
│   ├── golden/
│   ├── adversarial/
│   └── regression/
│
├── runs/
│   └── <run_id>/
│
└── tests/
    ├── unit/
    ├── integration/
    ├── contract/
    └── security/
```

The existing `.claude/skills` can remain as the prompt/instruction package initially. The new runtime becomes the authority that invokes them or, preferably, turns their responsibilities into code-backed agent workers.

---

## 23. Definition of “100% mature” for CLaiMB

The following should be treated as the engineering completion definition. These are **internal targets**, not claims that an external standard requires them.

### Structural

- Every L4-L11 transition is schema-validated.
- No layer can access undeclared tools/data.
- L10 runs with independent execution context.
- L11 cannot mutate verified numerical fields.
- Verification gates are enforced by runtime code, not only prompts.

### Correctness

- 100% headline KPI exactness across the golden set for known-answer cases.
- 0 false acceptance of deliberately corrupted material evidence in the adversarial suite.
- 100% provenance completion for released material claims.
- 100% correct disposition handling for rejected/unusable evidence fixtures.

### Safety

- No unresolved verification failure becomes PASS.
- No unsupported AI recommendation on curated non-AI cases.
- No benchmark promoted without qualification.
- No source failure silently disappears.
- Tenant boundaries are testable and enforced.

### Operability

- Every run is replayable from pinned inputs/versions.
- Layer cost and latency are observable.
- Failure reasons are machine-readable.
- Retry routing is measurable.
- Customer-facing finding generation is fully auditable.

### Analytical depth

- Multiple KPI types work end to end.
- At least one process-variant discovery path works automatically.
- Cross-source relationships can be traversed through the ontology/process layer.
- AI opportunity assessment distinguishes task fit from adoption readiness.
- At least one industry framework adapter is demonstrated beyond the universal core.

---

## 24. Recommended first engineering slice

Do **not** start by building the entire multi-layer architecture.

Start with exactly this vertical slice:

```text
existing pilot dataset
      ↓
existing L4 output fixture
      ↓
existing L5 output fixture
      ↓
existing L6 output fixture
      ↓
NEW runtime orchestrator
      ↓
NEW deterministic verifier
      ↓
NEW isolated verifier process
      ↓
existing L11 synthesis contract
      ↓
replay + telemetry
```

Then run two tests:

### Test A — clean run

Existing pilot artifacts should pass through unchanged and result in the same verified numbers.

### Test B — poisoned run

Manually change one EvidenceBundle field:

```text
0.9047 → 0.9547
```

The verifier must:

```text
catch mismatch
→ emit REJECT
→ identify query/evidence mismatch
→ route to L6
→ regenerate evidence
→ invalidate dependent artifacts
→ re-run required downstream stages
→ verify again
```

This single exercise proves more about CLaiMB’s maturity than adding another diagnostic prompt.

---

## 25. Final architectural position

The strongest version of CLaiMB is not “an 11-agent system.” It is a **governed evidence-and-reasoning runtime** with 11 typed analytical stages.

The architecture should therefore be thought of as:

```text
                         CLaiMB DATA AGENT

 CUSTOMER DATA ──→ GOVERNED DATA FOUNDATION
                    Bronze → Silver → Gold
                              |
                              v
                    BUSINESS SEMANTIC CONTROL
                    Intent → KPI Contract
                              |
                              v
                      DETERMINISTIC EVIDENCE
                         Current State
                              |
                              v
                   PROCESS INTELLIGENCE LAYER
                    Diagnosis + Relationships
                              |
                              v
                     AI OPPORTUNITY LAYER
                   Task Fit × Readiness × Risk
                              |
                              v
                  FRAMEWORK / BENCHMARK CONTEXT
                              |
                              v
                ┌────── VERIFICATION PLANE ──────┐
                │ deterministic gates            │
                │ independent re-execution       │
                │ semantic adversarial review    │
                │ provenance / contradiction     │
                └─────────────────────────────────┘
                              |
                              v
                      VERIFIED FINDING
                              |
                              v
                       ADVISORY / ROADMAP
                              |
                              v
                     POST-DEPLOYMENT TELEMETRY
                              |
                              └────→ re-measurement
```

The central strategic distinction is that CLaiMB should not attempt to outperform Snowflake, Databricks or Microsoft at generic data-question answering. Those platforms already document mature patterns for semantic modeling, source routing, trusted SQL assets and evaluation. CLaiMB’s differentiating layer is the evidence-driven chain from **business goal → measurable current state → operational gap → AI suitability → contextual benchmark → independently verified transformation finding**. citehttps://docs.snowflake.com/en/user-guide/views-semantic/verified-query-repositoryhttps://docs.databricks.com/aws/en/genie-agents/conceptshttps://learn.microsoft.com/en-us/fabric/data-science/data-agent-routing

The architecture already contains the right thesis. Maturation now means turning that thesis into an enforceable runtime and proving it systematically.

---

## Sources

1. APQC. Process Frameworks / PCF Version 8.0. https://www.apqc.org/process-frameworks
2. APQC. PCF Version 8.0 Process Definitions and Key Measures Collection. https://www.apqc.org/resource-library/resource-collection/pcf-version-80-process-definitions-and-key-measures-collection
3. APQC. PCF Case Studies. https://www.apqc.org/process-frameworks/pcf-case-studies
4. APQC / IBM. How IBM Made Data the Backbone of Client Conversations. https://www.apqc.org/ibm-data-case-study
5. ASCM. SCOR Digital Standard. https://www.ascm.org/corporate-solutions/standards-tools/scor-ds/
6. ASCM. SCOR DS open-access guidance. https://www.ascm.org/corporate-solutions/standards-tools/scor-ds/open-access-guidance/
7. ASCM. Ericsson SCOR case study. https://www.ascm.org/globalassets/documents--files/corporate-transformation/case-studies/ericsson-case-study.pdf
8. NIST. AI Risk Management Framework / Playbook. https://www.nist.gov/itl/ai-risk-management-framework/nist-ai-rmf-playbook
9. NIST. AI RMF use cases, including Workday. https://airc.nist.gov/airmf-resources/usecases/
10. ISO. ISO/IEC 42001:2023. https://www.iso.org/standard/42001
11. Snowflake. Cortex Analyst Verified Query Repository. https://docs.snowflake.com/en/user-guide/views-semantic/verified-query-repository
12. Snowflake. Cortex Analyst evaluations. https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-analyst-evaluations
13. Databricks. Genie Agents concepts. https://docs.databricks.com/aws/en/genie-agents/concepts
14. Databricks. Tune Genie Agent quality. https://docs.databricks.com/gcp/en/genie-agents/tune-quality
15. Databricks. Test and monitor a Genie Agent. https://docs.databricks.com/aws/en/genie-agents/monitor
16. Microsoft. Improve data source routing in a Fabric data agent. https://learn.microsoft.com/en-us/fabric/data-science/data-agent-routing
17. Celonis. Process Intelligence Graph. https://www.celonis.com/news/article/celonis-process-intelligence-graph-provides-a-common-language-for-enterprise-process-performance
18. van der Aalst, W. M. P. No AI Without PI! https://arxiv.org/abs/2508.00116
19. Jiang et al. KRCA. https://arxiv.org/abs/2607.01788
20. MARCH. Multi-Agent Reinforced Self-Check for LLM Hallucination. https://arxiv.org/abs/2603.24579
21. Microsoft Research. Exploring LLM-based Agents for Root Cause Analysis. https://www.microsoft.com/en-us/research/publication/exploring-llm-based-agents-for-root-cause-analysis/
22. Microsoft Research. AgentRx. https://www.microsoft.com/en-us/research/blog/systematic-debugging-for-ai-agents-introducing-the-agentrx-framework/
23. Barr, D. AI Transformation Gap Index. https://arxiv.org/abs/2603.13278
24. Current CLaiMB repository: https://github.com/aanasakhtar/data-agent-pipeline
