# Competitive Landscape — Who Else Is Building This

Research pass answering: is anyone (GitHub, Anthropic, AWS, enterprise
vendors) already doing what the CLaiMB 11-layer architecture proposes,
and better? Companion to `docs/claimb-idea-fit.md` and
`docs/claimb-pilot-run.md`.

## The landscape splits into two things people call "data agents" — and CLaiMB is not really competing with the first one

### 1. NL-to-SQL / "chat with your warehouse" — mature, crowded, not our differentiator

These answer questions over a governed semantic layer. This is CLaiMB's
L5-L6 territory (KPI resolution + evidence), and it's the most
battle-tested, well-funded part of the whole space:

| Product | What it actually is | Relevant to CLaiMB |
| --- | --- | --- |
| **Snowflake Cortex Analyst** | NL-to-SQL over Snowflake semantic views, with a documented "Verified Query Repository" of trusted NL/SQL pairs used as ground truth | Same idea as CLaiMB's L6 evidence provenance / query_hash, already productized and battle-tested at scale |
| **Databricks Genie** | NL-to-SQL/action agent grounded in an auto-populated "Genie Ontology"; 1.5M+ Genie Spaces created in 2026 | Ontology-grounding is more automated than anything in CLaiMB's L4/L5 design today |
| **Microsoft Fabric Copilot / Fabric IQ** | NL-to-SQL over Power BI semantic models, deeply integrated with Teams/Power BI | Most mature for BI-analyst workflows specifically |
| **[Wren AI](https://github.com/Mu-L/WrenAI)** (open source, ~10-14k stars) | Full "GenBI" stack: semantic layer + NL-to-SQL + charts + governed dashboards + embeddable API | Best open-source analog to a real semantic layer + evidence engine combined |
| **[Vanna](https://github.com/vanna-ai/vanna)** (open source, ~20-22k stars) | Lighter-weight, RAG-based text-to-SQL, MIT-licensed, easy to embed | Good for a minimal L6 evidence engine; less opinionated about semantics than Wren AI |

**Verdict on this category:** if we tried to build CLaiMB's L1-L6 entirely
from scratch, we'd be re-deriving a smaller, less mature version of what
Cortex Analyst, Genie, or Wren AI already do extremely well (semantic
layer + verified-query pattern + NL-to-SQL). This is not where CLaiMB should
spend novel engineering effort — see recommendation below.

### 2. Diagnose-a-gap → judge-AI-suitability → adversarially-verify → produce-a-defensible-finding — nobody is really doing this as a product

This is CLaiMB's actual differentiation: L7 (causal diagnosis with explicit
observed-vs-hypothesis labeling), L8 (AI-suitability scoring with a
`NO_AI_RECOMMENDATION` outcome as a first-class result), and L10
(independent adversarial verification with bounded retries before a
customer ever sees a claim). Closest things found:

| Project | How close is it? |
| --- | --- |
| **[Palantir AIP](https://www.palantir.com/docs/foundry/architecture-center/aip-architecture)** | Closest philosophical cousin. Ontology (≈ CLaiMB Gold+Intent) → AIP Logic → governed Actions with human-approval checkpoints (≈ CLaiMB's gate pattern). But it's a general enterprise action/orchestration platform — it doesn't ship a specialized "diagnose a KPI gap, score AI-fit, adversarially verify the causal story" pipeline. You'd build CLaiMB's L7-L10 logic *on top of* something like AIP, not get it for free from it. |
| **[Astronomer's agent tooling](https://github.com/astronomer/agents)** | MCP server + skills for Airflow/data-engineering workflows in Claude Code / Cursor — a real, current example of "skills for data infrastructure," structurally similar to what we just built (`.claude/skills/*`), but scoped to pipeline ops, not to KPI-diagnosis-and-verification. |
| **[Datus-agent](https://github.com/Datus-ai/Datus-agent)** | Open-source "AI-native context engineering for data" — SQL authoring/validation + semantic model + pipeline/report generation, with a self-correcting context loop. Has a validation step but not a distinct adversarial-verification *layer* with bounded retries the way CLaiMB's L10 specifies. |
| **Various GitHub multi-agent data-analyst repos** ([shakil1819](https://github.com/shakil1819/Multi-Agent-Data-Analyst), [ComposioHQ](https://github.com/ComposioHQ/data-analyst-agent), [K-Dense-AI's agentic-data-scientist](https://github.com/K-Dense-AI/agentic-data-scientist)) | Multi-agent task decomposition for analysis (planner/executor splits), some with continuous validation, but none document CLaiMB's specific chain: MetricContract → EvidenceBundle → DiagnosticRecord (with causal_status) → AIOpportunityRecord (with `NO_AI_RECOMMENDATION` as a valid output) → BenchmarkRecord (with suppression) → independent re-execution verification. |
| **AWS Bedrock AgentCore + Strands SDK** | A coordinator-agent-with-isolated-subagents *substrate* (identity, memory, a Cedar policy engine for governance, MCP access to Glue/Athena/S3 Tables) — this is infrastructure you'd build CLaiMB on, not a competing finished architecture. Genuinely useful as a hosting/governance layer if this ever needs real multi-tenant production infrastructure. |

**Verdict on this category:** nothing found productizes CLaiMB's specific
L7-L11 chain end to end. This is the actual novel part of the proposal.

## What this means for the build decision

1. **Don't rebuild L1-L6 from scratch as differentiation** — that's exactly
   the ground Cortex Analyst / Databricks Genie / Wren AI have spent years
   and huge budgets on. Our own hands-on medallion pipeline
   (`dbt/customer_platform/`) is a fine learning exercise and a fine
   substrate for the CLaiMB *pilot*, but a real product should strongly
   consider sitting on top of an existing semantic-layer/NL-to-SQL engine
   (Wren AI's open-source stack is the most credible free option; Cortex
   Analyst if already on Snowflake) rather than re-deriving evidence/query
   verification machinery that already exists and is better-tested elsewhere.
2. **This changes the cost-per-finding math from the earlier pilot** — if
   L5/L6 can be delegated to an existing semantic-layer product's verified-query
   pattern instead of custom-built and custom-verified, that's real
   engineering (and LLM-call) cost removed from the chain we costed in
   `docs/claimb-pilot-run.md`. Worth re-running that cost exercise assuming
   "L1-L6 via Wren AI / Cortex Analyst" rather than "L1-L6 fully custom."
3. **L7-L11 is where to actually invest** — diagnosis with explicit
   causal-status labeling, AI-suitability scoring with a real
   `NO_AI_RECOMMENDATION` path, and independent adversarial verification
   before synthesis. This pilot (`docs/claimb-pilot-run.md`) already showed
   these guardrails firing correctly on weak evidence — that's the part of
   the architecture actually worth refining and, eventually, building for real.
4. **Palantir AIP is worth a closer read**, not to copy but to compare
   governance patterns — their "agents interact only through Ontology-exposed
   objects/relationships/actions, never raw tables" rule is functionally the
   same discipline as CLaiMB's context-isolation policy (section 15 of the
   architecture doc) and this repo's Gold-layer boundary rule, and it's
   useful evidence that a large, scrutinized enterprise platform converged
   on the same design principle independently.

## Sources

- [Snowflake Cortex Analyst vs. Databricks Genie (2026)](https://colrows.com/blogs/cortex-analyst-vs-genie/)
- [Databricks Genie 2026 Upgrade](https://www.refontelearning.com/blog/databricks-genie-upgrade-business-analysts)
- [Microsoft Fabric IQ vs Snowflake Cortex vs Databricks Unity Catalog — ontology architecture 2026](https://pub.towardsai.net/microsoft-fabric-iq-vs-snowflake-cortex-vs-databricks-unity-catalog-the-enterprise-ontology-21457d9ed831)
- [Wren AI (GitHub)](https://github.com/Mu-L/WrenAI)
- [Vanna (GitHub)](https://github.com/vanna-ai/vanna)
- [Wren AI vs. Vanna comparison](https://medium.com/wrenai/wren-ai-vs-vanna-why-teams-choose-semantic-driven-genbi-over-basic-text-to-sql-7c818a51ff66)
- [Palantir AIP architecture overview](https://www.palantir.com/docs/foundry/architecture-center/aip-architecture)
- [Palantir AIP Agent-Ontology Interaction deep dive](https://zerofuturetech.substack.com/p/palantir-aip-agent-ontology-interaction)
- [Astronomer agents (GitHub)](https://github.com/astronomer/agents)
- [Datus-agent (GitHub)](https://github.com/Datus-ai/Datus-agent)
- [Multi-Agent Data Analyst (GitHub, shakil1819)](https://github.com/shakil1819/Multi-Agent-Data-Analyst)
- [ComposioHQ data-analyst-agent (GitHub)](https://github.com/ComposioHQ/data-analyst-agent)
- [Agentic Data Scientist (GitHub, K-Dense-AI)](https://github.com/K-Dense-AI/agentic-data-scientist)
- [AWS Bedrock AgentCore multi-agent orchestration (2026)](https://aws.amazon.com/blogs/industries/multi-agent-multimodal-data-analysis-on-aws-part-2-multi-agent-orchestration-and-predictive-analytics/)
- [Multi-cloud lakehouse architecture on AWS for Agentic AI](https://aws.amazon.com/blogs/big-data/multi-cloud-lakehouse-architecture-on-aws-for-agentic-ai-part-1-architecture-and-best-practices/)
- [Claude Skills architecture guidance](https://hatchworks.com/blog/claude/skills-architecture/)
