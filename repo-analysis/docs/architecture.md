# Architecture

## Purpose

`repo-analysis` is the shared analysis layer for two upstream Solana indexing frameworks:

- Carbon
- Yellowstone Vixen

The upstream repositories remain structurally intact in sibling folders. All local analysis logic lives in `repo-analysis/`.

## Implemented Milestone

The current implemented architecture covers the first durable Phase 0-3 slice of the system:

1. workspace bootstrap
2. upstream repo synchronization and verification
3. raw inventory extraction into normalized JSON artifacts
4. initial Rust parser ingestion into symbol and graph artifacts

This gives later retrieval and summary stages a stable inventory and symbol substrate.

## Components

### Scripts

- `scripts/bootstrap.sh`
  - prepares generated data directories
  - reports local toolchain availability
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
- carries doc comments, visibility, test markers, and spans into parsed symbols

### Symbol Index

`src/symbols/indexer.py` consumes raw inventory roots and writes:

- `data/parsed/<repo>/symbols.json`

The current artifact is deterministic and scoped to Rust source files discovered from `parser_relevant_source_roots`.

### Graph Layer

`src/graph/builder.py` derives a first code graph from the symbol artifact and writes:

- `data/graph/<repo>/graph.json`

The current graph includes repository, file, symbol, and reference nodes with `CONTAINS`, `DEFINES`, `IMPORTS`, `REFERENCES`, and `IMPLEMENTS` edges where available.

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
- `graph.json`
  - repository/file/symbol/reference nodes
  - structural edges derived from the symbol artifact

## Future Phases

The next architectural layers build on top of raw inventory:

1. higher-fidelity Rust parsing beyond the initial deterministic slice
2. symbol table persistence in columnar and database-backed forms
3. broader graph construction and query APIs
4. lexical retrieval
5. rerank and optional embedding sidecar
6. hierarchical summaries
7. benchmark and evaluation harness

## Explicit Future-Work Note

The current Phase 3 implementation intentionally stops at deterministic JSON artifacts:

- parquet and database-backed symbol persistence are not implemented yet
- broader semantic graph edges such as `CALLS`, resolved `USES`, control-flow, data-flow, and dependence edges are not implemented yet

Those should be treated as the next expansion layers on top of the current Rust parser/symbol/graph foundation rather than as missing bug fixes in the current slice.
