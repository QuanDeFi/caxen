# Caxen Workspace

This repository is an umbrella workspace for comparative analysis of two Solana indexing frameworks and shared analysis tooling.

## Top-level model

- `carbon/`: upstream `sevenlabs-hq/carbon` pinned to an explicit submodule commit.
- `yellowstone-vixen/`: upstream `rpcpool/yellowstone-vixen` pinned to an explicit commit.
- `repo-analysis/`: all local parser/index/search/summarization/evaluation tooling.

Upstream source trees are preserved as close to upstream as possible. New analysis code belongs under `repo-analysis/`.


## What Repo Analysis Contains

`repo-analysis` provides:

- raw inventory generation for the upstream repos
- Rust symbol, reference, statement, and summary extraction into `metadata.lmdb`
- graph artifacts served by a RyuGraph backend
- Tantivy-backed lexical search artifacts
- optional embedding sidecar artifacts
- graph query, retrieval-planning, answer-bundle, and evaluation CLI commands
- native worker support for tree-sitter inspection and BM25 indexing
- body/doc chunk indexing for symbol-level retrieval
- summary sync into LMDB metadata and graph summary nodes/edges
- explicit lookup/navigation tools for files, lexical search, signatures, bodies, enclosing context, implementations, inheritance, and bounded subgraph expansion

The main implementation lives under:

- `repo-analysis/src/`
- `repo-analysis/native/`
- `repo-analysis/scripts/`
- `repo-analysis/tests/`

Generated local artifacts live under:

- `repo-analysis/data/raw/`
- `repo-analysis/data/parsed/`
- `repo-analysis/data/graph/`
- `repo-analysis/data/search/`
- `repo-analysis/data/summaries/` (build progress only, if present)
- `repo-analysis/data/eval/`
