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

This gives later comparison, retrieval, and planning stages a stable inventory/search/summary substrate.

## Planned vs Implemented

`/AGENTS.md` describes the intended end-state architecture for this workspace. It includes later-phase capabilities that are not fully built yet.

The current implemented subset is narrower than the full roadmap:

- implemented: workspace bootstrap, repo sync/verification, normalized raw inventory, initial Rust parser ingestion, symbol artifacts, SQLite persistence, optional parquet export path, first semantic graph edges, SQLite FTS lexical search, graph-backed retrieval, deterministic summaries, agent toolkit commands, and a lightweight benchmark harness
- implemented: first `rustc` AST probing, persisted statement artifacts, first statement-level control/data/dependence-style graph edges, and a local embedding sidecar
- not implemented yet: tree-sitter or rust-analyzer-backed ingestion, stronger compiler-backed symbol resolution, richer interprocedural control/data semantics, model-backed embeddings, and deeper benchmark coverage

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
- `trace-calls`
- `compare-repos`
- `find-parsers`
- `find-datasources`
- `find-decoders`
- `find-runtime-handlers`
- `summarize-path`
- `prepare-context`

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

### Symbol Index

`src/symbols/indexer.py` consumes raw inventory roots and writes:

- `data/parsed/<repo>/symbols.json`
- `data/parsed/<repo>/symbols.sqlite3`
- `data/parsed/<repo>/parquet_status.json`

The current artifact is deterministic and scoped to Rust source files discovered from `parser_relevant_source_roots`.
It now includes:

- expanded import records
- struct fields, enum variants, and simple local variables
- resolved import and impl links where the current symbol table can support them
- symbol-level reference records for call and use sites
- persisted statement records with define/read/write/call rollups
- compiler-probe metadata under `parser_backends`

SQLite persistence is always written. Parquet export is implemented as an optional path that activates when `pyarrow` is installed.

### Graph Layer

`src/graph/builder.py` derives a first code graph from the symbol artifact and writes:

- `data/graph/<repo>/graph.json`

The current graph includes repository, file, symbol, and reference nodes with:

- `CONTAINS`
- `DEFINES`
- `IMPORTS`
- `REFERENCES`
- `IMPLEMENTS`
- `CALLS`
- `USES`
- `CONTROL_FLOW`
- `DATA_FLOW`
- `DEPENDENCE`
- `READS`
- `WRITES`
- `REFS`

### Search Layer

`src/search/indexer.py` builds a lexical search database under `data/search/<repo>/`:

- indexes repo, directory, file, and symbol documents
- stores searchable content in SQLite FTS5
- preserves metadata for paths, symbol IDs, crates, modules, and tags
- enables BM25-style lexical pruning without external search infrastructure

### Retrieval Layer

`src/retrieval/engine.py` implements the current coarse-to-fine retrieval slice:

- lexical shortlist from SQLite FTS
- optional embedding recall from the local sidecar
- graph-neighbor expansion from indexed symbol/file seeds
- symbol localization inside hot files
- lightweight score fusion for final context selection

### Embedding Sidecar

`src/embeddings/indexer.py` builds an optional local vector sidecar under `data/search/<repo>/`:

- hashed TF-IDF-style vectors over indexed documents
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
- `trace-calls`
- `compare-repos`
- `find-parsers`
- `find-datasources`
- `find-decoders`
- `find-runtime-handlers`
- `summarize-path`
- `prepare-context`

### Evaluation

`src/evaluation/harness.py` provides the current benchmark slice:

- lexical-only vs lexical-plus-graph vs embedding comparison
- deterministic query cases over the pinned upstream repos
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
- `search.sqlite3`
  - SQLite FTS5 lexical search over repo, directory, file, symbol, and statement documents
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

## Future Phases

The next architectural layers build on top of raw inventory:

1. higher-fidelity Rust parsing beyond the current deterministic-plus-probe slice
2. wider parquet availability across environments without relying on machine-local setup drift
3. stronger compiler-backed resolution and query APIs
4. richer interprocedural graph construction and retrieval
5. model-backed embeddings and better fusion/reranking
6. stronger directory/file/symbol summaries with incremental refresh
7. broader benchmark coverage and comparison tasks

## Explicit Future-Work Note

The current implemented slice now includes deterministic JSON artifacts, SQLite persistence, lexical search, summaries, first semantic graph edges, a compiler probe, statement artifacts, and an embedding sidecar.

The next unresolved layers are still important:

- parquet export depends on `pyarrow` being present in the active Python environment
- cross-file symbol resolution is still heuristic rather than compiler-backed
- the current statement/control/data/dependence graph is intra-function and heuristic
- the current embedding/vector sidecar is local hashed TF-IDF rather than a model-backed embedding stack
- the benchmark harness is intentionally small and should not be treated as a complete evaluation program

Those should be treated as the next expansion layers on top of the current inventory/search/summary/statement foundation rather than as missing bug fixes in the current slice.
