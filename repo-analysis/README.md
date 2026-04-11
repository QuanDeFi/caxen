# repo-analysis

Analysis toolkit for Carbon and Yellowstone Vixen.

## Intent

- Inventory both upstream repositories.
- Parse and index symbols with parser-first ingestion.
- Build graph-aware retrieval and hierarchical summaries.
- Evaluate retrieval strategies and agent workflows.

## Current Milestone

The implemented slice in this repository now covers the current Phase 0-6 foundation plus the first deeper analysis layer:

- workspace bootstrap and verification
- raw repo inventory adapters
- normalized `manifest.json` and `repo_map.json` outputs
- first Rust-oriented parser ingestion
- deterministic symbol, SQLite, and graph artifacts for scoped Rust source paths
- first semantic graph edges for imports, impls, calls, and uses
- SQLite FTS-based lexical search artifacts over repo/file/symbol documents
- `rustc` AST probe metadata and persisted statement artifacts
- statement-level graph nodes with first `CONTROL_FLOW`, `DATA_FLOW`, `DEPENDENCE`, `READS`, `WRITES`, and `REFS` edges
- a local embedding sidecar over indexed search documents
- deterministic project/directory/file/symbol summaries
- agent-facing CLI operations for repo overview, symbol lookup, call tracing, and context prep
- a lightweight benchmark harness for lexical, lexical-plus-graph, and embedding retrieval

The remaining future work is the more advanced version of these layers: stronger compiler-backed parsing, richer interprocedural semantics, model-backed embeddings, and broader evaluation coverage.

## Quickstart

```bash
./scripts/bootstrap.sh
./scripts/sync_repos.sh
./scripts/sync_repos.sh --verify
./scripts/parse_repos.sh
./scripts/build_index.sh
./scripts/build_search.sh
./scripts/build_embeddings.sh
./scripts/export_summaries.sh
./scripts/run_benchmarks.sh
```

## Structure

- `configs/`: pipeline configuration.
- `docs/`: architecture, schemas, retrieval, summaries, evaluation docs.
- `scripts/`: repeatable operational entry points.
- `src/`: adapters, parsers, symbols, graph, retrieval, agents.
- `tests/`: unit/integration/golden fixtures.

## Outputs

`parse_repos.sh` writes normalized raw inventory files to:

- `data/raw/carbon/manifest.json`
- `data/raw/carbon/repo_map.json`
- `data/raw/yellowstone-vixen/manifest.json`
- `data/raw/yellowstone-vixen/repo_map.json`

`build_index.sh` writes the first parser/symbol/graph artifacts to:

- `data/parsed/<repo>/symbols.json`
- `data/parsed/<repo>/symbols.sqlite3`
- `data/parsed/<repo>/parquet_status.json`
- `data/graph/<repo>/graph.json`

When `pyarrow` is available, `build_index.sh` also writes parquet tables for files, symbols, imports, and references under `data/parsed/<repo>/`.

`build_search.sh` writes lexical search artifacts to:

- `data/search/<repo>/search.sqlite3`
- `data/search/<repo>/search_manifest.json`

`build_embeddings.sh` writes the optional embedding sidecar to:

- `data/search/<repo>/embedding_index.json`
- `data/search/<repo>/embedding_manifest.json`

`export_summaries.sh` writes deterministic summary artifacts to:

- `data/summaries/<repo>/project.json`
- `data/summaries/<repo>/directories.json`
- `data/summaries/<repo>/files.json`
- `data/summaries/<repo>/symbols.json`
- `data/summaries/<repo>/summary_manifest.json`

## Toolkit

The CLI now exposes:

- `repo-overview`
- `find-symbol`
- `trace-calls`
- `compare-repos`
- `embedding-search`
- `find-parsers`
- `find-datasources`
- `find-decoders`
- `find-runtime-handlers`
- `summarize-path`
- `prepare-context`
