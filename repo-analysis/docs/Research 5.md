# Research 5: Solving Retrieval Noise with Staging, Gating, and Structure

## Problem

The current failure mode is not that the index lacks information. It is that retrieval is too eager and too flat:

- broad lexical search retrieves too many low-value fragments
- graph expansion starts from weak seeds
- bodies and statements appear before the system has localized the right symbol or file
- ranking logic accumulates repo-shaped topic boosts instead of relying on structural evidence

This produces familiar noise:

- local variables and statement shards outrank canonical symbols
- broad conceptual queries overfit to one repository's naming conventions
- retrieval quality depends on hand-tuned boosts for words like `datasource`, `decoder`, or `runtime`

## What the Research Actually Suggests

The papers and systems summarized in `Research.md`, `Research 2.md`, `Research 3.md`, and `Research 4.md` converge on a different pattern.

### 1. Change the retrieval object, not just the score function

GraphCoder and CodexGraph do not primarily fix noise with query-specific rerank hacks. They improve the *representation*:

- graph nodes represent symbols, files, and semantic units
- edges represent containment, calls, imports, implementations, and dependencies
- retrieval happens over structured code objects instead of flat chunks

Implication for `repo-analysis`:

- retrieval should be schema-driven
- stage boundaries should follow repository structure
- graph expansion should start from localized symbol seeds, not from arbitrary lexical hits

### 2. Retrieve iteratively and selectively

RepoCoder and Repoformer both push toward *control* over retrieval:

- RepoCoder uses iterative retrieval after seeing partial context
- Repoformer shows that retrieval should be gated because unnecessary retrieval can actively hurt the answer

Implication for `repo-analysis`:

- not every query should trigger broad lexical search + graph + embeddings
- exact symbol or path lookups should stay narrow
- broad exploratory questions can justify graph expansion and body hydration

### 3. Route through summaries before raw code

Hierarchical repository summarization and HCAG-style systems push retrieval through abstractions first:

- summary or directory/file rollups provide routing context
- symbol-level retrieval localizes the target surface
- graph expansion adds neighboring evidence
- raw body text is loaded only after the relevant region is known

Implication for `repo-analysis`:

The default retrieval path should be:

1. `summary`
2. `symbol`
3. `graph neighborhood`
4. `body`

This is the main antidote to statement noise.

### 4. Keep ranking signals generic

The research does not justify hardcoded boosts for repository-specific terms. The useful signals are mostly structural:

- exact name / exact qualified name
- symbol kind
- containment
- graph distance
- visibility
- semantic activity
- summary relevance

These signals transfer across repositories because they arise from parser output, graph structure, and summaries rather than repo-specific vocabulary.

### 5. Do not default to a repo-specific config layer

The papers do not rely on a large per-repo tuning surface. The default should be:

- better structural indices
- staged retrieval
- selective gating
- generic ranking signals

If a product requirement later demands separate architecture notes or benchmark fixtures, that information should stay outside the core retriever. It should not be required for ordinary retrieval quality, and it should not become a hidden substitute for weak localization or weak graph structure.

## Design Decision for `repo-analysis`

Based on the research, retrieval noise should be addressed by the following simplifications:

### A. Schema-driven retrieval pipeline

The engine should operate over explicit stages:

- summary docs: `repo`, `package`, `directory`, `file`, `doc`
- symbol docs: `symbol`
- graph neighbors: schema-defined edge families
- body docs: `function_body`, `type_body`

The stage order matters because it turns broad text retrieval into structural localization.

### B. Retrieval gate

Use a gate before broad retrieval:

- exact symbol hit: prefer symbol-only lookup, maybe graph if explicitly requested
- exact path/docs query: prefer summary/file/doc retrieval
- exploratory query: allow summary + symbol + graph + body
- embeddings should remain optional and gated, not default-on for every query

### C. Generic ranker

The ranker should only use generic structural signals:

- exact match quality
- identifier coverage
- document/symbol kind priority
- graph distance
- containment within the selected summary scope
- visibility
- semantic activity
- summary overlap

It should generically penalize:

- statement docs unless the query explicitly targets statements
- locals, parameters, fields, and unresolved refs for conceptual retrieval
- bodies when a canonical symbol is available

### D. Keep the core retriever self-sufficient

The default system should derive its routing and ranking signals from indexed artifacts that already exist:

- summaries
- symbol metadata
- graph neighborhoods
- lexical evidence

Separate repository config should be treated as optional product scaffolding, not as part of the core retrieval design.

## Practical Rule of Thumb

If retrieval quality is being improved by adding more term-specific boosts, that is usually a sign that:

- the stage order is wrong
- the gate is too permissive
- the seed localization is weak
- or the representation is too flat

The research-backed correction is:

`better staging + better gating + better structure`, not `more topic heuristics`.

## Sources

- RepoCoder: https://aclanthology.org/2023.emnlp-main.151/
- Repoformer: https://proceedings.mlr.press/v235/wu24a.html
- GraphCoder: https://arxiv.org/html/2406.07003v1
- CodexGraph: https://arxiv.org/html/2408.03910v2
- Hierarchical Repository-Level Code Summarization: https://arxiv.org/abs/2501.07857
- Making Retrieval-Augmented Language Models Robust to Irrelevant Context: https://arxiv.org/abs/2310.01558
- HCAG: https://arxiv.org/html/2603.20299v1
