# Caxen Workspace

This repository is an umbrella workspace for comparative analysis of two Solana indexing frameworks and a local repository-analysis toolkit.

## Workspace layout

- `carbon/`  
  Upstream `sevenlabs-hq/carbon`, pinned as a submodule commit.

- `yellowstone-vixen/`  
  Upstream `rpcpool/yellowstone-vixen`, pinned as a submodule commit.

- `repo-analysis/`  
  Local parsing, indexing, graph, search, summarization, retrieval, and evaluation tooling.

Upstream source trees should stay as close to upstream as possible. Local analysis code belongs under `repo-analysis/`.

## What `repo-analysis` provides

`repo-analysis` builds and serves a layered repository memory for LLM-oriented code understanding:

- raw inventory generation for upstream repos
- Rust symbol, import, reference, statement, and summary extraction
- LMDB-backed parsed metadata (`metadata.lmdb`)
- RyuGraph-backed structural graph storage and traversal
- Tantivy-backed lexical retrieval
- optional embedding sidecar artifacts
- graph query, retrieval planning, answer-bundle, and evaluation commands
- native worker support for tree-sitter inspection and BM25 indexing
- exact symbol/file/body/signature/context access
- iterative retrieval and graph-backed context expansion

## Main implementation areas

- `repo-analysis/src/`
- `repo-analysis/native/`
- `repo-analysis/scripts/`
- `repo-analysis/tests/`

## Generated local artifacts

Artifacts are written under `repo-analysis/data/`:

- `repo-analysis/data/raw/`
- `repo-analysis/data/parsed/`
- `repo-analysis/data/graph/`
- `repo-analysis/data/search/`
- `repo-analysis/data/summaries/`  
  Primarily summary build progress, if present
- `repo-analysis/data/eval/`
