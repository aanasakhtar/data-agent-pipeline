An evidence-driven architecture for turning customer data and business goals into verified AI-adoption findings

| Purpose. Define the target architecture for a cross-industry CLaiMB Data Agent that can ingest heterogeneous enterprise data, understand a business function and its goals, determine the measurable current state of target KPIs, diagnose the causes of performance gaps, identify AI-addressable opportunities, and produce defensible findings. |
| --- |

| Design position. The proposal treats Bronze, Silver, and Gold as part of the Data Agent itself. These layers create the governed data foundation on which the later reasoning layers operate. The result is one end-to-end system, not a data pipeline followed by an unrelated analyst agent. |
| --- |

# 1. Executive Summary
CLaiMB's Data Agent should become the analytical engine that sits between enterprise data and the platform's finding/advisory experience. Its responsibility is broader than answering questions over tables. It must connect four things that are usually separated: what the customer wants to improve, what the organization actually does, what the data can reliably measure, and where AI can create measurable improvement.
The proposed architecture is a multilayered system with two tightly connected sections. The first is the Data Foundation: Bronze, Silver, and Gold establish raw-data fidelity, quality, conformed entities, process traces, and business-ready metric facts. The second is the Intelligence and Trust Plane: specialized agentic layers resolve business intent and KPI semantics, build current-state evidence, diagnose operational gaps, assess AI suitability, ground results in internal and external frameworks, independently verify material claims, and finally synthesize a customer-facing finding.
The key architectural principle is that no layer should be asked to do everything. Data engineering, semantic interpretation, metric computation, diagnosis, AI opportunity assessment, and narrative synthesis have different failure modes and therefore should have different contracts, permissions, and verification mechanisms.

| Target outcome. For every material CLaiMB finding, the system should be able to trace the conclusion back through the goal, KPI definition, executable computation, source evidence, diagnostic reasoning, benchmark context, verification result, and final advisory mapping. |
| --- |

## 1.1 What the Data Agent Ultimately Does

```text
BUSINESS GOAL
   ↓
"Improve X from current state to target state"
   ↓
UNDERSTAND THE BUSINESS FUNCTION
   ↓
DEFINE WHAT X MEANS
   ↓
MEASURE THE CUSTOMER'S ACTUAL CURRENT STATE
   ↓
EXPLAIN WHERE / WHY THE GAP EXISTS
   ↓
DETERMINE WHETHER THE GAP IS AI-ADDRESSABLE
   ↓
COMPARE AGAINST VALID INTERNAL / EXTERNAL CONTEXT
   ↓
INDEPENDENTLY VERIFY THE EVIDENCE
   ↓
PRODUCE A VERIFIED FINDING + AI ADVISORY
```

# 2. Why a Multilayered Data Agent
Enterprise customer data is rarely organized around the question CLaiMB is trying to answer. Data may be distributed across ERP databases, CRM systems, workflow platforms, event logs, document repositories, semantic models, and operational spreadsheets. The same business concept can also appear under different names and at different levels of granularity.
A single agent that is simultaneously expected to discover data, clean it, interpret business terminology, write SQL, calculate KPIs, infer causes, benchmark performance, estimate value, and write the executive narrative creates a large shared reasoning surface. Errors in an early assumption can silently propagate into later calculations and prose.

| Challenge | What can go wrong | Required architectural response |
| --- | --- | --- |
| Heterogeneous enterprise data | Wrong source, join, grain, or time window | Source-scoped ingestion + semantic model + routing |
| Ambiguous business goals | "Automation" or "cycle time" is undefined | Intent layer + KPI Metric Contract |
| Current-state uncertainty | A plausible number is treated as a fact | Deterministic evidence engine + provenance |
| Causal overreach | Correlation is presented as root cause | Separate observation from diagnosis |
| AI over-prescription | Every problem becomes an LLM/agent recommendation | AI suitability and risk assessment |
| Benchmark misuse | Incomparable external or internal cohorts | Framework registry + benchmark qualification |
| Hallucinated metrics | LLM alters a number during synthesis | Immutable evidence + independent verification |
| Sensitive data exposure | Raw rows enter model context | In-situ execution + minimum necessary evidence |

## 2.1 Core Design Principles
1. Separate data preparation from business judgment.
2. Separate semantic definition from metric execution.
3. Treat evidence as a first-class object that downstream agents consume.
4. Give each agent a narrow analytical mandate and only the data it needs.
5. Prefer deterministic code for calculations, thresholds, and repeatable transformations.
6. Make provenance mandatory for every material claim.
7. Use independent verification rather than self-confidence as the principal trust mechanism.
8. Use external frameworks to structure meaning and context, not to override customer evidence.
9. Prefer internal operational evidence when establishing what is achievable inside the customer's own environment.
10. Allow the system to say 'not measurable' or 'not sufficiently supported' rather than forcing an answer.

# 3. Proposed End-to-End Architecture
The architecture is organized into a Data Foundation and an Intelligence/Trust Plane. Bronze, Silver, and Gold are not passive ETL stages; they are governed capabilities of the Data Agent that prepare customer data for safe reasoning.

```text
CLaiMB DATA AGENT
┌───────────────────────────────────────────────────────────────────┐
│  CUSTOMER CONTEXT                                                │
│  Business Function • Use Case • Goals • Current State • Scope   │
└───────────────────────────────┬───────────────────────────────────┘
                                │
                                ▼
┌───────────────────────────────────────────────────────────────────┐
│                         DATA FOUNDATION                           │
│                                                                   │
│  L1 BRONZE          L2 SILVER               L3 GOLD               │
│  raw + immutable →  clean + conform →      semantic + modeled   │
│  lineage/audit       quality controls        entities/processes  │
│                                                                   │
└───────────────────────────────┬───────────────────────────────────┘
                                │
                                ▼
┌───────────────────────────────────────────────────────────────────┐
│                      INTELLIGENCE & TRUST PLANE                    │
│                                                                   │
│ L4 INTENT      L5 KPI/METRIC      L6 EVIDENCE      L7 DIAGNOSIS   │
│ & SCOPE   →   RESOLUTION     →   / CURRENT    →   & PROCESS      │
│                                  STATE            ANALYSIS         │
│                                                                   │
│ L8 AI OPPORTUNITY + L9 BENCHMARK / FRAMEWORK + L10 VERIFICATION  │
│                         ↓                    ↓                     │
│                       VERIFIED FINDING / SYNTHESIS               │
└───────────────────────────────────────────────────────────────────┘
```

## 3.1 Layer Responsibilities at a Glance

| Layer | Primary job | Main artifact handed forward |
| --- | --- | --- |
| L1 Bronze | Capture customer data without changing its meaning | Immutable raw snapshot + lineage |
| L2 Silver | Conform, clean, standardize and quality-check data | Trusted conformed entities |
| L3 Gold | Model business entities, process traces and metric facts | Semantic business model |
| L4 Intent & Scope | Understand business function, use case, goals and constraints | BusinessFunctionContext |
| L5 KPI Resolution | Turn goals into explicit measurable definitions | MetricContract |
| L6 Evidence / Current State | Execute approved metrics and build evidence | EvidenceBundle |
| L7 Diagnosis | Explain operational patterns behind the measured gap | DiagnosticRecord |
| L8 AI Opportunity | Assess AI addressability, readiness, risk and control mode | AIOpportunityRecord |
| L9 Benchmark / Framework | Ground findings in valid context and standards | BenchmarkRecord + FrameworkEvidence |
| L10 Verification | Attempt to falsify material claims | VerifiedFindingRecord / rejection |
| L11 Synthesis | Turn verified records into findings and advisory mapping | Customer-facing FindingDraft |

# 4. Data Foundation: Bronze → Silver → Gold
The first three layers create a stable analytical substrate. Their role is to transform arbitrary customer data into a controlled semantic representation without asking the downstream reasoning agents to repeatedly rediscover how the customer's systems work.

## 4.1 L1 — Bronze: Raw Ingestion and Staging
Bronze is the fidelity layer. It should ingest scoped customer sources into an immutable or append-only representation, preserve source semantics, and attach audit metadata. The layer should not decide whether a field is 'correct' or 'useful'; it preserves the evidence so later layers can reproduce and inspect transformations.

| Bronze capability | Design requirement |
| --- | --- |
| Source discovery | Enumerate tables, schemas, files, event streams and metadata within the approved scope |
| Immutable landing | Preserve raw values and source structure; no business-rule transformations |
| Lineage | Source ID, object ID, ingestion time, batch ID, connector version |
| Data boundary | Prefer in-situ views/staging in the customer's perimeter |
| Failure handling | Mark unavailable sources explicitly; do not silently omit them |
| Reproducibility | Allow the same source snapshot to be reprocessed by downstream layers |

| Why it matters. Without Bronze, later agents can unknowingly reason over a transformed interpretation of customer data and lose the ability to reproduce or audit how that interpretation arose. |
| --- |

## 4.2 L2 — Silver: Conformance, Cleansing and Quality
Silver converts heterogeneous raw structures into typed, conformed entities. This is where CLaiMB standardizes timestamps, units, booleans, keys, duplicates, null handling, schema drift, and other transformation rules. Quality measurements become first-class outputs rather than hidden implementation details.

| Silver capability | Examples |
| --- | --- |
| Type normalization | Dates/times, numeric fields, booleans, units |
| Entity normalization | Customer, order, case, employee, product, document, activity |
| Deduplication | Business-key rules with retained-record explanation |
| Schema drift | Detect added/removed/renamed fields and impact |
| Quality profiling | Null rate, duplicate rate, invalid value rate, freshness |
| Semi-structured parsing | JSON/key-value extraction into typed attributes |

## 4.3 L3 — Gold: Semantic Business Model
Gold is the layer where data becomes useful for business reasoning. Rather than exposing dozens of raw customer tables to an LLM, CLaiMB creates canonical business entities and process representations.
Gold consolidates five business-ready structures: canonical entities; event and process traces; metric facts with executable provenance; actor/activity patterns; and text/document profiles.

| Architectural boundary. The Gold layer should expose business-ready semantics and reusable metric primitives. It should not decide whether a performance gap is strategically important or whether AI is the answer. Those are reasoning-layer responsibilities. |
| --- |

# 5. Intelligence Layer: From Business Goal to Measured Current State

## 5.1 L4 — Business Intent and Scope Agent
The first reasoning layer establishes exactly what the analysis is about. It receives the business function or use case, the customer's stated goals, the stated current state, constraints, organizational context, and authorized data scope. It should resolve which process and outcomes are in scope before other agents begin.

```text
BusinessFunctionContext
├── business_function
├── use_case
├── process_scope
├── customer_goal[]
├── stated_current_state
├── desired_target[]
├── time_horizon
├── organizational_scope
├── constraints
├── authorized_sources
└── unresolved_questions[]
```
This layer should not calculate KPIs. Its job is to make the analytical question explicit and bounded.

## 5.2 L5 — KPI / Metric Resolution Agent
This is the semantic control point of the Data Agent. A business goal such as 'reduce processing time' or 'increase automation to 80%' is an intention, not yet a measurable specification. The KPI layer converts the intention into a versioned Metric Contract.

```text
MetricContract
├── metric_id / version
├── business_process
├── semantic_definition
├── numerator / denominator
├── direction
├── unit + grain
├── time window
├── inclusion / exclusion rules
├── dimensions
├── customer target
├── framework reference (optional)
├── source mapping
├── executable query/template
├── quality requirements
└── provenance
```
The KPI layer should use the customer's own definitions first, then standardized terminology where needed. APQC's Process Classification Framework provides a strong cross-industry reference because it supplies a common process language, process hierarchy, definitions, recommended key measures, and industry-specific variants. APQC also positions the PCF as a basis for internal and external benchmarking. [1][2]
For specialized domains, the resolution layer should consult an industry overlay rather than forcing every process into one taxonomy. SCOR DS is an example for supply chain, where process levels, performance attributes, metrics and diagnostic relationships are explicitly connected. [3] Manufacturing can use ISO 22400 as a KPI-definition reference for manufacturing operations management. [4]

## 5.3 L6 — Evidence and Current-State Agent
Once a Metric Contract is accepted, the system measures the current state deterministically. The L6 layer is deliberately narrower than a general analyst: it retrieves the approved data, executes the metric, checks quality, generates supporting distributions and segment views, and packages the result as an Evidence Bundle.

```text
EvidenceBundle
├── evidence_id
├── metric_contract_id
├── observed_value
├── period
├── sample_size
├── distribution / trend
├── segment_results[]
├── source_objects[]
├── query + query_hash
├── execution_timestamp
├── freshness_status
├── data_quality_status
├── caveats[]
└── provenance_chain
```
This model follows a pattern increasingly visible in enterprise data agents. Snowflake documents verified natural-language/SQL pairs and uses them as trusted examples and evaluation ground truth for SQL generation; Microsoft Fabric Data Agents use semantic models, schema selection, source descriptions, example queries and source routing to make multi-source answering more reliable. [5][6][7]

# 6. Intelligence Layer: Operational Diagnosis
After the current state is measured, CLaiMB needs to determine where the operational problem is occurring and what observable patterns plausibly explain the performance gap. This layer should reason over Evidence Bundles, process traces, actor activity, and text/document profiles—not over uncontrolled raw tables.

## 6.1 L7 — Process and Gap Diagnosis Agent

| Diagnostic family | Evidence pattern | What the system can safely say |
| --- | --- | --- |
| Cycle / wait time | Case duration decomposed into active vs. waiting time | Where time is being consumed |
| Rework | Repeated activities or review loops | Where repeated work is concentrated |
| Handoffs | Frequent actor/team transitions | Where coordination burden occurs |
| Exception concentration | A small cohort drives a high share of exceptions | Which segments deserve targeted investigation |
| Manual burden | High human touch volume for repeatable activities | Where human effort is concentrated |
| Unstructured work | Text/document-heavy activities with measurable volume | Where information processing burden exists |
| Automation behavior | Existing automation/AI touches plus acceptance/override | Whether deployed automation is being trusted/used |
A key control here is separating observations from explanations. For example, '18% of cases contain rework' is directly measurable; 'poor upstream intake quality causes the rework' is a hypothesis that requires sequence or quality evidence. The agent must not turn a plausible hypothesis into a fact simply because it sounds operationally reasonable.

# 7. Intelligence Layer: AI Opportunity Assessment

## 7.1 L8 — AI Opportunity and Suitability Agent
This layer determines whether an identified operational problem is actually suitable for AI, and at what level of autonomy. It is the guardrail against the system becoming an 'LLM recommendation generator.' Not every gap is an AI problem; some require process redesign, data-quality improvement, policy changes, system integration, or capacity management.

| Dimension | Assessment question | Implication |
| --- | --- | --- |
| Repeatability | Does the task recur with recognizable structure? | Higher → stronger automation potential |
| Data availability | Are inputs observable and sufficiently reliable? | Low → defer or suppress |
| Determinism | Can good performance be objectively evaluated? | Higher → stronger autonomous case |
| Exception rate | How often does the task deviate from the normal pattern? | High → more human control |
| Judgment intensity | How much expert reasoning is required? | High → assistive/HITL |
| Error consequence | What is the cost of a wrong output? | Higher → stricter controls |
| Workflow integration | Can the AI operate within the existing process? | Low → implementation dependency |
| Governance sensitivity | Does the use case involve regulated/high-impact decisions? | High → stronger governance gate |
The resulting AIOpportunityRecord should state both the opportunity and the required control mode: assistive, human-in-the-loop, bounded automation, or autonomous execution. NIST's AI RMF and Generative AI Profile provide a cross-sector vocabulary for trustworthiness and risk considerations; ISO/IEC 42001 provides an organization-level management-system reference for responsible AI governance. [8][9]

```text
AIOpportunityRecord
├── linked_gap / evidence_ids
├── process_step
├── observed_problem
├── task_characteristics
├── ai_fit
├── autonomy_level
├── readiness
├── risk_profile
├── expected KPI impact
├── dependencies
├── human control points
└── recommendation confidence
```

# 8. Benchmark and Framework Intelligence
Benchmarking should be a separate concern from measurement. CLaiMB should first establish the customer's performance, then determine whether a valid comparison exists.

## 8.1 L9 — Framework and Benchmark Agent
The framework/benchmark layer should maintain a versioned registry containing process standards, KPI definitions, governance frameworks, internal benchmark rules, and approved external benchmark datasets.

| Reference type | Examples | Use in CLaiMB |
| --- | --- | --- |
| Cross-industry process framework | APQC PCF | Process taxonomy, terminology, measures |
| Industry framework | SCOR DS | Supply-chain process/metric/diagnostic model |
| Manufacturing KPI framework | ISO 22400 | Manufacturing KPI semantics |
| AI governance | NIST AI RMF; ISO/IEC 42001 | Risk and governance context |
| Internal benchmark | Teams, regions, products, business units | Show what is achievable inside the customer |
| External benchmark | Approved comparable cohorts | Provide broader context where comparable |
Internal benchmarks should be direction-aware and cohort-aware. A higher-is-better metric may use an upper-tail statistic; a lower-is-better metric may use a lower-tail statistic. The system should also evaluate cohort size, comparability, stability, missingness and variance before promoting a segment to a benchmark.

```text
BenchmarkRecord
├── metric_id
├── benchmark_source
├── cohort_definition
├── cohort_count
├── cases_per_cohort
├── direction
├── statistic_used
├── benchmark_value
├── stability / comparability
└── suppression_reason
```
This separates two different claims: 'another part of the organization performs at X' and 'X is a valid target for this organization.' The first can be factual while the second requires comparability evidence.

# 9. Trust Layer: Independent Verification
The verification layer is the architectural boundary between analytical reasoning and customer-facing truth. Its purpose is not to ask the generating model whether it is confident. Its purpose is to independently attempt to falsify the material claims produced upstream.

## 9.1 L10 — Verification and Adversarial Review Agent

| Verification engine | Question | Release rule |
| --- | --- | --- |
| Semantic check | Does the computation conform to the MetricContract? | Must pass |
| Query re-execution | Does independent execution reproduce the value? | Must pass for headline metrics |
| Arithmetic check | Do formulas reproduce derived value/ROI? | Must pass |
| Data quality check | Is the evidence sufficiently complete, fresh and valid? | Pass or directional-only |
| Benchmark check | Is the comparison cohort valid and direction-aware? | Pass or suppress |
| Contradiction check | Do findings materially conflict? | Resolve or flag |
| Provenance check | Can every material number trace to evidence? | Must pass |
| Narrative integrity | Did synthesis change verified numeric content? | Must pass |
The verifier can return only three broad dispositions: PASS, LOW-CONFIDENCE/DIRECTIONAL, or REJECT. Rejections should route back only to the relevant producing layer with the exact failed invariant; bounded retries prevent infinite loops. Persistent failures should escalate rather than being silently overwritten.

## 9.2 Evidence and Claim Graph

```text
Customer goal
   ↓
MetricContract
   ↓
Executable query / deterministic computation
   ↓
EvidenceBundle
   ↓
DiagnosticRecord / AIOpportunity / BenchmarkRecord
   ↓
Verification result
   ↓
VerifiedFindingRecord
   ↓
Executive synthesis
   ↓
Advisory
```

| Trust principle. A model may propose a claim, but the system—not the model's confidence—must establish whether the claim is releasable. |
| --- |

# 10. L11 — Executive Synthesis and Advisory Mapping
The final layer should be intentionally lightweight. It receives only verified records and transforms them into a customer-facing finding with a clear narrative, severity, evidence summary, and the appropriate CLaiMB advisory or recommendation.
- No direct source-data access. The synthesis layer should never query customer tables.
- No metric editing. Numeric values are locked to verified records.
- No new factual claims. New claims require new evidence and return to the verification path.
- Advisory matching. The layer selects or maps to existing solution/advisory constructs rather than inventing unsupported products.
- Clear confidence. Directional evidence must remain explicitly directional.

```text
The released finding record contains the finding ID, headline, severity, verified metrics, linked evidence, diagnosis, benchmark context, AI opportunity, advisory match, verification status, confidence, and provenance chain.
```

# 11. End-to-End Example: Accounts Payable
Consider an AP use case where a customer states: 'We process invoices in three days with 50% automation.' The customer establishes a goal of achieving 80% straight-through processing. Customer data includes ERP invoices, procurement records, document metadata, workflow events and employee activity.

| Layer | Example action | Result |
| --- | --- | --- |
| Bronze | Ingest ERP invoice/workflow sources and document metadata | Immutable source snapshots |
| Silver | Standardize dates, approval flags, keys; parse discrepancy JSON | Conformed invoice entities |
| Gold | Build invoice case traces, actor activity and metric facts | Business-ready AP model |
| Intent | Scope invoice processing and define relevant goals | BusinessFunctionContext |
| KPI | Resolve STP and cycle time definitions | Versioned MetricContracts |
| Evidence | Execute metrics over the approved period | Observed STP/cycle-time evidence |
| Diagnosis | Analyze rework, manual touches, exception cohorts and text burden | DiagnosticRecords |
| AI Opportunity | Assess invoice extraction/matching opportunities | AI opportunity with control mode |
| Benchmark | Compare eligible internal teams/regions and approved external context | Qualified benchmark context |
| Verification | Re-run metrics, recompute derived value and test contradictions | PASS / flags |
| Synthesis | Create finding and advisory mapping | Verified executive finding |

## 11.1 What a Strong Finding Looks Like
A strong finding would not simply say 'invoice processing should use an LLM.' It would state the measured gap, show the relevant operational evidence, identify where work is concentrated, explain why the task characteristics make a particular AI intervention plausible, identify the control mode required, and connect any economic estimate to verified assumptions.

```text
FINDING
"Straight-through invoice processing is materially below the customer's target"

Evidence:
- MetricContract: STP definition + denominator
- Current state: verified observed value
- Target: customer-defined 80%
- Sample: verified transaction count
- Process evidence: rework / exception / manual-touch concentration
- AI fit: evidence extraction + matching is repetitive and evaluable
- Control: human review for low-confidence matches
- Benchmark: qualified internal cohort / external reference
- Verification: independent re-query + arithmetic + provenance PASS
```

# 12. Recommended Framework Strategy for CLaiMB
CLaiMB should not attempt to create a universal process-and-KPI taxonomy from scratch. The better strategy is to maintain a canonical internal ontology with adapters to established frameworks. The internal model becomes the common interface while external frameworks provide authoritative vocabulary, process mappings, KPI definitions, and contextual benchmarks.

| Framework | Recommended role | Why it fits |
| --- | --- | --- |
| APQC PCF | Primary cross-industry process backbone | Broad process taxonomy, common language, KPI definitions, industry variants |
| SCOR DS | Supply-chain overlay | Connects processes, metrics, diagnostics, practices and skills |
| ISO 22400 | Manufacturing KPI overlay | Structured KPI concepts for manufacturing operations management |
| NIST AI RMF / GenAI Profile | AI-risk overlay | Cross-sector trustworthiness and risk vocabulary |
| ISO/IEC 42001 | AI-governance overlay | Management-system reference for organizations using/providing AI |
| Customer operating model | Highest-priority local context | Reflects how the customer actually defines and runs the process |
The registry should store framework version, jurisdiction/industry scope, applicable process nodes, metric definitions, source attribution, effective dates, and mapping confidence. This allows CLaiMB to evolve its knowledge layer without hard-coding assumptions into every agent prompt.

# 13. Enterprise Security, Governance and Data Boundary
Because CLaiMB will operate across industries, the architecture must treat customer data handling as a system property rather than an agent instruction. The safest default is for raw rows to remain inside the customer's approved execution environment while agents consume only the minimum data necessary for their task.

| Control | Target design |
| --- | --- |
| Tenant isolation | Customer-scoped connectors, schemas, execution identities and artifact namespaces |
| Least privilege | Layer-specific read/write permissions; synthesis never reads source data |
| In-situ computation | Push filtering/aggregation into customer-controlled data systems where possible |
| PII minimization | Return aggregates, distributions and pseudonymous IDs unless row-level inspection is explicitly justified |
| Auditability | Persist agent, tool, query, artifact, model and verification events |
| Data freshness | Track ingestion and source freshness per evidence bundle |
| Governance | Map AI opportunity risk to required controls and human checkpoints |

# 14. Evaluation and Quality Strategy
CLaiMB should evaluate the Data Agent at every layer instead of measuring only the final narrative. A finding can sound convincing while being wrong because the metric was misinterpreted, the source was wrong, the join was incorrect, or a causal explanation was unsupported.

| Layer | What should be tested |
| --- | --- |
| Bronze | Source coverage, ingestion completeness, lineage integrity, snapshot reproducibility |
| Silver | Transformation correctness, duplicate handling, data-quality detection, schema-drift handling |
| Gold | Entity/process reconstruction, trace accuracy, metric primitive correctness |
| Intent | Correct business-process and scope interpretation |
| KPI | Metric semantic correctness and target interpretation |
| Evidence | Query correctness, numerical reproducibility, provenance completeness |
| Diagnosis | Evidence-backed diagnostic precision; unsupported-causality rate |
| AI Opportunity | Expert-rated AI-fit precision; inappropriate recommendation rate |
| Benchmark | Comparability and directionality correctness |
| Verification | False-claim interception rate; false acceptance rate |
| Synthesis | Numeric integrity, evidence coverage, narrative fidelity |

## 14.1 Golden Evaluation Set
- Known-answer cases. Synthetic or curated datasets with exact expected KPI values and findings.
- Ambiguous-goal cases. Goals where multiple KPI definitions appear plausible.
- Data-quality adversarial cases. Missing columns, duplicate cases, stale data, wrong units, invalid timestamps, misleading names.
- Cross-source cases. The same business concept appears across several sources and requires correct routing.
- Contradiction cases. Customer's stated current state conflicts with observed metrics.
- AI false-positive cases. Operational gaps that are real but are better solved by process redesign or non-AI technology.
- Benchmark traps. Small cohorts, incomparable business units, direction mistakes, unstable segments.
Snowflake's documented evaluation pattern—using verified natural-language/SQL pairs as ground truth and measuring SQL correctness separately from response quality—is a useful model for CLaiMB's own evaluation harness. [6]

# 15. Recommended Implementation Roadmap

| Phase | Build | Outcome |
| --- | --- | --- |
| 1. Data foundation | Bronze + Silver + Gold contracts, lineage and semantic model | Stable reusable customer data substrate |
| 2. KPI control | Intent context + MetricContract + metric registry | Goals become explicitly measurable |
| 3. Evidence | Deterministic current-state engine + EvidenceBundle | Reproducible customer KPI truth |
| 4. Intelligence | Diagnosis + AI suitability + benchmark/framework layers | Evidence-backed gaps and AI opportunities |
| 5. Verification | Independent re-query, arithmetic, contradiction and provenance gates | Release control for material findings |
| 6. Synthesis + evaluation | Verified finding binder + golden set + regression/observability | Executive-ready outputs with continuous quality |
The target architecture should be introduced incrementally. The sequencing below prioritizes the controls that most directly improve trust, while avoiding a large first release consisting only of additional agent prompts.

| Build recommendation. Keep deterministic transformations and metric computation primarily in code/services. Use LLMs where language reasoning is valuable: business-intent interpretation, semantic mapping, hypothesis generation, diagnosis, framework retrieval, and synthesis. |
| --- |

# 16. What This Makes CLaiMB
The strategic value of the architecture is not that CLaiMB has more agents than competing products. Enterprise platforms already demonstrate orchestration over multiple data sources, semantic models, process analysis, root-cause analysis, and verified query patterns. Microsoft Fabric currently documents multi-source routing and semantic-model-based data access; SAP Signavio provides process analysis and root-cause capabilities; Snowflake provides semantic models, verified query patterns and evaluation infrastructure. [5][7][10]
CLaiMB's opportunity is to connect these ideas around a different end-to-end objective: determine whether a business goal has a measurable gap in the customer's actual operations, diagnose the operational constraint behind that gap, and translate the evidence into an AI transformation opportunity with a defensible chain of proof.

| Proposed positioning. CLaiMB is an evidence-driven AI transformation Data Agent: it turns business goals and enterprise operational data into verified measurements, diagnosed gaps, and defensible AI opportunities. |
| --- |

## 16.1 Target Properties of the Finished System

| Property | Meaning for CLaiMB |
| --- | --- |
| Cross-industry | Core architecture remains stable while frameworks and process vocabularies plug in by industry |
| Evidence-driven | Findings are generated from explicit, reproducible evidence artifacts |
| Multi-agent | Agents specialize by responsibility and failure mode rather than sharing one giant prompt |
| Explainable | Each finding has metric, source, evidence, diagnostic and verification lineage |
| Enterprise-safe | Raw data remains within controlled boundaries where possible |
| Extensible | New data sources, frameworks, KPIs and diagnostic modules can be added without rewriting the whole agent |
| Measurable | Every layer has explicit evaluation metrics and regression tests |

# 17. Final Recommendation
Adopt the multilayer architecture as the target design for the CLaiMB Data Agent, with Bronze → Silver → Gold treated as the governed data foundation and the subsequent intelligence layers treated as typed, scope-isolated reasoning stages. The critical control point should be the KPI/Metric Contract, because the system cannot reliably measure a business gap until it knows exactly what the KPI means. The critical trust point should be independent verification, because multi-agent decomposition alone does not guarantee correctness.
The result is a system that can move from 'the customer wants to improve this' to 'this is what the customer actually measures today, this is where the gap exists, this is what the evidence supports as the operational cause, this is why an AI intervention is or is not suitable, this is the contextual benchmark, and this is the verified chain supporting the finding.'

# Sources
[1] APQC. Process Frameworks. https://www.apqc.org/process-frameworks
[2] APQC. PCF Version 8.0 Process Definitions and Key Measures Collection. https://www.apqc.org/resource-library/resource-collection/pcf-version-80-process-definitions-and-key-measures-collection
[3] ASCM. SCOR Digital Standard. https://www.ascm.org/corporate-solutions/standards-tools/scor-ds/
[4] ISO. ISO 22400-1:2014 - KPIs for manufacturing operations management. https://www.iso.org/standard/56847.html
[5] Microsoft. Improve data source routing - Microsoft Fabric data agent. https://learn.microsoft.com/en-us/fabric/data-science/data-agent-routing
[6] Snowflake. Cortex Analyst Verified Query Repository. https://docs.snowflake.com/en/user-guide/views-semantic/verified-query-repository
[7] Snowflake. Cortex Analyst evaluations. https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-analyst-evaluations
[8] NIST. Artificial Intelligence Risk Management Framework: Generative Artificial Intelligence Profile. https://www.nist.gov/publications/artificial-intelligence-risk-management-framework-generative-artificial-intelligence
[9] ISO. ISO/IEC 42001:2023 - Artificial intelligence - Management system. https://www.iso.org/standard/42001
[10] SAP. SAP Signavio Process Intelligence - Process Analysis. https://help.sap.com/docs/signavio-process-intelligence/user-guide/process-analysis
[11] SAP. Working with Root Cause Analysis. https://help.sap.com/docs/signavio-process-intelligence/user-guide/working-with-root-cause-analysis


---

# 1. Architecture Definition

## 1.1 Layer Model

```text
L1 BRONZE
Raw customer data + immutable snapshots + lineage
        ↓
L2 SILVER
Typed/conformed entities + quality controls
        ↓
L3 GOLD
Canonical business entities + process traces + metric primitives
        ↓
L4 INTENT & SCOPE
Business function + use case + goals + current-state context
        ↓
L5 KPI / METRIC RESOLUTION
MetricContract
        ↓
L6 EVIDENCE / CURRENT STATE
EvidenceBundle
        ↓
L7 OPERATIONAL DIAGNOSIS
DiagnosticRecord
        ↓
L8 AI OPPORTUNITY / SUITABILITY
AIOpportunityRecord
        ↓
L9 BENCHMARK + FRAMEWORK INTELLIGENCE
BenchmarkRecord / FrameworkEvidence
        ↓
L10 INDEPENDENT VERIFICATION
PASS / LOW_CONFIDENCE / REJECT / HUMAN_REVIEW
        ↓
L11 EXECUTIVE SYNTHESIS
FindingDraft
```

## 1.2 Design Rule

The architecture is not intended to maximize the number of agents. It is intended to isolate failure modes and make every material analytical transition inspectable, reproducible, and independently verifiable.

---

# 2. Layer 1 Skill Specification

**Skill Path:** `skills/bronze-ingest-staging/SKILL.md`

```yaml
---
name: bronze-ingest-staging
description: Introspects approved customer data sources and stages raw tables, event logs, files, and metadata into an immutable Bronze landing zone.
version: 1.0.0
metadata:
  layer: bronze
  phase: ingestion
allowed-tools:
  - sql_introspect_schema
  - stage_table_snapshot
  - scan_object_store_metadata
  - register_source_status
---
```

### Responsibilities

1. Discover scoped sources and objects.
2. Preserve raw source fidelity.
3. Create immutable/append-only snapshots.
4. Attach audit metadata.
5. Reconcile source and landed record/object counts.
6. Quarantine failed sources.
7. Emit a complete source-coverage manifest.

### Invariants

- Zero business transformation.
- No silent source omission.
- Every artifact has lineage.
- Every unavailable source is propagated downstream.

### Output

`BronzeArtifactManifest`

```yaml
BronzeArtifactManifest:
  source_id:
  object_id:
  snapshot_id:
  row_count:
  object_count:
  schema_fingerprint:
  ingested_at:
  source_status:
  quarantine_reason:
  lineage:
```

---

# 3. Layer 2 Skill Specification

**Skill Path:** `skills/silver-conform-cleanse/SKILL.md`

```yaml
---
name: silver-conform-cleanse
description: Converts Bronze source artifacts into typed, conformed, quality-profiled entities while preserving transformation lineage.
version: 1.0.0
metadata:
  layer: silver
  phase: transformation
allowed-tools:
  - run_transformation_sql
  - parse_semi_structured_json
  - register_quality_metrics
  - register_schema_mapping
---
```

### Responsibilities

- Type normalization
- Entity/key normalization
- Deduplication
- Semi-structured parsing
- Schema drift detection
- Quality profiling
- Transformation lineage

### Invariants

- Transformations must be explicit.
- Duplicate resolution must be explainable.
- Missing values must not be silently imputed as business truth.
- Quality metrics become part of downstream evidence confidence.

### Output

`SilverEntity`

```yaml
SilverEntity:
  entity_name:
  source_objects:
  typed_columns:
  transformation_rules:
  null_rates:
  duplicate_rates:
  schema_drift:
  freshness:
  lineage:
```

---

# 4. Layer 3 Skill Specification

**Skill Path:** `skills/gold-normalize-model/SKILL.md`

```yaml
---
name: gold-normalize-model
description: Builds canonical business entities, event/process traces, reusable metric facts, actor activity, and text/document profiles from Silver data.
version: 1.0.0
metadata:
  layer: gold
  phase: semantic_modeling
allowed-tools:
  - build_case_traces
  - aggregate_metric_facts
  - compute_segment_statistics
  - profile_unstructured_text
  - register_semantic_mapping
---
```

### Standard Outputs

```text
gold_canonical_events
gold_case_traces
gold_metric_facts
gold_actor_activity
gold_text_profiles
```

### Gold Boundary

Gold answers:

> What does the customer's operational data look like in business terms?

Gold does not decide:

> What should leadership do?

---

# 5. Layer 4 Skill Specification

**Skill Path:** `skills/intent-business-scope/SKILL.md`

```yaml
---
name: intent-business-scope
description: Resolves the analytical scope of a CLaiMB business function or use case from customer intent, goals, current-state context, and constraints.
version: 1.0.0
metadata:
  layer: semantic_control
  phase: intent_resolution
allowed-tools:
  - resolve_business_function
  - resolve_process_scope
  - retrieve_framework_context
---
```

### Output

`BusinessFunctionContext`

### Invariants

- Preserve the customer's stated current state.
- Explicitly identify the process and objective.
- Do not invent KPI definitions.
- Carry unresolved ambiguity forward.

---

# 6. Layer 5 Skill Specification

**Skill Path:** `skills/kpi-metric-resolution/SKILL.md`

```yaml
---
name: kpi-metric-resolution
description: Resolves business goals into explicit, versioned, executable Metric Contracts using customer definitions, Gold semantics, and applicable framework knowledge.
version: 1.0.0
metadata:
  layer: semantic_control
  phase: metric_resolution
allowed-tools:
  - search_metric_registry
  - retrieve_framework_definition
  - map_metric_to_gold
  - generate_metric_query
  - validate_metric_contract
---
```

### Purpose

This layer is mandatory before current-state measurement.

A goal such as:

> Increase automation to 80%

must first become a formal `MetricContract`.

### MetricContract

```yaml
MetricContract:
  metric_id:
  version:
  business_process:
  metric_name:
  user_goal_text:
  semantic_definition:
  direction:
  numerator_definition:
  denominator_definition:
  grain:
  unit:
  time_window:
  inclusion_rules:
  exclusion_rules:
  dimensions:
  target_value:
  target_source:
  source_entities:
  gold_fields:
  executable_query_template:
  expected_result_shape:
  data_quality_requirements:
  minimum_sample_guidance:
  framework_references:
  provenance:
```

### Non-Negotiable Invariants

1. No headline KPI without an accepted MetricContract.
2. Every metric must specify its denominator.
3. Every metric must specify its grain.
4. Metric direction must be explicit.
5. A metric with unresolved semantic ambiguity cannot become a headline result.
6. The executable query must be consistent with the contract.

---

# 7. Layer 6 Skill Specification

**Skill Path:** `skills/evidence-current-state/SKILL.md`

```yaml
---
name: evidence-current-state
description: Executes approved Metric Contracts against Gold data, computes deterministic current-state measures, validates quality, and creates immutable Evidence Bundles.
version: 1.0.0
metadata:
  layer: evidence_control
  phase: measurement
allowed-tools:
  - execute_metric_query
  - compute_distribution_statistics
  - compute_segment_statistics
  - validate_evidence_quality
  - create_evidence_bundle
---
```

### EvidenceBundle

```yaml
EvidenceBundle:
  evidence_id:
  metric_contract_id:
  observed_value:
  period:
  sample_size:
  distribution_summary:
  trend_summary:
  segment_results:
  source_objects:
  query:
  query_hash:
  execution_timestamp:
  data_quality_status:
  freshness_status:
  source_coverage:
  caveats:
  provenance_chain:
```

### Evidence Status

```text
HIGH
MEDIUM
LOW
UNUSABLE
```

Evidence confidence is determined from measurable properties such as:

- source coverage
- sample adequacy
- freshness
- missingness
- duplicate rate
- schema integrity
- reproducibility
- stability

---

# 8. Layer 7 Skill Specification

**Skill Path:** `skills/operational-diagnosis/SKILL.md`

```yaml
---
name: operational-diagnosis
description: Analyzes verified current-state evidence and Gold process models to identify operational friction, rework, queues, manual burden, handoffs, concentration, and automation behavior.
version: 1.0.0
metadata:
  layer: reasoning
  phase: diagnosis
allowed-tools:
  - query_evidence
  - query_process_traces
  - run_diagnostic_module
  - compare_segments
---
```

### Diagnostic Library

Diagnostics are modular and activated according to the business function.

```text
Cognitive / Information Drag
Rework
Queue / Waiting
Handoff
Exception Concentration
Manual Burden
Automation / AI Behavior
```

### DiagnosticRecord

```yaml
DiagnosticRecord:
  diagnostic_id:
  category:
  observation:
  interpretation:
  evidence_ids:
  source_queries:
  affected_process_steps:
  affected_segments:
  severity:
  confidence:
  causal_status:
    - observed
    - hypothesis
    - supported
    - unverified
```

### Invariant

A hypothesis must never be represented as an observed fact.

---

# 9. Layer 8 Skill Specification

**Skill Path:** `skills/ai-opportunity-assessment/SKILL.md`

```yaml
---
name: ai-opportunity-assessment
description: Determines whether an observed operational gap is suitable for AI, what autonomy level is appropriate, and what readiness, risk, and human-control requirements apply.
version: 1.0.0
metadata:
  layer: reasoning
  phase: ai_opportunity
allowed-tools:
  - assess_task_characteristics
  - assess_ai_fit
  - assess_readiness
  - assess_ai_risk
  - map_solution_pattern
---
```

### Assessment Dimensions

```text
repeatability
determinism
data availability
exception rate
judgment intensity
error consequence
workflow integration
governance sensitivity
evaluation measurability
existing automation
```

### Autonomy Levels

```text
ASSISTIVE
HUMAN_IN_LOOP
BOUNDED_AUTOMATION
AUTONOMOUS
```

### AIOpportunityRecord

```yaml
AIOpportunityRecord:
  opportunity_id:
  linked_metric_gaps:
  linked_diagnostics:
  process_step:
  observed_problem:
  evidence_ids:
  task_characteristics:
  ai_fit:
  readiness:
  risk_profile:
  autonomy_level:
  human_control_points:
  expected_kpi_impact:
  dependencies:
  recommendation_confidence:
```

### Required Alternative

The agent must be capable of returning:

```text
NO_AI_RECOMMENDATION
```

when process redesign, data quality, governance, integration, or another intervention is more appropriate.

---

# 10. Layer 9 Skill Specification

**Skill Path:** `skills/framework-benchmark-intelligence/SKILL.md`

```yaml
---
name: framework-benchmark-intelligence
description: Grounds process/KPI interpretation in approved frameworks and proposes internal or external benchmarks only when comparability requirements are satisfied.
version: 1.0.0
metadata:
  layer: reasoning
  phase: benchmark_framework
allowed-tools:
  - retrieve_framework
  - retrieve_metric_definition
  - query_internal_benchmarks
  - evaluate_cohort_comparability
  - compute_directional_benchmark
---
```

### Framework Registry

```text
APQC PCF
SCOR / SCOR DS
ISO 22400
NIST AI RMF / GenAI Profile
ISO/IEC 42001
Customer-specific operating model
```

### Benchmark Qualification

Before a benchmark can become a target proposal, evaluate:

```text
cohort size
cases per cohort
process comparability
metric direction
stability
dispersion
time consistency
```

### BenchmarkRecord

```yaml
BenchmarkRecord:
  metric_id:
  benchmark_source:
  cohort_definition:
  cohort_count:
  cases_per_cohort:
  direction:
  statistic_used:
  benchmark_value:
  stability:
  comparability:
  suppression_reason:
```

---

# 11. Layer 10 Skill Specification

**Skill Path:** `skills/verification-adversarial-review/SKILL.md`

```yaml
---
name: verification-adversarial-review
description: Independently attempts to falsify every material analytical record before it can be released to executive synthesis.
version: 1.0.0
metadata:
  layer: trust
  phase: verification
allowed-tools:
  - validate_metric_contract
  - reexecute_metric_query
  - recompute_calculation
  - validate_data_quality
  - cross_check_records
  - validate_provenance
---
```

### Verification Engines

```text
1. Semantic Verification
2. SQL Re-execution
3. Arithmetic Verification
4. Data Quality Verification
5. Benchmark Verification
6. Contradiction Verification
7. Provenance Verification
8. Narrative Integrity Verification
```

### Operating Principle

The verifier does not ask:

> "Does the producer sound confident?"

It asks:

> "Can I independently reproduce or falsify the material claim?"

### Outcomes

```text
PASS
LOW_CONFIDENCE
REJECT
UNVERIFIABLE_NEEDS_HUMAN_REVIEW
```

### Rejection Loop

```text
REJECT
  ↓
Exact discrepancy
  ↓
Targeted retry
  ↓
Maximum 2 retries
  ↓
Human review
```

No unresolved failure may be converted into a guessed pass.

---

# 12. Layer 11 Skill Specification

**Skill Path:** `skills/executive-synthesis/SKILL.md`

```yaml
---
name: executive-synthesis
description: Converts verified analytical records into customer-facing findings and advisory matches without modifying factual evidence.
version: 1.0.0
metadata:
  layer: synthesis
  phase: executive_reporting
allowed-tools:
  - assemble_finding
  - assign_severity
  - match_advisory_solution
---
```

### Inputs

Only:

```text
PASS
LOW_CONFIDENCE / DIRECTIONAL
```

records.

### Invariants

- No source-data access.
- No Gold access.
- No numeric mutation.
- No unsupported factual claims.
- New factual claims require a new evidence path.

---

# 13. Orchestration Contract

The orchestrator is a workflow controller, not an analyst.

```yaml
OrchestratorResponsibilities:
  - manage_state
  - route_artifacts
  - enforce_permissions
  - enforce_dependencies
  - trigger_retries
  - enforce_verification_gate
  - escalate_human_review
```

It must not:

- independently calculate KPIs
- write findings
- alter evidence
- bypass verification

---

# 14. Orchestration State Machine

```text
CREATED
   ↓
SOURCE_SCOPE_VALIDATED
   ↓
BRONZE_COMPLETE
   ↓
SILVER_COMPLETE
   ↓
GOLD_COMPLETE
   ↓
INTENT_RESOLVED
   ↓
METRICS_RESOLVED
   ├── unresolved → NEEDS_INPUT
   ↓
CURRENT_STATE_MEASURED
   ├── quality failure → DATA_REPAIR / SUPPRESS
   ↓
OPERATIONALLY_DIAGNOSED
   ↓
AI_OPPORTUNITIES_ASSESSED
   ↓
BENCHMARKED
   ↓
VERIFICATION
   ├── reject → TARGETED_RETRY
   ├── low confidence → DIRECTIONAL
   └── repeated failure → HUMAN_REVIEW
   ↓
SYNTHESIZED
   ↓
FINDING_RELEASED
```

---

# 15. Context Isolation Policy

The context-isolation matrix is an architectural control.

```text
P1 / L4:
  business context + required evidence
  NO financial context

KPI Resolution:
  business goal + Gold semantics + framework definitions
  NO financial assumptions

Evidence:
  approved MetricContract + Gold
  NO narrative authority

Diagnosis:
  EvidenceBundle + Gold process models
  NO payroll unless explicitly required for a separate downstream calculation

AI Opportunity:
  verified gaps + diagnostics
  NO ability to rewrite source evidence

Benchmark:
  verified metric evidence + framework registry
  NO unrestricted financial assumptions

Verifier:
  independent access to source computation
  NO producer reasoning traces

Synthesis:
  verified records only
  NO source query access
```

Permissions should be technically enforced through:

```text
agent identity
tool allowlists
data/view permissions
artifact permissions
output-schema permissions
```

---

# 16. Provenance / Claim Graph

Every material customer-facing claim should have a machine-traceable chain:

```text
Finding
  ↓
Verified Record
  ↓
EvidenceBundle
  ↓
MetricContract
  ↓
Executable Query
  ↓
Gold Object
  ↓
Silver Transformation
  ↓
Bronze Snapshot
  ↓
Customer Source
```

This allows CLaiMB to answer:

- What exactly was measured?
- Which source produced it?
- What definition was used?
- Which SQL produced it?
- Was it independently verified?
- Which advisory depends on it?

---

# 17. Financial Value Contract

Financial value calculations are downstream of measured evidence.

## 17.1 Fully Loaded Cost

```text
FLC_r =
baseAnnualSalary_r × overheadMultiplier_r
```

## 17.2 Addressable Labor Pool

```text
ALP =
Σ(
  headcount_r
  × FLC_r
  × pctTimeOnFunction_r
  × pctAutomatable_r
)
```

## 17.3 Goal Gap

Lower is better:

```text
Gap =
(Current - Target) / Current
```

Higher is better:

```text
Gap =
(Target - Current) / Target
```

## 17.4 Value

```text
Total Annual Unlock =
Gap × ALP
```

## 17.5 Cash / Capacity Split

```text
Cash Benefit =
Total Annual Unlock × Realization Factor

Capacity Benefit =
Total Annual Unlock - Cash Benefit
```

Cash and capacity must remain separate in customer-facing output.

---

# 18. Internal Benchmark Policy

Customer evidence should be prioritized in this order:

```text
Customer-defined target
        ↓
Customer internal benchmark
        ↓
Qualified industry benchmark
        ↓
General external context
```

Internal benchmarking should be direction-aware.

```text
Higher-is-better → upper-tail statistic
Lower-is-better  → lower-tail statistic
```

A p75 rule is therefore not universal.

---

# 19. Closed-Loop Architecture

Once customers deploy recommended AI solutions, AI/workflow telemetry can re-enter the Data Agent.

```text
Baseline
  ↓
Finding
  ↓
AI Advisory
  ↓
Deployment
  ↓
AI / Workflow Telemetry
  ↓
Bronze
  ↓
Silver
  ↓
Gold
  ↓
Current-State Re-measurement
  ↓
Impact Verification
```

This enables CLaiMB to measure realized transformation rather than only recommending it.

---

# 20. Repository Structure

```text
skills/
├── bronze-ingest-staging/
│   └── SKILL.md
├── silver-conform-cleanse/
│   └── SKILL.md
├── gold-normalize-model/
│   └── SKILL.md
├── intent-business-scope/
│   └── SKILL.md
├── kpi-metric-resolution/
│   └── SKILL.md
├── evidence-current-state/
│   └── SKILL.md
├── operational-diagnosis/
│   └── SKILL.md
├── ai-opportunity-assessment/
│   └── SKILL.md
├── framework-benchmark-intelligence/
│   └── SKILL.md
├── verification-adversarial-review/
│   └── SKILL.md
└── executive-synthesis/
    └── SKILL.md

registry/
├── metric_registry/
├── process_ontology/
├── framework_registry/
├── diagnostic_modules/
├── advisory_catalog/
└── benchmark_sources/

artifacts/
├── bronze/
├── silver/
├── gold/
├── business_context/
├── metric_contracts/
├── evidence/
├── diagnostics/
├── ai_opportunities/
├── benchmarks/
├── verification/
└── findings/
```

---

# 21. Implementation Roadmap

## Phase 1 — Data Foundation

Build:

```text
Bronze → Silver → Gold
```

with source coverage, lineage, quality, and canonical semantic models.

## Phase 2 — Semantic Control

Build:

```text
Intent & Scope
KPI / Metric Resolution
```

with `BusinessFunctionContext` and `MetricContract`.

## Phase 3 — Evidence

Build:

```text
Evidence / Current State
```

with deterministic execution and provenance.

## Phase 4 — Verification

Build the verifier before expanding the finding catalogue.

Start with deterministic verification services and extend with adversarial semantic review where required.

## Phase 5 — Reasoning

Add:

```text
Operational Diagnosis
AI Opportunity / Suitability
Benchmark / Framework Intelligence
```

## Phase 6 — Synthesis

Release only through the verification gate.

## Phase 7 — Evaluation and Observability

Maintain:

- golden datasets
- regression tests
- agent execution telemetry
- provenance checks
- failure analysis

## Phase 8 — Closed-Loop Measurement

Ingest AI deployment telemetry back into the Medallion foundation.

---

# 22. Non-Negotiable System Invariants

1. No headline KPI without an approved `MetricContract`.
2. No metric without an executable computation.
3. No material number without provenance.
4. No finding without evidence.
5. No causal interpretation without supporting evidence.
6. No AI recommendation without a suitability assessment.
7. No benchmark without comparability checks.
8. No source failure may disappear silently.
9. No agent may access context outside its role.
10. No producer agent is the sole verifier of its own claim.
11. No synthesis agent can mutate verified numerical evidence.
12. No financial value without explicit assumptions.
13. No low-confidence evidence may silently become a high-confidence headline.
14. No repeated verification failure may be converted into a guessed answer.
15. The system must be able to return "not measurable" or "not sufficiently supported."

---

# 23. Architectural Thesis

The complete CLaiMB Data Agent is not simply:

```text
data → LLM → answer
```

It is:

```text
customer data
    ↓
faithful capture
    ↓
conformance
    ↓
business semantic model
    ↓
explicit business intent
    ↓
explicit KPI definition
    ↓
deterministic evidence
    ↓
operational diagnosis
    ↓
AI suitability
    ↓
contextual benchmark/framework evidence
    ↓
independent verification
    ↓
verified executive finding
```

The intended outcome is a Data Agent that can move from:

> "The customer wants to improve this."

to:

> "This is exactly what the goal means, this is the customer's measured current state, this is the observable operational gap, this is what the evidence supports as the operational cause, this is whether AI is appropriate, this is the relevant benchmark/context, and this is the independently verified evidence chain behind the recommendation."
