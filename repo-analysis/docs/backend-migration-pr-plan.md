# Backend Migration Plan (Tantivy + LMDB + RyuGraph)

This document translates the architecture target into a concrete, file-by-file PR sequence for this repository.

## Goals and non-goals

### Goals
- Interactive paths must never hydrate the full symbol payload (`load_symbol_index`) or full graph payload (`load_graph_view_uncached`).
- Route lexical/top-k retrieval to Tantivy.
- Route exact metadata/body/summary/cache reads to LMDB.
- Route graph traversal/path/slice operations to a graph backend (RyuGraph).
- Keep CLI/toolkit JSON output stable.

### Non-goals
- Removing SQLite build artifacts in the first PRs.
- Changing external command names or breaking existing toolkit consumers.

---

## Current hot-path touchpoints

### Search
- `repo-analysis/src/search/indexer.py`
  - `search_documents`
  - `search_documents_scoped`
  - `find_files`
  - `lookup_symbol_documents`
  - `load_agent_cache`

### Symbols/summaries/eval metadata
- `repo-analysis/src/symbols/persistence.py`
  - `load_summary_bundle_database`
  - `load_symbol_index`
  - `load_symbol_by_id`
  - `load_symbols_by_ids`
- `repo-analysis/src/evaluation/harness.py`
  - eval cache reads/writes currently using SQLite-backed flow

### Graph
- `repo-analysis/src/graph/store.py`
  - `write_graph_database`
- `repo-analysis/src/graph/query.py`
  - `execute_graph_query`
  - `where_defined`
  - `callers_of`
  - `callees_of`
  - `statement_slice`
  - `path_between`
  - `load_graph_view_uncached`

### Orchestration/public facade
- `repo-analysis/src/retrieval/engine.py`
  - `retrieve_context`
- `repo-analysis/src/retrieval/planner.py`
  - `prepare_answer_bundle`
- `repo-analysis/src/agents/toolkit.py`
  - public wrappers (`where_defined`, `get_symbol_signature`, `get_symbol_body`, `callers_of`, `callees_of`, `statement_slice`, `path_between`, `prepare_answer_bundle`, etc.)

---

## New backend interfaces (first-class contract)

Add a new package:

```text
repo-analysis/src/backends/
  search_backend.py
  metadata_store.py
  graph_backend.py
```

### `SearchBackend`
- `search(query, limit, kinds, path_prefix=None)`
- `find_file(path_pattern, limit)`
- `lookup_symbol_docs(symbol_id, kinds, limit)`
- `compare_repo_candidates(query, limit)`

### `MetadataStore`
- `get_symbol(symbol_id)`
- `get_symbols(symbol_ids)`
- `resolve_qname(qname)`
- `resolve_name(name, repo=None)`
- `get_symbol_body(symbol_id)`
- `get_summary_by_id(summary_id)`
- `get_summary_by_path(path)`
- `get_summary_by_symbol(symbol_id)`
- `get_eval_case(case_name, fingerprint)`
- `put_eval_case(...)`

### `GraphBackend`
- `neighbors(...)`
- `callers_of(...)`
- `callees_of(...)`
- `reads_of(...)`
- `writes_of(...)`
- `refs_of(...)`
- `implements_of(...)`
- `inherits_of(...)`
- `path_between(...)`
- `statement_slice(...)`

---

## PR sequence

## PR-0: Baseline instrumentation + guardrails

### Files to touch
- `repo-analysis/src/retrieval/engine.py`
- `repo-analysis/src/retrieval/planner.py`
- `repo-analysis/src/agents/toolkit.py`
- `repo-analysis/src/graph/query.py`
- `repo-analysis/src/search/indexer.py`
- `repo-analysis/src/symbols/persistence.py`

### Changes
1. Add timing spans around:
   - `search_documents`
   - `where_defined`
   - `get_symbol_signature`
   - `get_symbol_body`
   - `callers_of`
   - `callees_of`
   - `path_between`
   - `statement_slice`
   - `prepare_answer_bundle`
   - `retrieve_context`
2. Add counters:
   - full symbol payload loads (increment when `load_symbol_index` is called)
   - full graph payload loads (increment when `load_graph_view_uncached` is called)
3. Emit metrics in debug logs and optionally return in internal diagnostics payloads.

### Acceptance
- Existing tests pass.
- A benchmark/dev run can explicitly show whether full payload hydration happened.

---

## PR-1: Tantivy search cutover behind `SearchBackend`

### New files
- `repo-analysis/src/backends/search_backend.py`
- `repo-analysis/src/backends/tantivy/search.py`

### Existing files
- `repo-analysis/src/search/indexer.py` (document extraction/build helpers only)
- `repo-analysis/src/retrieval/engine.py`
- `repo-analysis/src/retrieval/planner.py`
- `repo-analysis/src/agents/toolkit.py`

### Changes
1. Introduce `SearchBackend` protocol/interface.
2. Implement Tantivy-backed backend adaptor.
3. Route current calls from toolkit/retrieval to backend methods instead of direct `search.indexer` hot-path SQLite reads.
4. Keep SQLite output generation optional for compatibility, but stop reading it on hot path.

### Acceptance
- `find-symbol`, `find-file`, and lexical retrieval in `retrieve_context` run via backend.
- No `load_agent_cache` usage in interactive path.

---

## PR-2: LMDB metadata cutover behind `MetadataStore`

### New files
- `repo-analysis/src/backends/metadata_store.py`
- `repo-analysis/src/backends/lmdb/store.py`
- `repo-analysis/src/backends/lmdb/codecs.py`

### Existing files
- `repo-analysis/src/symbols/persistence.py` (extraction/build only)
- `repo-analysis/src/evaluation/harness.py`
- `repo-analysis/src/agents/toolkit.py`
- `repo-analysis/src/retrieval/engine.py`

### Changes
1. Implement LMDB environment with named DBs:
   - `meta`, `file_by_path`, `symbol_by_id`, `symbol_ids_by_qname`, `symbol_ids_by_name`, `symbol_ids_by_path`, `body_by_symbol_id`, `statement_by_id`, `summary_by_id`, `summary_by_path`, `summary_by_symbol_id`, `eval_case_cache`, `prompt_payload_cache`, `bundle_score_cache`.
2. Move exact lookup flow to LMDB-first order:
   - `symbol_id` → `qname` → `name` → `path` → Tantivy fallback.
3. Route `where_defined`, `get_symbol_signature`, `get_symbol_body`, and summary lookups through `MetadataStore`.
4. Replace eval cache access in harness with LMDB reads/writes.

### Acceptance
- Interactive metadata commands no longer call `load_symbol_index`.
- Keyed symbol/body/summary lookups complete without whole-dataset hydration.

---

## PR-3: Graph execution cutover behind `GraphBackend` (RyuGraph)

### New files
- `repo-analysis/src/backends/graph_backend.py`
- `repo-analysis/src/backends/ryugraph/loader.py`
- `repo-analysis/src/backends/ryugraph/queries.py`

### Existing files
- `repo-analysis/src/graph/builder.py` (artifact extraction stays)
- `repo-analysis/src/graph/store.py` (sink changes to graph backend loader)
- `repo-analysis/src/graph/query.py`
- `repo-analysis/src/agents/toolkit.py`
- `repo-analysis/src/retrieval/planner.py`

### Changes
1. Keep graph artifact builder; swap sink from SQLite writer to RyuGraph bulk load.
2. Map toolkit commands to engine-native graph queries:
   - callers/callees/reads/writes/refs/implements/inherits/path/slice.
3. Remove Python BFS-style full adjacency dependence from interactive paths.
4. Keep summary nodes out of graph v1; hydrate summaries from LMDB by key.

### Acceptance
- Interactive graph commands no longer call `load_graph_view_uncached`.
- `path_between` and `statement_slice` run without full graph hydration.

---

## PR-4: Retrieval/bundle orchestration rewrite

### Files to touch
- `repo-analysis/src/retrieval/engine.py`
- `repo-analysis/src/retrieval/planner.py`
- `repo-analysis/src/agents/toolkit.py`

### Changes
1. Rewrite `retrieve_context` pipeline:
   - Tantivy lexical prune
   - optional embedding stage
   - RyuGraph expansion
   - LMDB hydration
   - rerank
   - bundle assembly
2. Rewrite `prepare_answer_bundle` to use backend contracts only.
3. Ensure provenance comes from Tantivy stored fields + LMDB payloads.

### Acceptance
- No full symbol or graph load counters increment in steady interactive runs.

---

## PR-5: Remove SQLite hot-path reads

### Files to touch
- `repo-analysis/src/search/indexer.py`
- `repo-analysis/src/symbols/persistence.py`
- `repo-analysis/src/graph/query.py`
- `repo-analysis/src/evaluation/harness.py`
- any CLI/build script toggles under `repo-analysis/scripts/`

### Changes
1. Delete/disable read paths for:
   - `search.sqlite3`
   - `symbols.sqlite3`
   - `graph.sqlite3`
   - `summary.sqlite3`
   - `eval.sqlite3`
2. Keep optional export/debug commands if needed.

### Acceptance
- Hot-path code uses only Tantivy + LMDB + RyuGraph.
- Backward-compatible JSON output remains unchanged.

---

## Risk controls

- Keep façade stable in `agents/toolkit.py`; migrate internals first.
- Feature-flag backend routing (`SEARCH_BACKEND`, `METADATA_BACKEND`, `GRAPH_BACKEND`) during transition.
- Add smoke tests that assert no full-load counters in interactive command tests.
- Retain one-release compatibility export for SQLite artifacts to ease rollback.

---

## First implementation checklist (next PR to open)

1. Land `src/backends/search_backend.py` + Tantivy adapter skeleton.
2. Add routing from `retrieval/engine.py` and `agents/toolkit.py` for lexical calls.
3. Add PR-0 counters for full symbol/graph loads.
4. Add regression test asserting no counter increment for `find-symbol`/`find-file`/`search-lexical`.

This gives the fastest measurable win while preserving current CLI surface.
