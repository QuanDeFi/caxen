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
./repo-analysis/scripts/run_benchmarks.sh
```

Optional:

```bash
./repo-analysis/scripts/build_embeddings.sh
```

## Main outputs

- `data/raw/<repo>/`: raw inventory
- `data/parsed/<repo>/`: `symbols.sqlite3`, parquet status, query manifest
- `data/graph/<repo>/`: `graph.sqlite3`
- `data/search/<repo>/`: `search.sqlite3`, BM25/Tantivy, and optional embeddings
- `data/summaries/<repo>/`: `summary.sqlite3`
- `data/eval/`: benchmark and scoring output

Default runtime is DB-first. JSON exports are optional with `--emit-json` on `build-index`, `build-search`, and `build-summaries`.

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

For grounded repo questions, use `repo-analysis` outputs before opening arbitrary files.

Recommended order:

1. Read `data/parsed/<repo>/query_manifest.json` to see which artifacts exist.
2. Use summaries first:
   `repo-overview`, `summarize-path`, `get-summary`
3. Use lexical/symbol lookup next:
   `find-symbol`, `find-file`, `search-lexical`, `where-defined`
4. Use graph expansion for relationships:
   `who-imports`, `callers-of`, `callees-of`, `reads-of`, `writes-of`, `refs-of`, `implements-of`, `inherits-of`, `path-between`, `expand-subgraph`, `statement-slice`
5. Prepare final evidence for answering:
   `prepare-context`, `plan-query`, `prepare-answer-bundle`, `retrieve-iterative`

Prefer these artifacts:

- `data/summaries/<repo>/summary.sqlite3`
- `data/parsed/<repo>/symbols.sqlite3`
- `data/graph/<repo>/graph.sqlite3`
- `data/search/<repo>/search.sqlite3`
- `data/search/<repo>/tantivy/`

Treat `prepare-answer-bundle` as the default handoff artifact for an external LLM. It is the compact, provenance-carrying context package.
