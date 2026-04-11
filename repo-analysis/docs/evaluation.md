# Evaluation

## Current Benchmark Slice

`src/evaluation/harness.py` provides a lightweight benchmark harness.

It currently compares:

- lexical-only retrieval
- lexical-plus-graph retrieval
- graph-plus-rerank retrieval
- summary-aware retrieval
- vector-recall retrieval
- selective retrieval on vs off

The harness writes `data/eval/benchmarks.json`.

## Current Cases

The built-in cases target stable queries over the pinned upstream repos, for example:

- Yellowstone Vixen proc-macro symbol lookup
- Yellowstone Vixen runtime handler/source traits
- Carbon decoder/filter traits

Each run records:

- query
- task type
- mode
- latency
- exact-hit status
- path-hit status
- files opened
- prepared-token estimate
- retrieval summary metadata
- selected results

## Current Limitations

- the benchmark set is small and deterministic
- there is no answer-quality grading yet
- answer quality is still proxied through hit-rate and context-shape metrics
- model-backed embedding benchmarks require an external embedding provider configuration
