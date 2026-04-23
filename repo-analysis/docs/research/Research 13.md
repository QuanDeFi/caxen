# Further Reserch into Sufficiency estimation, project memory, Utilization-aware attribution, Execution evidence, process-aware evaluation

**these five directions are not separate side quests. They fit together into one control loop for repository agents.**
A strong system would: retrieve until evidence is sufficient, attribute which evidence actually mattered, preserve a repository-native project state over time, turn execution into reusable signals instead of a final yes/no check, and be evaluated under benchmarks that make shortcutting hard. The newer academic work increasingly supports that as the right systems framing. ([arXiv][1])

## 1. Sufficiency estimation + stopping policies

This now looks like the **closest direct path** to your original goal of higher repo-task accuracy with lower token use. The key shift is from “retrieve what seems relevant” to “retrieve until the current evidence set is probably enough.” The general RAG paper *Sufficient Context* formalizes this distinction and shows that many failures come from poor behavior when context is insufficient, not just from poor generation when context is sufficient; its selective-generation method improves the fraction of correct answers among responses by 2–10%. In code, Repoformer shows that retrieval should be **conditional**, not automatic, and reports up to **70% inference speedup** without hurting repository-level completion performance. ([arXiv][2])

The strongest supporting evidence comes from pruning and filtering work. HCP shows that preserving dependency topology while removing low-value implementation detail can reduce prompt size from **over 50,000 tokens to around 8,000** while improving completion quality. SWE-Pruner reports **23–54% token reduction** on agent tasks such as SWE-Bench Verified and up to **14.84× compression** on single-turn code tasks with minimal performance loss. CODEFILTER then adds a more important idea: retrieved context should be scored by **impact**, not just relevance, because some retrieved chunks are actually harmful. ([arXiv][3])

What still looks missing is a true **stop policy**. The literature gives us pieces of it—selective retrieval, pruning, impact labels, and confidence-aware context inlining—but not yet a repository-native estimator that says: “the marginal value of another search step is now below its token and latency cost.” InlineCoder is especially interesting here because it uses an initial draft “anchor” plus **perplexity-based confidence estimation** to decide how much caller/callee context to inline, which is close in spirit to sufficiency-aware stopping even if it is not a full stop policy yet. ([arXiv][4])

My current conclusion on this topic is: **the next important research object is not a better retriever, but a marginal-utility estimator for evidence.** That would let the agent stop early with a defensible confidence bound instead of continuing to search out of habit. ([arXiv][1])

## 2. Repository-native project memory

This looks like the **largest conceptual expansion** beyond your original framing. SWE-ContextBench shows that correctly selected summarized prior context improves resolution accuracy and substantially reduces runtime and token cost, while wrongly selected or unfiltered context can hurt. The benchmark is explicitly about experience reuse across related repository tasks, not one-shot issue solving. ([arXiv][5])

SLUMP then shows that long-horizon coding has its own failure mode: when the specification emerges gradually, implementation faithfulness drops even when the platform stays the same. Its ProjectGuard layer recovers **90% of the faithfulness gap** on Claude Code, increases fully faithful components from **118 to 181**, and reduces severe failures from **72 to 49**. That is unusually strong evidence that specification tracking should be treated as a first-class systems component rather than a side effect of retrieval. ([arXiv][6])

The memory papers increasingly point toward **repository-native representations**, not generic chat summaries. CodeMEM maintains AST-guided code-context memory and code-session memory, improving instruction following by **12.2%** on the current turn and **11.5%** at the session level while reducing interaction rounds by **2–3**. Improving Code Localization with Repository Memory uses recent commits, linked issues, and functionality summaries from actively evolving areas of the codebase, and reports gains on both SWE-bench Verified and SWE-bench Live. MemGovern converts GitHub repair history into **135K governed experience cards** and improves SWE-bench Verified resolution by **4.65%**. SWE-Exp shows that removing comprehension experiences, modification experiences, or experience extraction all hurts Pass@1. Subtask-level memory adds another strong result: **+4.7 percentage points Pass@1 on average** over a vanilla agent, with bigger gains on harder tasks. ([arXiv][7])

LoCoEval is also important because it shows current memory systems are still not really adapted to repository-oriented long-horizon conversations. It builds conversations averaging **50 turns** with contexts up to **64K–256K tokens**, and finds that existing approaches—especially generic memory systems—still struggle; a **unified memory** that integrates conversational and repository information performs better. ([arXiv][8])

My updated conclusion here is: **the right memory object is not “conversation history.”** It is a structured repository state containing design commitments, commit-history abstractions, module/functionality summaries, regression history, and spec deltas. The open problem is that the field still lacks a standard schema for this memory and good policies for updating and invalidating it as the repo evolves. ([arXiv][5])

## 3. Utilization-aware attribution

This still looks underdeveloped, but it is becoming measurable. ContextBench matters because it explicitly distinguishes **retrieved/explored** context from **utilized** context and shows a persistent gap between the two. That alone changes the research target: retrieval quality is not enough if the final answer or patch does not actually depend on the retrieved evidence. ([arXiv][1])

The strongest progress so far is in **proxy attribution**. CODEFILTER labels chunks by observed impact on completion, and RepoShapley argues that chunk utility is often interaction-dependent, not independent, so filtering should consider coalition effects rather than one chunk at a time. RACE-bench adds a complementary white-box layer by evaluating intermediate reasoning quality on feature-addition tasks; it finds that “apply-success but test-fail” cases show **35.7% lower reasoning recall** and **94.1% higher over-prediction** than successful cases. RepoReason adds dynamic slicing metrics—reading load, simulation depth, and integration width—and reports a prevalent **aggregation deficit**, with integration width as the main bottleneck. ([arXiv][9])

So the field can now say **that** retrieved evidence was underused or misused, and it has some ways to score chunk-level helpfulness or reasoning-step failures. What it still cannot do well is produce a clean **causal support graph** from artifact to belief update to final patch correctness. That is the missing bridge if you want reliable control policies. ([arXiv][1])

My conclusion here is that attribution research should move toward outputs like: “these 3 symbols, this failing trace region, and this prior memory item were the decisive supports for the patch.” Right now, the literature is good at exposing the gap and weak at closing it. ([arXiv][1])

## 4. Execution evidence as reusable signals

This direction looks more promising than before. The strongest evidence is that **raw pass/fail is too coarse**, but structured execution evidence is already helping. DAIRA treats execution traces as first-class evidence and then converts raw logs into a structured execution workflow report with an **ASCII execution tree** and function-role analysis. On SWE-bench Verified it reports **79.4%** resolution with Gemini 3 Flash Preview while reducing inference cost by about **10%** and input tokens by about **25%**. ([arXiv][10])

EnvGraph supports the same direction from repository generation rather than issue resolution. It models repository executability as an **environment alignment** problem, uses execution-evidence-based attribution, and improves functional correctness by **5.72–5.87 percentage points** over the strongest non-EnvGraph baseline. SWE-Next adds the systems angle: it mines real merged pull requests and keeps only self-verifying commit pairs with strict test improvement and no regressions, producing **2,308 instances** from **3,971 repositories** and **102,582 candidate commit pairs** while reusing environments through repo-quarter profiles. ([arXiv][11])

FeatureBench shows why this matters. It derives feature-level tasks by tracing from unit tests along dependency graphs, builds **200 tasks** and **3,825 executable environments**, and finds that Claude 4.5 Opus drops from **74.4%** on SWE-bench to **11.0%** on FeatureBench. RepoReason reinforces that execution-grounded diagnosis can expose where reasoning breaks down by using the environment as a semantic oracle and dynamic slicing to measure the true causal reasoning surface. ([arXiv][12])

My current conclusion is: **execution should not enter the system only at the final test stage.** It should be compressed into reusable intermediate signals such as caller paths, violated assumptions, runtime state transitions, key-function roles, and regression signatures, then fed back into retrieval, planning, and memory. DAIRA and EnvGraph are the clearest early examples of that pattern. ([arXiv][10])

## 5. Leakage-resistant, process-aware evaluation

This now looks foundational. SWE-QA-Pro explicitly targets **long-tail repositories with executable environments**, filters out questions that strong direct-answer baselines can solve without exploration, and reports about a **13-point** gap between agentic workflows and direct answering for Claude Sonnet 4.5. IDE-Bench takes a different approach to contamination control by creating **80 tasks across eight never-published repositories** in containerized environments that mimic real IDE agent workflows. ([arXiv][13])

The contamination problem is real enough that benchmark results can be misleading without those controls. *The SWE-Bench Illusion* shows that state-of-the-art models can identify buggy file paths from issue descriptions alone with up to **76%** accuracy on SWE-Bench Verified but only **53%** on repositories outside SWE-Bench, which strongly suggests memorization or contamination effects. RepoMod-Bench addresses a different shortcut by hiding all tests from the agent and using implementation-agnostic black-box testing; under that setup, pass rates collapse from **91.3%** on repositories under **10K LOC** to **15.3%** above **50K LOC**. ([arXiv][14])

Even executable evaluation is not enough if the tests are weak. STING strengthens SWE-bench suites via mutation-guided augmentation and finds that **77%** of Verified instances contain at least one surviving incorrect variant; after strengthening the tests, top-10 repair agents lose **4.2%–9.0%** resolved rate. RACE-bench and RepoReason then add the missing white-box/process-aware layer by measuring intermediate reasoning quality rather than only final pass/fail. ([arXiv][15])

So the answer here is not one perfect benchmark yet. It is a bundle of requirements: **long-tail or unpublished repositories, executable environments, hidden or strengthened tests, explicit exploration requirements, and white-box reasoning diagnostics.** The literature is converging on that bundle, but it has not standardized it yet. ([arXiv][13])

## What I think now

The deeper research changes the original framing in a useful way:

**repository understanding is not mainly a long-context reading problem. It is a control problem over evidence, state, and verification.**
The strongest next-generation system would combine:

* a **sufficiency estimator** with explicit stopping,
* **artifact-level attribution** of what actually mattered,
* **repository-native project memory** rather than generic summaries,
* **execution-derived intermediate signals** rather than only final tests,
* and **evaluation protocols** designed to resist memorization and weak-test inflation. ([arXiv][2])

If I had to rank what looks most promising to build next, I would still put **sufficiency estimation** first and **repository-native memory** second. Sufficiency is the most direct lever on token cost and latency. Memory is the biggest unlock for long-horizon real work. Attribution and execution-signal reuse are the mechanisms that make those two more reliable, and stronger evaluation is what keeps the whole research program honest. ([arXiv][16])

One caution: a lot of the most relevant evidence here is from **2025–2026 arXiv/OpenReview-style work**, so the direction is clear, but the field is still moving fast and some results are not yet “settled” in the archival sense. ([arXiv][1])

[1]: https://arxiv.org/abs/2602.05892 "[2602.05892] ContextBench: A Benchmark for Context Retrieval in Coding Agents"
[2]: https://arxiv.org/abs/2411.06037 "[2411.06037] Sufficient Context: A New Lens on Retrieval Augmented Generation Systems"
[3]: https://arxiv.org/html/2406.18294v2 "Hierarchical Context Pruning: Optimizing Real-World Code Completion with Repository-Level Pretrained Code LLMs"
[4]: https://arxiv.org/abs/2601.00376 "[2601.00376] In Line with Context: Repository-Level Code Generation via Context Inlining"
[5]: https://arxiv.org/abs/2602.08316 "SWE Context Bench: A Benchmark for Context Learning in Coding"
[6]: https://arxiv.org/abs/2603.17104 "When the Specification Emerges: Benchmarking Faithfulness Loss in Long-Horizon Coding Agents"
[7]: https://arxiv.org/abs/2601.02868 "[2601.02868] CodeMEM: AST-Guided Adaptive Memory for Repository-Level Iterative Code Generation"
[8]: https://arxiv.org/abs/2603.06358 "A Scalable Benchmark for Repository-Oriented Long-Horizon Conversational Context Management"
[9]: https://arxiv.org/abs/2508.05970 "[2508.05970] Impact-driven Context Filtering For Cross-file Code Completion"
[10]: https://arxiv.org/html/2603.22048v3 "DAIRA: Dynamic Analysis–enhanced Issue Resolution Agent"
[11]: https://arxiv.org/abs/2604.03622 "[2604.03622] Toward Executable Repository-Level Code Generation via Environment Alignment"
[12]: https://arxiv.org/abs/2602.10975 "[2602.10975] FeatureBench: Benchmarking Agentic Coding for Complex Feature Development"
[13]: https://arxiv.org/abs/2603.16124 "SWE-QA-Pro: A Representative Benchmark and Scalable Training Recipe for Repository-Level Code Understanding"
[14]: https://arxiv.org/abs/2506.12286 "[2506.12286] The SWE-Bench Illusion: When State-of-the-Art LLMs Remember Instead of Reason"
[15]: https://arxiv.org/abs/2604.01518 "[2604.01518] Are Benchmark Tests Strong Enough? Mutation-Guided Diagnosis and Augmentation of Regression Suites"
[16]: https://arxiv.org/abs/2403.10059 "[2403.10059] Repoformer: Selective Retrieval for Repository-Level Code Completion"
