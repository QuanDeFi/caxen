# Higher-Accuracy Repo Understanding With Lower Token Usage

Here is the condensed summary:

LLM coding agents usually fail on repo tasks not because the model is too weak, but because **repo context is gathered and used poorly**. The core problem is getting the **right code, in the right amount, at the right time** without wasting tokens.

The strongest pattern across recent work is:

**1. Do not try to read the whole repo.**
Instead, make the agent **navigate the repo intelligently**.

**2. The best setup is a repository intelligence layer.**
That means a persistent structural index of the codebase with things like:

* symbols and signatures
* imports and call relations
* file and module structure
* tests, runners, and build artifacts
* repo conventions and architecture notes

**3. Hybrid retrieval works best.**
Use a mix of:

* keyword / symbol / path search
* semantic search
* graph or structure-based expansion / reranking

No single retrieval method is enough on its own.

**4. Structure-aware retrieval beats flat chunk retrieval.**
For repo tasks, agents do better when they reason over:

* symbol graphs
* dependency relations
* execution paths
* build/test topology

rather than just retrieving arbitrary text chunks.

**5. Multi-resolution context is important.**
Best flow:

* first show a compact repo map or skeleton
* then zoom into relevant files / symbols
* only then load exact raw code spans for verification or editing

So: **map → skeleton → raw code**, not raw code first.

**6. Raw file reading should be selective.**
Graph / structural queries should do most of the navigation.
Full code reads should mostly be used for:

* final verification
* making edits
* handling edge cases

**7. Execution context matters a lot.**
Understanding a repo is not only about static code relationships. Agents improve when they also use:

* tests
* stack traces
* build definitions
* entrypoints
* coverage
* runtime outputs

**8. Developer-authored project context is highly valuable.**
Things like:

* project rules
* conventions
* architectural notes
* examples
* workflow guidance

often explain how the repo is supposed to be used and reduce mistakes.

**9. Final answers should be evidence-backed.**
Agents should not answer confidently from summaries alone.
Summaries are for navigation; final claims should be grounded in exact file / symbol / code-span evidence.

**10. The practical takeaway:**
The best path to higher repo-task accuracy with lower token use is:

* persistent repo index
* hybrid retrieval
* hierarchical localization
* just-in-time code loading
* execution/build/test grounding
* persistent project memory

So the overall conclusion is:

**Higher accuracy comes less from feeding more raw code into the model, and more from giving the model a better retrieval and navigation system for the repo.**

[1]: https://arxiv.org/html/2602.05892v3 "ContextBench: A Benchmark for Context Retrieval in Coding Agents"
[2]: https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents "Effective context engineering for AI agents \ Anthropic"
[3]: https://sourcegraph.com/blog/anatomy-of-a-coding-assistant "The anatomy of an AI coding assistant | Sourcegraph"
[4]: https://arxiv.org/html/2303.12570v3 "RepoCoder: Repository-Level Code Completion Through Iterative Retrieval and Generation"
[5]: https://arxiv.org/html/2603.27277v1 "Codebase-Memory: Tree-Sitter-Based Knowledge Graphs for LLM Code Exploration via MCP"
[6]: https://arxiv.org/html/2512.18925v2 "Beyond the Prompt: An Empirical Study of Cursor Rules"
[7]: https://aider.chat/docs/repomap.html "Repository map | aider"
[8]: https://www.swebench.com/verified.html "SWE-bench Verified"


--------------------------------------------------------

# Follow-Up Research Based On Further Academic Sources

The stronger core should come from **benchmarks and method papers** on repository-level QA, retrieval, planning, and execution-grounded evaluation. ([arXiv][1])

* **ContextBench (2026)**: process-oriented benchmark for **context retrieval** in coding agents; 1,136 issue-resolution tasks from 66 repositories, with gold contexts, and it explicitly measures recall, precision, efficiency, and the gap between explored and utilized context. ([arXiv][1])
* **CoReQA (2025)**: repository-level QA benchmark built from GitHub issues/comments over **176 repositories** and **4 languages**. ([arXiv][2])
* **CodeRepoQA (2024)**: large-scale multi-turn software-engineering QA benchmark with **585,687 entries** from **30 repositories** across **5 languages**. ([arXiv][3])
* **SWE-QA (2025)**: **576** repository-level QA pairs designed for cross-file reasoning and multi-hop dependency analysis. ([arXiv][4])
* **SWE-QA-Pro (2026)**: long-tail, executable repo benchmark designed to reduce memorization effects; it reports that agentic workflows materially outperform direct answering. ([arXiv][5])
* **Beyond Code Snippets / StackRepoQA (2026)**: **1,318** real developer questions mapped to **134 Java repositories**; it shows moderate baseline QA accuracy, clear memorization effects, and that **graph-based retrieval** gives the largest gains, though the ceiling is still limited. ([arXiv][6])
* **RepoCoder (2023)**: iterative retrieval-generation for repo-level completion; improves the in-file baseline by **more than 10%** and introduces RepoEval. ([arXiv][7])
* **RepoFusion (2023)**: shows that training models to use repository context improves context-aware completion and can outperform much larger models. ([arXiv][8])
* **CodePlan (2024/FSE)**: frames repository-level coding as a **planning** problem using dependency analysis and change-impact analysis; in its evaluation, CodePlan gets **5/7** repositories through validity checks while baselines get none. 
* **GraphCoder (2023)**: replaces flat sequence retrieval with a **code context graph** over control flow and data/control dependence, improving exact match by **5.93%** over RepoCoder. 
* **CodexGraph (2024)**: argues similarity retrieval has low recall on complex tasks and proposes graph-database access to code repositories for more precise navigation. ([arXiv][9])
* **CodeRAG (2025)**: requirement graph + code graph retrieval for repo-level generation, explicitly aimed at retrieving “supportive code” across the repository. ([arXiv][10])
* **CGM / Code Graph Model (2025)**: integrates repository graph structure directly into the model’s reasoning path and pairs it with graph-RAG for repo tasks. 
* **RepoST (2025)**: shows that **execution-grounded** sandbox environments matter for training and evaluation; training with RepoST improves Pass@1 on both HumanEval and RepoEval. ([OpenReview][11])

The academic picture now looks more consistent than before:

**First**, repository-level understanding is clearly a **distinct problem** from snippet-level code QA or completion. The newer QA benchmarks were created precisely because single-file or snippet benchmarks miss cross-file dependencies, architecture questions, and multi-hop reasoning over real repositories. ([arXiv][2])

**Second**, the literature increasingly points to **retrieval and navigation** as the bottleneck. ContextBench is especially important here because it evaluates retrieval quality directly, instead of only end-task success, and it finds that better agent scaffolding alone does not solve the context problem. StackRepoQA also shows that structured graph retrieval helps, but only modestly, which suggests repo understanding still needs better retrieval, not just better prompting. ([arXiv][1])

**Third**, the best-supported design move is **structure-aware retrieval**. GraphCoder, CodexGraph, CodeRAG, and CGM all converge on the same idea: flat chunk retrieval is too weak for repository-scale tasks, and code should be represented through dependencies, graph structure, or graph-queryable relations. 

**Fourth**, there are really two different academic strategies for better repo understanding. One is **better inference-time retrieval** like RepoCoder, GraphCoder, CodexGraph, and CodeRAG. The other is **training the model to use repository context better**, as in RepoFusion and the training recipe in SWE-QA-Pro. The evidence suggests both matter; retrieval helps at inference, but some gains also require training models to digest repository context more effectively. ([arXiv][7])

**Fifth**, for actual code-editing tasks, static retrieval is not enough. CodePlan shows that repository edits should often be modeled as **multi-step planning over dependency propagation**, not as a one-shot generation problem. RepoST reinforces that **execution feedback** and runnable environments are critical for both evaluation and training. 

So the more academic version of the conclusion is:

**The strongest evidence does not support “just give the LLM more code.”**
It supports building systems that combine:

* **repo-specific benchmarks**
* **structure-aware retrieval**
* **graph or dependency representations**
* **planning / change-propagation**
* **execution-grounded evaluation**
* and, increasingly, **training procedures that teach models to use repo context well**. ([arXiv][1])

One caveat: several of the strongest recent sources here, especially from **2025–2026**, are still **arXiv or OpenReview papers**, so they are academic sources, but not all are fully matured archival consensus yet. The direction is still quite consistent across them. ([arXiv][1])

[1]: https://arxiv.org/abs/2602.05892 "ContextBench: A Benchmark for Context Retrieval in Coding Agents"
[2]: https://arxiv.org/html/2501.03447v1 "CoReQA: Uncovering Potentials of Language Models in Code Repository Question Answering"
[3]: https://arxiv.org/pdf/2412.14764 "CodeRepoQA: A Large-scale Benchmark for Software Engineering Question Answering"
[4]: https://arxiv.org/pdf/2509.14635 "SWE-QA: Can Language Models Answer Repository-level Code Questions?"
[5]: https://arxiv.org/abs/2603.16124 "[2603.16124] SWE-QA-Pro: A Representative Benchmark and Scalable Training Recipe for Repository-Level Code Understanding"
[6]: https://arxiv.org/pdf/2603.26567 "Beyond Code Snippets: Benchmarking LLMs on Repository-Level Question Answering"
[7]: https://arxiv.org/abs/2303.12570 "RepoCoder: Repository-Level Code Completion Through Iterative Retrieval and Generation"
[8]: https://arxiv.org/abs/2306.10998 "[2306.10998] RepoFusion: Training Code Models to Understand Your Repository"
[9]: https://arxiv.org/abs/2408.03910 "[2408.03910] CodexGraph: Bridging Large Language Models and Code Repositories via Code Graph Databases"
[10]: https://arxiv.org/html/2504.10046v1 "CodeRAG: Supportive Code Retrieval on Bigraph for Real-World Code Generation"
[11]: https://openreview.net/forum?id=2txrMBpw3q "RepoST: Scalable Repository-Level Coding Environment Construction with Sandbox Testing | OpenReview"

---------------------------------------------------------


# Academic-source-only design memo: higher-accuracy repository understanding for LLM coding agents

## 1. Problem definition

Repository-level code understanding is a different problem from snippet-level code QA or single-file completion. The harder setting requires the model or agent to reason across multiple files, long-range dependencies, software architecture, and execution contexts such as tests and build behavior. This is exactly why newer benchmarks moved beyond snippet tasks: RepoBench targets repository-level retrieval and completion, CoReQA targets repository QA across 176 repositories, CodeRepoQA scales repository QA to 585,687 multi-turn entries from 30 repositories, SWE-QA focuses on cross-file and multi-hop repository questions, SWE-QA-Pro targets long-tail repositories with executable environments, and SWE-bench turns real GitHub issues into code-editing tasks over full repositories. ([arXiv][1])

The core bottleneck is not simply model size. The recent academic evidence points to a context problem: agents often retrieve too much irrelevant code, miss the decisive dependencies, or fail to convert explored context into utilized evidence. ContextBench is especially important here because it evaluates retrieval itself, not just final issue resolution, and finds only marginal gains from more sophisticated scaffolding, a recall-over-precision tendency, and a persistent gap between explored and utilized context. ([arXiv][2])

A second part of the problem is token efficiency. Several papers now show that blindly concatenating large repository context is either impossible because of context-window limits or actively harmful because irrelevant code degrades generation. Hierarchical Context Pruning reports that whole-repository concatenation can exceed context limits and hurt performance, while GraphCoder explicitly argues that adding too much irrelevant repository information confuses the model and degrades completion quality. ([arXiv][3])

A third part is evaluation leakage and superficial success. StackRepoQA shows that high scores can come from reproducing memorized Stack Overflow answers rather than genuine repository reasoning, and SWE-QA-Pro was built specifically to reduce this problem by using long-tail repositories and filtering out questions that direct-answer baselines can solve without real codebase exploration. ([arXiv][4])

## 2. Literature map

### 2.1 Benchmark line: what the field is trying to measure

There are now at least four benchmark families. First are **retrieval/completion** benchmarks such as RepoBench and RepoEval, which study whether systems can find cross-file evidence and use it for completion. Second are **repository QA** benchmarks such as CoReQA, CodeRepoQA, SWE-QA, SWE-QA-Pro, and StackRepoQA, which focus on answering architecture, dependency, and intent questions over real repositories. Third are **repository-scale generation/editing** benchmarks such as RepoExec, EvoCodeBench, and SWE-bench, which test whether the model can generate or edit code that works in a real repo. Fourth are **process benchmarks** such as ContextBench and SWE-ContextBench, which measure intermediate behavior like retrieval precision/recall, context reuse, runtime, and token cost instead of only end-task success. ([arXiv][1])

### 2.2 Method line: how papers try to improve repo understanding

One line of work improves **inference-time retrieval**. RepoCoder uses iterative retrieval-generation, where model output from an early pass becomes a better query for a later pass, and reports over 10% gains over the in-file baseline. DraCo replaces simple import or text-similarity retrieval with extended dataflow analysis over a repository context graph and improves exact match and identifier F1. Repoformer argues retrieval should be selective, not automatic on every request, and reports up to 70% online inference speedup without hurting performance. 

A second line improves **structure awareness**. GraphCoder uses a statement-level code context graph with control-flow and data/control-dependence edges, improving exact match by 5.93% over RepoCoder. CodexGraph turns repository search into iterative graph querying over a code graph database. InlineCoder reframes repository-level generation by inlining the target into its call graph and retrieving both upstream usage and downstream dependencies. LingmaAgent builds a top-down repository knowledge graph and combines it with Monte Carlo tree search for repository exploration. 

A third line treats repository work as **planning or deep exploration**, not one-shot prompting. CodePlan models repository editing as a planning problem using dependency analysis, change may-impact analysis, and adaptive planning. DeepRepoQA treats repository QA as structured search with MCTS over an action space rather than flat retrieval alone. LingmaAgent similarly uses summarize-analyze-plan loops over a repository graph. ([arXiv][5])

A fourth line improves **training**, not just retrieval at inference time. RepoFusion shows that training models to incorporate repository context materially improves completion, to the point that a much smaller model can outperform or match far larger baselines on single-line completion. SWE-QA-Pro pairs its benchmark with a two-stage training recipe, SFT plus RLAIF, and reports that a trained 8B open model can surpass GPT-4o on that benchmark. RepoST constructs repository-level executable environments and shows that training with execution feedback improves Pass@1 on both HumanEval and RepoEval. ([arXiv][6])

A fifth line focuses on **context control and compression**. Hierarchical Context Pruning preserves dependency topology while pruning implementation detail. Impact-driven Context Filtering finds that only a small subset of retrieved chunks help completion and that some retrieved chunks are actively harmful, then trains a filter to keep useful evidence while shrinking prompts. SWE-ContextBench extends this idea from single tasks to experience reuse across related tasks and shows that correctly selected summarized context can raise accuracy while reducing runtime and token cost. ([arXiv][3])

## 3. Architecture implications

The literature most strongly supports a **multi-view repository intelligence layer** in front of the model. That layer should not be a flat embedding index alone. It should include at least: a file/module dependency graph, symbol and signature inventory, call graph, dataflow or dependence graph where feasible, and build/test metadata. That recommendation follows directly from GraphCoder’s code context graph, DraCo’s repository context graph, CodexGraph’s graph database interface, InlineCoder’s call-graph inlining, LingmaAgent’s repository knowledge graph, and CodePlan’s dependency and impact analyses. 

The retrieval layer should be **hybrid and staged**. A good design is not “semantic search only” or “graph queries only.” The papers point toward a pipeline where a first stage proposes candidates using cheap lexical or similarity cues, and a second stage expands or reranks them using structure: call edges, dependence edges, file topology, or usage contexts. RepoCoder, DraCo, GraphCoder, CodexGraph, InlineCoder, and StackRepoQA all point in that direction: structural signals improve performance, but they are most useful when layered on top of baseline retrieval rather than used as the only mechanism. 

The prompt-building layer should be **dependency-preserving but aggressively selective**. The safest academic conclusion is not “more context is always better,” but “keep the dependencies, discard the noise.” HCP shows that pruning function implementations from dependent files can preserve accuracy while shrinking inputs; Repoformer shows retrieval itself should be conditional; CodeFilter shows many retrieved chunks are neutral or harmful; SWE-ContextBench shows summarized prior context helps only when selected correctly. ([arXiv][3])

For editing tasks, the control policy should be **plan first, edit second**. CodePlan shows repository-level change is better framed as a multi-step plan over dependencies and impacts, not a single generation call. LingmaAgent and DeepRepoQA reinforce the same point: repository reasoning benefits from explicit exploration policies, tree search, and summarize-analyze-plan loops. ([arXiv][5])

For generation and issue resolution, **execution feedback is not optional**. SWE-bench was designed around real issue resolution in executable repositories; RepoExec emphasizes executability, functional correctness, and dependency use; RepoST shows that scalable sandboxed execution environments improve both training and evaluation; Gistify evaluates whether a model can reproduce repository functionality through runtime behavior. A repository agent that cannot compile, run tests, inspect failures, and iterate will miss a major part of the task. ([arXiv][7])

If you control model training, the literature supports training on **repository-context usage and tool behavior**, not only on generic code tokens. RepoFusion, RepoST, and SWE-QA-Pro all report gains from training regimes that specifically teach the model to consume repository context, exploit execution feedback, or use agentic tool interaction more effectively. ([arXiv][6])

## 4. Evaluation rubric grounded only in papers

A strong evaluation should score the system on five separate layers.

**A. Retrieval quality.**
Measure context recall, precision, and efficiency on ContextBench, and retrieval success on RepoBench-R. Also measure the explored-versus-utilized gap: how much retrieved context actually appears in the final reasoning or patch. ([arXiv][2])

**B. Repository QA quality.**
Evaluate on CoReQA, CodeRepoQA, SWE-QA, SWE-QA-Pro, and StackRepoQA. Report not just a single score, but splits by question type: intent understanding, cross-file reasoning, multi-hop dependency analysis, and long-tail/post-cutoff questions. The key reason is that these papers show repository QA failure often comes from either poor navigation or memorization leakage. ([arXiv][8])

**C. Completion and generation quality.**
For completion-style tasks, use RepoBench-C/P, RepoEval-style tasks, and report exact match, identifier-sensitive metrics, and edit similarity where the benchmark supports them. For generation-style tasks, use RepoExec and EvoCodeBench and report Pass@1, executability, functional correctness, and dependency-use metrics such as DIR where applicable. ([arXiv][1])

**D. Full repository editing and issue resolution.**
Use SWE-bench-class tasks for end-to-end repository edits and keep build/test validity as the main success criterion. CodePlan is a useful complement here because it stresses multi-file validity checks, not just local patch plausibility. ([arXiv][7])

**E. Efficiency and robustness.**
Track tokens per solved task, retrieval latency, runtime, and tool calls. Also measure sensitivity to irrelevant context by comparing unfiltered retrieval, selective retrieval, and filtered retrieval. Repoformer, CodeFilter, ContextBench, and SWE-ContextBench all show that efficiency and robustness should be first-class metrics, not afterthoughts. ([arXiv][9])

## 5. Bottom line

The academic literature does **not** support the strategy of letting an LLM read as much of the repository as possible. The more consistent result is that repository understanding improves when systems do four things well: build structured repository representations, retrieve selectively with dependency awareness, plan or explore before answering or editing, and close the loop with execution-based verification. RepoCoder, GraphCoder, DraCo, CodexGraph, CodePlan, LingmaAgent, Repoformer, RepoST, SWE-QA-Pro, and ContextBench all point in that same direction from different angles. 

A good research agenda from here is to treat repo understanding as a **systems problem with measurable subcomponents**: retrieval quality, compression quality, exploration quality, execution grounding, and final task success. That framing is the one most aligned with the benchmark and method papers now appearing in 2024–2026. ([arXiv][2])


[1]: https://arxiv.org/abs/2306.03091 "[2306.03091] RepoBench: Benchmarking Repository-Level Code Auto-Completion Systems"
[2]: https://arxiv.org/abs/2406.18294 "[2406.18294] Hierarchical Context Pruning: Optimizing Real-World Code Completion with Repository-Level Pretrained Code LLMs"
[3]: https://arxiv.org/abs/2603.26567 "Beyond Code Snippets: Benchmarking LLMs on Repository-Level Question Answering"
[4]: https://arxiv.org/abs/2309.12499 "[2309.12499] CodePlan: Repository-level Coding using LLMs and Planning"
[5]: https://arxiv.org/abs/2306.10998 "[2306.10998] RepoFusion: Training Code Models to Understand Your Repository"
[6]: https://arxiv.org/abs/2310.06770 "[2310.06770] SWE-bench: Can Language Models Resolve Real-World GitHub Issues?"
[7]: https://arxiv.org/abs/2602.05892 "[2602.05892] ContextBench: A Benchmark for Context Retrieval in Coding Agents"
[8]: https://arxiv.org/abs/2501.03447 "[2501.03447] CoReQA: Uncovering Potentials of Language Models in Code Repository Question Answering"
[9]: https://arxiv.org/abs/2403.10059 "[2403.10059] Repoformer: Selective Retrieval for Repository-Level Code Completion"

---------------------------------------------------------

# Subjects That Deserve Further Research

Yes. My view is that **six subjects stand out** as especially worth deeper research.

**1. Context retrieval quality, not just end-task success**
This is the most important one. ContextBench shows that current agents still have a big gap between the code they **explore** and the code they **actually use**, and that better scaffolding alone only gives marginal retrieval gains. That suggests the field still does not know how to retrieve the *minimal sufficient* evidence set for a repo task. ([arXiv][1])

**2. Context utilization and evidence-backed reasoning**
Related but distinct: even when agents retrieve relevant files, they often do not convert that context into grounded answers or edits. I think this deserves its own line of work: not only “did the system fetch the right files?” but “did the final answer clearly depend on the retrieved evidence?” ContextBench makes that gap visible, and it is one of the clearest signs that repository reasoning is still brittle. ([arXiv][1])

**3. Long-horizon project memory and specification tracking**
This looks underexplored and very important. SWE-ContextBench shows that correctly selected summarized prior experience can improve accuracy and reduce cost, while bad or unfiltered reuse can hurt. SLUMP goes further and shows that when the specification emerges gradually over a long session, agents lose faithfulness unless an external project-state layer helps them track commitments. That is a strong signal that coding agents need better persistent project memory, not just better one-shot retrieval. ([arXiv][2])

**4. Anti-memorization benchmarks for true repo understanding**
This area deserves a lot more work because benchmark quality determines whether the field is fooling itself. SWE-QA-Pro was built around long-tail repositories and explicitly filters out questions that direct-answer baselines can solve without real exploration. StackRepoQA also shows that moderate repository-QA performance can be inflated by memorization, and that performance drops on post-cutoff questions. So the benchmark problem is not solved yet. ([arXiv][3])

**5. Execution-aware and feature-level repository understanding**
A lot of current work still over-focuses on static code structure. But real repo work often means understanding how a feature behaves through tests, dependency paths, and execution. FeatureBench is a good sign here: it uses an execution-based protocol and derives feature-level tasks by tracing from tests along dependency graphs. I think this whole area—feature-level reasoning, execution-grounded retrieval, and runtime-aware repo understanding—deserves much more research. ([OpenReview][4])

**6. Repository understanding from documentation and other non-code artifacts**
This is underrated. SWD-Bench argues that documentation quality should be evaluated through functionality QA and feature-driven development, not just by prompting the model to “judge the docs.” That points to a broader research gap: agents need to integrate code, docs, PR history, tests, and build files into one coherent repo model. Right now, most work still treats code as the main source of truth. ([arXiv][5])

Two more areas look very promising, but I would place them just below the top six:

**7. Training models specifically for repository reasoning**
SWE-QA-Pro is important because it suggests that better training for tool use and repository exploration can materially improve small models, rather than relying only on stronger base models. I think this deserves more work, but only after the field improves evaluation and retrieval diagnostics; otherwise it is too easy to train toward the wrong target. ([arXiv][3])

**8. Security-aware repository understanding**
SecRepoBench shows that even strong models still struggle to generate code that is both correct and secure in real repositories, and that repository context plus agent workflows matter here. This is a very important applied direction, especially for C/C++ and infra-heavy codebases, though I see it more as a domain-critical extension of the broader repo-understanding problem. ([arXiv][6])

If I had to prioritize the field, I would rank them like this:

1. retrieval quality + utilization
2. long-horizon project memory / specification tracking
3. benchmark design against memorization
4. execution-aware feature-level reasoning
5. training for repository exploration
6. multi-artifact understanding across code, docs, and tests
7. security-aware repo reasoning

My strongest opinion after this research is: **the biggest missing piece is not another clever graph index by itself. It is a full theory of how an agent should accumulate, compress, reuse, and verify repository knowledge over time.** ContextBench, SWE-ContextBench, SWE-QA-Pro, and SLUMP all point in that direction. ([arXiv][1])


[1]: https://arxiv.org/abs/2602.05892 "ContextBench: A Benchmark for Context Retrieval in Coding Agents"
[2]: https://arxiv.org/abs/2602.08316 "SWE Context Bench: A Benchmark for Context Learning in Coding"
[3]: https://arxiv.org/abs/2603.16124 "SWE-QA-Pro: A Representative Benchmark and Scalable Training Recipe for Repository-Level Code Understanding"
[4]: https://openreview.net/forum?id=41xrZ3uGuI "FeatureBench: Benchmarking Agentic Coding for Complex Feature Development | OpenReview"
[5]: https://arxiv.org/html/2604.06793v1 "Evaluating Repository-level Software Documentation via Question Answering and Feature-Driven Development"
[6]: https://arxiv.org/html/2504.21205v3 "SecRepoBench: Benchmarking Code Agents for Secure Code Completion in Real-World Repositories"
