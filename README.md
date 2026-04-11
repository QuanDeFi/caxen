# Caxen Workspace

This repository is an umbrella workspace for comparative analysis of two Solana indexing frameworks and shared analysis tooling.

## Top-level model

- `carbon/`: upstream `sevenlabs-hq/carbon` pinned to the commit currently published on `origin/v1.0-rc`.
- `yellowstone-vixen/`: upstream `rpcpool/yellowstone-vixen` pinned to an explicit commit.
- `repo-analysis/`: all local parser/index/search/summarization/evaluation tooling.

Upstream source trees are preserved as close to upstream as possible. New analysis code belongs under `repo-analysis/`.

## Getting started

```bash
git submodule update --init --recursive
./repo-analysis/scripts/bootstrap.sh
./repo-analysis/scripts/sync_repos.sh --verify
./repo-analysis/scripts/parse_repos.sh
./repo-analysis/scripts/build_index.sh
./repo-analysis/scripts/build_search.sh
./repo-analysis/scripts/build_embeddings.sh
./repo-analysis/scripts/export_summaries.sh
```

## Repository policy highlights

- Do not move or flatten upstream repository content.
- Keep retrieval parser-first, symbol-aware, graph-backed, and selective.
- Keep implementation details in `repo-analysis/docs/` and code in `repo-analysis/src/`.
- Treat retrieval as parser-first, starting from raw inventory plus deterministic Rust symbol, statement graph, lexical search, embedding sidecar, summary, and graph artifacts.
