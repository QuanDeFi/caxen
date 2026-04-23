# Further research into multi-view graph indexing, interaction-aware context filtering, search/traversal policy, execution grounding

**How should an LLM agent navigate a multi-view repository graph under a strict token and tool-call budget while maximizing final evidence quality?**

My updated view is this:

The literature is starting to converge on a **four-part stack**:

1. **multi-view graph indexing**
2. **interaction-aware context filtering**
3. **explicit search / traversal policy**
4. **execution and test-aware grounding**

That stack now looks much more plausible than flat RAG or simple long-context prompting. ([arXiv][1])

## 1. Multi-view graph indexing looks stronger than single-view graph retrieval

The newer graph papers are moving away from “just use a call graph” or “just use AST nodes.” GRACE explicitly builds a **multi-level, multi-semantic graph** spanning file structure, ASTs, function call graphs, class hierarchies, and data-flow graphs, then uses hybrid retrieval plus graph-aware reranking. RIG also frames repository understanding as a **Repository Intelligence Graph** rather than a single structure. RPG goes one step further and argues for a planning graph that encodes functionality, file structures, data flows, and function designs together. ([arXiv][1])

That suggests the deeper research target is not “graph vs no graph,” but **which graph views should be present simultaneously**. The strongest candidate set, based on the current papers, is:

* file / directory hierarchy
* symbol ownership and signatures
* call / reference edges
* inheritance / type relations
* data-flow or dependence edges
* test/code dependency edges
* build / dependency / environment edges

GRACE supports the first five directly, TDAD adds code–test dependency graphs, and EnvGraph shows that external dependency satisfaction plus internal reference resolution are both first-class parts of repository success. ([arXiv][1])

So the next research question here should be:

**Which edge families improve retrieval most under a fixed token budget, and which ones only add graph complexity without improving final evidence quality?**

Right now the papers strongly suggest “more structured than text,” but they do **not** yet settle the optimal graph schema. ([arXiv][1])

## 2. Set-level context utility is real, and this deserves a lot more research

This area looks more important now than before. RepoShapley makes the key point very explicitly: chunk utility is often **interaction-dependent**. A snippet may be useless alone but crucial when paired with complementary evidence, and another snippet may look good in isolation but become harmful when combined with conflicting context. CODEFILTER is closely aligned with that and trains on chunk **polarity**, explicitly modeling whether retrieved cross-file chunks are beneficial or harmful. ([arXiv][2])

That means the right abstraction is probably **not chunk ranking**, but **evidence set construction**. The agent should not ask only “is this chunk relevant?” It should ask:

* does this chunk complete another chunk
* does it conflict with another chunk
* is it a dependency anchor
* is it only useful after a certain path is activated
* does it increase or reduce ambiguity

RepoShapley is especially important because it pushes toward **coalition-aware filtering**, which feels much closer to the real repository problem than independent chunk scoring. ([arXiv][2])

So this now looks like one of the most important research subjects for your challenge:

**How should an agent score the utility of a set of retrieved evidence, not just each retrieved item independently?** ([arXiv][2])

## 3. Search policy is emerging as a separate scientific problem

The search papers now make this much clearer. GraphCodeAgent exposes explicit multi-hop graph traversal where the agent can move through the repository and decide at each step whether to retrieve or discard the current node. RANGER combines a knowledge graph with MCTS for a dual-stage retrieval system that can handle both entity queries and natural-language queries. LingmaAgent also uses repository knowledge graph construction plus an MCTS-enhanced understanding phase. SGAgent adds a very important refinement: it argues that repository repair should not jump straight from localization to fixing, but should insert a **suggestion** phase that incrementally retrieves context until the bug is understood. ([arXiv][3])

This changes the framing. The problem is not only “what should be retrieved,” but also:

* when to expand graph neighborhoods
* when to switch from graph traversal to raw file reading
* when to stop searching
* when to summarize
* when to trigger planning
* when to verify against tests or runtime evidence

RANGER also notes a tradeoff: MCTS-style graph exploration can improve navigation, but repeated high-fidelity LLM scoring creates higher cost and nondeterminism. That means search policy research should not only optimize accuracy; it should optimize **accuracy per token and per tool call**. ([arXiv][4])

So the central question here becomes:

**What is the best budgeted traversal policy over a repository graph?**
That now looks like a first-class research area, not just an implementation detail. ([arXiv][3])

## 4. Build/test/environment grounding looks even more important than before

The recent work strengthened this point a lot. TDAD builds an AST-derived code–test dependency graph and applies weighted impact analysis so the agent knows **which tests are most likely affected** before committing a patch. EnvGraph pushes the same idea into repository generation: successful repository execution depends on both **external dependency satisfaction** and **repository-internal reference resolution**, and it uses execution evidence like build results, runtime errors, stack traces, and test outcomes to drive iterative revision. It reports gains of **5.72–5.87 points** in functional correctness over the strongest non-EnvGraph baseline. RPG/ZeroRepo also uses test validation in its graph-driven generation flow. ([arXiv][5])

Hydra’s findings support this from a retrieval angle: similarity-based retrieval often misses required dependencies, while dependency-aware retrieval is more robust, and the best results come from a **hybrid** strategy that anchors generation on true dependencies and augments them with similarity-based usage signals. ([arXiv][6])

This suggests a big design implication:

**build/test/environment edges should probably be part of the main repository graph, not bolted on later.**
They look increasingly like core navigation signals, especially for deciding what is actually relevant under budget. ([arXiv][7])

## 5. The best current shape of the system

After this round of research, the most credible repository-navigation stack looks like this:

**Layer 1: multi-view repository graph**
file hierarchy, symbols, references, call edges, type relations, data flow, test links, build/dependency/environment edges. ([arXiv][1])

**Layer 2: hybrid candidate generation**
mix lexical / semantic retrieval with graph-based expansion and reranking, because the papers keep showing that dependency-aware retrieval is better than similarity-only, but hybrid often works best. ([arXiv][6])

**Layer 3: coalition-aware filtering**
filter the candidate set based on complementarity, conflict, and group utility rather than naive per-chunk ranking. ([arXiv][2])

**Layer 4: budgeted traversal policy**
use explicit search rules or learned policies to decide expansion, pruning, summarization, raw-code reads, and stopping. ([arXiv][3])

**Layer 5: execution-aware verification**
feed back build failures, stack traces, runtime errors, test results, and dependency problems into the graph and use them to re-rank or revise. ([arXiv][7])

That overall shape now seems much better supported than the simpler “retrieve some chunks and hope” pattern. ([arXiv][1])

## 6. What deserves the next deepest research now

If I were prioritizing the next round of work, I would focus on these exact research questions:

### A. Graph schema ablations

Which combinations of edge types give the best downstream evidence quality per token?

* call/reference only
* call + type + hierarchy
* add data flow
* add tests
* add build/dependency/environment edges ([arXiv][1])

### B. Set-level evidence utility

How should we score a **group** of evidence instead of each chunk independently?

* complementary pairs
* conflicting evidence
* bridge nodes
* dependency anchors
* ambiguity reduction ([arXiv][2])

### C. Traversal policy under budget

What search policy gives the best answer quality per token/tool-call budget?

* BFS-like neighborhood expansion
* dependency-first expansion
* MCTS
* localize → suggest → fix
* summarize-before-expand vs expand-before-summarize ([arXiv][8])

### D. Execution-aware ranking

How much can build/test/runtime evidence improve retrieval ranking and stopping decisions?

* failing tests
* impacted tests
* unresolved imports
* dependency installation failures
* stack trace anchors ([arXiv][5])

## Bottom line

My updated conclusion is stronger now:

The core problem is best seen as **budgeted evidence acquisition over a multi-view software graph**. The winning system is likely not a pure retriever and not a pure planner, but a **graph-indexed, coalition-filtered, policy-driven, execution-grounded navigator**. ([arXiv][1])

The single most important unresolved research question now seems to be:

**How do we jointly optimize graph schema, evidence-set construction, and traversal policy under a fixed token and tool-call budget?** ([arXiv][1])

[1]: https://arxiv.org/abs/2509.05980 "GRACE: Graph-Guided Repository-Aware Code Completion through Hierarchical Code Fusion"
[2]: https://arxiv.org/abs/2601.03378 "[2601.03378] RepoShapley: Shapley-Enhanced Context Filtering for Repository-Level Code Completion"
[3]: https://arxiv.org/html/2504.10046v2 "GraphCodeAgent: Dual Graph-Guided LLM Agent for Retrieval-Augmented Repo-Level Code Generation"
[4]: https://arxiv.org/html/2509.25257v1 "RANGER: Repository‑level Agent for Graph‑Enhanced ..."
[5]: https://arxiv.org/html/2603.17973v1 "TDAD: Test-Driven Agentic Development – Reducing Code Regressions in AI Coding Agents via Graph-Based Impact Analysis"
[6]: https://arxiv.org/html/2602.11671v1 "Do Not Treat Code as Natural Language: Implications for Repository-Level Code Generation and Beyond"
[7]: https://arxiv.org/html/2604.03622v1 "Toward Executable Repository-Level Code Generation via Environment Alignment"
[8]: https://arxiv.org/abs/2602.23647 "SGAgent: Suggestion-Guided LLM-Based Multi-Agent Framework for Repository-Level Software Repair"
