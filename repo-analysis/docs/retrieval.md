# Retrieval

## Current Retrieval Stack

The current implementation is deterministic and artifact-first:

1. build raw inventory
2. build Rust symbol and graph artifacts
3. build lexical search artifacts in SQLite FTS
4. optionally build the embedding sidecar over indexed documents
5. optionally apply the selective retrieval gate
6. run retrieval as lexical prune -> embedding side recall -> graph expansion -> symbol localization -> summary bonus -> score fusion

## Lexical Prune

`src/search/indexer.py` builds `data/search/<repo>/search.sqlite3`.

Indexed document kinds:

- repo
- directory
- file
- symbol
- statement

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
- `INHERITS`
- `TESTS`
- `CONTROL_FLOW`
- `DATA_FLOW`
- `DEPENDENCE`
- `READS`
- `WRITES`
- `REFS`

The current implementation is depth-bounded and intentionally simple.

## Symbol Localization

When a file is a hot lexical hit, the retrieval layer scores symbols within that file against the query so final context packs stay symbol-centric.

## Embedding Sidecar

`src/embeddings/indexer.py` builds a provider-based vector sidecar from indexed search documents.

Current properties:

- bounded and optional
- persisted under `data/search/<repo>/`
- used as a secondary recall path, not the primary retrieval layer
- defaults to deterministic local hashing
- can use an OpenAI-backed dense embedding provider when configured

## Selective Retrieval

`src/retrieval/engine.py` now includes a heuristic retrieval gate.

Current behavior:

- if lexical search already returns a narrow exact symbol hit, graph expansion and embedding recall can be skipped
- broader architecture queries still use the full coarse-to-fine path
- the gate decision is included in the retrieval summary for auditability

## Summary-Aware Scoring

When summary artifacts are available, retrieval can add bounded score bonuses from:

- file summaries
- symbol summaries

This keeps summaries as a support layer for ranking rather than a replacement for opening source.

## Current Limitations

- retrieval is still heuristic rather than compiler-backed
- the model-backed embedding path depends on external credentials and is not the default
- the selective gate is heuristic rather than learned
- graph expansion is present for statement-level control/data edges but remains heuristic and intra-function
