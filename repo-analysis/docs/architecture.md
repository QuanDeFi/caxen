# Architecture

## Purpose

`repo-analysis` is the shared analysis layer for two upstream Solana indexing frameworks:

- Carbon
- Yellowstone Vixen

The upstream repositories remain structurally intact in sibling folders. All local analysis logic lives in `repo-analysis/`.

## Implemented Milestone

The current implemented architecture covers the first durable slice of the system:

1. workspace bootstrap
2. upstream repo synchronization and verification
3. raw inventory extraction into normalized JSON artifacts

This gives later parser, graph, search, and summary stages a stable inventory substrate.

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

## Future Phases

The next architectural layers build on top of raw inventory:

1. parser-first syntax and symbol extraction
2. symbol table persistence
3. graph construction
4. lexical retrieval
5. rerank and optional embedding sidecar
6. hierarchical summaries
7. benchmark and evaluation harness
