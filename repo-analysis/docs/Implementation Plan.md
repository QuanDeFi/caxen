Use this as the implementation plan.

## Target

Make the hot path genuinely:

* **Tantivy** for lexical retrieval
* **LMDB** for metadata, summaries, and eval cache
* **graph engine** for graph traversal and path queries

Right now the repo only has the abstraction layer. `MetadataStore` still serves SQLite, `RyuGraphBackend` still reads `ryugraph.json` or SQLite, and `SearchBackend` is still a wrapper around `search.indexer` with SQLite fallback. `graph.query` also still falls back to full graph and symbol loads for non-covered operations.    

## Definition of done

You are done only when all of these are true:

* `retrieve_context`, `prepare_answer_bundle`, `where_defined`, `get_symbol_signature`, `get_symbol_body`, `neighbors`, `callers_of`, `callees_of`, `reads_of`, `writes_of`, `refs_of`, `statement_slice`, and `path_between` do **not** read `symbols.sqlite3`, `graph.sqlite3`, `summary.sqlite3`, or `search.sqlite3` on the interactive path.
* `load_symbol_index()` and `load_graph_view_uncached()` are never called from interactive commands.
* `CAXEN_ENABLE_SQLITE_HOTPATH_READS` can be deleted without breaking runtime behavior.
* Search still returns the same or better top results.
* Benchmarks improve on latency and do not regress relevance.   

---

## Phase 0 — Freeze the baseline

### Goal

Create a stable benchmark and telemetry baseline before changing engines.

### Work

Keep and extend the current telemetry:

* count full symbol payload loads
* count full graph payload loads
* time each interactive command
* time search, graph expansion, metadata hydration separately

Telemetry already exists and should be the migration gate. 

### Add

Extend tests to assert zero full payload loads for:

* `path_between`
* `statement_slice`
* `prepare_answer_bundle`
* `retrieve_iterative`
* graph-heavy compare paths

### Deliverable

A benchmark report on:

* `find-symbol`
* `find-file`
* `where-defined`
* `get-symbol-signature`
* `get-symbol-body`
* `callers-of`
* `callees-of`
* `path-between`
* `statement-slice`
* `prepare-answer-bundle`

---

## Phase 1 — Make search truly Tantivy-first

### Goal

Remove SQLite FTS from the hot path.

### Why first

The code is already closest here. `search_documents()` already prefers Tantivy and only falls back to SQLite. 

### Changes

#### 1. Split search build from search serving

In `repo-analysis/src/search/indexer.py`:

* keep `build_documents()`
* keep Tantivy build
* move SQLite build behind a debug/export flag
* stop treating `search.sqlite3` as required runtime state

#### 2. Replace `TantivySearchBackend`

In `repo-analysis/src/backends/tantivy/search.py`:

* stop calling `search.indexer.search_documents()` as the primary API
* call the native BM25/Tantivy query path directly
* remove fallback to `lookup_symbol_documents()` except under an explicit compatibility flag

Right now `TantivySearchBackend` is only a wrapper around legacy functions. 

#### 3. Add a real stored-field retrieval contract

Tantivy results must return enough fields so planner/toolkit never need SQLite for search results:

* `doc_id`
* `kind`
* `path`
* `name`
* `qualified_name`
* `symbol_id`
* `title`
* `preview`
* `score`
* compact metadata

#### 4. Replace these hot-path callers

* `find_symbol`
* `find_file`
* `search_lexical`
* lexical stage of `retrieve_context`
* compare-repo candidate retrieval

These already go through `SearchBackend`, so the refactor is contained.   

### Deliverable

Interactive search works with no SQLite dependency.

---

## Phase 2 — Replace the metadata shim with real LMDB

### Goal

Remove SQLite from metadata, summaries, and eval cache reads.

### Why second

This removes `load_symbol_index()` pressure and fixes exact-lookup latency.

### Current problem

`LmdbMetadataStore` is not LMDB. It is a SQLite compatibility bridge. 

### Changes

#### 1. Implement a real LMDB environment

Replace `repo-analysis/src/backends/lmdb/store.py` with a real LMDB-backed store.

Use named databases:

* `symbol_by_id`
* `symbol_ids_by_qname`
* `symbol_ids_by_name`
* `file_by_path`
* `body_by_symbol_id`
* `summary_by_id`
* `summary_by_path`
* `summary_by_symbol_id`
* `eval_case_cache`

#### 2. Add a metadata build sink

Add a new writer in `symbols.persistence.py`:

* `write_lmdb_metadata_bundle(...)`

It should write:

* symbol payloads
* exact indexes
* statement slices or body fragments needed for `get_symbol_body`
* summary payloads
* optional file metadata

Do **not** keep summary lookup split between `symbols.sqlite3` and `summary.sqlite3` in the new hot path.

#### 3. Change `MetadataStore`

Keep the protocol in `backends/metadata_store.py`, but change `get_metadata_store()` to return real LMDB.

#### 4. Update callers

These must become LMDB-only:

* `where_defined`
* `get_symbol_signature`
* `get_symbol_body`
* `get_enclosing_context` metadata portion
* summary lookup in planner
* eval cache in `evaluation.harness`

Today toolkit still falls back to `load_symbol_by_id()` in some cases; remove that once LMDB is live. 

### Deliverable

Exact symbol, summary, and eval reads are LMDB-only.

---

## Phase 3 — Replace JSON graph serving with a real graph engine

### Goal

Stop reading `ryugraph.json` as a fake graph backend.

### Current problem

`RyuGraphBackend` is not using a graph DB. It scans `ryugraph.json`, and `write_ryugraph_payload()` just dumps JSON.  

### Changes

#### 1. Decide one graph runtime

Use one real engine for:

* `neighbors`
* `callers_of`
* `callees_of`
* `reads_of`
* `writes_of`
* `refs_of`
* `implements_of`
* `inherits_of`
* `statement_slice`
* `path_between`
* `symbol_summary`

#### 2. Change `graph/store.py`

`write_graph_database()` currently writes SQLite and then emits JSON. Replace this with:

* graph artifact generation
* native graph load
* optional debug export

The builder is already good enough: `build_graph_artifact()` emits the right node/edge structure. Keep that. 

#### 3. Replace `backends/ryugraph/loader.py`

Turn it into a real loader:

* create node tables / graph schema
* bulk insert nodes
* bulk insert edges
* persist backend metadata

#### 4. Replace `backends/ryugraph/queries.py`

Implement engine-native queries for:

* seed resolution
* first-hop and multi-hop neighbor expansion
* incoming/outgoing edge queries
* shortest path
* statement graph traversal
* symbol summary aggregation

Right now `statement_slice` and `path_between` are missing in this backend and therefore fall back to legacy code. 

#### 5. Delete the Python traversal fallback

In `graph/query.py`:

* remove `load_graph_view()`
* remove `load_symbols_payload()` from graph execution
* keep only adapter logic around the graph backend

Right now `execute_graph_query()` still falls back to loading graph payloads and symbol payloads if the backend returns `None`. That must go. 

### Deliverable

All graph operations are served by the graph engine, not Python adjacency over JSON/SQLite.

---

## Phase 4 — Refactor retrieval around the real backends

### Goal

Make the main agent path use only the three new systems.

### Current state

`retrieve_context()` already goes through `SearchBackend`, `GraphBackend`, and `MetadataStore`, but the backends are still transitional. 

### Changes

#### 1. `retrieve_context`

Keep the current overall flow:

* lexical prune
* optional embeddings
* graph expansion
* metadata hydration
* rerank
* summary bonus

But enforce:

* lexical results from Tantivy only
* graph expansion from graph engine only
* symbol hydration from LMDB only
* summary bonus from LMDB only

#### 2. `prepare_answer_bundle`

In `retrieval/planner.py`:

* keep using `GraphBackend` and `MetadataStore`
* remove `load_summary_artifacts()` from the interactive path
* fetch summaries from LMDB
* remove any assumption that `summary.sqlite3` exists

Planner already routes most of this correctly; the backend implementations are the missing piece. 

#### 3. `agents/toolkit.py`

Remove fallback usage of:

* `load_symbol_by_id`
* summary artifact scans
* graph legacy wrappers once graph backend covers all operations

### Deliverable

The planner/toolkit layer becomes pure orchestration.

---

## Phase 5 — Migrate eval cache off SQLite

### Goal

Move benchmark reuse into LMDB and update cache fingerprints.

### Current state

`evaluation.harness` still creates and fingerprints `eval.sqlite3`, and fingerprints still include legacy artifacts such as `symbols.sqlite3`, `graph.sqlite3`, `search.sqlite3`, and `summary.sqlite3`. 

### Changes

#### 1. Change eval cache implementation

Move `get_eval_case()` and `put_eval_case()` fully into LMDB.

#### 2. Update artifact fingerprinting

Fingerprint:

* Tantivy index manifest
* LMDB metadata build manifest
* graph backend build manifest

Do not fingerprint removed SQLite artifacts.

#### 3. Keep exported JSON reports

`benchmarks.json`, `bundle_scores.json`, and prompt export JSON can stay.

### Deliverable

Eval caching is LMDB-backed and consistent with the new runtime.

---

## Phase 6 — Remove compatibility mode

### Goal

Delete the old hot-path code.

### Remove

* SQLite hot-path reads in `search.indexer.search_documents`
* compatibility `LmdbMetadataStore` SQLite code
* `graph.sqlite3` runtime dependency
* `ryugraph.json` runtime dependency
* `load_symbol_index()` in interactive paths
* `load_graph_view_uncached()` in interactive paths
* `CAXEN_ENABLE_SQLITE_HOTPATH_READS`
* SQLite export builders for debugging
* JSON exports for inspection
* migration tooling

---

## Practical advice

Do **not** try to land the full cutover in one Phase.

The correct strategy is:

* first make search truly native
* then make exact metadata truly native
* then move graph execution
* only then remove the compatibility code


