# Modular, Gate-Locked Agent Workflow Architecture

This document provides a comprehensive technical overview of an **Orchestrator-Worker Agent Pipeline**, a multi-agent framework designed for data architecture, schema reconciliation, and transformation pipelines.

## 1. High-Level Architecture & Workflow Design

The system follows an **Orchestrator-Worker Pattern** governed by a strict state-machine validation layer (`gate-hook.py`). Execution is gate-locked: operations remain blocked until intent is classified, routes are selected, and explicit human approval is received.

```text
                     ┌──────────────────────────────┐
                     │       User Entry Point       │
                     └──────────────┬───────────────┘
                                    │
                                    ▼
                     ┌──────────────────────────────┐
                     │      Orchestrator Agent      │
                     │   (Intent & Route Selection) │
                     └──────────────┬───────────────┘
                                    │
       ┌────────────────────────────┼────────────────────────────┐
       ▼                            ▼                            ▼
 [Route A: Standard]        [Route B: Source Map]      [Route C: Full Pipeline]
 (Standards QA)             (Target Lookup)            (New / Existing Work)
                                                                  │
                                                                  ▼
                                                   ┌──────────────────────────────┐
                                                   │    Gate-Lock Verification    │
                                                   │  (gate-hook.py Active)       │
                                                   └──────────────┬───────────────┘
                                                                  │
                                                                  ▼
                      ┌────────────────────────────────────────────────────────────┐
                      │                 PARALLEL EXECUTION BATCH                   │
                      │                                                            │
                      │  ┌─────────────────┐ ┌─────────────────┐ ┌────────────────┐│
                      │  │ Phase 0: Drift  │ │ Phase 1: Source │ │ Phase 2: Entity ││
                      │  │ Schema Check    │ │ Exploration     │ │ Mapping        ││
                      │  └────────┬────────┘ └────────┬────────┘ └───────┬────────┘│
                      │           │                   │                  │         │
                      │           └─────────────────┐ │ ┌────────────────┘         │
                      │                             ▼ ▼ ▼                          │
                      │                      ┌────────────────┐                    │
                      │                      │ Phase 3: Domain│                    │
                      │                      │ Journey Design │                    │
                      │                      └────────────────┘                    │
                      └──────────────────────────────┬─────────────────────────────┘
                                                     │
                                                     ▼
                                      ┌──────────────────────────────┐
                                      │      Gate 1: User Approval   │
                                      │   (Blueprint Review)         │
                                      └──────────────┬───────────────┘
                                                     │
                                                     ▼
                                      ┌──────────────────────────────┐
                                      │   Phase 4: Main Blueprint    │
                                      │   & Digest Generation        │
                                      └──────────────┬───────────────┘
                                                     │
                                                     ▼
                                      ┌──────────────────────────────┐
                                      │ Phase 4.5: Plan Validation    │
                                      │    (Read-Only Dry-Run SQL)    │
                                      └──────────────┬───────────────┘
                                                     │
                                                     ▼
                                      ┌──────────────────────────────┐
                                      │     Plan Approval Gate       │
                                      │      (Write Files)            │
                                      └──────────────┬───────────────┘
                                                     │
                                                     ▼
                                      ┌──────────────────────────────┐
                                      │ Phase 5: Implementation &     │
                                      │ Post-Build Validation (5.5)  │
                                      └──────────────────────────────┘
```

## 2. Core Execution Flow

```text
+-----------------------------------------------------------------------------------------------+
|  1. ENTRY & ORCHESTRATION                                                                     |
|  Orchestrator Agent evaluates payload intent and maps route. Gate locks prevent execution.    |
+-----------------------------------------------------------------------------------------------+
                                               |
                                               v
+-----------------------------------------------------------------------------------------------+
|  2. PARALLEL ANALYSIS & DISCOVERY (Phases 0–3)                                                |
|  - Phase 0: Schema Drift Check (Data Platform Connectors)                                     |
|  - Phase 1: Source Exploration & Profiling (Subagent)                                         |
|  - Phase 2: Entity & Attribute Mapping (Subagent)                                             |
|  - Phase 3: Journey & Relationship Design (Subagent)                                          |
|                                                                                               |
|  * Note: Phases 0–3 fire in parallel as a single message batch.                              |
+-----------------------------------------------------------------------------------------------+
                                               |
                                               v
+-----------------------------------------------------------------------------------------------+
|  3. BLUEPRINT & DRY-RUN VALIDATION (Phases 4–4.5)                                             |
|  - Phase 4: Master Blueprint Design & Digest Generation (Main Agent)                          |
|  - Phase 4.5: Read-Only Plan Validation & Dry-Run SQL Verification (Subagent)                 |
+-----------------------------------------------------------------------------------------------+
                                               |
                                               v
+-----------------------------------------------------------------------------------------------+
|  4. IMPLEMENTATION & TESTING (Phases 5–5.5)                                                   |
|  - Plan Approval Gate: Human Approval & Plan Archival (plans/*.html)                         |
|  - Phase 5: Model & Schema Implementation (Main Agent)                                       |
|  - Phase 5.5: Development Environment Testing & Row-Count Verification (Main Agent)          |
+-----------------------------------------------------------------------------------------------+
```

## 3. Detailed Stage Descriptions (Phases 0 through 5.5)

### Phase 0: Schema Drift Check
* **Role:** Schema Validation Subagent
* **Integrations:** Data Warehouse, Data Transformation Framework, Data Integration Engine.
* **Process:** Compares declared source definitions against target raw/bronze tables in development and production environments against active ingestion streams.
* **Output:** `Schema Drift Report` (`schema-drift`).

### Phase 1: Discovery & Source Exploration
* **Role:** Source Analysis Subagent
* **Integrations:** Automated Profilers, Metadata Catalogs.
* **Process:** Performs entity identification, grain determination, primary/foreign key discovery, and data quality profiling across target sources.
* **Output:** `Source Analysis Report` (`source-analysis`). Requires human sign-off.

### Phase 2: System Mapping
* **Role:** Entity Mapping Subagent
* **Integrations:** Source Connectors (Business Applications, Operational Platforms, Communication Systems).
* **Process:** Constructs column-level target mappings across disparate sources. Resolves timezone normalization, update keys, Slowly Changing Dimensions (SCD Type 2) strategies, and interaction status definitions.
* **Output:** System Mapping Matrix.

### Phase 3: Domain & Journey Design
* **Role:** Domain Design Subagent
* **Integrations:** Identity Resolution Engine, Relational Graph Tools.
* **Process:** Models stage transitions, entry/exit rules, multi-source identity resolution, parent-child rollups, attribution modeling, and complex join strategies (Left, Outer, Anti, Semi, Window joins).
* **Output:** `Journey Design Specification` (`journey-design`).

### Phase 4: Master Blueprint Architecture
* **Role:** Main Orchestrator Agent
* **Integrations:** System Architecture Generator.
* **Process:** Consolidates findings from Phases 0–3 into a 9-section Data Model Blueprint detailing grains, field mapping tables, metric SQL logic, dependency graphs, and data quality flags. Generates an executive Design Digest for review.
* **Output:** `Data Model Blueprint` (`blueprint`). Requires human sign-off.

### Phase 4.5: Plan-Phase Data Validation
* **Role:** Data Validation Subagent (Read-Only)
* **Integrations:** Sandboxed Read-Only Query Engine.
* **Process:** Executes dry-run SQL queries against target environments to evaluate join match percentages, key coverage metrics, value distribution patterns, and pre-execution validation checks.
* **Output:** `Validation Report` (`validation`).

### Plan Approval Gate (Gate Hook Enforcement)
* **Role:** Main Orchestrator Agent
* **Process:** Compiles drift analysis, validation queries, and blueprint documentation into a finalized artifact archived under `plans/plan_[timestamp].html`. Blocks local file modification until explicit plan approval is granted.

### Phase 5: Code Implementation
* **Role:** Transformation Implementation Agent (Main)
* **Integrations:** Data Modeling Engine, Schema Generators, Version Control Tools.
* **Process:** Generates Staging, Silver, Gold, and Platinum analytical models along with schema testing suites and mapping views while adhering to standard coding practices.

### Phase 5.5: Post-Build Validation
* **Role:** Data Validation Agent (Main)
* **Integrations:** Development Sandbox Database Environment.
* **Process:** Compiles and tests models in an isolated development environment (`development_sandbox`). Conducts pre/post row count checks and data variance analyses between development and production environments before preparing commit summaries.
* **Output:** `Model Validation Report` (`model-validation`).

## 4. Execution Matrix & Safety Mechanisms

| Phase | Task / Stage Name | Execution Agent | Tool / Integration Layer | Key Deliverable / Artifact Output | Enforcement Mechanism |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **0** | **Schema Drift Check** | Schema Validation Subagent | Data Warehouse, Transformation Engine & Data Connectors | `Schema Drift Report` (`schema-drift`) | Hard Gate (`gate-hook.py`) |
| **1** | **Source Exploration** | Source Analysis Subagent | Automated Data Profilers & Metadata Inspection | `Source Analysis Report` (`source-analysis`) | User Approval Gate |
| **2** | **System Mapping** | Entity Mapping Subagent | Business Application Integration Connectors | Column-level target map (including timezone, update keys, SCD2 strategy, and status definitions) | Automated Validation |
| **3** | **Journey Design** | Domain Design Subagent | Identity Resolution Engine & Relational Graphs | Stage models, identity resolution, parent-child rollups, and complex join definitions (`journey-design`) | Automated Validation |
| **4** | **Master Blueprint Design** | Main Orchestrator Agent | System Architecture Generator | 9-Section Data Model Blueprint + Executive Design Digest (`blueprint`) | User Approval Gate |
| **4.5** | **Plan Validation** | Data Validation Subagent | Sandboxed Read-Only Query Engine | Real-query execution report (join match percentages, key coverage, value distributions) | Read-Only Dry Run |
| **—** | **Plan Archival / Approval Gate** | Main Orchestrator Agent | Local File System Operations | Archived full plan document (`plans/plan_*.html`) | Gate Hook Enforcement |
| **5** | **Implementation** | Transformation Implementation Agent | Modeling Frameworks & Version Control Tools | Staging/Silver/Gold models, schema definitions, standard view transformations | Local File System Commit |
| **5.5** | **Post-Build Validation** | Data Validation Agent | Development Sandbox Database | Pre/post row-count checks, variance reports, and standard commit message (`model-validation`) | Development-Only Execution Rule |

## 5. Security & Safety Guardrails

1. **Gate-Locked Invocations:** Agents are prohibited from performing file edits or destructive actions prior to explicit user authorization at defined milestone checkpoints.
2. **Deterministic Execution:** The gate hook monitors pipeline state. If a required subagent step fails or is skipped, execution halts immediately.
3. **Sandbox Isolation:** All dry-run validations in Phase 4.5 execute strictly in read-only mode. Code compilation and testing in Phase 5.5 take place exclusively within development sandbox environments (`development_sandbox`), preventing premature production exposure.
