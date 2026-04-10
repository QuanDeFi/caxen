# Retrieval

## Current Retrieval Stack

The current implementation is deterministic and artifact-first:

1. build raw inventory
2. build Rust symbol and graph artifacts
3. build lexical search artifacts in SQLite FTS
4. run retrieval as lexical prune -> graph expansion -> symbol localization -> score fusion

## Lexical Prune

`src/search/indexer.py` builds `data/search/<repo>/search.sqlite3`.

Indexed document kinds:

- repo
- directory
- file
- symbol

Each document carries searchable text plus metadata such as path, symbol ID, crate, module path, and heuristic tags.

## Structural Expansion

`src/retrieval/engine.py` uses `graph.json` to expand around lexical seed hits.

Current edge-aware expansion uses:

- `CALLS`
- `USES`
- `IMPLEMENTS`
- `IMPORTS`
- `DEFINES`
- `CONTAINS`
- `REFERENCES`

The current implementation is depth-bounded and intentionally simple.

## Symbol Localization

When a file is a hot lexical hit, the retrieval layer scores symbols within that file against the query so final context packs stay symbol-centric.

## Current Limitations

- retrieval is still heuristic rather than compiler-backed
- there is no vector/embedding sidecar yet
- there is no retrieval gate model; selectivity is currently driven by which CLI command is used
- graph expansion does not include control-flow or data-flow edges
