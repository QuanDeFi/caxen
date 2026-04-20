# repo-analysis

Local repository-analysis toolkit for the upstream repos in this workspace.

It builds a layered code-understanding index for LLM-oriented repository navigation:

- parsed metadata
- lexical retrieval
- structural graph traversal
- summaries
- optional embeddings
- retrieval planning and answer bundles
- evaluation and benchmark reuse

## Runtime architecture

The default runtime is:

- **Tantivy** for lexical / identifier / path retrieval
- **LMDB** for parsed metadata, summaries, symbol bodies, and eval cache
- **RyuGraph** for graph storage and traversal
- **optional embeddings** as a semantic sidecar

This is a hybrid design. Embeddings are not the source of truth. Repository understanding should be grounded in:

1. lexical / identifier retrieval
2. exact symbol and file lookup
3. graph-backed structural reasoning
4. tool-backed expansion
5. iterative retrieval

## Repository outputs

Main outputs are written under `data/`:

- `data/raw/<repo>/`  
  Raw inventory inputs

- `data/parsed/<repo>/`  
  `metadata.lmdb` and parsed metadata artifacts

- `data/graph/<repo>/`  
  Graph database served by the RyuGraph backend

- `data/search/<repo>/`  
  `tantivy/` plus optional embedding sidecar artifacts

- `data/eval/`  
  `eval.lmdb`, prompt exports, benchmark/scoring outputs

- `data/summaries/<repo>/`  
  Summary build progress only, if present

## Full setup

From the workspace root:

```bash
./repo-analysis/scripts/bootstrap.sh
./repo-analysis/scripts/sync_repos.sh --verify
./repo-analysis/scripts/parse_repos.sh
./repo-analysis/scripts/build_index.sh
./repo-analysis/scripts/build_search.sh
./repo-analysis/scripts/export_summaries.sh
cargo build --manifest-path repo-analysis/native/Cargo.toml
./repo-analysis/scripts/build_embeddings.sh
./repo-analysis/scripts/precompute_eval_cache.sh
```

Optional benchmark run:

```bash
./repo-analysis/scripts/run_benchmarks.sh
```

For a single repo such as `carbon`:

```bash
./repo-analysis/scripts/parse_repos.sh --repo carbon
./repo-analysis/scripts/build_index.sh --repo carbon
./repo-analysis/scripts/build_search.sh --repo carbon
./repo-analysis/scripts/export_summaries.sh --repo carbon
cargo build --manifest-path repo-analysis/native/Cargo.toml
./repo-analysis/scripts/build_embeddings.sh --repo carbon
./repo-analysis/scripts/precompute_eval_cache.sh --repo carbon
```

## CLI

Use:

```bash
python3 repo-analysis/src/cli/main.py --help
```

The CLI is designed to operate against the standard local artifact layout under `repo-analysis/data/...`, while still allowing explicit overrides when needed.

### Build and maintenance commands

- `parse-repos`
- `build-index`
- `build-search`
- `build-summaries`
- `build-embeddings`
- `run-benchmarks`
- `export-benchmark-prompts`
- `score-answer-bundles`
- `score-external-answers`
- `benchmark-interactive`

### Lookup and search commands

- `repo-overview`
- `find-symbol`
- `find-file`
- `search-lexical`
- `embedding-search`
- `where-defined`
- `get-symbol-signature`
- `get-symbol-body`
- `get-summary`
- `get-enclosing-context`
- `summarize-path`

### Graph and relationship commands

- `trace-calls`
- `who-imports`
- `adjacent-symbols`
- `graph-query`
- `path-between`
- `statement-slice`
- `callers-of`
- `callees-of`
- `reads-of`
- `writes-of`
- `refs-of`
- `implements-of`
- `inherits-of`
- `expand-subgraph`

### Retrieval-planning and agent-facing commands

- `prepare-context`
- `plan-query`
- `prepare-answer-bundle`
- `retrieve-iterative`
- `compare-repos`

## Typical usage

### Quick repo inspection

```bash
python3 repo-analysis/src/cli/main.py repo-overview --repo carbon
python3 repo-analysis/src/cli/main.py summarize-path --repo carbon crates/core/src
```

### Exact symbol and lexical lookup

```bash
python3 repo-analysis/src/cli/main.py find-symbol --repo carbon "InstructionDecoder"
python3 repo-analysis/src/cli/main.py where-defined --repo carbon "InstructionDecoder"
python3 repo-analysis/src/cli/main.py get-symbol-body --repo carbon "InstructionDecoder"
python3 repo-analysis/src/cli/main.py search-lexical --repo carbon "deduplication filter"
```

### Structural / graph questions

```bash
python3 repo-analysis/src/cli/main.py callers-of --repo carbon "Pipeline::run"
python3 repo-analysis/src/cli/main.py callees-of --repo carbon "Pipeline::run"
python3 repo-analysis/src/cli/main.py who-imports --repo carbon "InstructionDecoder"
python3 repo-analysis/src/cli/main.py path-between --repo carbon "Pipeline::run" "InstructionDecoder"
python3 repo-analysis/src/cli/main.py statement-slice --repo carbon "Pipeline::run"
```

### Agent-style retrieval

```bash
python3 repo-analysis/src/cli/main.py plan-query --repo carbon "How does Carbon route datasource updates through the pipeline?"
python3 repo-analysis/src/cli/main.py prepare-context --repo carbon "How does Carbon route datasource updates through the pipeline?"
python3 repo-analysis/src/cli/main.py prepare-answer-bundle --repo carbon "How does Carbon route datasource updates through the pipeline?"
python3 repo-analysis/src/cli/main.py retrieve-iterative --repo carbon "How does Carbon route datasource updates through the pipeline?"
```

## Recommended workflow for LLM agents

For grounded repository questions, prefer this order:

1. **summary / overview first**
   - `repo-overview`
   - `summarize-path`
   - `get-summary`

2. **exact lookup next**
   - `find-symbol`
   - `find-file`
   - `where-defined`
   - `get-symbol-signature`
   - `get-symbol-body`

3. **lexical search**
   - `search-lexical`

4. **graph-backed structural expansion**
   - `who-imports`
   - `callers-of`
   - `callees-of`
   - `reads-of`
   - `writes-of`
   - `refs-of`
   - `implements-of`
   - `inherits-of`
   - `path-between`
   - `expand-subgraph`
   - `statement-slice`

5. **final answer preparation**
   - `prepare-context`
   - `plan-query`
   - `prepare-answer-bundle`
   - `retrieve-iterative`

Treat `prepare-answer-bundle` as the default handoff artifact for an external LLM consumer.

## Notes on embeddings

Embeddings are optional.

They are intended for semantic recall only:

- use them to widen candidate recall
- do not use them as the source of truth
- do not prefer them over exact lexical / structural retrieval for hard codebase questions

The strongest repo reasoning comes from parsed structure, graph traversal, exact metadata access, and iterative retrieval.

## Native worker

`repo-analysis/native/` contains the native worker used for:

- tree-sitter Rust inspection
- BM25/Tantivy indexing support
- paged Tantivy document listing for embedding builds

Build it with:

```bash
cargo build --manifest-path repo-analysis/native/Cargo.toml
```

## Tests

Run targeted test suites with:

```bash
python3 -m unittest repo-analysis/tests/unit/test_runtime_boundaries.py
python3 -m unittest repo-analysis/tests/unit/test_search_and_summaries.py
python3 -m unittest repo-analysis/tests/integration/test_build_index.py
python3 -m unittest repo-analysis/tests/integration/test_retrieval_pipeline.py
```

## Operational notes

- This toolkit is designed for local, single-machine use.
- The CLI is explicit enough for debugging and alternate artifact roots, but normal usage should follow the default local workspace layout.
- The main persistent stores are under `data/parsed/`, `data/graph/`, `data/search/`, and `data/eval/`.
