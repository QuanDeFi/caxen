```
caxen/
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
