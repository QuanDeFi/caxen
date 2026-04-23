# Further research into Graph schema ablations, Set-level evidence utility, Traversal policies, Execution-aware ranking

My updated view is that the repository-navigation problem breaks into **two core subproblems**:

* **how to build the right evidence graph**
* **how to acquire the right evidence set under budget**

The papers suggest that the first is mostly a **representation problem**, while the second is a **policy problem**. The best current work is starting to connect both. Most of the strongest signals here are from 2025–2026 arXiv papers, so I would treat the conclusions as **strong but still provisional** rather than fully settled consensus. ([arXiv][1])

## A. Graph schema ablations

The strongest current conclusion is that **single-view graphs are probably too weak**. GRACE does not just use a call graph; it uses a **multi-level, multi-semantic code graph** that unifies file structure, ASTs, function call graphs, class hierarchies, and data-flow graphs, then retrieves and reranks subgraphs instead of flat chunks. It reports gains of **8.19 EM** and **7.51 ES** over the strongest graph-RAG baselines in its setup. RANGER points in the same direction from a retrieval-agent angle: it builds a repository knowledge graph with **hierarchical and cross-file dependencies down to the variable level**, then uses different retrieval modes for entity queries versus natural-language queries. ([arXiv][1])

Hydra makes the schema question even more concrete because it includes an ablation-style argument about **granularity**. It finds that dependency-aware retrieval is more robust than similarity-only retrieval, that the hybrid retriever works best, and that **function- and class-level retrieval contribute the most**, while **variable-level retrieval adds complementary gains** rather than carrying the system alone. That is a very useful clue for your challenge: not all graph detail is equally valuable, and the likely “core edge set” is **symbol ownership + call/reference + type/hierarchy**, with data flow and variables added selectively. ([arXiv][2])

The newer indexing work also suggests a practical constraint: richer graphs are only useful if they are cheap enough to build and query. The TypeScript indexing paper argues that graph-based indexing helps because it preserves call chains and dependencies that keyword and similarity methods miss, but it also shows that parser and indexing efficiency become bottlenecks on large repositories, even in one language. That implies graph schema research should not just ask “what edges help accuracy,” but also “what edges are worth their build/query cost.” ([arXiv][3])

My current judgment is:

* **Core graph views likely worth default inclusion:** file hierarchy, symbols/signatures, call/reference edges, and type/class hierarchy. ([arXiv][1])
* **High-value but task-dependent additions:** data flow, variable-level relations, code–test dependency edges, build/dependency/environment edges. Hydra, TDAD, and EnvGraph all imply these help, but mostly when the task is completion/editing with executable consequences. ([arXiv][2])

So the next research question here is not “graph or no graph,” but:

**Which graph views are worth their cost for which task class: QA, completion, repair, or executable repo generation?** ([arXiv][1])

## B. Set-level evidence utility

This now looks like one of the most important areas.

CODEFILTER provides a very strong empirical signal: on its RepoEval-API analysis, only **15%** of top-10 retrieved cross-file chunks actually support completion, **5.6%** are actively harmful, and the rest are irrelevant. It also reports that these negative-impact chunks affect **19.81%** of instances, and that filtering them can produce **over 10% exact-match improvement** in the affected cases. That is one of the clearest signals in the literature that “retrieve top-k chunks and pass them all through” is fundamentally wasteful and sometimes damaging. ([arXiv][4])

RepoShapley pushes this even further by arguing that chunk utility is **interaction-dependent**. Its main contribution is not just another filter, but a coalition-aware view: chunk usefulness depends on **saturation**, **interference**, and the value of a chunk **in combination** with others. It explicitly models signed chunk effects, structured interaction, and coalition selection, then distills verified keep/drop decisions into a single controller. That is very close to the real repository problem, where one snippet may be useless alone but critical when paired with its caller, callee, or type definition. ([arXiv][5])

So I now think the right unit of optimization is **not the chunk**. It is the **evidence set**. The agent should score not only relevance but also:

* complementarity
* conflict/interference
* dependency anchoring
* ambiguity reduction
* coverage of a minimal causal path

That conclusion is strongly supported by CODEFILTER’s chunk polarity results and RepoShapley’s coalition-aware filtering design. ([arXiv][4])

The most important unresolved question here is:

**How should an agent build a minimal but sufficient evidence coalition rather than a top-k list?** ([arXiv][5])

## C. Traversal policy under budget

The search-policy story is also getting much stronger.

RANGER suggests a **split policy**: direct lookup for entity-style queries, but graph exploration for natural-language queries. Its dual-stage design is important because it implies there may not be one best traversal rule for all repository questions. Some queries want fast symbolic lookup; others want exploratory search over neighborhoods. ([arXiv][6])

SGAgent strengthens the case for **staged traversal**. It argues that localize-then-fix leaves a reasoning gap, and inserts a **suggestion phase** where the system incrementally retrieves context from buggy locations until it fully understands the bug, then hands actionable repair guidance to the fixer. This is a very important clue: a good traversal policy may need an explicit **understanding phase**, not just localization followed by generation. SGAgent also reports strong downstream numbers on SWE-Bench with this policy. ([arXiv][7])

RepoSearch-R1 adds the training angle: it uses **MCTS-guided exploration** for repository QA and reports **16.0%** improvement over no-retrieval, **19.5%** over iterative retrieval, and **33%** better training efficiency than its comparison setup. That suggests search policy is not just an inference trick; it can become a learned behavior. ([arXiv][8])

Putting those together, the most plausible policy family right now seems to be:

* cheap symbolic/entity lookup when the query is explicit
* graph-neighborhood expansion when the query is underspecified
* a dedicated **understanding/suggestion** stage before patching
* selective escalation from graph navigation to raw-code reading
* stopping decisions based on evidence sufficiency, not just top-k exhaustion

RANGER, SGAgent, and RepoSearch-R1 all support some version of that picture. ([arXiv][6])

So the key open question is:

**What traversal policy maximizes final evidence quality per token and tool call, not just final accuracy in isolation?** ([arXiv][6])

## D. Execution-aware ranking

This area now looks even more important than before.

TDAD gives one of the cleanest practical results: building a dependency map between code and tests so the agent knows **which tests to verify before committing a patch** reduced regressions by **70%** and improved issue resolution from **24% to 32%** in one deployment setup. It also found that plain TDD prompting without targeted test context actually made regressions worse. That is a very strong signal that **execution-related context beats procedural prompting**. ([arXiv][9])

EnvGraph goes beyond tests and treats execution grounding as a full alignment problem. It builds a **dual-layer environment representation**: one layer for external dependency satisfaction and one for repository-internal reference resolution. It then executes the repo, gathers **dependency installation failures, runtime errors, stack traces, and test outcomes**, normalizes them into an evidence schema, attributes the dominant source of misalignment, and revises the repo iteratively. Its ablation results are especially useful for your research question: removing either graph hurts, but removing **execution-evidence-based attribution** and the **iterative alignment loop** hurts most. For GPT-5 in its setup, removing evidence-based attribution drops functional correctness by **11.36** points, and removing the iterative loop drops it by **12.10**. ([arXiv][10])

This changes the ranking picture quite a bit. Build/test/runtime signals should not be treated as post-hoc verification only. They appear strong enough to act as **primary ranking and stopping signals**. The agent should probably treat unresolved imports, missing dependencies, failing impacted tests, and stack-trace anchors as first-class evidence in retrieval and prioritization. TDAD and EnvGraph both support that conclusion. ([arXiv][9])

## What I think now

The research direction is now clearer than before.

The four subjects are not independent. They look like one integrated problem:

* **Graph schema** defines what can be navigated.
* **Set-level utility** defines what evidence should be kept together.
* **Traversal policy** defines how the graph is explored under budget.
* **Execution-aware ranking** defines how runtime reality should redirect the search.

The strongest emerging architecture is therefore:

**multi-view graph → hybrid retrieval → coalition-aware filtering → staged traversal policy → execution-aware reranking and stopping**. ([arXiv][1])

The part that now looks most underexplored, and probably most promising for your challenge, is this:

**joint optimization of evidence-set construction and traversal policy over a multi-view repository graph, with execution signals used to update both ranking and stopping.** ([arXiv][5])

[1]: https://arxiv.org/abs/2509.05980 "[2509.05980] GRACE: Graph-Guided Repository-Aware Code Completion through Hierarchical Code Fusion"
[2]: https://arxiv.org/pdf/2602.11671 "Do Not Treat Code as Natural Language: Implications for Repository-Level Code Generation and Beyond"
[3]: https://arxiv.org/html/2604.18413v2 "TypeScript Repository Indexing for Code Agent Retrieval"
[4]: https://arxiv.org/html/2508.05970 "Impact-driven Context Filtering For Cross-file Code Completion"
[5]: https://arxiv.org/abs/2601.03378 "[2601.03378] RepoShapley: Shapley-Enhanced Context Filtering for Repository-Level Code Completion"
[6]: https://arxiv.org/abs/2509.25257 "[2509.25257] RANGER -- Repository-Level Agent for Graph-Enhanced Retrieval"
[7]: https://arxiv.org/abs/2602.23647 "[2602.23647] SGAgent: Suggestion-Guided LLM-Based Multi-Agent Framework for Repository-Level Software Repair"
[8]: https://arxiv.org/abs/2510.26287 "[2510.26287] Empowering RepoQA-Agent based on Reinforcement Learning Driven by Monte-carlo Tree Search"
[9]: https://arxiv.org/abs/2603.17973 "[2603.17973] TDAD: Test-Driven Agentic Development - Reducing Code Regressions in AI Coding Agents via Graph-Based Impact Analysis"
[10]: https://arxiv.org/html/2604.03622v1 "Toward Executable Repository-Level Code Generation via Environment Alignment"
