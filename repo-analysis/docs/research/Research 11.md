# Further research into sufficiency estimators, utilization-aware attribution, repository-native memory, execution evidence compression, 

Yes. After continuing the research, I think these five questions now form a **coherent second-generation research agenda** for repository agents.

The main shift is this: the field is moving away from “better repo RAG” and toward a **closed-loop repository reasoning system** with five linked parts: **sufficiency-aware retrieval, utilization-aware attribution, repository-native memory, execution-derived intermediate signals, and leakage-resistant evaluation**. ContextBench, ReCUBE, SWE-ContextBench, FeatureBench, SWE-QA-Pro, StackRepoQA, RepoMod-Bench, and IDE-Bench all point in that direction from different angles. ([arXiv][1])

## 1. Can we build a sufficiency estimator?

I think **yes, partially**, and this now looks like one of the best research directions. The conceptual basis is already there: *Sufficient Context* separates failures caused by **insufficient evidence** from failures caused by **poor use of sufficient evidence**, and shows that models often answer incorrectly instead of abstaining when the context is not sufficient; its selective generation method improves the fraction of correct answers among responses by **2–10%**. In code, Repoformer shows that retrieval should be **selective rather than automatic**, giving up to **70% online inference speedup** without harming completion quality, while FastCode shows that **scouting-first structural navigation** can improve reasoning accuracy while reducing token use. ([arXiv][2])

What is new from the code-specific papers is that sufficiency is starting to look like a **benefit prediction** problem rather than a relevance problem. Impact-driven Context Filtering finds that only a **small subset** of retrieved chunks actually helps completion and that some retrieved chunks **degrade** it; RepoShapley pushes further by modeling chunk utility as **interaction-dependent**, not independent, and supervises keep/drop decisions using Shapley-style marginal contributions. InlineCoder adds a useful signal for future sufficiency estimators: it first generates an “anchor,” then uses **perplexity-based confidence estimation** to decide how to inline caller/callee context around that anchor. ([arXiv][3])

The strongest open problem is that current systems still do not know **when to stop searching**. ContextBench shows recall-heavy retrieval and a large explored-versus-utilized gap; CoSIL, GraphLocator, and FastCode show that dependency-guided and graph-guided exploration helps localization, but they are still mostly optimizing better search, not **provably sufficient stopping**. So the next step is not just better retrieval ranking; it is a **repository-native stopping policy** that predicts: “the current evidence set is sufficient for safe answer/edit generation, and more search is unlikely to help enough to justify the cost.” ([arXiv][1])

My view is that this question has become more precise than before. The best formulation is now: **can we estimate marginal utility of the next retrieved artifact and stop when expected utility falls below cost?** The literature is close to this, but not there yet. ([arXiv][3])

## 2. Can we build utilization-aware attribution?

I think **yes, but only in a first-generation form today**. ContextBench already gives the field a key metric by distinguishing **explored** from **utilized** context, and ReCUBE isolates repository-level context utilization directly by asking models to reconstruct a masked file using the rest of the repo; even in the full-context setting, GPT-5 reaches only **37.57% strict pass rate**, and dependency-graph-based Caller-Centric Exploration improves strict pass rate by up to **7.56%**. That means utilization is measurable and still very weak. ([arXiv][1])

The attribution side is beginning to take shape. Impact-driven Context Filtering labels retrieved chunks as positive, neutral, or negative based on their effect on completion likelihood, while RepoShapley models context contribution at the **coalition** level because chunks can help only in combination or become harmful in interaction. Those are early but important moves away from “was this chunk retrieved?” toward “did this chunk actually change the outcome probability?” ([arXiv][3])

What is still missing is **causal attribution from artifact to patch correctness**. RACE-bench helps because it provides structured intermediate reasoning ground truth and shows that “apply-success but test-fail” cases have **35.7% lower reasoning recall** and **94.1% higher over-prediction** than successful cases. RepoReason adds another useful white-box lens with dynamic slicing metrics like reading load, simulation depth, and integration width, and finds an **aggregation deficit** where integration width is the main bottleneck. These are strong evaluation tools, but they are not yet a complete attribution mechanism that says, with confidence, which retrieved artifacts caused the correct patch or answer. ([arXiv][4])

So the research opportunity here is very strong: a future agent should produce not only an answer or patch, but also an **artifact-level support graph** showing which files, symbols, trace events, and prior memories changed the agent’s belief and why. Right now the field can measure the gap; it still cannot close it cleanly. ([arXiv][1])

## 3. Can project memory be made repository-native?

I think **yes, and this may be the most important expansion beyond the original problem**. SWE-ContextBench shows that **correctly selected summarized prior context** improves resolution accuracy and substantially reduces runtime and token cost, while unfiltered or wrongly selected context can hurt. SLUMP then shows a deeper long-horizon failure mode: when the specification emerges gradually, structural integration degrades, and an external project-state layer, ProjectGuard, recovers **90% of the faithfulness gap**, increases fully faithful components from **118 to 181**, and reduces severe failures from **72 to 49**. ([arXiv][5])

The memory papers suggest that repository-native memory is already feasible in several forms. Improving Code Localization with Repository Memory uses **commit history, linked issues, and functionality summaries** from actively evolving code as non-parametric memory and improves localization on SWE-bench-style settings. MemGovern turns GitHub history into **135K governed experience cards** and improves SWE-bench Verified resolution by **4.65%**. SWE-Exp extracts reusable issue-resolution knowledge at multiple levels and reaches **73.0% Pass@1** on SWE-Bench Verified with Claude 4 Sonnet. Structurally Aligned Subtask-Level Memory improves Pass@1 by **+4.7 pp on average** over vanilla agents by retrieving memory at the subtask level rather than whole-instance similarity. Memory Transfer Learning then shows that even **cross-domain** memory can help by transferring meta-knowledge like validation routines rather than task-specific code. ([arXiv][6])

The real insight is that useful memory is not generic chat history. The best evidence points toward memory objects like: **design commitments, architectural invariants, regression history, prior successful localization patterns, active-module summaries, and commit-history abstractions**. That is much closer to how human maintainers think about a repository than simple conversational summaries. ([arXiv][6])

The main open problem is schema. The field still lacks a stable, shared representation for repository-native memory: what exactly should be stored, how should it be updated after edits or failures, and how should conflicting memories be resolved when the spec evolves. That looks like a major research gap. ([arXiv][5])

## 4. Can execution evidence be compressed into reusable signals?

I think **yes, and this is where the field may get the biggest accuracy gains per token**. The strongest result is that execution feedback is useful, but raw pass/fail tests are too coarse. SWE-RM makes this explicit: execution-based feedback is often a **sparse, binary signal** and cannot distinguish between different successful or unsuccessful trajectories very well. That is why execution evidence should be turned into something denser than plain test outcomes. ([arXiv][7])

Several papers now show what that denser signal could look like. DAIRA treats execution traces as first-class evidence, extracting **call stacks, variable mutations, and runtime states** into structured semantic reports; with Gemini 3 Flash Preview, it reaches **79.4%** on SWE-bench Verified while cutting overall inference expense by about **10%** and token consumption by about **25%**. Env Graph does something similar for repository generation: it uses **execution-evidence-based attribution** inside an iterative alignment loop and improves functional correctness by **5.72–5.87 percentage points** over the strongest non-Env Graph baseline. Agentic Rubrics explores an execution-free but still repository-grounded verifier: an expert agent first explores the repo, then creates a rubric checklist that scores candidate patches, improving parallel TTS performance over strong baselines without running tests. ([arXiv][8])

The infrastructure papers make this more practical. RepoST builds scalable sandbox environments and shows that training with execution feedback improves Pass@1 by **5.5%** on HumanEval and **3.5%** on RepoEval. SWE-Next scales executable task collection by mining real merged PRs and retaining only commit pairs with strict test improvement and no regressions, producing **2,308 self-verifying instances** from **3,971 repositories** and **102,582 candidate commit pairs** while reusing environments through repo-quarter profiles. That suggests execution evidence can be collected and reused at scale instead of being treated as an expensive one-off endpoint. ([arXiv][9])

What is still missing is a standard way to **compress execution evidence into reusable planning signals**. Right now the promising ingredients exist—trace summaries, rubric criteria, sandbox feedback, execution-grounded training data—but the field has not yet unified them into a reusable interface for retrieval and planning. The best next step is likely a representation that converts traces and failures into structured objects like **“caller path,” “runtime invariant,” “violated assumption,” “observed state transition,”** and **“regression signature.”** ([arXiv][8])

## 5. Can evaluation be realistic, executable, and leakage-resistant at the same time?

I think **yes, but no single benchmark fully does this yet**. SWE-QA-Pro gets close on the QA side: it uses **long-tail repositories with executable environments**, filters out questions solvable by direct-answer baselines, and shows that agentic workflows beat direct answering by about **13 points** for Claude Sonnet 4.5. StackRepoQA adds another important ingredient by showing that much apparent repository-QA success comes from **memorization of Stack Overflow content**, with lower performance on post-cutoff questions. IDE-Bench contributes a different contamination control: **80 tasks across eight never-published repositories**, specifically created to avoid training-data contamination. ([arXiv][10])

On the executable side, FeatureBench and RepoMod-Bench add realism but in different ways. FeatureBench derives feature-level tasks from tests and dependency graphs, giving **200 tasks** and **3,825 executable environments**, and shows a huge gap between SWE-bench-style performance and true feature development, with Claude 4.5 Opus dropping from **74.4%** on SWE-bench to **11.0%** on FeatureBench. RepoMod-Bench hides all tests from agents and uses **implementation-agnostic black-box interface testing** across **21 repositories**, finding a severe scaling collapse from **91.3%** pass rate below **10K LOC** to **15.3%** above **50K LOC**. RepoReason and RACE-bench then add white-box/process-level evaluation by measuring intermediate reasoning structure, not just final success. ([arXiv][11])

A further complication is that many execution-based benchmarks still depend on test quality. STING shows that **77%** of SWE-bench Verified instances admit at least one surviving incorrect variant under the original tests; after augmenting the suites, resolved rates for the top-10 repair agents drop by **4.2%–9.0%**. So even “executable evaluation” is not enough by itself; the tests also need to be strong enough to reject semantically wrong but plausible patches. ([arXiv][12])

So the answer here is: **the ingredients now exist, but they are still fragmented**. A strong next-generation benchmark would need all of these at once: long-tail or private-like repositories, post-cutoff snapshots, executable verification, hidden or mutation-hardened tests, explicit exploration requirements, and white-box process diagnostics. The literature is clearly moving there, but it has not yet converged on a single standard. ([arXiv][10])

## What this now says about the original repo-understanding problem

After this round of research, I would restate the original subject like this:

**Repository understanding is not mainly a long-context reading problem. It is a control problem over evidence.**
A strong repository agent should:

* stop early once evidence is sufficient,
* know which artifacts actually support its answer,
* preserve repository-grounded project state across evolving specs,
* turn execution into reusable intermediate signals,
* and be judged under benchmarks that do not reward memorization or weak tests. ([arXiv][1])

## The directions that now look most promising

If I rank them by research value, I would put them in this order:

**1. Sufficiency estimation + stopping policies.**
This is closest to your original objective of higher accuracy with lower token use, and the literature has clear signals but no complete solution yet. ([arXiv][2])

**2. Repository-native project memory.**
This is the biggest conceptual expansion and probably the most important for long-horizon real work. ([arXiv][5])

**3. Utilization-aware attribution.**
The field can now observe the retrieved-versus-used gap, but not yet explain it causally enough to drive reliable control. ([arXiv][1])

**4. Execution evidence as reusable signals.**
This may produce large practical gains, especially for debugging and feature reasoning, once trace evidence is standardized. ([arXiv][8])

**5. Leakage-resistant, process-aware evaluation.**
This is foundational because it determines whether gains in the first four areas are scientifically credible. ([arXiv][10])

One caution: a lot of the most relevant work here is from **2025–2026 arXiv/OpenReview-style research**, so the direction is strong, but not fully settled yet. Still, the convergence across independent papers is already pretty clear. ([arXiv][1])

[1]: https://arxiv.org/html/2602.05892v1 "ContextBench: A Benchmark for Context Retrieval in Coding Agents"
[2]: https://arxiv.org/abs/2411.06037 "[2411.06037] Sufficient Context: A New Lens on Retrieval Augmented Generation Systems"
[3]: https://arxiv.org/abs/2508.05970 "[2508.05970] Impact-driven Context Filtering For Cross-file Code Completion"
[4]: https://arxiv.org/abs/2603.26337 "A Benchmark for Evaluating Repository-Level Code Agents ..."
[5]: https://arxiv.org/abs/2602.08316 "[2602.08316] SWE Context Bench: A Benchmark for Context Learning in Coding"
[6]: https://arxiv.org/abs/2510.01003 "[2510.01003] Improving Code Localization with Repository Memory"
[7]: https://arxiv.org/html/2512.21919v1 "SWE-RM: Execution-Free Feedback for Software Engineering Agents"
[8]: https://arxiv.org/abs/2603.22048 "Dynamic analysis enhances issue resolution"
[9]: https://arxiv.org/html/2503.07358v1 "RepoST: Scalable Repository-Level Coding Environment ..."
[10]: https://arxiv.org/abs/2603.16124 "[2603.16124] SWE-QA-Pro: A Representative Benchmark and Scalable Training Recipe for Repository-Level Code Understanding"
[11]: https://arxiv.org/abs/2602.10975 "[2602.10975] FeatureBench: Benchmarking Agentic Coding for Complex Feature Development"
[12]: https://arxiv.org/html/2604.01518v1 "Are Benchmark Tests Strong Enough? Mutation-Guided Diagnosis and Augmentation of Regression Suites"
