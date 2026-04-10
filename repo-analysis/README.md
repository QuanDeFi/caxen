# repo-analysis

Analysis toolkit for Carbon and Yellowstone Vixen.

## Intent

- Inventory both upstream repositories.
- Parse and index symbols with parser-first ingestion.
- Build graph-aware retrieval and hierarchical summaries.
- Evaluate retrieval strategies and agent workflows.

## Current Milestone

The implemented slice in this repository is the Phase 0-2 foundation:

- workspace bootstrap and verification
- raw repo inventory adapters
- normalized `manifest.json` and `repo_map.json` outputs

Parser-first symbol extraction, graph building, lexical search, summaries, and evaluation remain future phases.

## Quickstart

```bash
./scripts/bootstrap.sh
./scripts/sync_repos.sh
./scripts/sync_repos.sh --verify
./scripts/parse_repos.sh
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
