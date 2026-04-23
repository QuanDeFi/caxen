# Research 5: Solving Retrieval Noise in Repository-Scale Code Understanding

## Problem

Retrieval noise appears when a natural-language query matches many superficially related code artifacts that are not actually central to the task.

Typical examples include:

- setters and builder methods
- helpers and wrappers
- constants and fields
- locals and statement fragments
- tests, examples, and scaffolding
- generated or boilerplate code

These artifacts often share words with the query, so flat lexical retrieval surfaces them early. Once retrieval expands from those weak matches, graph neighbors and body text add even more irrelevant context. The result is a context set biased toward token overlap rather than architectural or semantic relevance.

This is the core failure mode:

- retrieval units are too flat or too fine-grained
- seed localization is weak
- broad search and expansion happen too early
- ranking overweights lexical overlap
- systems compensate with ad hoc heuristics instead of fixing representation and control flow

## What The Research Suggests

The research surveyed across the earlier documents converges on a clear pattern: retrieval quality is improved primarily by changing the retrieval substrate and the retrieval process, not by endlessly tuning keyword boosts.

### 1. Change the retrieval object, not just the score function

Several systems improve retrieval by representing code as structured objects rather than flat chunks.

- Graph-based systems retrieve over symbols, files, and dependency relations rather than raw text windows.
- Static-analysis-based systems incorporate syntax, control flow, data flow, and dependency structure.
- Structure-grounded methods treat semantic relationships such as calls, imports, inheritance, and containment as first-class retrieval evidence.

The important implication is that the retriever should operate over meaningful program entities and their relations, not over arbitrary text fragments alone.

### 2. Structural signals matter more than lexical overlap

Code semantics are carried by program structure. Semantically important elements are often not the ones with the highest lexical salience.

Useful relevance signals include:

- exact identifier matches
- symbol kind
- containment
- call and dependency relations
- inheritance and implementation relations
- visibility
- semantic activity
- path and scope locality

Low-value signals include raw token overlap by itself, especially when it pulls in incidental members, fragments, or boilerplate.

### 3. Coarse-to-fine retrieval is better than flat retrieval

The strongest recurring pattern is staged retrieval.

Instead of immediately retrieving low-level code fragments, systems first localize a coarse area of the repository, then refine within that area using structural tools.

A common sequence is:

1. retrieve coarse units such as files, modules, or major symbols
2. identify candidate regions by semantic intent or broad lexical cues
3. run precise structural retrieval inside that narrowed scope
4. only then hydrate detailed code bodies or local fragments

This is the main mechanism for reducing early noise.

### 4. Precise structural retrieval inside a narrowed scope matters

One important detail beyond generic staging is that the fine-grained phase should not just be “more search.” It should use structure-aware queries.

Examples include:

- AST-based symbol lookup
- inheritance-chain lookup
- call-graph traversal
- data-flow or dependency queries
- exact definition and reference extraction

The broad phase identifies where to look. The structural phase determines what is actually relevant there.

### 5. Graph propagation is more powerful than local neighborhood lookup alone

Some of the strongest results come from graph-based propagation rather than single-hop expansion.

Once a strong seed is found, relevance can diffuse through call, dependency, and containment graphs so that indirect but necessary support code accumulates score.

This is different from merely listing neighbors:

- local neighbor expansion finds directly adjacent code
- graph propagation can recover lexically opaque but semantically necessary dependencies

That matters for long-horizon understanding tasks, where the required context often spans helper code and setup code that do not share query vocabulary.

### 6. Retrieval should be gated

Not every query should trigger broad repository retrieval.

If a query is already localized, broad retrieval may only add noise and cost. Several lines of work suggest that retrieval should be explicitly controlled:

- decide whether retrieval is needed
- decide which stage depth is needed
- stop expansion when sufficient evidence is already present

This gating can be heuristic or learned, but the principle is the same: unnecessary retrieval is itself a source of noise.

### 7. Structure-aware encoders are better than text-only encoders

The research also suggests that embeddings and rankers should encode more than tokens.

Promising approaches include:

- dual encoders that combine syntax and dependency structure
- graph neural encoders over AST or dependency graphs
- hybrid retrieval that combines lexical filtering with semantic reranking over structure-aware embeddings

This matters because pure text embeddings still tend to overreward surface similarity when architectural relevance depends on program relations.

## Design Principles

Based on the research, a robust repository retriever should follow these principles.

### A. Use structural representations

Index program entities such as:

- repositories
- packages
- directories
- files
- symbols
- bodies
- graph relations

Where possible, enrich them with:

- AST structure
- control-flow or data-flow information
- dependency or call graphs
- containment hierarchy

### B. Use staged retrieval

Default retrieval should move from coarse to fine:

1. summary or coarse repository units
2. candidate symbols or files
3. graph or structural expansion
4. code bodies and local detail

Fine-grained code should be loaded only after the likely target region is localized.

### C. Use structural disambiguation after coarse retrieval

Once a candidate region is found, refine using structural operators rather than repeating flat search.

Examples:

- resolve the defining symbol
- find relevant callees or callers
- inspect inheritance or implementation links
- extract exact definitions, signatures, or statements

The point is to trade breadth for precision once localization succeeds.

### D. Prefer structural ranking signals

Ranking should emphasize:

- exact identifier quality
- symbol kind priority
- visibility
- containment depth
- graph distance
- semantic centrality or activity
- summary-level relevance

Ranking should strongly suppress:

- statement fragments unless explicitly requested
- locals, fields, and parameters for conceptual queries
- unresolved refs
- incidental matches from tests/examples/scaffolding when not relevant

### E. Add retrieval gating

A good system should answer three questions before broad expansion:

- does this query need external repository context at all?
- how deep should retrieval go?
- when should expansion stop?

The goal is not maximal retrieval. The goal is sufficient, relevant retrieval.

### F. Evaluate both relevance and efficiency

Evaluation should measure more than whether a relevant symbol appeared somewhere in the candidate set.

Important dimensions include:

- retrieval precision and recall
- rank quality of correct files or symbols
- downstream task success
- context efficiency
- noise budget

The practical objective is high relevance with minimal irrelevant context.

## Practical Rule Of Thumb

If retrieval quality is being improved mainly by adding more query-specific or domain-specific scoring rules, that usually indicates a deeper design problem.

The likely causes are:

- poor retrieval units
- weak seed localization
- insufficient staging
- insufficient structural querying
- insufficient gating

The research-backed correction is:

`better structure + better staging + better gating + better propagation`, not `more keyword heuristics`.

## Conclusions

The research points toward a retrieval architecture with four core properties:

- structure-aware representation
- coarse-to-fine retrieval
- explicit control over when and how retrieval expands
- ranking based on semantic and architectural centrality rather than surface overlap alone

In short, retrieval noise is not mainly a ranking-tuning problem. It is a representation and retrieval-control problem.

## Sources

- RepoCoder: https://aclanthology.org/2023.emnlp-main.151/
- Repoformer: https://proceedings.mlr.press/v235/wu24a.html
- Amazon selective retrieval overview: https://www.amazon.science/blog/enhancing-repository-level-code-completion-with-selective-retrieval
- GraphCoder: https://arxiv.org/html/2406.07003v1
- CodexGraph: https://arxiv.org/html/2408.03910v2
- Hierarchical Repository-Level Code Summarization: https://arxiv.org/abs/2501.07857
- Making Retrieval-Augmented Language Models Robust to Irrelevant Context: https://arxiv.org/abs/2310.01558
- HCAG: https://arxiv.org/html/2603.20299v1
- InfCode-C++: https://arxiv.org/html/2604.10516v1
- ReflectCode: https://arxiv.org/html/2604.10235v1
- Graph-of-Skills: https://arxiv.org/html/2510.24749v1
- CodeComp: https://arxiv.org/html/2604.05333
- Structure-grounded code retrieval work: https://arxiv.org/html/2511.16005v1
- Repository retrieval survey / reflective code retrieval reference: https://www.preprints.org/manuscript/202510.0924
