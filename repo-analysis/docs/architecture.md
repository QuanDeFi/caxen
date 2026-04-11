# Architecture

## Purpose

`repo-analysis` is the shared analysis layer for two upstream Solana indexing frameworks:

- Carbon
- Yellowstone Vixen

The upstream repositories remain structurally intact in sibling folders. All local analysis logic lives in `repo-analysis/`.

## Implemented Milestone

The current implemented architecture covers the first durable Phase 0-6 slice of the system plus the first deeper analysis layer:

1. workspace bootstrap
2. upstream repo synchronization and verification
3. raw inventory extraction into normalized JSON artifacts
4. initial Rust parser ingestion into symbol and graph artifacts
5. lexical search indexing
6. deterministic summaries and agent-facing query operations
7. first compiler-probed statement/data/control analysis and an embedding sidecar
8. graph query APIs plus optional parser-backend probes and a model-backed embedding path

This gives later comparison, retrieval, and planning stages a stable inventory/search/summary substrate.

## Planned vs Implemented

`/AGENTS.md` describes the intended end-state architecture for this workspace. It includes later-phase capabilities that are not fully built yet.

The current implemented subset is narrower than the full roadmap:

- implemented: workspace bootstrap, repo sync/verification, normalized raw inventory, initial Rust parser ingestion, symbol artifacts, SQLite persistence, optional parquet export path, first semantic graph edges, graph-backed retrieval, deterministic summaries, agent toolkit commands, and a lightweight benchmark harness
- implemented: `rustc` AST probing, backend-preferred symbol fusion that uses `rust-analyzer` document symbols or `tree-sitter` symbols when available, Cargo-metadata-backed workspace dependency resolution, persisted statement artifacts, interprocedural semantic summaries, a graph query API, answer-quality grading in evaluation, and a provider-based embedding sidecar with an OpenAI-backed path when credentials are configured
- implemented: a native Rust helper for tree-sitter-backed inspection and local BM25 indexing, canonical `graph.sqlite3` storage, `query_manifest.json` build metadata, retrieval planning, iterative retrieval, answer-bundle preparation, prompt export, bundle sufficiency scoring, and offline external-answer grading
- still heuristic: optional backend availability depends on the local environment, symbol resolution is workspace-aware rather than fully compiler-semantic, and interprocedural data/control semantics are still conservative rollups rather than full program analysis

Use this document and the code under `src/` as the source of truth for current behavior. Use `AGENTS.md` as the roadmap for the next layers.

## Components

### Scripts

- `scripts/bootstrap.sh`
  - prepares generated data directories
  - reports local toolchain availability
  - reports whether optional parquet export support is available
- `scripts/sync_repos.sh`
  - initializes submodules
  - verifies that recorded gitlinks match checked-out submodule refs
- `scripts/parse_repos.sh`
  - runs the Python inventory CLI

### CLI

`src/cli/main.py` is the operator entry point for repository inventory tasks.

Current subcommand:

- `parse-repos`
- `build-index`
- `build-search`
- `build-embeddings`
- `build-summaries`
- `run-benchmarks`
- `repo-overview`
- `find-symbol`
- `embedding-search`
- `where-defined`
- `trace-calls`
- `who-imports`
- `adjacent-symbols`
- `compare-repos`
- `find-parsers`
- `find-datasources`
- `find-decoders`
- `find-runtime-handlers`
- `summarize-path`
- `prepare-context`
- `graph-query`
- `path-between`
- `statement-slice`
- `callers-of`
- `callees-of`
- `reads-of`
- `writes-of`
- `plan-query`
- `prepare-answer-bundle`
- `retrieve-iterative`
- `export-benchmark-prompts`
- `score-answer-bundles`
- `score-external-answers`

### Adapters

Repository-specific adapters live under `src/adapters/`:

- `src/adapters/carbon/`
- `src/adapters/yellowstone_vixen/`

Each adapter contributes:

- repo-specific analysis surfaces
- build and test command hints
- parser-relevant source roots
- inventory notes for downstream tooling

### Common Inventory Layer

`src/common/inventory.py` performs the reusable filesystem and manifest scan:

- walks the repository tree
- detects language mix
- inventories files and directories
- identifies package roots and crate boundaries
- expands workspace member globs
- derives module graph seeds
- emits normalized `manifest.json` and `repo_map.json`

### Parsers

`src/parsers/rust.py` implements the first Rust-oriented parser path:

- strips comments and strings before structural scanning
- recognizes modules, imports, impl blocks, functions, methods, and core type declarations
- tracks multi-line struct/enum/union container spans
- carries doc comments, visibility, test markers, and spans into parsed symbols

`src/parsers/rustc_backend.py` adds a compiler-backed probe layer:

- invokes `rustc -Z unpretty=ast-tree` under `RUSTC_BOOTSTRAP=1`
- records per-file parse success and AST-derived item/statement/control counts
- aggregates backend availability and probe counts into the parsed symbol artifact

`src/parsers/tree_sitter_backend.py` and `src/parsers/rust_analyzer_backend.py` add higher-fidelity backend inputs:

- `tree-sitter` symbol extraction when a Rust grammar is installed locally
- `rust-analyzer` document-symbol extraction when a working server binary is available
- primary parser fusion that prefers `rust-analyzer`, then `tree-sitter`, then the deterministic parser
- aggregated backend availability and sample counts under `parser_backends`

`native/` adds the local Rust helper used by the Python orchestration layer:

- tree-sitter-backed Rust inspection for deterministic syntax counts and symbol extraction
- Tantivy BM25 index build/query support over JSONL search documents
- local-only operation with no hosted search or model dependency

### Symbol Index

`src/symbols/indexer.py` consumes raw inventory roots and writes:

- `data/parsed/<repo>/symbols.json`
- `data/parsed/<repo>/symbols.sqlite3`
- `data/parsed/<repo>/parquet_status.json`
- `data/parsed/<repo>/query_manifest.json`

The current artifact is deterministic and scoped to Rust source files discovered from `parser_relevant_source_roots`.
It now includes:

- expanded import records
- struct fields, enum variants, and simple local variables
- Cargo-metadata-backed workspace package discovery and dependency-alias resolution
- trait inheritance records and resolved supertraits
- resolved import and impl links where the current symbol table can support them
- symbol-level reference records for call and use sites, including `self.method()` and `self.field`
- persisted statement records with define/read/write/call rollups
- interprocedural semantic summaries propagated across direct call chains
- per-file `primary_parser_backend` rollups
- compiler-probe metadata under `parser_backends`

SQLite persistence is always written. Parquet export is implemented as an optional path that activates when `pyarrow` is installed.

### Graph Layer

`src/graph/builder.py` derives a first code graph from the symbol artifact and writes:

- `data/graph/<repo>/graph.json`
- `data/graph/<repo>/graph.sqlite3`

The current graph includes repository, file, symbol, and reference nodes with:

- `CONTAINS`
- `DEFINES`
- `IMPORTS`
- `REFERENCES`
- `IMPLEMENTS`
- `INHERITS`
- `CALLS`
- `USES`
- `TESTS`
- `CONTROL_FLOW`
- `DATA_FLOW`
- `DEPENDENCE`
- `READS`
- `WRITES`
- `REFS`

### Search Layer

`src/search/indexer.py` builds a lexical search database under `data/search/<repo>/`:

- indexes repo, directory, file, and symbol documents
- stores searchable content in SQLite metadata tables and a Tantivy BM25 sidecar
- persists `documents.jsonl` as the deterministic bridge into the native BM25 builder
- preserves metadata for paths, symbol IDs, crates, modules, and tags
- enables local BM25 lexical pruning without external search infrastructure

### Retrieval Layer

`src/retrieval/engine.py` implements the current coarse-to-fine retrieval slice:

- lexical shortlist from SQLite FTS
- optional embedding recall from the local sidecar
- graph-neighbor expansion from indexed symbol/file seeds
- symbol localization inside hot files
- summary-aware score bonuses
- a heuristic selective retrieval gate
- lightweight score fusion for final context selection

`src/retrieval/planner.py` adds the consumer-facing retrieval orchestration layer:

- query intent classification and retrieval-plan generation
- answer-bundle preparation for external LLM consumers
- iterative retrieval refinement from prior bundle state plus explicit hints
- deterministic provenance and evidence packaging

### Embedding Sidecar

`src/embeddings/indexer.py` builds an optional local vector sidecar under `data/search/<repo>/`:

- hashed TF-IDF-style vectors over indexed documents by default
- an OpenAI-backed dense embedding path when `OPENAI_API_KEY` is configured
- persisted `embedding_index.json` and `embedding_manifest.json`
- bounded semantic recall used as a side path in retrieval rather than as the primary layer

### Summaries

`src/summaries/builder.py` writes deterministic summaries under `data/summaries/<repo>/`:

- `project.json`
- `directories.json`
- `files.json`
- `symbols.json`
- `summary_manifest.json`

These summaries are generated from raw inventory, symbol artifacts, and graph edges rather than from model calls.

### Agent Toolkit

`src/agents/toolkit.py` exposes repository-facing operations through the CLI:

- `repo-overview`
- `find-symbol`
- `where-defined`
- `trace-calls`
- `who-imports`
- `adjacent-symbols`
- `compare-repos`
- `find-parsers`
- `find-datasources`
- `find-decoders`
- `find-runtime-handlers`
- `summarize-path`
- `prepare-context`
- `graph-query`
- `path-between`
- `statement-slice`
- `callers-of`
- `callees-of`
- `reads-of`
- `writes-of`
- `plan-query`
- `prepare-answer-bundle`
- `retrieve-iterative`

### Evaluation

`src/evaluation/harness.py` provides the current benchmark slice:

- lexical-only, graph, rerank, summary-aware, vector-recall, and selective-retrieval comparisons
- deterministic query cases over the pinned upstream repos
- deterministic answer-quality grading derived from prepared context
- deterministic prompt export for external LLM consumers
- bundle sufficiency scoring
- offline external-answer grading against expected entities, terms, and provenance
- JSON output under `data/eval/benchmarks.json`

## Output Model

Each repo currently emits two raw artifacts under `data/raw/<repo>/`:

- `manifest.json`
  - summary metadata for the repo
  - git source info
  - language mix
  - file inventory rollups
  - dependency manifests
  - build/test commands
  - parser-relevant source roots
- `repo_map.json`
  - directories
  - files
  - probable package roots
  - crate boundaries
  - generated-code markers
  - test directories

The current parser slice also emits:

- `symbols.json`
  - Rust file rollups
  - extracted symbols with spans, docstrings, visibility, and container links
  - normalized import records
  - reference records for calls and uses
  - compiler-probe metadata
  - statement records with define/read/write/call rollups
- `symbols.sqlite3`
  - queryable local persistence for files, symbols, imports, references, and statements
- `parquet_status.json`
  - whether parquet export ran on the current machine
- `graph.json`
  - repository/file/symbol/reference nodes
  - structural and first semantic edges derived from the symbol artifact
- `graph.sqlite3`
  - canonical local graph query store for nodes, edges, and metadata
- `query_manifest.json`
  - build metadata, feature flags, and local artifact locations for parsed/search/query surfaces
- `search.sqlite3`
  - SQLite metadata and fallback lexical search over repo, directory, file, symbol, and statement documents
- `documents.jsonl`
  - deterministic search document export used by the native BM25 builder
- `tantivy/`
  - local BM25 index sidecar
- `search_manifest.json`
  - search document counts and artifact metadata
- `embedding_index.json`
  - local hashed vector sidecar over indexed documents
- `embedding_manifest.json`
  - embedding model, dimensions, and document counts
- `project.json`, `directories.json`, `files.json`, `symbols.json`
  - deterministic summary artifacts for agent-facing navigation
- `benchmarks.json`
  - retrieval benchmark results for the current harness
- `prompt_exports/*.json`
  - deterministic prompt packages and bundled evidence for external LLM consumers

## Future Phases

The next architectural layers build on top of raw inventory:

1. higher-fidelity Rust parsing beyond the current deterministic-plus-probe slice
2. wider parquet availability across environments without relying on machine-local setup drift
3. stronger compiler/LSP-backed resolution and query APIs
4. richer interprocedural graph construction and retrieval precision
5. model-backed embeddings and better fusion/reranking
6. stronger directory/file/symbol summaries with incremental refresh
7. broader benchmark coverage and comparison tasks

## Explicit Future-Work Note

The current implemented slice now includes deterministic JSON artifacts, SQLite persistence, lexical search, summaries, first semantic graph edges, a compiler probe, statement artifacts, and an embedding sidecar.

The next unresolved layers are still important:

- parquet export depends on `pyarrow` being present in the active Python environment
- workspace-aware symbol resolution still stops short of full compiler-semantic name resolution
- the current interprocedural graph is based on propagated summaries rather than whole-program data/control analysis
- the current embedding/vector sidecar defaults to local hashed TF-IDF unless a model-backed provider is configured
- the benchmark harness is intentionally small and should not be treated as a complete evaluation program

Those should be treated as the next expansion layers on top of the current inventory/search/summary/statement foundation rather than as missing bug fixes in the current slice.
