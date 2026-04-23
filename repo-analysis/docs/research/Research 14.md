# Further research into control theory layer, cost-aware sequential decision problem

After going deeper, I think the exact question you highlighted is **the right center of gravity**, but the literature still answers it only **indirectly**, not with one settled repository-agent paper. The closest evidence comes from combining **code-specific papers** on graph retrieval, filtering, search, and execution grounding with **adjacent retrieval-control papers** on adaptive retrieval and stopping. Most of the strongest sources here are 2025–2026 arXiv or OpenReview papers, so I would treat the direction as strong but still emerging. ([arXiv][1])

My updated conclusion is:

**The right formulation is a cost-aware sequential decision problem.**
The agent should not be optimized as “retrieve top-k chunks, then answer.” It should be optimized as a controller that repeatedly decides whether to:

* expand the repository graph,
* read raw code,
* compress/summarize evidence,
* execute tests/build steps,
* or stop and answer.

That framing is supported from several directions. Stop-RAG explicitly casts iterative RAG as a finite-horizon MDP with `continue` versus `stop` actions. The multi-hop retrieval–reasoning survey argues that retrieval, control, and stop/continue criteria should be treated as one interleaved execution procedure, not as separate modules. RepoSearch-R1 and IGPO both reinforce the same idea from the training side: multi-turn search needs explicit turn-level credit assignment rather than only final-answer supervision. ([arXiv][2])

## What the code papers imply when combined

The code-specific literature now supports four parts of this joint problem:

**1. A structured state representation**
GRACE and RANGER both argue that repository context should be represented as a **multi-view graph**, not a flat text index. GRACE uses file structure, ASTs, call graphs, class hierarchies, and data-flow graphs. RANGER builds a repository knowledge graph with hierarchical and cross-file dependencies down to variable level and uses different retrieval modes for entity queries and natural-language queries. ReCUBE adds that caller-centric dependency exploration can materially improve context utilization in generation tasks. ([arXiv][1])

**2. Evidence should be selected as a set, not a list**
CODEFILTER shows that many retrieved chunks are neutral or harmful, and RepoShapley makes the stronger claim that chunk value is often **interaction-dependent**. Its core argument is exactly aligned with your challenge: some snippets only become useful when paired with complementary evidence, while others interfere with decoding when combined. REPOFILTER adds adaptive retrieval control directly into repository completion by training the model to emit “enough context” versus “more context” signals and to mark chunks as positive, negative, or neutral. ([arXiv][3])

**3. Traversal policy matters separately from retrieval**
RANGER uses MCTS-guided graph exploration for natural-language queries. SGAgent argues that repository repair should not jump straight from localization to patching; it inserts a **suggestion** phase that incrementally retrieves context until the bug is understood. RepoSearch-R1 treats repository QA as a trained search problem and reports gains over no-retrieval, iterative retrieval, and generic agentic RL baselines. SWE-Replay adds a related test-time insight: instead of restarting exploration from scratch, agents can reuse and branch from prior trajectories at important intermediate states, improving performance while cutting cost. ([arXiv][4])

**4. Execution evidence should affect both ranking and stopping**
TDAD shows that code–test dependency graphs and weighted impact analysis can sharply reduce regressions and improve issue resolution by surfacing the tests most likely to be affected by a patch. EnvGraph pushes this further by treating repository executability as an environment-alignment problem and using execution-evidence-based attribution plus an iterative alignment loop. Its ablations are especially important: removing execution-evidence-based attribution or the iterative loop hurts more than removing either graph alone. That is strong evidence that runtime signals should not be treated as post-hoc verification only. ([arXiv][5])

## The missing control theory layer

What the code literature still lacks is a fully explicit **joint control objective**. The closest pieces come from adjacent retrieval-control work.

Stop-RAG is important because it formalizes stopping as a value-based control problem: extra retrieval has a cost, and the controller should stop when the expected value of more retrieval is lower than its cost or distraction risk. SEAKR frames adaptive retrieval around uncertainty: the system first decides **whether retrieval is needed**, then how to integrate it. CRAG adds a lightweight retrieval evaluator that estimates the quality of retrieved evidence and triggers different corrective actions depending on that quality. Chain-of-Retrieval RAG and RELOOP both support stepwise retrieval with evolving state rather than fixed one-shot retrieval. ([arXiv][2])

From the training side, IGPO is especially useful because it gives a concrete way to score intermediate steps: it defines the reward of a turn as the **marginal increase in the policy’s probability of the correct answer**. RepoSearch-R1 similarly argues that repository agents benefit from MCTS-generated trajectories and explicit process-level training. REX-RAG adds a caution: exploration is helpful, but only if paired with policy correction, because unconstrained exploration can push the agent into dead ends. ([arXiv][6])

So the deeper answer is:

**joint optimization should probably be framed as budgeted evidence acquisition with dense process rewards.**
That means optimizing not just the final answer, but the quality of intermediate evidence acquisition steps under token, tool-call, and runtime budgets. ([arXiv][6])

## What I think the best current formalization is

I would now model the repository agent as a **POMDP-like controller over a multi-view repository graph**.

The **state** should include:

* the current explored subgraph,
* the current selected evidence coalition,
* what raw code spans have already been read,
* unresolved ambiguity or competing hypotheses,
* and any execution signals seen so far, like failing tests, unresolved imports, build errors, or stack-trace anchors.
  This is an inference from GRACE, RANGER, RepoShapley, TDAD, and EnvGraph taken together. ([arXiv][1])

The **actions** should include:

* lookup a specific entity,
* expand a graph neighborhood,
* inspect a raw file/span,
* summarize or compress a subgraph,
* run a targeted test or build step,
* revise rankings using runtime evidence,
* or stop.
  That action space is directly suggested by RANGER, SGAgent, TDAD, EnvGraph, and Stop-RAG. ([arXiv][4])

The **reward** should not be terminal-only.
The strongest direction in the literature is to combine:

* final task reward,
* explicit cost penalties for tokens/tool calls/runtime,
* and dense intermediate rewards tied to evidence quality, uncertainty reduction, or information gain.
  IGPO gives one concrete template for dense turn-level rewards; Stop-RAG gives a value-based stop controller; RepoShapley and CODEFILTER suggest that intermediate reward should reflect the marginal utility of **sets of evidence**, not just isolated chunks. ([arXiv][6])

The **stop rule** should likely be based on **marginal expected value of the next action**, not on fixed hop count or prompt-based self-confidence alone.
That is the clearest lesson from Stop-RAG, CRAG, SEAKR, and the retrieval–reasoning survey. In your setting, the stop decision should probably ask: “Will one more graph expansion, raw-code read, or execution probe likely improve final evidence enough to justify its cost?” ([arXiv][2])

## The strongest unresolved research questions now

After this deeper pass, I think the highest-value unresolved questions are:

**1. How do you estimate evidence sufficiency on code tasks?**
RepoShapley and CODEFILTER show how to score evidence utility, and Stop-RAG shows how to score stop/continue for iterative retrieval, but I did not find a paper that fully solves **repo-specific sufficiency estimation** using graph state + execution evidence together. That looks open. ([arXiv][7])

**2. How do you combine coalition-aware evidence selection with graph traversal?**
Current work is split: graph papers focus on navigation, while filtering papers focus on which chunks to keep. The joint problem—constructing a minimal, complementary evidence coalition while deciding where to navigate next—still looks underdeveloped. ([arXiv][1])

**3. How should execution signals feed back into the controller?**
TDAD and EnvGraph clearly show that execution evidence is high-value, but the field has not yet standardized how failing tests, dependency failures, and runtime traces should update ranking, frontier expansion, and stop decisions inside one unified controller. ([arXiv][5])

**4. What is the right process reward for repo agents?**
IGPO gives one strong general mechanism, RepoSearch-R1 gives an MCTS-driven training recipe, and SWE-Replay shows trajectory reuse can improve test-time scaling. But for repository work specifically, the best intermediate reward signal is still open: information gain, ambiguity reduction, coalition value, test-impact reduction, or some weighted mix. ([arXiv][6])

## My best current answer

So after this deeper research, my strongest answer is:

**The problem should be treated as joint optimization of three things at once:**

* **which evidence coalition to hold,**
* **which repository-graph action to take next,**
* **and when to stop and commit.**

And the most promising design is:

**multi-view repo graph + coalition-aware evidence model + value/policy-based traversal + execution-aware reranking/stopping.**
The code-specific literature now strongly supports each piece individually, and the adjacent adaptive-retrieval literature supports the control layer needed to join them. What is still missing is a single repository-agent framework that learns all four together end-to-end. ([arXiv][1])

[1]: https://arxiv.org/abs/2509.05980 "GRACE: Graph-Guided Repository-Aware Code Completion through Hierarchical Code Fusion"
[2]: https://arxiv.org/html/2510.14337v1 "Stop-RAG: Value-Based Retrieval Control for Iterative RAG"
[3]: https://arxiv.org/abs/2508.05970 "Impact-driven Context Filtering For Cross-file Code Completion"
[4]: https://arxiv.org/abs/2509.25257 "RANGER -- Repository-Level Agent for Graph-Enhanced Retrieval"
[5]: https://arxiv.org/abs/2603.17973 "TDAD: Test-Driven Agentic Development - Reducing Code Regressions in AI Coding Agents via Graph-Based Impact Analysis"
[6]: https://arxiv.org/html/2510.14967v2 "Information Gain-based Policy Optimization: A Simple and Effective Approach for Multi-Turn Search Agents"
[7]: https://arxiv.org/abs/2601.03378 "RepoShapley: Shapley-Enhanced Context Filtering for Repository-Level Code Completion"
