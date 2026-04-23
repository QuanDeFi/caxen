# Research Source Summaries

Companion to `Research Sources.md`. Numbering matches the source list within each section.

These summaries are written from the linked source bodies. For papers, they are meant to capture the paper's problem, method, and main empirical or conceptual takeaway rather than just the citation metadata.

## Academic Sources

1. **The Program Dependence Graph and Its Use in Optimization**  
   Type: Research paper.  
   Labels: `program-dependence-graph`, `compiler-optimization`, `static-analysis`, `dependence-analysis`.  
   Summary: This classic paper defines the program dependence graph as a representation that makes both data and control dependences explicit, then shows how that unified structure supports more efficient compiler optimizations and incremental updates after transformations such as branch deletion or loop unrolling.

2. **A review of software change impact analysis**  
   Type: Survey paper.  
   Labels: `change-impact-analysis`, `survey`, `taxonomy`, `software-maintenance`.  
   Summary: Lehnert's review organizes two decades of software change impact analysis research through a taxonomy of methods, artifacts, and evaluation criteria, then uses that survey to highlight unresolved challenges around automation quality, coverage across artifact types, and the difficulty of comparing approaches on common ground.

3. **Integrated Impact Analysis for Managing Software Changes**  
   Type: Research paper (ICSE 2012).  
   Labels: `change-impact-analysis`, `information-retrieval`, `dynamic-analysis`, `mining-software-repositories`.  
   Summary: This paper treats impact analysis as an adaptive maintenance task driven by a natural-language change request, combining information retrieval with optional execution-trace evidence and repository-history signals so the system can choose the most useful mix of available context for identifying affected code.

4. **CodeBERT: A Pre-Trained Model for Programming and Natural Languages**  
   Type: Research paper (Findings of EMNLP / arXiv).  
   Labels: `code-model`, `pretraining`, `code-search`, `documentation-generation`.  
   Summary: CodeBERT introduces a bimodal natural-language/code pretraining recipe and shows that these shared representations improve downstream tasks like code search and documentation generation, making the paper foundational for later retrieval and code-understanding work.

5. **GraphCodeBERT: Pre-training Code Representations with Data Flow**  
   Type: Research paper (ICLR / arXiv).  
   Labels: `code-model`, `data-flow`, `structure-aware`, `code-search`.  
   Summary: GraphCodeBERT argues that semantic program structure matters more than treating code as flat tokens, and uses data-flow-aware pretraining objectives to improve search, translation, clone detection, and refinement.

6. **CodeXGLUE: A Machine Learning Benchmark Dataset for Code Understanding and Generation**  
   Type: Benchmark paper (arXiv).  
   Labels: `benchmark`, `dataset`, `code-understanding`, `code-generation`.  
   Summary: CodeXGLUE packages a broad suite of code understanding and generation tasks with shared baselines, making the paper more about benchmark design and cross-task evaluation infrastructure than about one new model alone.

7. **UniXcoder: Unified Cross-Modal Pre-training for Code Representation**  
   Type: Research paper (arXiv).  
   Labels: `code-model`, `cross-modal`, `ast`, `code-completion`.  
   Summary: UniXcoder unifies encoder-style understanding and decoder-style generation in one pretrained code model, using AST and comment signals so the same backbone can support both analysis-heavy and generation-heavy downstream tasks.

8. **ReAct: Synergizing Reasoning and Acting in Language Models**  
   Type: Research paper (arXiv / ICLR).  
   Labels: `agent-loop`, `reasoning-and-acting`, `tool-use`, `decision-making`.  
   Summary: ReAct shows that interleaving explicit reasoning traces with external actions produces better multi-step behavior than pure reasoning or pure acting alone, especially when the model needs to gather fresh evidence instead of hallucinating through uncertainty.

9. **LLMs: Understanding Code Syntax and Semantics for Code Analysis**  
   Type: Research paper (arXiv).  
   Labels: `code-analysis`, `syntax-semantics`, `ast-cfg-cg`, `llm-evaluation`.  
   Summary: This study breaks code-analysis ability into syntax, static-behavior, and dynamic-behavior understanding, then evaluates frontier models across languages to show that LLMs can handle some structural code reasoning but still struggle to reliably support deeper analysis tasks.

10. **RepoBench: Benchmarking Repository-Level Code Auto-Completion Systems**  
   Type: Benchmark paper (arXiv).  
   Labels: `benchmark`, `code-completion`, `retrieval`, `pipeline-evaluation`.  
   Summary: RepoBench separates repository completion into retrieval, completion, and end-to-end pipeline tasks so researchers can tell whether a system fails because it found the wrong context, completed poorly from good context, or mishandled both.

11. **RepoFusion: Training Code Models to Understand Your Repository**  
   Type: Research paper (arXiv).  
   Labels: `repo-completion`, `training`, `repository-context`, `code-models`.  
   Summary: RepoFusion argues that repository context should be learned during training instead of patched in only at inference time, and shows that models trained this way become much stronger at context-aware completion than much larger generic baselines.

12. **CodePlan: Repository-level Coding using LLMs and Planning**  
   Type: Research paper (arXiv).  
   Labels: `planning`, `repo-editing`, `impact-analysis`, `multi-step-edits`.  
   Summary: CodePlan treats repository-level maintenance tasks as sequences of planned edits rather than isolated generations, combining dependency analysis and may-impact analysis to pick, order, and condition multi-file changes.

13. **Making Retrieval-Augmented Language Models Robust to Irrelevant Context**  
   Type: Research paper (arXiv).  
   Labels: `rag-robustness`, `irrelevant-context`, `retrieval-training`, `multi-hop`.  
   Summary: This paper studies how irrelevant retrieved context degrades reasoning, then shows that filtering and training on mixtures of relevant and irrelevant evidence makes RAG systems more robust without giving up the upside of retrieval.

14. **SWE-bench: Can Language Models Resolve Real-World GitHub Issues?**  
   Type: Benchmark paper (arXiv).  
   Labels: `benchmark`, `issue-resolution`, `github-issues`, `coding-agents`.  
   Summary: SWE-bench establishes real GitHub issue resolution as a durable testbed for software-engineering agents, emphasizing that practical issue fixing demands environment interaction, long-context reasoning, and coordinated edits across codebase boundaries.

15. **RepoCoder: Repository-Level Code Completion Through Iterative Retrieval and Generation**  
   Type: Research paper (EMNLP 2023).  
   Labels: `repo-completion`, `retrieval`, `iterative-generation`, `benchmark`.  
   Summary: RepoCoder treats repository completion as an iterative loop between retrieval and generation instead of a one-shot prompt, and the paper shows that this repeated grounding is what lifts completion quality over in-file and vanilla RAG baselines.

16. **RepoQA: Evaluating Long Context Code Understanding**  
   Type: Benchmark paper (arXiv).  
   Labels: `benchmark`, `long-context`, `code-search`, `repo-understanding`.  
   Summary: RepoQA moves long-context evaluation away from toy "needle" setups and toward repository code search, measuring whether models can actually understand code and natural-language descriptions well enough to find the right function in large repos.

17. **GraphCoder: Enhancing Repository-Level Code Completion via Code Context Graph-based Retrieval and Language Model**  
   Type: Research paper (arXiv).  
   Labels: `graph-retrieval`, `code-completion`, `code-context-graph`, `repo-rag`.  
   Summary: GraphCoder replaces loose sequence-style retrieval with a code-context graph built from control and data dependencies, using that structure to retrieve more targeted repository context for completion.

18. **Hierarchical Context Pruning: Optimizing Real-World Code Completion with Repository-Level Pretrained Code LLMs**  
   Type: Research paper (arXiv).  
   Labels: `context-pruning`, `repo-code-llms`, `dependencies`, `code-completion`.  
   Summary: This paper studies what repository context actually matters for completion and turns that analysis into hierarchical context pruning, which keeps dependency topology while stripping away low-value implementation detail to fit repo prompts into available context.

19. **Repoformer: Selective Retrieval for Repository-Level Code Completion**  
   Type: Research paper (ICML 2024 / PMLR).  
   Labels: `code-completion`, `selective-retrieval`, `efficiency`, `repo-rag`.  
   Summary: Repoformer makes the case that retrieval is not always beneficial, trains a model to predict when cross-file retrieval will help, and shows that skipping unnecessary retrieval can improve both accuracy and latency in repository-level completion.

20. **A First Look at License Compliance Capability of LLMs in Code Generation**  
   Type: Research paper (ICSE paper / arXiv full paper).  
   Labels: `license-compliance`, `benchmark`, `code-generation-eval`, `legal-risk`.  
   Summary: The paper frames license compliance as a distinct evaluation problem for code LLMs, builds LiCoEval around a legally motivated "striking similarity" threshold, and shows that even strong models still emit non-trivial amounts of closely matching code while rarely supplying the right license information, especially for copyleft code.  
   Notes: The canonical paper title on arXiv is `LiCoEval: Evaluating LLMs on License Compliance in Code Generation`.

21. **CodexGraph: Bridging Large Language Models and Code Repositories via Code Graph Databases**  
   Type: Research paper (arXiv).  
   Labels: `graph-database`, `repo-agents`, `code-retrieval`, `tooling`.  
   Summary: CodexGraph proposes graph-database-backed codebase interaction as a middle ground between low-recall similarity search and brittle task-specific tools, so agents can query repository structure through a more general interface.

22. **MemLong: Memory-Augmented Retrieval for Long Text Modeling**  
   Type: Research paper (arXiv).  
   Labels: `long-context`, `memory`, `retrieval`, `language-modeling`.  
   Summary: MemLong adds an external retrieval memory to long-context modeling so the model can pull semantically relevant earlier chunks instead of depending only on ever-growing attention, improving long-context performance while stretching usable context length much further.

23. **RepoFixEval: A Repository-Level Program Repair Benchmark From Issue Discovering to Bug Fixing**  
   Type: Benchmark paper (OpenReview withdrawn submission).  
   Labels: `program-repair`, `benchmark`, `repo-bugs`, `evaluation-pipeline`.  
   Summary: RepoFixEval treats repository-level repair as a multi-stage process - issue discovery, bug localization, and fix generation - and shows that current LLMs remain weak on realistic multi-file repair, especially before they even reach the patching stage.

24. **Sufficient Context: A New Lens on Retrieval Augmented Generation Systems**  
   Type: Research paper (arXiv).  
   Labels: `rag`, `context-sufficiency`, `hallucination`, `selective-generation`.  
   Summary: This paper separates RAG failures caused by weak reasoning over good context from failures caused by context that was never sufficient in the first place, then uses that distinction to show where different model families hallucinate or abstain and to motivate a selective-generation method for safer response behavior.

25. **CodeRepoQA: A Large-scale Benchmark for Software Engineering Question Answering**  
   Type: Benchmark paper (arXiv).  
   Labels: `repo-qa`, `large-scale`, `multi-turn`, `software-engineering`.  
   Summary: CodeRepoQA scales repository QA into a very large multi-turn benchmark and uses that scale to show that software-engineering QA remains difficult for current LLMs, with context length and dialogue structure both affecting performance.

26. **CoReQA: Uncovering Potentials of Language Models in Code Repository Question Answering**  
   Type: Benchmark paper (arXiv).  
   Labels: `repo-qa`, `benchmark`, `issue-data`, `evaluation`.  
   Summary: CoReQA builds repository-level QA from GitHub issues and comments and argues that realistic repo QA needs richer evaluation than BLEU-style matching because answers mix natural language, code snippets, and cross-file repository knowledge.

27. **Repository-level Code Search with Neural Retrieval Methods**  
   Type: Research paper (arXiv).  
   Labels: `code-search`, `commit-history`, `reranking`, `bug-fixing`.  
   Summary: This work defines repository-level search as finding the set of current files most relevant to a bug or question, then uses commit-message retrieval plus CodeBERT reranking to show that repository history is a strong signal for practical search.

28. **LocAgent: Graph-Guided LLM Agents for Code Localization**  
   Type: Research paper (arXiv).  
   Labels: `code-localization`, `graph-guided-agents`, `issue-resolution`, `multi-hop-reasoning`.  
   Summary: LocAgent represents repositories as heterogeneous graphs over files, classes, functions, and dependency edges so an agent can localize relevant code through structured multi-hop search instead of shallow file retrieval, yielding markedly stronger localization accuracy and better downstream issue-resolution performance.

29. **CoSIL: Software Issue Localization via LLM-Driven Code Repository Graph Searching**  
   Type: Research paper (arXiv).  
   Labels: `issue-localization`, `code-graphs`, `iterative-search`, `swe-bench`.  
   Summary: CoSIL localizes issues by having the model iteratively explore a dynamically built repository call graph instead of relying on static indexing, using graph-guided search and context pruning to balance search breadth against prompt budget and improving both localization and downstream patch resolution.
   Notes: The canonical arXiv title is `CoSIL: Software Issue Localization via LLM-Driven Code Repository Graph Searching`.

30. **GraphCodeAgent: Dual Graph-Guided LLM Agent for Retrieval-Augmented Repo-Level Code Generation**  
   Type: Research paper (arXiv).  
   Labels: `graph-guided-agents`, `repo-generation`, `multi-hop-retrieval`, `requirements`.  
   Summary: GraphCodeAgent uses two linked graphs, one over requirement relations and one over structural-semantic code dependencies, then lets an agent perform multi-hop retrieval over them to surface both implicit APIs and supporting repository context that ordinary lexical retrieval misses in repo-level generation.
   Notes: Earlier versions of the paper appeared under the title `CodeRAG: Supportive Code Retrieval on Bigraph for Real-World Code Generation`.

31. **SecRepoBench: Benchmarking Code Agents for Secure Code Completion in Real-World Repositories**  
   Type: Benchmark paper (arXiv).  
   Labels: `security`, `code-agents`, `secure-completion`, `benchmark`.  
   Summary: SecRepoBench tests secure completion in real C/C++ repositories and shows that while agent frameworks outperform standalone LLMs on security-sensitive code tasks, the overall gap to dependable secure coding is still large.

32. **Knowledge Graph Based Repository-Level Code Generation**  
   Type: Research paper (arXiv / workshop paper).  
   Labels: `knowledge-graphs`, `repo-generation`, `code-search`, `retrieval`.  
   Summary: This paper models a repository as a knowledge graph to improve context-aware code search and generation, arguing that explicit relational structure helps generation stay consistent with evolving codebase context.

33. **Code Researcher: Deep Research Agent for Large Systems Code and Commit History**  
   Type: Research paper (Microsoft Research paper / preprint).  
   Labels: `agentic-repair`, `systems-code`, `commit-history`, `deep-research`.  
   Summary: Code Researcher is presented as a deep-research coding agent that gathers structured context from large codebases and rich commit history before patching, and the paper argues that this broader research phase is what lets it outperform standard issue-fixing agents on systems crash tasks.

34. **The SWE-Bench Illusion: When State-of-the-Art LLMs Remember Instead of Reason**  
   Type: Research paper (arXiv).  
   Labels: `swe-bench`, `benchmark-validity`, `memorization`, `contamination`.  
   Summary: The paper questions how much SWE-Bench performance reflects real problem solving by testing whether models can identify buggy files from issue text alone, and finds evidence that strong results may be inflated by memorization or contamination rather than robust repository reasoning.

35. **Repository-Level Code Understanding by LLMs via Hierarchical Summarization: Improving Code Search and Bug Localization**  
   Type: Research paper (Springer book chapter).  
   Labels: `hierarchical-summarization`, `repo-understanding`, `code-search`, `bug-localization`.  
   Summary: The chapter argues that hierarchical summarization is an effective structure-aware compression layer for large repositories, letting LLMs reason over repo shape instead of raw file dumps and improving both search and localization performance.

36. **CoIR: A Comprehensive Benchmark for Code Information Retrieval Models**  
   Type: Benchmark paper (ACL 2025).  
   Labels: `benchmark`, `code-information-retrieval`, `datasets`, `evaluation`.  
   Summary: CoIR broadens code retrieval evaluation across many domains and task types, and its central claim is that existing retrieval models still do not generalize well once the benchmark stops looking like a single leaderboard niche.

37. **RepoST: Scalable Repository-Level Coding Environment Construction with Sandbox Testing**  
   Type: Research paper (COLM 2025 / OpenReview).  
   Labels: `sandbox-testing`, `training-data`, `repo-generation`, `execution-feedback`.  
   Summary: RepoST focuses on constructing execution-grounded training and evaluation environments at scale by isolating target functions and dependencies into sandbox tests, which lets the authors build large repo-level datasets without needing to execute whole repositories.

38. **SWE-Exp: Experience-Driven Software Issue Resolution**  
   Type: Research paper (arXiv).  
   Labels: `issue-resolution`, `experience-memory`, `learning-from-trajectories`, `swe-bench`.  
   Summary: SWE-Exp reframes issue resolution as a continual-learning problem by extracting reusable experience from prior successful and failed repair trajectories, storing it in a structured experience bank, and using that memory to reduce repeated blind exploration on future issues.

39. **Impact-driven Context Filtering For Cross-file Code Completion**  
   Type: Research paper (arXiv).  
   Labels: `code-completion`, `context-filtering`, `cross-file-context`, `retrieval`.  
   Summary: This work measures the actual contribution of retrieved cross-file chunks to completion quality, shows that many retrieved snippets are neutral or harmful, and then uses those labels to train CODEFILTER, a context-filtering stage that improves both completion accuracy and prompt efficiency by pruning negative retrieved context.

40. **GRACE: Graph-Guided Repository-Aware Code Completion through Hierarchical Code Fusion**  
   Type: Research paper (arXiv).  
   Labels: `code-completion`, `graph-retrieval`, `hierarchical-fusion`, `repo-rag`.  
   Summary: GRACE argues that repository completion suffers when retrieval ignores structural relations and when retrieved snippets are flattened into plain text, so it builds a multi-level code graph, hybrid graph-and-text retrieval, and a structural fusion mechanism that preserves dependencies while injecting repository context into completion.

41. **SWE-QA: Can Language Models Answer Repository-level Code Questions?**  
   Type: Benchmark paper (arXiv).  
   Labels: `repo-qa`, `taxonomy`, `realistic-questions`, `cross-file-reasoning`.  
   Summary: SWE-QA is built from real GitHub issue discussions, develops a taxonomy of repository-level questions, and turns those naturally occurring developer information needs into a benchmark for intent understanding and cross-file reasoning.

42. **RANGER -- Repository-Level Agent for Graph-Enhanced Retrieval**  
   Type: Research paper (arXiv).  
   Labels: `retrieval`, `knowledge-graphs`, `repo-qa`, `code-search`.  
   Summary: RANGER frames repository retrieval as a graph-navigation problem over a repository knowledge graph, combining direct Cypher-style lookups for explicit code-entity queries with MCTS-guided graph exploration for natural-language queries so one agent can serve multiple repository tasks.

43. **Improving Code Localization with Repository Memory**  
   Type: Research paper (arXiv).  
   Labels: `code-localization`, `repository-memory`, `commit-history`, `issue-resolution`.  
   Summary: This work augments localization agents with non-parametric repository memory built from commit history, linked issues, and summaries of actively changing modules, showing that carrying forward historical repository knowledge materially improves localization over handling each issue from scratch.

44. **Retrieval-Augmented Code Generation: A Survey with Focus on Repository-Level Approaches**  
   Type: Survey paper (arXiv).  
   Labels: `survey`, `retrieval`, `repo-generation`, `evaluation`.  
   Summary: This survey organizes repository-level retrieval-augmented code generation around retrieval modality, generation strategy, training setup, and evaluation, and uses that structure to map the field's open problems around long-range dependencies, context quality, and realistic repo-level benchmarks.

45. **An Exploratory Study of Code Retrieval Techniques in Coding Agents**  
   Type: Preprint / survey-style study.  
   Labels: `code-retrieval`, `coding-agents`, `lexical-vs-semantic`, `context-management`.  
   Summary: This preprint surveys how coding agents gather repository context, contrasting lexical search, semantic retrieval, LSP-style structure, and agentic search loops, and argues that retrieval quality now matters more than raw reasoning depth for many coding systems.

46. **Beyond Function-Level Search: Repository-Aware Dual-Encoder Code Retrieval with Adversarial Verification**  
   Type: Research paper (EMNLP 2025 / arXiv).  
   Labels: `repo-retrieval`, `benchmark`, `dual-encoder`, `change-requests`.  
   Summary: The paper shifts retrieval from isolated function matching toward change-request-aware repository reasoning, introduces RepoAlign-Bench, and uses a reflected dual-encoder setup to better align change intent with relevant repository context.

47. **Information Gain-based Policy Optimization: A Simple and Effective Approach for Multi-Turn Search Agents**  
   Type: Research paper (arXiv).  
   Labels: `search-agents`, `reinforcement-learning`, `dense-rewards`, `information-gain`.  
   Summary: IGPO trains multi-turn search agents with intrinsic turn-level rewards defined by the model's marginal information gain about the correct answer, addressing sparse-reward failure modes and improving both accuracy and sample efficiency over outcome-only RL baselines.

48. **Stop-RAG: Value-Based Retrieval Control for Iterative RAG**  
   Type: Research paper (arXiv).  
   Labels: `iterative-rag`, `retrieval-control`, `reinforcement-learning`, `multi-hop-qa`.  
   Summary: Stop-RAG treats iterative retrieval as a finite-horizon control problem and learns when to stop retrieving rather than using fixed loop counts or weak confidence heuristics, improving multi-hop QA accuracy while reducing unnecessary retrieval cost and distraction.

49. **Empowering RepoQA-Agent based on Reinforcement Learning Driven by Monte-carlo Tree Search**  
   Type: Research paper (arXiv).  
   Labels: `repo-qa`, `reinforcement-learning`, `mcts`, `agent-training`.  
   Summary: The paper introduces RepoSearch-R1, an MCTS-driven reinforcement-learning framework for repository agents, and uses it to train a RepoQA agent that can generate stronger tool-use trajectories without distillation from larger closed models, improving answer completeness and training efficiency on repository QA tasks.

50. **SACL: Understanding and Combating Textual Bias in Code Retrieval with Semantic-Augmented Reranking and Localization**  
   Type: Research paper (Findings of EMNLP 2025).  
   Labels: `code-retrieval`, `bias`, `reranking`, `generation`.  
   Summary: The paper demonstrates that current code retrievers lean too heavily on superficial textual signals like names and docstrings, then proposes SACL to inject semantic and structural signals that improve both retrieval quality and downstream code generation.

51. **InfCode-C++: Intent-Guided Semantic Retrieval and AST-Structured Search for C++ Issue Resolution**  
   Type: Research paper (arXiv).  
   Labels: `cplusplus`, `issue-resolution`, `semantic-retrieval`, `ast-search`.  
   Summary: InfCode-C++ argues that Python-oriented retrieval patterns do not transfer cleanly to C++, and combines intent-level retrieval with deterministic AST querying to localize and patch issues in large, statically typed repositories.

52. **Beyond the Prompt: An Empirical Study of Cursor Rules**  
   Type: Research paper (arXiv / MSR 2026).  
   Labels: `developer-directives`, `context`, `coding-assistants`, `empirical-study`.  
   Summary: This empirical study analyzes real Cursor rule files across open-source repositories and shows that developers use persistent machine-readable guidance to encode conventions, project facts, examples, and explicit LLM directives that ordinary prompts miss.

53. **SWE-RM: Execution-free Feedback For Software Engineering Agents**  
   Type: Research paper (arXiv).  
   Labels: `reward-models`, `execution-free-feedback`, `swe-bench`, `reinforcement-learning`.  
   Summary: SWE-RM studies how reward models can provide finer-grained feedback than unit tests for software engineering agents, arguing that good test-time selection performance alone is not enough for RL and that calibration and classification quality are critical if execution-free feedback is meant to drive reliable agent improvement.

54. **In Line with Context: Repository-Level Code Generation via Context Inlining**  
   Type: Research paper (arXiv).  
   Labels: `repo-generation`, `context-inlining`, `call-graphs`, `code-completion`.  
   Summary: InlineCoder reframes repository-level generation as a context-inlining problem by first drafting an anchor completion, then using that draft to inline the unfinished function into its callers and retrieve its callees, giving the model an upstream and downstream repository view that captures dependencies more directly than similarity-based retrieval alone.

55. **CodeMEM: AST-Guided Adaptive Memory for Repository-Level Iterative Code Generation**  
   Type: Research paper (arXiv).  
   Labels: `memory`, `iterative-generation`, `ast-guided`, `repo-generation`.  
   Summary: CodeMEM addresses long multi-turn coding sessions by maintaining AST-guided repository memory and a code-centric session memory that explicitly tracks validated changes and forgetting risks, improving iterative repository-level generation without relying on natural-language-only memory summaries.

56. **RepoShapley: Shapley-Enhanced Context Filtering for Repository-Level Code Completion**  
   Type: Research paper (arXiv).  
   Labels: `code-completion`, `context-filtering`, `shapley`, `repo-rag`.  
   Summary: RepoShapley treats retrieved chunks as interaction-dependent coalitions rather than isolated evidence, using Shapley-style marginal contribution estimates plus bounded post-verification to supervise keep/drop decisions and retrieval triggers that reduce harmful context in repository-level completion.

57. **Reliable Graph-RAG for Codebases: AST-Derived Graphs vs LLM-Extracted Knowledge Graphs**  
   Type: Research paper (arXiv).  
   Labels: `graph-rag`, `ast`, `repo-retrieval`, `architecture-reasoning`.  
   Summary: The paper compares vector-only retrieval, LLM-generated repository graphs, and deterministic AST-derived graphs on architecture-style codebase questions, and argues that deterministic code graphs give better coverage, lower indexing cost, and stronger multi-hop grounding than LLM-extracted graphs.

58. **SWE-Pruner: Self-Adaptive Context Pruning for Coding Agents**  
   Type: Research paper (arXiv).  
   Labels: `context-pruning`, `coding-agents`, `compression`, `token-efficiency`.  
   Summary: SWE-Pruner treats context compression for coding agents as a task-aware skimming problem, using an explicit goal plus a lightweight learned skimmer to retain code lines relevant to the current objective; the paper shows sizable token reductions across agent and single-turn code benchmarks with limited loss in task performance.

59. **FeatureBench: Benchmarking Agentic Coding for Complex Feature Development**  
   Type: Benchmark paper (ICLR 2026 / OpenReview).  
   Labels: `feature-development`, `execution-based-eval`, `agentic-coding`, `dependency-graphs`.  
   Summary: FeatureBench shifts evaluation away from narrow bug-fix tasks toward end-to-end feature work, automatically mining feature-oriented tasks from repositories through tests and dependency traces so that agents are judged on executable product-level changes.

60. **Gistify: Codebase-Level Understanding via Runtime Execution**  
   Type: Benchmark paper (ICLR 2026 / OpenReview).  
   Labels: `codebase-understanding`, `runtime-execution`, `benchmark`, `minimal-reproduction`.  
   Summary: Gistify evaluates whether a model truly understands a codebase's execution behavior by asking it to compress a repository into a single self-contained file that reproduces a specified entrypoint, making success depend on execution-faithful abstraction rather than local patch retrieval alone.

61. **IDE-Bench: Evaluating Large Language Models as IDE Agents on Real-World Software Engineering Tasks**  
   Type: Benchmark paper (arXiv).  
   Labels: `benchmark`, `ide-agents`, `software-engineering-tasks`, `evaluation-harness`.  
   Summary: IDE-Bench evaluates coding agents through an IDE-native tool interface rather than raw terminal access, using Dockerized multi-language tasks over never-published repositories to measure whether models can act as practical engineering collaborators on realistic implementation, debugging, refactoring, and performance tasks.

62. **ContextBench: A Benchmark for Context Retrieval in Coding Agents**  
   Type: Benchmark paper (arXiv).  
   Labels: `context-retrieval`, `coding-agents`, `benchmark`, `process-metrics`.  
   Summary: ContextBench focuses on the retrieval process inside coding agents rather than only final issue resolution, adding gold context annotations and trajectory-level recall, precision, and efficiency metrics to expose where agents waste or misuse context.

63. **SWE Context Bench: A Benchmark for Context Learning in Coding**  
   Type: Benchmark paper (arXiv).  
   Labels: `context-reuse`, `benchmark`, `efficiency`, `programming-agents`.  
   Summary: SWE-ContextBench studies whether agents can learn from prior related tasks, showing that context reuse can boost accuracy and cut cost when the reused context is selected and summarized well, but can hurt when the reuse signal is noisy.

64. **Do Not Treat Code as Natural Language: Implications for Repository-Level Code Generation and Beyond**  
   Type: Research paper (arXiv).  
   Labels: `repo-generation`, `structure-aware-retrieval`, `dependencies`, `code-completion`.  
   Summary: This paper argues that repository retrieval should respect code structure rather than importing NLP chunking assumptions, and proposes Hydra, a structure-aware indexing and dependency-retrieval framework that explicitly pulls true cross-file dependencies and usage examples for repository-level generation.

65. **Evaluating AGENTS.md: Are Repository-Level Context Files Helpful for Coding Agents?**  
   Type: Research paper (arXiv).  
   Labels: `agents-md`, `context-files`, `coding-agents`, `repository-context`.  
   Summary: This paper evaluates repository-level context files such as `AGENTS.md` across both SWE-bench-style tasks and repositories that already contain developer-written context files, finding that these files often make agents explore more broadly but usually reduce task success and increase cost unless they stay minimal and tightly scoped.

66. **SGAgent: Suggestion-Guided LLM-Based Multi-Agent Framework for Repository-Level Software Repair**  
   Type: Research paper (arXiv).  
   Labels: `software-repair`, `multi-agent`, `suggestions`, `knowledge-graphs`.  
   Summary: SGAgent inserts an explicit suggestion phase between localization and patch generation, using a KG-backed repository toolkit and coordinated localizer, suggester, and fixer agents so repair decisions are grounded in richer repository understanding before edits are made.

67. **A Scalable Benchmark for Repository-Oriented Long-Horizon Conversational Context Management**  
   Type: Benchmark paper (arXiv).  
   Labels: `long-horizon-context`, `conversation-memory`, `benchmark`, `repo-agents`.  
   Summary: This paper introduces LoCoEval, a benchmark for repository-oriented multi-turn conversations that stress context retention under iterative requirements, noisy inputs, and retrospective questions, and shows that existing context-management methods, especially standalone memory systems, remain weak without tighter integration of repository and conversational memory.

68. **SWE-QA-Pro: A Representative Benchmark and Scalable Training Recipe for Repository-Level Code Understanding**  
   Type: Benchmark and training paper (arXiv).  
   Labels: `repo-qa`, `benchmark`, `agentic-training`, `long-tail-repos`.  
   Summary: SWE-QA-Pro aims to make repository QA harder and less gameable by using long-tail repositories and executable environments, and then pairs the benchmark with a synthetic-data training recipe for teaching smaller models stronger tool use.

69. **When the Specification Emerges: Benchmarking Faithfulness Loss in Long-Horizon Coding Agents**  
   Type: Benchmark paper (arXiv).  
   Labels: `long-horizon-agents`, `faithfulness`, `specification-drift`, `benchmark`.  
   Summary: The paper studies how coding agents drift away from user intent over long interaction histories, introducing a benchmark centered on emergent specification changes and showing that strong final patches can still hide substantial faithfulness loss as agents overfit intermediate artifacts rather than the evolving task specification.

70. **TDAD: Test-Driven Agentic Development - Reducing Code Regressions in AI Coding Agents via Graph-Based Impact Analysis**  
   Type: Research paper (arXiv).  
   Labels: `regression-reduction`, `impact-analysis`, `testing`, `coding-agents`.  
   Summary: TDAD focuses on preventing regressions from coding agents by building a source-to-test dependency map that tells the agent which tests are likely affected by a change, showing that targeted verification context cuts regressions more effectively than generic TDD-style procedural prompting.

71. **HCAG: Hierarchical Abstraction and Retrieval-Augmented Generation on Theoretical Repositories with LLMs**  
   Type: Research paper (arXiv).  
   Labels: `hierarchical-abstraction`, `repo-generation`, `retrieval`, `theory-to-code`.  
   Summary: HCAG reframes repository-level generation as a planning problem over hierarchical knowledge, building an offline abstraction layer that links theory, architecture, and implementation and then using top-down retrieval to scaffold generation across repository levels.

72. **Dynamic analysis enhances issue resolution**  
   Type: Research paper (arXiv).  
   Labels: `issue-resolution`, `dynamic-analysis`, `runtime-traces`, `software-repair`.  
   Summary: This paper proposes DAIRA, an issue-resolution agent that incorporates lightweight runtime tracing into the repair loop so the model can reason over variable states and call stacks rather than relying only on static context and pass/fail execution feedback, reducing speculative search on hard bugs.

73. **Bridging Code Property Graphs and Language Models for Program Analysis**  
   Type: Research paper (arXiv).  
   Labels: `program-analysis`, `code-property-graphs`, `security`, `mcp-tools`.  
   Summary: The paper introduces Codebadger, an MCP-style interface over Joern code property graphs, and shows how exposing slicing, taint, and data-flow tools lets LLMs analyze large codebases for vulnerability discovery and patching without reading everything into context.

74. **ReCUBE: Evaluating Repository-Level Context Utilization in Code Generation**  
   Type: Benchmark paper (arXiv).  
   Labels: `repo-generation`, `benchmark`, `context-utilization`, `dependency-graphs`.  
   Summary: ReCUBE isolates repository-level context use by asking models to reconstruct a masked file from the rest of a real repository, then evaluates the result with usage-aware tests; the paper shows that even strong models still struggle to turn broad repository context into correct code, while the proposed caller-centric exploration tools improve agent performance.

75. **A Benchmark for Evaluating Repository-Level Code Agents with Intermediate Reasoning on Feature Addition Task**  
   Type: Benchmark paper (arXiv).  
   Labels: `feature-development`, `benchmark`, `reasoning-traces`, `repo-agents`.  
   Summary: This paper introduces RACE-bench, a feature-addition benchmark that pairs executable verification with structured intermediate reasoning annotations for issue understanding, localization, decomposition, and implementation steps, making it possible to evaluate where repository-level code agents fail instead of treating them as black boxes.

76. **ATime-Consistent Benchmark for Repository-Level Software Engineering Evaluation**  
   Type: Benchmark paper (arXiv).  
   Labels: `time-consistency`, `benchmark`, `repo-evaluation`, `prompt-control`.  
   Summary: This paper proposes a time-consistent evaluation protocol that snapshots repositories before future pull requests and compares the same agent with and without repository-derived knowledge under matched prompts, arguing that temporal consistency and prompt control are necessary to make repository-level software engineering evaluation credible.

77. **Beyond Code Snippets: Benchmarking LLMs on Repository-Level Question Answering**  
   Type: Benchmark paper (arXiv / conference paper).  
   Labels: `repo-qa`, `stackoverflow`, `memorization`, `structural-augmentation`.  
   Summary: This paper builds StackRepoQA from real developer questions and accepted answers over Java repositories and shows that repository QA remains difficult even with structural retrieval, with some high scores traceable to memorized answer patterns rather than true repository reasoning.

78. **Codebase-Memory: Tree-Sitter-Based Knowledge Graphs for LLM Code Exploration via MCP**  
   Type: Research paper (arXiv).  
   Labels: `knowledge-graphs`, `mcp`, `tree-sitter`, `token-efficiency`.  
   Summary: Codebase-Memory proposes a persistent tree-sitter knowledge graph exposed via MCP, and the paper's main argument is that graph-native exploration can answer many repository questions with far fewer tokens and tool calls than repeated file-grepping.

79. **Compressing Code Context for LLM-based Issue Resolution**  
   Type: Research paper (arXiv).  
   Labels: `context-compression`, `issue-resolution`, `swe-bench`, `token-efficiency`.  
   Summary: This paper argues that issue-resolution agents fail partly because oversized repository context both costs too much and distracts the model, then introduces an oracle-guided code distillation process plus a learned compressor that preserves patch-critical code while cutting tokens sharply and improving resolution rates on SWE-bench Verified.

80. **Are Benchmark Tests Strong Enough? Mutation-Guided Diagnosis and Augmentation of Regression Suites**  
   Type: Benchmark paper (arXiv).  
   Labels: `benchmark-validity`, `mutation-testing`, `regression-suites`, `swe-bench`.  
   Summary: This work argues that weak regression suites can over-credit repair agents, introduces STING to generate targeted tests from surviving program variants, and shows that strengthening SWE-bench-style suites lowers apparent resolved rates while increasing confidence that passing patches are semantically correct.

81. **Beyond Isolated Tasks: A Framework for Evaluating Coding Agents on Sequential Software Evolution**  
   Type: Benchmark paper (arXiv).  
   Labels: `sequential-evaluation`, `software-evolution`, `technical-debt`, `benchmark`.  
   Summary: This work argues that stateless single-PR evaluation overstates agent quality, then introduces SWE-STEPS to measure performance across chains of dependent changes where regressions, technical debt, and cumulative repository health matter alongside whether the current task appears solved.

82. **Toward Executable Repository-Level Code Generation via Environment Alignment**  
   Type: Research paper (arXiv).  
   Labels: `repo-generation`, `executability`, `environment-alignment`, `revision-loops`.  
   Summary: The paper reframes repository-level generation as an environment alignment problem in which a generated repository must satisfy both external dependency installation and internal reference resolution, and introduces EnvGraph to iteratively revise code using execution evidence from those two layers.

83. **Graph of Skills: Dependency-Aware Structural Retrieval for Massive Agent Skills**  
   Type: Research paper (arXiv).  
   Labels: `agent-skills`, `structural-retrieval`, `dependency-graphs`, `context-budgeting`.  
   Summary: Graph of Skills addresses the scaling problem in large skill libraries by building an executable dependency graph offline and retrieving bounded, dependency-aware skill bundles at inference time instead of loading the whole library.

84. **Evaluating Repository-level Software Documentation via Question Answering and Feature-Driven Development**  
   Type: Benchmark paper (arXiv).  
   Labels: `documentation`, `qa-based-eval`, `feature-driven-dev`, `repo-understanding`.  
   Summary: This paper argues that repository documentation should be evaluated by whether it supports understanding and implementation work, then introduces SWD-Bench to score documentation through QA, file localization, and functionality-completion tasks.

85. **CodeComp: Structural KV Cache Compression for Agentic Coding**  
   Type: Research paper (arXiv).  
   Labels: `kv-cache`, `compression`, `agentic-coding`, `program-analysis`.  
   Summary: CodeComp argues that standard KV compression throws away structurally critical code tokens, so it injects static-analysis priors into compression and recovers much more full-context behavior under tight memory budgets.

86. **Structure-Grounded Knowledge Retrieval via Code Dependencies for Multi-Step Data Reasoning**  
   Type: Research paper (arXiv).  
   Labels: `structure-grounded-retrieval`, `dependency-graphs`, `multi-step-reasoning`, `code-generation`.  
   Summary: SGKR treats executable dependency structure, not just lexical similarity, as the retrieval target for multi-step data reasoning, and builds task-specific subgraphs that help agents assemble the right code and knowledge context.

87. **TypeScript Repository Indexing for Code Agent Retrieval**  
   Type: Research paper (arXiv).  
   Labels: `typescript`, `indexing`, `code-agent-retrieval`, `compiler-api`.  
   Summary: This paper focuses on retrieval infrastructure rather than generation directly, replacing slow LSP-mediated TypeScript symbol resolution with a parser built on the TypeScript Compiler API so large repositories can be indexed into richer function-level dependency structures more efficiently for code-agent retrieval.

## Documentation

1. **Introduction.**  
   Type: Documentation.  
   Labels: `parser-tooling`, `tree-sitter`, `syntax-trees`, `incremental-parsing`.  
   Summary: The Tree-sitter introduction explains the system as a fast, incremental, error-tolerant parsing library for source code, which is why it has become a common structural backbone for repository indexing, chunking, and AST-aware retrieval systems.

2. **Faiss Documentation.**  
   Type: Documentation.  
   Labels: `vector-search`, `similarity-search`, `faiss`, `retrieval-infrastructure`.  
   Summary: The Faiss docs present the library as dense-vector indexing and nearest-neighbor infrastructure for retrieval workloads, making it a practical building block for embedding-based code search and repository RAG pipelines.

3. **Basic Programming Problems (MBPP).**  
   Type: Repository documentation.  
   Labels: `benchmark`, `dataset`, `mbpp`, `evaluation`.  
   Summary: The MBPP task README summarizes the benchmark's role inside `lm-evaluation-harness`, tying it back to the original program-synthesis paper and highlighting that the dataset measures short Python synthesis from natural-language descriptions rather than repository-scale coding.

4. **jcodemunch-mcp / SPEC.md**  
   Type: Repository documentation.  
   Labels: `mcp`, `symbol-retrieval`, `tree-sitter`, `token-efficiency`.  
   Summary: The jcodemunch repository documents a tree-sitter-backed MCP server for token-efficient codebase exploration, pushing a symbol-first, outline-first interaction style instead of repeated whole-file reads.

## Blogs/Articles

1. **The anatomy of an AI coding assistant**  
   Type: Blog post.  
   Labels: `coding-assistants`, `context`, `product-architecture`, `repo-retrieval`.  
   Summary: This Sourcegraph post explains a coding assistant as a context system wrapped around an LLM, showing how retrieval, chat, edit support, and autocomplete all depend on getting repository context into the model efficiently.

2. **Enhancing Repository-Level Code Completion with Selective Retrieval**  
   Type: Blog post.  
   Labels: `selective-retrieval`, `code-completion`, `latency`, `repo-rag`.  
   Summary: Amazon's writeup turns the Repoformer paper into an engineering argument: most completion requests do not benefit from retrieval, so a learned retrieval gate can cut latency sharply while still improving final completion quality.

3. **AI Design Patterns: Engineering Modular ML Pipelines and Agentic Systems**  
   Type: Blog post.  
   Labels: `design-patterns`, `agent-systems`, `ml-pipelines`, `architecture`.  
   Summary: The post lays out two families of reusable AI architecture patterns - modular ML microservices and agentic LLM control patterns - and treats both as engineering responses to complexity, maintainability, and the need for explicit planning, reflection, and tool integration.

4. **Effective context engineering for AI agents**  
   Type: Blog post.  
   Labels: `context-engineering`, `agents`, `token-budget`, `applied-ai`.  
   Summary: Anthropic's post argues that building capable agents is increasingly a context-management problem, and develops a practical framework for curating, compressing, and refreshing the information agents see across many turns.

5. **What Is HumanEval?**  
   Type: Industry explainer.  
   Labels: `benchmark`, `code-eval`, `humaneval`, `functional-correctness`.  
   Summary: This IBM overview explains HumanEval as a unit-test-based benchmark for Python code generation, focusing on why pass@k and functional correctness matter and where the benchmark falls short on efficiency, security, and real-world repository complexity.
