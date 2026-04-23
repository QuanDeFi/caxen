# Further Research on Code Retrieval, Long-horizon project memory, Anti-memorization benchmark and Execution-aware, feature-level understanding

After digging deeper, my updated view is that the original problem is **broader and more interesting than “better repo retrieval.”** The strongest academic pattern is that repository understanding now looks like a **four-layer systems problem**:

(1) retrieve the right evidence,
(2) verify that the model actually used it,
(3) preserve project state across long sessions, and
(4) validate understanding against executable feature behavior rather than static code structure alone. ([arXiv][1])

## 1) Retrieval quality and context utilization: this is still the center of the problem

The clearest result is still from **ContextBench**: more agent scaffolding does **not** solve repository retrieval by itself. The paper reports only **marginal gains** from sophisticated scaffolds, a strong **recall-over-precision** bias, and a persistent gap between code the agent **explores** and code it **uses** in the final solution. That means the field still does not have a good answer to the “minimal sufficient evidence” problem. ([arXiv][1])

That same conclusion becomes sharper in **ReCUBE**, which isolates **repository-level context utilization** rather than general SWE success. Even in the **full-context** setting, GPT-5 reaches only **37.57% strict pass rate**, and adding the paper’s dependency-graph-based **Caller-Centric Exploration** improves strict pass rate by up to **7.56%**. The implication is important: giving the model more repository context is not enough; the hard part is helping it **navigate and exploit** the right dependency path. ([arXiv][2])

Older retrieval-efficiency papers fit this pattern well. **Repoformer** argues that unconditional retrieval is often wasteful because many retrieved chunks are **unhelpful or harmful**, and it reports up to **70% inference speedup** from **selective retrieval** without hurting performance. **Hierarchical Context Pruning** shows that keeping dependency topology while pruning implementation detail can reduce inputs from **over 50,000 tokens to about 8,000** while improving completion. **SWE-Pruner** pushes this into agent settings with **23–54% token reduction** on SWE-style tasks and up to **14.84× compression** on single-turn code reasoning, while preserving or improving performance. ([arXiv][3])

Recent repository-navigation papers suggest that **localizing first** is becoming the practical strategy. **LocAgent** uses a heterogeneous graph of files, classes, functions, and dependencies, reaching **92.7% file-level localization accuracy** and improving downstream issue resolution by **12% Pass@10**. **CoSIL** iteratively searches a call graph and reports **43.0% Top-1 localization** on SWE-bench Lite and **44.6%** on Verified. **OrcaLoca** combines relevance scoring with **distance-aware context pruning** and reports **65.33% function match rate** on SWE-bench Lite. **FastCode** explicitly frames the problem as separating **exploration** from **content consumption**, reporting better reasoning accuracy with lower token use through a structural “scouting-first” policy. ([arXiv][4])

So this subject expands the original research question in a specific way: the best target is not “better retrieval” in general, but **minimal-sufficient, dependency-aware, cost-aware retrieval**. The main open questions now look like: how to estimate **context sufficiency**, how to know **when to stop searching**, and how to guarantee that retrieved evidence is **actually consumed** rather than just collected. The broader RAG literature supports this framing: **Sufficient Context** argues that one must separate failures caused by **insufficient context** from failures caused by poor **context utilization**. ([arXiv][5])

## 2) Long-horizon project memory and specification tracking: this is the biggest expansion beyond the original framing

**SWE-ContextBench** shows that repository agents should not be evaluated as if every task is independent. The benchmark links **1,100 base tasks** with **376 related tasks** across **51 repositories** and **9 languages**, and finds that **correctly selected summarized experience** improves accuracy while substantially reducing runtime and token cost; unfiltered or wrong experience can provide little benefit or even hurt. That is strong evidence that project memory is not just “nice to have.” ([arXiv][6])

**SLUMP** goes further and studies a different failure mode: the case where the specification is revealed gradually over a long session instead of being given upfront. It finds that structural integration degrades under emergent specification, and its mitigation layer, **ProjectGuard**, recovers **90% of the faithfulness gap** on Claude Code, raising fully faithful components from **118 to 181** and cutting severe failures from **72 to 49**. That makes specification tracking look like a distinct research target, not just a side effect of weak retrieval. ([arXiv][7])

The newer long-horizon benchmarks reinforce that single-task evaluation is too shallow. **SWE-STEPS** reports that isolated-PR evaluation can **overstate performance by up to 20 percentage points** because it ignores spillover from earlier poor decisions. **SlopCodeBench** finds that no tested agent solves any problem end-to-end, with verbosity increasing in **89.8%** of trajectories, structural erosion in **80%**, and agent code becoming **2.2× more verbose** than human repository code. **SWE-CI** also shifts the setting from one-shot repair to long-term maintenance, with tasks spanning an average of **233 days** and **71 commits**. ([arXiv][8])

Memory systems aimed at code agents are starting to look useful here. **SWE-Exp** treats issue resolution as an **experience-driven** process rather than a memoryless one and reports **41.6% Pass@1** on SWE-bench Verified under open-source agent frameworks. **MemGovern** shows that externally governed experience memory can improve SWE-bench resolution by **4.65%** using **135K experience cards**, and emphasizes that useful memory is not just raw trajectory storage but **standardized, searchable repair logic**. Even outside a single benchmark, **Memory Transfer Learning** reports a **3.7% average score improvement across six coding benchmarks**, arguing that transferable value lies more in **meta-knowledge** like modification heuristics and verification routines than in task-specific code snippets. ([arXiv][9])

This changes the original problem a lot. The original framing was mostly about “how to understand one repo for one task with fewer tokens.” The newer evidence says the real problem is often “how to maintain a **compressed, trustworthy, updatable project state** across many related tasks.” That pushes repo understanding toward **working memory**, **episodic memory**, and **specification-state management**, not only retrieval indexes. ([arXiv][6])

## 3) Anti-memorization benchmark design: this matters more than it first seemed

The benchmark problem is serious. **CoReQA** already showed that both short-context retrieval baselines and long-context “read the repo” baselines struggle on repository QA across **176 repositories** and **4 languages**. But the later benchmarks sharpen the methodological issue: some apparent repository-understanding success is not real reasoning. ([arXiv][10])

**StackRepoQA** is the strongest direct warning. It is built from **1,318 real developer questions** across **134 Java repositories** and finds only **moderate** baseline accuracy, some gains from structural retrieval, but still limited overall repository comprehension. More importantly, it reports that high scores often come from **verbatim reproduction of Stack Overflow answers** rather than genuine repo reasoning. That means a benchmark can look good while measuring partial memorization instead of real navigation and grounding. ([arXiv][11])

**SWE-QA-Pro** responds directly to that problem by using **diverse long-tail repositories with executable environments**, enforcing topical balance, and filtering out questions that direct-answer baselines can solve without real exploration. In that setting, agentic workflows outperform direct answering by about **13 points** for Claude Sonnet 4.5. That is a strong sign that once leakage is reduced, exploration quality matters much more. ([arXiv][12])

Even outside pure QA, newer executable benchmarks are trying to remove shortcuts. **FeatureBench** can be updated over time to mitigate leakage because tasks are derived automatically from tests and dependency traces. **RepoMod-Bench** hides tests from agents and uses **implementation-agnostic** black-box verification; it then shows a severe scaling collapse from **91.3%** average pass rate on repositories under **10K LOC** to **15.3%** on those above **50K LOC**. That kind of design makes it harder for systems to overfit to visible tests or common benchmark artifacts. ([arXiv][13])

So this subject complements the original research by changing the **scientific standard** for evaluating repository understanding. If the benchmark leaks too much or rewards shallow recall, then retrieval, memory, and execution improvements are all hard to interpret. For this area, benchmark design is not just bookkeeping; it is part of the core research problem. ([arXiv][12])

## 4) Execution-aware, feature-level understanding: this is the strongest correction to static repo reasoning

This topic turned out to be one of the most important. **FeatureBench** argues that end-to-end, feature-oriented software development is underrepresented in current evaluation. Its tasks are derived by tracing from unit tests through a dependency graph, and the benchmark contains **200 tasks** and **3,825 executable environments** from **24 repositories**. The striking result is that a model with **74.4%** resolved rate on SWE-bench achieves only **11.0%** on FeatureBench. That suggests current agents are much weaker at feature integration than standard bug-fix benchmarks imply. ([arXiv][13])

**ReCUBE** supports the same conclusion from a different angle. By forcing the model to reconstruct a masked file from the rest of the repository and scoring it with **usage-aware** tests that simulate internal logic and cross-file integration, it isolates whether the model can really leverage repository context. The low pass rates there suggest that even modern models still struggle to transform repository context into behaviorally correct code. ([arXiv][2])

**Gistify** makes the execution point even sharper. It asks the model to create a **single, minimal, self-contained file** that reproduces a specific repository functionality from an entrypoint, which requires following execution flow through the codebase and compressing only the essential components. The authors report that current state-of-the-art models struggle on this task, especially when the execution trace is long. That is a very direct test of whether the agent really understands codebase behavior rather than just retrieving similar text. ([OpenReview][14])

The environment-construction papers matter here too. **RepoST** shows that scalable **sandbox testing** can provide execution feedback without requiring the full repository to be rebuilt every time, and training with RepoST-Train improves Pass@1 by **5.5% on HumanEval** and **3.5% on RepoEval**. **SWE-Next** scales this idea by mining and executing candidate commit pairs, filtering for self-verifying instances, and producing **2,308** execution-grounded tasks from **3,971 repositories** and **102,582** candidate pairs. These papers suggest that execution grounding is becoming a practical infrastructure problem, not just an evaluation idea. ([arXiv][15])

This expands the original subject from **static repository comprehension** to **behavioral repository comprehension**. A system can be decent at symbol graphs, file retrieval, and repository QA, yet still fail to understand what a feature actually does when exercised through callers, tests, and runtime paths. The newer execution-centric work says that this distinction is real and measurable. ([arXiv][13])

## What this does to the original research question

After this deeper pass, I would restate the original topic like this:

**The real problem is how to build a coding agent that can find the minimal sufficient evidence for a repo task, prove that its answer or patch is grounded in that evidence, preserve project knowledge across long sessions, and validate understanding against executable feature behavior — all under token and latency constraints.** ([arXiv][1])

That is broader than the original “better code retrieval/indexing” framing, but it still complements it rather than replacing it. Retrieval is still the first layer; the newer work just shows that **retrieval alone is not enough**. ([arXiv][1])

## The research directions that now look most worthwhile

The strongest next directions, in my view, are:

1. **Minimal-sufficient evidence retrieval**
   Build retrieval systems that optimize for the **smallest sufficient evidence set**, not raw recall. This should include stopping criteria, context-sufficiency estimators, and utilization-aware reranking. ([arXiv][1])

2. **Evidence utilization metrics and mechanisms**
   The field needs direct ways to test whether retrieved context was actually used, and better mechanisms for turning structural evidence into grounded edits or answers. ContextBench and ReCUBE make this gap visible, but they do not solve it. ([arXiv][1])

3. **Project-state memory for evolving specifications**
   Specification tracking, design-commitment tracking, and structured experience reuse look like a major opportunity. SLUMP, SWE-ContextBench, SWE-STEPS, SlopCodeBench, SWE-Exp, and MemGovern all point to this. ([arXiv][6])

4. **Execution-grounded feature reasoning**
   FeatureBench, ReCUBE, Gistify, RepoST, and SWE-Next suggest that the strongest future systems will need explicit support for caller tracing, test-centric exploration, feature decomposition, and lightweight execution feedback loops. ([arXiv][13])

5. **Leakage-resistant evaluation**
   Benchmark design still needs work: post-cutoff, long-tail, executable, exploration-required tasks should become the norm, otherwise it remains too easy to confuse memorization or benchmark gaming with repository understanding. ([arXiv][12])

One caveat: many of the most relevant papers here are **very recent 2025–2026 arXiv or OpenReview papers**, so the evidence is strong enough to shape a research agenda, but still fast-moving rather than fully settled. ([arXiv][1])

The strongest practical conclusion is still the same, but now more precise: **better repo understanding will come less from “longer context” and more from better evidence selection, better evidence use, better long-session memory, and stronger execution-grounded verification.** ([arXiv][1])

[1]: https://arxiv.org/abs/2602.05892 "[2602.05892] ContextBench: A Benchmark for Context Retrieval in Coding Agents"
[2]: https://arxiv.org/abs/2603.25770 "[2603.25770] ReCUBE: Evaluating Repository-Level Context Utilization in Code Generation"
[3]: https://arxiv.org/abs/2403.10059 "[2403.10059] Repoformer: Selective Retrieval for Repository-Level Code Completion"
[4]: https://arxiv.org/abs/2503.09089 "[2503.09089] LocAgent: Graph-Guided LLM Agents for Code Localization"
[5]: https://arxiv.org/abs/2411.06037 "[2411.06037] Sufficient Context: A New Lens on Retrieval Augmented Generation Systems"
[6]: https://arxiv.org/abs/2602.08316 "[2602.08316] SWE Context Bench: A Benchmark for Context Learning in Coding"
[7]: https://arxiv.org/abs/2603.17104 "[2603.17104] When the Specification Emerges: Benchmarking Faithfulness Loss in Long-Horizon Coding Agents"
[8]: https://arxiv.org/abs/2604.03035 "[2604.03035] Beyond Isolated Tasks: A Framework for Evaluating Coding Agents on Sequential Software Evolution"
[9]: https://arxiv.org/abs/2507.23361?utm_source=chatgpt.com "SWE-Exp: Experience-Driven Software Issue Resolution"
[10]: https://arxiv.org/abs/2501.03447 "[2501.03447] CoReQA: Uncovering Potentials of Language Models in Code Repository Question Answering"
[11]: https://arxiv.org/abs/2603.26567 "[2603.26567] Beyond Code Snippets: Benchmarking LLMs on Repository-Level Question Answering"
[12]: https://arxiv.org/abs/2603.16124 "[2603.16124] SWE-QA-Pro: A Representative Benchmark and Scalable Training Recipe for Repository-Level Code Understanding"
[13]: https://arxiv.org/abs/2602.10975 "[2602.10975] FeatureBench: Benchmarking Agentic Coding for Complex Feature Development"
[14]: https://openreview.net/forum?id=nmdDgo4OXC "Gistify: Codebase-Level Understanding via Runtime Execution | OpenReview"
[15]: https://arxiv.org/abs/2503.07358 "[2503.07358] RepoST: Scalable Repository-Level Coding Environment Construction with Sandbox Testing"
