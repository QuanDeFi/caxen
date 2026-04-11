# Evaluation

## Current Benchmark Slice

`src/evaluation/harness.py` provides a lightweight benchmark harness.

It currently compares:

- lexical-only retrieval
- lexical-plus-graph retrieval
- embedding-only retrieval

The harness writes `data/eval/benchmarks.json`.

## Current Cases

The built-in cases target stable queries over the pinned upstream repos, for example:

- Yellowstone Vixen proc-macro symbol lookup
- Carbon filter-symbol lookup

Each run records:

- query
- mode
- latency
- exact-hit status
- path-hit status
- selected results

## Current Limitations

- the benchmark set is small and deterministic
- there is no answer-quality grading yet
- there are no summary-aware or selective-retrieval benchmark modes yet
- the embedding mode uses the local hashed sidecar, not a model-backed embedding service
