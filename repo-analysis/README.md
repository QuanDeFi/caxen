# repo-analysis

Local analysis toolkit for the upstream repos in this workspace.

## Run

From the workspace root:

```bash
./repo-analysis/scripts/bootstrap.sh
./repo-analysis/scripts/sync_repos.sh --verify
./repo-analysis/scripts/parse_repos.sh
./repo-analysis/scripts/build_index.sh
./repo-analysis/scripts/build_search.sh
./repo-analysis/scripts/export_summaries.sh
./repo-analysis/scripts/precompute_eval_cache.sh
./repo-analysis/scripts/run_benchmarks.sh
```

Optional:

```bash
./repo-analysis/scripts/build_embeddings.sh
```

## Main outputs

- `data/raw/<repo>/`: raw inventory inputs
- `data/parsed/<repo>/`: `metadata.lmdb`
- `data/graph/<repo>/`: graph database served by the RyuGraph backend
- `data/search/<repo>/`: `tantivy/` and optional embeddings
- `data/eval/`: `eval.lmdb`, prompt exports, benchmark and scoring output
- `data/summaries/<repo>/`: build progress only, if present

Default runtime is:

- Tantivy for lexical retrieval
- LMDB for metadata, summaries, and eval cache
- RyuGraph for graph storage and traversal

## CLI

Use:

```bash
python3 repo-analysis/src/cli/main.py --help
```

Commands:

- `parse-repos`
- `build-index`
- `build-search`
- `build-summaries`
- `build-embeddings`
- `precompute_eval_cache.sh`
- `run-benchmarks`
- `repo-overview`
- `find-symbol`
- `find-file`
- `search-lexical`
- `embedding-search`
- `trace-calls`
- `where-defined`
- `who-imports`
- `adjacent-symbols`
- `compare-repos`
- `find-parsers`
- `find-datasources`
- `find-decoders`
- `find-runtime-handlers`
- `summarize-path`
- `prepare-context`
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
- `get-summary`
- `get-symbol-signature`
- `get-symbol-body`
- `get-enclosing-context`
- `plan-query`
- `prepare-answer-bundle`
- `retrieve-iterative`
- `export-benchmark-prompts`
- `score-answer-bundles`
- `score-external-answers`

## LLM agent use

For grounded repo questions, use repo-analysis outputs before opening arbitrary files.

Recommended order:

1. Use summary/context tools first:
   `repo-overview`, `summarize-path`, `get-summary`
2. Use lexical/symbol lookup next:
   `find-symbol`, `find-file`, `search-lexical`, `where-defined`
3. Use graph expansion for relationships:
   `who-imports`, `callers-of`, `callees-of`, `reads-of`, `writes-of`, `refs-of`, `implements-of`, `inherits-of`, `path-between`, `expand-subgraph`, `statement-slice`
4. Prepare final evidence for answering:
   `prepare-context`, `plan-query`, `prepare-answer-bundle`, `retrieve-iterative`

Prefer these artifacts:

- `data/parsed/<repo>/metadata.lmdb`
- `data/graph/<repo>/`
- `data/search/<repo>/tantivy/`
- `data/eval/eval.lmdb`

Treat `prepare-answer-bundle` as the default handoff artifact for an external LLM.