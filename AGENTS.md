# AGENTS.md

## Mission

Build a Codex-friendly workspace for repository analysis around two Solana indexing frameworks:

1. `carbon/` from `sevenlabs-hq/carbon` pinned to `v1.0-rc`
2. `yellowstone-vixen/` from `rpcpool/yellowstone-vixen`
3. `repo-analysis/` as the third top-level folder containing all shared code-analysis, parsing, indexing, summarization, retrieval, and evaluation tooling

This repository is not a fork of either upstream project. Treat `carbon/` and `yellowstone-vixen/` as upstream source trees that remain structurally intact. All new analysis code belongs in `repo-analysis/`.

## Workspace layout

Create and preserve this top-level layout:

```text
/
├── README.md
├── AGENTS.md
├── carbon/
├── yellowstone-vixen/
└── repo-analysis/
    ├── README.md
    ├── pyproject.toml
    ├── package.json
    ├── .env.example
    ├── configs/
    │   ├── indexer.yaml
    │   ├── retriever.yaml
    │   ├── summarizer.yaml
    │   └── benchmarks.yaml
    ├── docs/
    │   ├── architecture.md
    │   ├── schemas.md
    │   ├── retrieval.md
    │   ├── summaries.md
    │   └── evaluation.md
    ├── scripts/
    │   ├── bootstrap.sh
    │   ├── sync_repos.sh
    │   ├── parse_repos.sh
    │   ├── build_index.sh
    │   ├── build_search.sh
    │   ├── build_embeddings.sh
    │   ├── run_benchmarks.sh
    │   └── export_summaries.sh
    ├── data/
    │   ├── raw/
    │   ├── parsed/
    │   ├── graph/
    │   ├── search/
    │   ├── summaries/
    │   └── eval/
    ├── src/
    │   ├── cli/
    │   ├── adapters/
    │   │   ├── carbon/
    │   │   └── yellowstone_vixen/
    │   ├── parsers/
    │   │   ├── tree_sitter/
    │   │   ├── rust_analyzer/
    │   │   └── ts_morph/
    │   ├── symbols/
    │   ├── graph/
    │   ├── search/
    │   ├── embeddings/
    │   ├── summaries/
    │   ├── retrieval/
    │   ├── rerank/
    │   ├── agents/
    │   ├── evaluation/
    │   └── common/
    ├── tests/
    │   ├── fixtures/
    │   ├── unit/
    │   ├── integration/
    │   └── golden/
    └── notebooks/
```

## Non-negotiable repository rules

- Keep upstream repo contents inside `carbon/` and `yellowstone-vixen/` as close to upstream as possible.
- Do not move files out of those repos to fit local preferences.
- Do not start by embedding full files into a flat vector index.
- Do not make embeddings the only retrieval method.
- Do not make file-level retrieval the only retrieval method.
- Do not make retrieval always-on for every agent step.
- Prefer parser-first, symbol-aware, graph-backed, hierarchical, coarse-to-fine retrieval.
- Keep agent instructions concise at the root. Put implementation detail into `repo-analysis/docs/` and code into `repo-analysis/src/`.

## Why this structure

Codex reads `AGENTS.md` before starting work and applies the closest file along the working-directory path, so this root file should define the durable workspace rules and leave package-specific behavior to deeper documentation if needed. The Codex docs also recommend keeping the main `AGENTS.md` practical and concise, and referencing additional task-specific docs when instructions grow. Carbon itself is organized around `crates`, `datasources`, `decoders`, `examples`, `metrics`, `packages`, and `scripts`, while Yellowstone Vixen describes a runtime-plus-parser architecture for program-aware Solana data pipelines. The plan below preserves both upstream trees and places all analysis tooling in a third folder. citeturn2view2turn2view3turn2view0turn2view1

## Plan vs Implementation

This file is the target architecture for the workspace, not a claim that every phase below is already implemented.

Current implementation status:

- Phase 0 and Phase 1 workspace setup are in place.
- Phase 2 raw inventory is implemented and produces normalized `manifest.json` and `repo_map.json`.
- Phase 3 now includes an initial Rust parser/symbol/graph slice plus a `rustc` AST probe, statement-level nodes, and first control-flow/data-flow/dependence-style edges.
- Phase 4-6 now include lexical search, an embedding sidecar, deterministic summaries, and agent-facing query commands.
- The remaining roadmap is now the more advanced version of those layers: deeper compiler-backed parsing, stronger statement/control/data semantics, and better model-backed embeddings.

When there is any ambiguity, treat `repo-analysis/docs/architecture.md` and the code under `repo-analysis/src/` as the source of truth for what actually works today.

## Phase 0: bootstrap the workspace

Goal: create a stable umbrella workspace that Codex Web can operate on repeatedly.

Tasks:

1. Create the top-level folders exactly as shown above.
2. Initialize a root `README.md` that explains the three-folder model.
3. Add a minimal `.gitignore` at the root for generated index artifacts, caches, logs, `.venv`, `node_modules`, and large data outputs under `repo-analysis/data/`.
4. Add `repo-analysis/README.md` with quickstart commands and architectural intent.
5. Decide whether the umbrella workspace uses:
   - Git submodules for `carbon/` and `yellowstone-vixen/`, or
   - ordinary clones managed by `repo-analysis/scripts/sync_repos.sh`.

Preferred default: use Git submodules if this is meant to be a long-lived workspace. Use plain clones only if rapid local experimentation matters more than upstream update hygiene.

## Phase 1: pull the upstream repositories

### Carbon

- Clone `https://github.com/sevenlabs-hq/carbon.git` into `carbon/`.
- Immediately pin to `v1.0-rc`.
- Do not flatten or partially copy the repo.
- Preserve the existing Carbon layout, especially:
  - `crates/`
  - `datasources/`
  - `decoders/`
  - `examples/`
  - `metrics/`
  - `packages/`
  - `scripts/`

### Yellowstone Vixen

- Clone `https://github.com/rpcpool/yellowstone-vixen.git` into `yellowstone-vixen/`.
- Pin to a specific commit hash after cloning, even if starting from `main`.
- Preserve the existing Vixen layout and its parser/runtime structure.

### Acceptance criteria

- `carbon/` is checked out at `v1.0-rc`.
- `yellowstone-vixen/` is pinned to an explicit commit.
- Both repos build independently before any analysis tooling is added.
- No analysis code has been added inside the upstream folders except optional repo-local `AGENTS.md` files if later needed.

## Phase 2: inventory and normalize both repos

Goal: create a unified machine-readable description of each repo before building retrieval.

Implement in `repo-analysis/src/adapters/`.

Tasks:

1. Build one adapter for Carbon and one for Yellowstone Vixen.
2. For each repo, collect:
   - language mix
   - file inventory
   - module graph seeds
   - dependency manifests
   - test commands
   - build commands
   - parser-relevant source roots
3. Emit normalized metadata into `repo-analysis/data/raw/<repo>/manifest.json`.
4. Emit a repo map into `repo-analysis/data/raw/<repo>/repo_map.json` with:
   - directories
   - files
   - probable package roots
   - crate boundaries
   - generated-code markers
   - test directories

### Repo-specific expectations

For Carbon, treat the repo as a Rust-first monorepo with meaningful boundaries across `crates`, `datasources`, `decoders`, `examples`, `metrics`, and `packages`. For Yellowstone Vixen, treat runtime, parsers, handlers, and sources as first-class analysis surfaces. citeturn2view0turn2view1

## Phase 3: build the parser-first indexing pipeline

Goal: index symbols and structure before any semantic retrieval.

Implement in:

- `repo-analysis/src/parsers/`
- `repo-analysis/src/symbols/`
- `repo-analysis/src/graph/`

### 3A. Parsing layer

Use parser-first ingestion:

- Tree-sitter for broad syntax coverage and fast cross-language parsing.
- `rust-analyzer` or Rust compiler-derived tooling for higher-fidelity Rust symbol extraction.
- `ts-morph` or TypeScript compiler APIs for any TypeScript packages or scripts.

Extract at least:

- repo
- package/crate
- module/file
- class/struct/enum/trait
- function/method
- impl block
- local variable
- field reference
- statement-level node
- fine-grained ref/use node
- import/use edge
- reference/definition edge
- test symbol
- doc comment / comment blocks

### 3B. Symbol index

Create a symbol table with one stable record per symbol or first-class analysis entity:

- `symbol_id`
- `repo`
- `path`
- `language`
- `kind`
- `name`
- `qualified_name`
- `span`
- `signature`
- `docstring`
- `visibility`
- `container_symbol_id`
- `statement_id` when applicable
- `scope_symbol_id` for locals and fine-grained ref/use entities
- `reference_target_symbol_id` for field references and resolved uses when available

Treat the following as first-class indexable entities when the parser can recover them with acceptable fidelity:

- local variables
- field references
- statement-level nodes
- fine-grained ref/use nodes

Persist to `repo-analysis/data/parsed/<repo>/symbols.parquet` and a queryable local database.

### 3C. Graph index

Build a code graph that stores at least these node and edge types:

First-class node types:

- repository, package/crate, module/file, type, function/method, impl block
- local variable
- field reference
- statement-level node
- fine-grained ref/use node

Edge types:

- `CONTAINS`
- `CALLS`
- `USES`
- `IMPORTS`
- `IMPLEMENTS`
- `INHERITS`
- `DEFINES`
- `REFERENCES`
- `TESTS`
- `CONTROL_FLOW`
- `DATA_FLOW`
- `DEPENDENCE`
- `REFS`
- `READS`
- `WRITES`

Persist to `repo-analysis/data/graph/<repo>/` and expose a simple graph query API.

When language tooling allows, construct statement-level graph fragments with control-flow, data-flow, and dependence edges so agents can reason below the symbol/file layer.

### Acceptance criteria

- A full parse run succeeds for both repos.
- Symbol extraction covers all Rust modules that parse successfully.
- The graph can answer: “where is this symbol defined?”, “what calls this function?”, “what imports this module?”, and “what symbols are adjacent to this one?”

## Phase 4: add lexical and structural search

Goal: make retrieval fast before adding expensive reranking.

Implement in:

- `repo-analysis/src/search/`
- `repo-analysis/src/retrieval/`
- `repo-analysis/src/rerank/`

### Retrieval stages

1. **Lexical prune**
   - BM25 or Tantivy-based indexing over filenames, symbol names, comments, docstrings, and code bodies.
2. **Structural expansion**
   - Expand candidate sets through graph neighbors and container relationships.
3. **Symbol localization**
   - Narrow from file/module to exact symbol-level spans.
4. **Optional vector recall sidecar**
   - Maintain an embedding-backed candidate recall path over symbols, summaries, and selected code spans.
   - Use it only as a secondary recall or tie-break path, not as the primary retrieval layer.
5. **Neural, embedding-based, or LLM rerank**
   - Re-rank only the pruned shortlist.
6. **Selective retrieval gate**
   - Do not retrieve by default if the task can be solved from local conversation state or already-open context.

### Optional embedding/vector sidecar

Implement in `repo-analysis/src/embeddings/`.

Requirements:

- build a vector index over selected retrieval units such as project summaries, directory summaries, file summaries, symbol summaries, and selected code spans
- generate embeddings incrementally and record model/version metadata
- support embedding-based recall as a bounded side path after lexical prune or after graph expansion
- support embedding-based rerank or fusion with lexical and graph scores
- keep lexical + graph retrieval fully functional when embeddings are disabled

### Rules

- Embeddings are optional and secondary.
- Lexical retrieval must remain available even if embeddings are disabled.
- Graph expansion should be bounded by depth and fan-out.
- Embedding recall must be bounded and auditable.
- Final context packs must be small, explicit, and symbol-centric.

## Phase 5: generate hierarchical summaries

Goal: let agents form a fast mental model of the repo before opening raw code.

Implement in `repo-analysis/src/summaries/`.

Produce summaries at four levels:

1. project summary
2. directory/package summary
3. file summary
4. symbol summary

Each summary should include:

- purpose
- main dependencies
- key entry points
- important exported symbols
- notable tests
- possible relevance tags (datasource, decoder, parser, runtime, metrics, CLI, examples)

Persist to `repo-analysis/data/summaries/<repo>/`.

### Rules

- Summaries should be regenerated incrementally.
- Summaries must reference symbol IDs and file paths.
- Summaries are aids for retrieval and planning, not a replacement for opening source.

## Phase 6: create the agent-facing analysis toolkit

Goal: make Codex Web fast at answering repo-analysis tasks.

Implement in `repo-analysis/src/agents/` and expose a CLI.

Required agent operations:

- `repo-overview <repo>`
- `find-symbol <repo> <query>`
- `trace-calls <repo> <symbol>`
- `compare-repos <symbol-or-feature>`
- `find-parsers`
- `find-datasources`
- `find-decoders`
- `find-runtime-handlers`
- `summarize-path <repo> <path>`
- `prepare-context <task>`

### Important comparison workflows

The toolkit should be able to answer questions like:

- How does Carbon model datasources, pipes, decoders, and processors?
- How does Yellowstone Vixen model runtime, parsers, handlers, and sources?
- What are the analogous extension points between the two repos?
- Where would a ClickHouse sink, parser, or repo-analysis adapter fit in each codebase?

## Phase 7: evaluation and benchmarks

Goal: validate that the indexing stack actually helps LLM analysis.

Implement in `repo-analysis/src/evaluation/`.

Create benchmark sets for:

- symbol lookup
- cross-file call tracing
- architecture questions
- “find the right extension point” tasks
- compare-and-contrast tasks across Carbon and Yellowstone Vixen

Track at least:

- retrieval latency
- number of files opened
- number of tokens prepared for the model
- exact-hit rate on target symbols
- path-level recall
- answer quality on comparison tasks

### Evaluation modes

- lexical only
- lexical + graph
- lexical + graph + rerank
- lexical + graph + rerank + summaries
- lexical + graph + vector recall + rerank
- lexical + graph + vector recall + rerank + summaries
- selective retrieval on vs off

## Phase 8: Codex Web workflow guidance

When working in this repo, Codex should:

1. Start at the root `AGENTS.md`.
2. Inspect `repo-analysis/docs/architecture.md` before making large structural changes.
3. Treat upstream repos as read-only unless the task explicitly asks to patch them.
4. Prefer using the analysis toolkit to answer repo questions before scanning raw files manually.
5. For large tasks, create a plan document under `repo-analysis/docs/` before editing code.
6. Verify retrieval behavior with a benchmark slice before adding new retrieval stages.

## Suggested implementation order

1. Bootstrap workspace and sync scripts.
2. Clone and pin both upstream repos.
3. Build raw repo inventory adapters.
4. Implement parser ingestion and symbol extraction.
5. Implement graph index.
6. Implement lexical search.
7. Add hierarchical summaries.
8. Add retrieval orchestration and reranking.
9. Add agent CLI commands.
10. Add benchmarks and regression tests.

## Definition of done

This workspace is ready when all of the following are true:

- Both upstream repos are present and pinned.
- The third folder contains all analysis tooling.
- A full parse/index pass works for both repos.
- Agents can retrieve symbol-level context faster than naive file scanning.
- The system can answer architecture and extension-point questions across both repos.
- The evaluation suite can compare retrieval strategies and catch regressions.

## References for design choices

This plan follows OpenAI Codex guidance that `AGENTS.md` should define durable repo instructions and stay practical, with details moved into supporting docs as needed. It also follows the public repository structures and framework descriptions in Carbon and Yellowstone Vixen, and the repository-level code-analysis literature favoring parser-first, symbol-aware, graph-backed, hierarchical, and selective retrieval over flat chunk-only indexing. citeturn2view2turn2view3turn2view0turn2view1turn0search0turn0search1
