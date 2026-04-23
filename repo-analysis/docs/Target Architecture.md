# Repo-Analysis: Target Architecture and Phased Migration

## Purpose

`repo-analysis` should become a **repository intelligence layer for coding agents**, not just a local search tool.

The goal is to help an agent:

- reach a correct mental model of a repository faster
- spend fewer tokens on blind file reads
- retrieve smaller but more sufficient evidence sets
- stay grounded while answering, documenting, planning, and editing
- improve over repeated work on the same repository

The research in `docs/research/` points to one central conclusion:

**the problem is not mainly "better chunk retrieval."**
It is **cost-aware evidence acquisition over structured repository state**.

That means the long-term system should be optimized as a controller over:

- structured repository artifacts
- multi-view graph traversal
- selective retrieval and stopping
- evidence-set construction
- repository-native memory
- execution-derived signals
- evaluation of both quality and efficiency

This document translates that research into a staged architecture for the current repository.

## What The Current Prototype Already Gets Right

The current implementation already matches a meaningful part of the literature.

- It is **parser-first**, not embedding-first.
- It uses a **three-engine runtime** with Tantivy, LMDB, and RyuGraph.
- It already supports **symbols, statements, summaries, and graph traversal**.
- It already has an **agent-facing retrieval path** in `retrieve_context`, `plan_query`, and `prepare_answer_bundle`.
- It already treats embeddings as a **sidecar**, not the primary truth source.
- It already includes an early form of **selective retrieval gating**.

That is a strong base. The architecture in [Overview.md](/home/ops/dev/caxen/repo-analysis/docs/Overview.md) and [Design & Requirements.md](/home/ops/dev/caxen/repo-analysis/docs/Design%20&%20Requirements.md) is directionally correct.

## Where The Prototype Is Still Thin

The research corpus also makes the current gaps fairly clear.

### 1. Retrieval is still mostly heuristic

The current retrieval stack has lexical search, exact symbol lookup, graph expansion, reranking, and summaries, but it does **not yet estimate evidence sufficiency** or optimize for the **smallest sufficient evidence set**.

### 2. The graph is useful but not yet multi-view enough

The graph covers code structure well enough for the current slice, but the research strongly suggests that future gains will come from adding more views:

- code-to-test relations
- build/dependency/environment relations
- change-impact relations
- history-derived relations
- runtime/execution-derived relations

### 3. Summaries are present but shallow

The summary layer is useful for routing, but it is still mostly deterministic rollup text. It is not yet a richer abstraction layer for subsystem intent, dependency boundaries, change surfaces, or execution behavior.

### 4. There is no repository-native memory layer

The system currently indexes repository state, but it does not preserve **project memory** across tasks:

- prior successful retrieval paths
- design commitments
- active subsystem notes
- commit-history abstractions
- prior failure and regression signatures
- evolving task/specification state

### 5. Execution feedback is mostly outside the architecture

The research now makes it clear that build/test/runtime evidence should affect retrieval, ranking, and stopping. The current repo mostly stops before that layer.

### 6. Evaluation is too narrow for the next stage

The evaluation harness measures retrieval modes and interactive command latency, which is useful, but the next architecture needs additional metrics:

- explored vs utilized evidence
- prompt efficiency
- evidence sufficiency
- retrieval noise rate
- impacted-test ranking quality
- long-horizon memory reuse quality

## Target System

The best target for this repository is a **layered repository intelligence system** with one cross-cutting controller.

### Cross-cutting controller

This is the main architectural change in emphasis.

`repo-analysis` should stop acting like a passive collection of indexes and start acting like a **budgeted evidence controller** that decides:

- whether retrieval is needed
- which retrieval stage to use
- how far to expand
- which evidence items belong together
- when enough evidence has been collected
- when to run targeted verification
- when to stop

That controller should primarily live in the retrieval/planning surface, not in the storage engines.

### Layer 1. Artifact Ingestion

Purpose:

- scan repositories
- parse source code
- collect exact symbols and statements
- collect package/build/test metadata
- fingerprint artifacts for rebuilds

Current base:

- `src/symbols/indexer.py`
- `src/parsers/*`
- adapter inventory

Target extension:

- keep the current parser-first approach
- preserve per-repo isolated artifacts
- add language-specific parsers behind one normalized repository IR
- add normalized build/test/config metadata collection
- add change/history sidecars as optional artifacts

### Layer 2. Repository IR And Multi-View Graph

Purpose:

- store the repository as connected program entities rather than disconnected text
- support graph navigation, path search, slicing, impact propagation, and neighborhood expansion

Current base:

- `src/graph/builder.py`
- `src/backends/ryugraph/*`

Target graph views:

- file and directory hierarchy
- package/module ownership
- symbol/signature ownership
- call/reference edges
- type/inheritance/implementation edges
- selected data-flow / dependence edges
- code-to-test edges
- build/dependency/environment edges
- optional history and execution evidence edges

Design rule:

Keep the current graph runtime, but widen the graph schema only when an added edge family is queryable, benchmarkable, and cheap enough to justify its build/query cost.

### Layer 3. Retrieval And Localization

Purpose:

- localize candidate repository regions cheaply
- avoid early prompt flooding
- promote exact identity and structural relevance over text overlap

Current base:

- `src/search/indexer.py`
- `src/backends/tantivy/search.py`
- `src/retrieval/engine.py`

Target behavior:

1. summaries and coarse scopes first
2. exact symbol/file localization next
3. graph expansion inside the narrowed scope
4. body hydration only for likely winners
5. optional semantic sidecar only when lexical/structural paths are weak

Design rule:

Default to **coarse-to-fine hybrid retrieval**. Do not let embeddings become the default route.

### Layer 4. Evidence-Set Construction

Purpose:

- build a small, coherent evidence coalition rather than a top-k bag of hits
- reduce harmful and redundant context
- preserve dependency paths that matter

Current base:

- `prepare_answer_bundle`
- reranking and stage scoring

Target extension:

- utility-aware filtering
- coalition-aware evidence scoring
- bridge-node preservation
- ambiguity reduction scoring
- path-complete evidence bundles for explanation and edits

This is where the research on CODEFILTER, RepoShapley, selective retrieval, and caller-centric exploration fits most directly.

### Layer 5. Repository-Native Memory

Purpose:

- preserve repository knowledge across tasks and long sessions
- reduce repeated blind exploration
- carry forward trustworthy project state

This layer does not exist yet and should be added explicitly.

Memory objects should include:

- subsystem summaries refined through repeated use
- design commitments and architectural invariants
- recent active-module summaries
- prior successful localization trails
- prior failing retrieval trails
- commit-history abstractions
- regression signatures and impacted-test mappings
- evolving specification notes tied to repo entities

This memory should be **repository-native**, not generic chat transcript replay.

### Layer 6. Execution And Verification Signals

Purpose:

- turn build/test/runtime evidence into retrieval and planning signals
- reduce false confidence from static-only reasoning

This layer should eventually capture:

- failing test identifiers
- impacted-test candidates
- build/dependency failures
- unresolved imports/references
- stack trace anchors
- trace summaries
- runtime state transition summaries
- regression signatures

Design rule:

Execution should not be only a final gate. It should feed back into ranking, memory, and stopping.

### Layer 7. Evaluation And Observability

Purpose:

- measure whether the system is actually improving the agent
- separate retrieval quality from generation quality
- protect against "more context, same or worse outcome"

Current base:

- `src/evaluation/harness.py`
- telemetry and artifact metadata

Target metrics:

- retrieval recall and precision
- explored vs utilized evidence
- evidence bundle size and token cost
- sufficiency estimator quality
- harmful-context rate
- query latency
- verification-hit rate
- impacted-test ranking quality
- memory reuse lift
- end-task success under fixed budget

## Phased Migration

Each phase below is designed so the repository stays usable while it evolves.

### Phase 0. Stabilize The Current Core

Outcome:

- treat the current three-engine architecture as the stable baseline
- make it easy for a coding agent to use immediately

Work:

- preserve the current CLI and artifact layout
- make summary-first and exact-lookup-first usage the default agent workflow
- improve artifact metadata and telemetry so retrieval decisions can be inspected
- harden the current summary and answer-bundle path

Why this first:

The current system is already good enough to complement an agent today if it is used as a **routing surface** rather than as a general-purpose semantic search box.

### Phase 1. Retrieval Quality Before New Complexity

Outcome:

- improve localization, reranking, and prompt efficiency without changing the runtime shape

Work:

- add stronger query typing and route selection
- strengthen summary-scope localization
- improve suppression of low-value artifacts like locals/tests/scaffolding when not requested
- add evidence-bundle diagnostics
- add retrieval-noise metrics to evaluation

Code focus:

- `src/retrieval/engine.py`
- `src/retrieval/planner.py`
- `src/backends/tantivy/search.py`
- `src/evaluation/harness.py`

Why this phase:

The research strongly suggests that better control over the current layers is higher leverage than immediately adding more storage or more embeddings.

### Phase 2. Multi-View Graph Expansion

Outcome:

- move from "code graph" to "repository evidence graph"

Work:

- add code-to-test edges
- add build/dependency/environment nodes and edges
- add change-impact-oriented edges where feasible
- expose graph queries that can support impacted-test and execution-aware reasoning

Code focus:

- `src/graph/builder.py`
- `src/backends/ryugraph/queries.py`
- `src/agents/toolkit.py`

Why this phase:

This is the point where the system starts to reflect the stronger 2025-2026 graph literature instead of only the earlier symbol/call graph shape.

### Phase 3. Sufficiency And Evidence-Set Control

Outcome:

- stop optimizing for "more relevant hits"
- start optimizing for "smallest sufficient evidence set"

Work:

- add a sufficiency estimator
- add stop/continue decisions to retrieval loops
- add coalition-aware evidence filtering
- add evidence attribution hooks
- add evaluated prompt-budget targets

Code focus:

- `src/retrieval/engine.py`
- `src/retrieval/planner.py`
- new `src/evidence/` or `src/control/` package
- `src/evaluation/harness.py`

Why this phase:

This is the phase most directly tied to the user goal of better accuracy with fewer tokens.

### Phase 4. Repository-Native Memory

Outcome:

- support repeated work on the same repository without starting from zero each time

Work:

- add a repository memory store
- define schemas for project-state objects
- store reusable subsystem and localization memories
- store spec deltas and design commitments
- add retrieval routes that can consult memory before broad repo search

Code focus:

- new `src/memory/` package
- LMDB buckets for memory artifacts
- retrieval/planner integration

Why this phase:

The long-horizon papers suggest memory becomes essential once the tool is used across many sessions and tasks, not only once per repo.

### Phase 5. Execution-Aware Loop

Outcome:

- close the loop between static retrieval and executable verification

Work:

- ingest targeted build/test/runtime evidence
- rank and route by impacted tests
- turn trace and failure evidence into reusable retrieval signals
- support execution-aware refinement of answer bundles and edit plans

Code focus:

- new `src/execution/` package
- graph and memory integration
- evaluation harness expansion

Why this phase:

This is where repo understanding becomes behavior-aware rather than only structure-aware.

## Recommended Immediate Operating Mode

Until later phases exist, the best way to use the current repo with a coding agent is:

1. `repo-overview` and `summarize-path` first
2. `find-symbol`, `find-file`, `where-defined`, `get-symbol-signature` next
3. `callers-of`, `callees-of`, `who-imports`, `path-between`, `statement-slice` only after localization
4. `plan-query` or `prepare-answer-bundle` before asking the model for a final explanation
5. targeted tests/builds outside the tool after the retrieval phase

That makes the current prototype act like a **repo router** rather than a last-mile answer engine.

## Concrete Recommendation For This Repository

The best next implementation order is:

1. strengthen retrieval diagnostics and routing
2. add evidence-set metrics and prompt-efficiency evaluation
3. expand the graph to include code-test and build/dependency relations
4. add a sufficiency-aware control layer
5. add repository-native memory
6. add execution-derived signals

In other words:

**keep the current three-engine core, but evolve the system upward into a controller over evidence, memory, and verification.**

That is the migration path most consistent with both the current codebase and the research folder.
