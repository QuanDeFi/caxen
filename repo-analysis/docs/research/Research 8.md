# Further research on Structure-aware retrieval, Dependency-preserving compression/filtering, Exploration and planning policies, change-impact analysis

The central challenge is **not** “how do we stuff more repository text into the model,” but **how do we navigate repository structure under a token budget**. The strongest papers increasingly converge on the same shape of solution: represent the repo structurally, retrieve with dependency awareness, compress while preserving topology, and use an explicit exploration policy instead of flat one-shot retrieval. The older software-engineering literature is highly relevant here, because modern repo agents are rediscovering ideas that look a lot like program dependence graphs, system dependence graphs, slicing, and change-impact analysis. ([Digital Commons][1])

## 1. Structure-aware retrieval deserves the deepest research

This is the strongest direction. Classic program-analysis work already showed why dependence structure matters: PDGs make data and control dependences explicit, and SDGs turn interprocedural slicing into a graph reachability problem. Modern repo-level methods are effectively reusing that idea for LLM context construction. GraphCoder uses a statement-level code context graph built from control flow and dependence edges; GRACE expands that to a multi-level graph spanning file structure, ASTs, call graphs, class hierarchies, and data flow; LingmaAgent builds a top-down repository knowledge graph with function-call relationships; and ReCUBE’s caller-centric toolkit shows that dependency-graph-guided exploration improves context utilization over baseline agent settings. ([Digital Commons][1])

The more specific lesson is that **“graph retrieval” is not one thing**. The best recent work is moving toward **multi-view graphs** rather than a single call graph: file hierarchy, symbol ownership, call edges, inheritance, AST neighborhoods, dataflow, and sometimes requirement-to-code mappings. GRACE’s gains come from this broader graph and a hybrid retriever; SaraCoder improves retrieval by combining semantic refinement, graph-based structural similarity, diversity control, and identifier disambiguation; and knowledge-graph-based repository generation papers explicitly frame the value of graph retrieval as tracking inter-file modular dependencies, not just semantic similarity. ([arXiv][2])

So the deeper research question here is not merely “should we use graphs?” It is: **what graph should we build, at what granularity, and which edge types are actually predictive for repo tasks?** The literature suggests that future gains will likely come from comparing graph schemas systematically: statement-level dependence graphs versus function-level call/reference graphs versus build/dependency graphs versus caller-centric exploration graphs. That comparison still seems underdeveloped. ([arXiv][3])

## 2. Dependency-preserving compression/filtering is the most direct path to lower token use

This is the part of the literature that feels most directly aligned with your stated goal. HCP shows that **maintaining topological dependencies** helps completion, while **pruning specific function implementations** in dependent files does not significantly hurt accuracy. Repoformer shows retrieval itself should be selective, because always retrieving is inefficient and sometimes harmful; it reports up to **70% inference speedup** without harming performance. CodeFilter goes further and shows that after retrieval, **only a small subset of chunks actually helps**, while some chunks actively degrade performance. REPOFUSE makes a similar point from a latency perspective: it explicitly frames the “context-latency conundrum” and uses truncated context construction to improve both exact match and inference speed. ([arXiv][4])

That means the next research frontier is not generic summarization. It is **utility-aware compression**. The field needs better models of **which structural evidence must survive compression**: signatures, callers, callees, dependency paths, class hierarchy, import/export boundaries, test touchpoints, build targets, and configuration edges. HCP gives one concrete answer at function level; CodeFilter gives another at retrieved-chunk level; SWE-ContextBench adds that even summarized prior experience only helps when it is **correctly selected**, while unfiltered or badly selected experience gives limited or negative benefit. ([arXiv][4])

One especially important implication is that **persistent repo context files are not automatically the answer**. The recent AGENTS.md study finds that repository context files tend to reduce task success and increase inference cost by over 20% when they contain unnecessary requirements. That fits the rest of the compression literature: more context is not the same as better context. Minimal, high-utility context appears to be the safer design principle. ([arXiv][5])

## 3. Exploration and planning policies are more important than they first look

Once retrieval becomes graph-aware, the next bottleneck is **how the agent traverses that structure**. CodePlan already showed this in 2023: repository editing is better framed as a planning problem over interdependent edits, using incremental dependency analysis and change may-impact analysis, and it got 5 of 6 repositories through validity checks while non-planning baselines got none. DeepRepoQA applies the same intuition to repository QA, using MCTS to balance exploration and exploitation over structured actions. LingmaAgent pushes that further for issue resolution: build a repository knowledge graph, explore it with MCTS, then summarize, analyze, and plan before patch generation. SGAgent adds another important nuance: the field has overemphasized “localize-then-fix,” and a separate **suggestion** phase helps bridge localization and patching. ([arXiv][6])

This makes me think the real research target is **budgeted search policy**, not just better retrieval. RepoSearch-R1 is especially interesting here because it treats repository QA as an RL problem and shows better answer completeness than no-retrieval and iterative-retrieval baselines, while improving training efficiency. The specific question worth deeper research is: **how should an agent allocate search budget across hierarchy expansion, dependency expansion, caller expansion, summarization, and direct file reads?** The literature shows that search policy matters, but it still does not give a settled answer on the optimal action space or stopping rule. ([arXiv][7])

## 4. Classic change-impact analysis should be pulled much more directly into repo agents

This is where I think there is a real underexploited bridge between software engineering and LLM agents. The older literature defines change impact analysis as identifying the potential consequences of a change, and later work combines textual IR, dynamic traces, developer-verified locations, historical commits, and build dependency graphs to improve impact sets. BLIMP Tracer is especially relevant because it shows that **build dependency graphs** can be traversed from changed files to impacted deliverables. In modern repo agents, this same logic could rank which files, tests, modules, and build targets are most likely to matter before the agent spends tokens reading code. ([DNB][8])

So I would now treat **impact analysis as a first-class retrieval primitive**. Instead of only asking “what code looks semantically similar to the query?”, the agent should also ask “what artifacts are most likely to be affected if this symbol, file, or issue description is the seed?” That could unify bug localization, edit planning, and context compression under a single dependency-sensitive scoring model. The existing literature strongly suggests that this is promising, but I do not think the current repo-agent papers have explored it deeply enough yet. ([cs.wm.edu][9])

## 5. The most promising next research agenda

If the goal is to solve your current challenge, I would prioritize deeper research in this order.

First, **graph schema design for repository retrieval**: which combination of hierarchy, call/reference, dependence, build, and runtime/test edges gives the best retrieval under a fixed token budget. The recent graph papers are strong, but they do not yet settle the best graph design. ([arXiv][3])

Second, **set-level context utility modeling**: not just whether one chunk helps, but whether a *combination* of chunks helps. CodeFilter already shows that some chunks are harmful, but the next step is interaction-aware utility estimation over groups of evidence. ([arXiv][10])

Third, **search policy over structured repos**: how the agent should move through a repo graph, when it should expand dependency neighborhoods, when it should summarize, when it should stop, and when it should switch from graph navigation to raw-code verification. This is where CodePlan, DeepRepoQA, LingmaAgent, and RepoSearch-R1 all point. ([arXiv][6])

Fourth, **impact-aware retrieval and build/test-aware grounding**: integrate classical impact analysis and build dependency graphs into retrieval and ranking, instead of treating them as post-hoc engineering artifacts. The build/test layer looks too important to remain secondary. ([cs.wm.edu][9])

## Bottom line

After the deeper research, my view is stronger than before: the best path is not “better prompting,” “more context,” or even “better embeddings.” It is a **repository navigation stack** built from four coupled ideas: **structured repository graphs, dependency-preserving compression, policy-driven exploration, and impact/build/test-aware ranking**. That combination seems the most credible route to faster, cheaper, and more accurate repo understanding. ([arXiv][2])

The single research question I would now put at the center is:

**How should an LLM agent navigate a multi-view repository graph under a strict token and tool-call budget while maximizing final evidence quality?** ([arXiv][11])

[1]: https://digitalcommons.mtu.edu/michigantech-p/12533 "The Program Dependence Graph and Its Use in Optimization"
[2]: https://arxiv.org/abs/2509.05980 "[2509.05980] GRACE: Graph-Guided Repository-Aware Code Completion through Hierarchical Code Fusion"
[3]: https://arxiv.org/html/2406.07003v2 "GraphCoder: Enhancing Repository-Level Code Completion via Code Context Graph-based Retrieval and Language Model"
[4]: https://arxiv.org/abs/2406.18294 "[2406.18294] Hierarchical Context Pruning: Optimizing Real-World Code Completion with Repository-Level Pretrained Code LLMs"
[5]: https://arxiv.org/abs/2602.11988 "[2602.11988] Evaluating AGENTS.md: Are Repository-Level Context Files Helpful for Coding Agents?"
[6]: https://arxiv.org/abs/2309.12499 "[2309.12499] CodePlan: Repository-level Coding using LLMs and Planning"
[7]: https://arxiv.org/html/2510.26287v1 "Empowering RepoQA-Agent based on Reinforcement Learning Driven by Monte-carlo Tree Search"
[8]: https://d-nb.info/1020114983/34 "A review of software change impact analysis"
[9]: https://www.cs.wm.edu/~denys/pubs/ICSE12-ImpactAnalysis.pdf "Microsoft Word - ICSE2012-IA-CRC-v5.doc"
[10]: https://arxiv.org/abs/2508.05970 "[2508.05970] Impact-driven Context Filtering For Cross-file Code Completion"
[11]: https://arxiv.org/abs/2602.08316?utm_source=chatgpt.com "SWE Context Bench: A Benchmark for Context Learning in Coding"
