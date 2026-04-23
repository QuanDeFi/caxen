# LLM Agents for Code Repositories: Architectures, Retrieval, and Best Practices

## Executive Summary  
Large language models (LLMs) are increasingly used as assistants for coding and codebase maintenance.  Unlike single-shot text completion, *code agents* combine LLM reasoning with external tools and data to handle the scale and structure of real-world software projects. Recent research emphasizes **retrieval-augmented** and **agentic** approaches that retrieve relevant code snippets, documentation, tests, and commit history, then iteratively reason about them.  We survey architectures (plain LLM prompts, RAG, tool-using agents, chain-of-thought, ReAct, reflection, modular pipelines), repository access patterns (file/text retrieval, AST/graph-based retrieval, semantic embeddings, version control data, CI artifacts), data representations (raw code, tokenized code, ASTs, graphs, bytecode, docstrings, type annotations), indexing strategies (vector databases, sparse/dense retrieval, hierarchical and hybrid methods, metadata, caching, freshness), and long-context solutions (windowing, summarization, memory-augmented generation, long-context LLMs). 

We also review evaluation frameworks (benchmarks like CodeXGLUE, HumanEval, MBPP, CodeSearchNet, and newer repo-level repair tasks) and metrics (exact match, BLEU/CodeBLEU, and functional correctness like pass@k).  Optimization techniques include fine-tuning/LoRA, instruction tuning, distillation, prompt engineering (e.g. chain-of-thought), tool invocation (e.g. linters, test runners), and grounding outputs via tests or static analysis.  For tooling, language servers, static analyzers (CodeQL, linters), symbolic execution engines, test harnesses, and Git/CI integration are key.  Privacy and licensing are serious concerns: LLMs may inadvertently leak proprietary code or violate open-source licenses【46†L46-L53】【46†L79-L88】. 

Open challenges include richer multimodal context (combining code, docs, diagrams, logs, discussions)【48†L2209-L2218】, deeper agentic loops with graph-based reasoning【48†L2216-L2224】, efficient long-context models and summarization【48†L2223-L2231】, multilingual code support, and realistic benchmarks for multi-file workflows【48†L2237-L2245】【48†L2252-L2260】.  We recommend experiments comparing vanilla vs. retrieval-augmented vs. agentic pipelines, using large code LLMs (e.g. GPT-4o, CodeLlama) on mixed-size repositories.  Use metrics beyond token accuracy (e.g. test-pass rate, static analysis checks, developer usability), and ablations (with/without retrieval, chain-of-thought, tools, memory).  Detailed pros/cons and references follow.  

## 1. Agent Architectures and Reasoning Patterns  
LLM-based **agents** range from simple prompts to sophisticated multi-step workflows. Key patterns include:  

- **Single-turn LLM:** A single prompt (possibly with examples) fed to the model, output used directly. *Pros:* Easy to implement; no extra indexing. *Cons:* Strictly limited by context window; depends entirely on model’s internal knowledge; no iterative feedback. (Many coding tools began as single-shot code completion, but cannot easily handle large codebases.)  

- **Retrieval-Augmented (RAG):** The input is augmented by retrieving relevant context (code snippets, docs, tests) from the repository. A retriever (keyword search, vector similarity, graph queries) selects chunks which are concatenated to the prompt. This anchors generation in the actual codebase【17†L317-L324】【17†L331-L340】. *Pros:* Incorporates up-to-date project context; scales beyond window size; reduces hallucination by grounding in real code. *Cons:* Retrieval errors add “noise”; managing index updates and relevance is complex. (We detail retrieval methods in §4.)  

- **Tool-using Agents (ReAct-style):** The LLM is coupled with tools/APIs (search, compilers, docs) in a loop. For example, ReAct (Yao et al. 2023) interleaves *“Thought”* (chain-of-thought reasoning) and *“Action”* (tool calls) steps【16†L16-L24】【16†L28-L36】. The agent can query a search engine or compiler mid-reasoning. *Pros:* Models can verify steps via tools (e.g. run code/tests) and access outside knowledge. *Cons:* Orchestration overhead; requires engineering to parse tool I/O; risk of action loops.  

- **Chain-of-Thought (CoT) Prompting:** The prompt explicitly asks the LLM to “think step-by-step” (Wei et al. 2022). It remains a single forward pass, but the output includes intermediate reasoning. *Pros:* Can improve complex reasoning (e.g. multi-step code logic). *Cons:* Still limited to internal knowledge; no external grounding; can hallucinate across steps【16†L60-L68】.  

- **Reflexion / Reflection:** After an attempt, the agent “reflects” on its output (e.g. by checking with a compiler or unit tests, or by re-asking itself) and revises its plan. For example, **reflection-augmented planning** wraps an LLM in evaluation loops【11†L382-L386】. *Pros:* Enables iterative self-correction; error-driven refinement. *Cons:* More LLM queries; may still struggle with unseen errors.  

- **Modular Pipelines:** Complex tasks are decomposed into stages (e.g. retrieving relevant files → planning fixes → code generation → testing). Each stage may use a separate model call or system (e.g. one LLM for code search, one for generation). Microservices (data ingestion, AST parser, etc.) communicate via APIs【9†L124-L132】【9†L132-L140】. *Pros:* Clear separation of concerns; easier to maintain/scale; each module can be optimized separately. *Cons:* System complexity; latency overhead from multiple calls; error propagation between stages.  

**Pros and Cons Summary:** Table 1 compares these architectures.  

| Agent Type              | Description                                                         | Pros                                      | Cons                                          |
|-------------------------|---------------------------------------------------------------------|-------------------------------------------|-----------------------------------------------|
| Single-turn LLM         | One-shot prompt-driven completion                                    | Simple; stateless                         | Limited to context window; static knowledge   |
| Retrieval-Augmented     | Augments prompt with retrieved code/docs                            | Adds real project context; scalable       | Retrieval noise; index maintenance            |
| Tool-using (ReAct)      | Interleaved reasoning and tool (search/execute) steps               | External grounding (APIs, compilers); interpretable | Complex orchestration; dependency on tools  |
| Chain-of-Thought (CoT)  | Prompted to generate internal reasoning steps                       | Improves logical reasoning                | No external info; can hallucinate【16†L60-L68】 |
| Reflexion (Reflection)  | Self-evaluation loops (LLM reviews own output, re-prompts)          | Iterative self-correction                 | Extra compute; may not catch all errors       |
| Modular Pipeline        | Sequential stages (microservices, multi-LLM chain)                  | Clear structure; maintainable             | Higher latency; engineering overhead         |

**Implementation Notes:** In practice, many systems combine patterns: e.g. a RAG pipeline with CoT prompts, or a ReAct agent that uses chain-of-thought for each question. Tools like LangChain and AutoGen provide frameworks for such patterns【11†L431-L440】. 

## 2. Repository Access Patterns  
Agents must access and navigate large repositories. Common patterns include:  

- **File-level retrieval:** Simple search by file path or content (e.g. using `grep`/BM25) to find files or lines matching identifiers. Often a first pass. (E.g. exact *identifier matching* picks files where a class or function name appears【17†L336-L344】.)  

- **AST and Graph Access:** Parse code into an AST (abstract syntax tree) and extract structures (function/class definitions, call graph). Agents can query or traverse ASTs or control-flow graphs. For example, Tree-sitter or compiler front-ends allow programmatic queries (used in [25] “DKB” approach). Graph-based searches can follow `import` or call dependencies across files【17†L352-L360】.  

- **Semantic Indexes / Embeddings:** Represent code snippets as vectors (using models like CodeBERT, UniXcoder, etc.) and build a vector database. Retrieval is by vector similarity (dense retrieval)【17†L346-L355】. This can capture semantics beyond exact text. For example, *semantic search* can find functions with similar behavior.  

- **Commit History and PR Data:** Incorporate version control metadata. Commit messages, diffs, issue discussions and PR comments provide rationale and evolution of code. Agents (e.g. Code Researcher) explicitly retrieve relevant past commits into a “memory” when diagnosing bugs【20†L79-L87】. Issue trackers or PR comments can be parsed to understand the goal of changes.  

- **Tests and CI Artifacts:** Automated tests, coverage reports, and CI logs offer context. An agent might search for related unit tests or run the test suite. For instance, a fix-generation agent may run failing tests to locate bugs. While there is little published on automating this yet, it is a best practice to surface test code and results as part of context.  

- **Documentation and Comments:** Docstrings, README, and inline comments give semantic clues. These can be indexed or presented to the LLM alongside code. (HumanEval, for example, includes detailed docstrings guiding generation【38†L74-L81】.)  

- **CI/CD Metadata:** Build configuration (Dockerfiles, pipeline scripts) and deployment logs can inform environment constraints. These are rarely used by LLM agents yet but are part of complete repository context in theory.  

Implementation: Practically, one often pre-indexes the repository (file content, AST nodes, docs) into a search index (sparse and/or dense). Table 2 compares retrieval modalities:

| Retrieval Mode         | Example Techniques        | Pros                                           | Cons                        |
|------------------------|---------------------------|------------------------------------------------|-----------------------------|
| Identifier/Sparse (BM25) | Keyword search (grep, BM25)【17†L336-L344】  | Fast, well-understood; good for exact matches  | Misses semantic similarity  |
| Dense (Embeddings)     | Vector DB with code embeddings【17†L346-L355】 | Captures semantic similarity; flexible         | Needs pre-computed embeddings; may miss structure |
| AST/Graph-based        | Querying parsed AST/CPG; graph traversal【17†L352-L360】 | Captures structure and dependencies; good for multi-hop reasoning【25†L99-L107】 | Heavier indexing; brittle for dynamic code |
| Hybrid                | Combine above (lexical + vector + graph)【17†L359-L363】 | Balances recall/precision; more robust         | Complex to implement        |

Agents may combine methods (e.g. first file-level search, then vector search within those files, then graph queries on AST). Ensuring indices stay *fresh* (updated as code changes) is important for interactive dev environments.

## 3. Code Data Representations  
How code is represented affects retrieval and model input:

- **Raw Text / Tokens:** The simplest is plain source code (with or without comments). Tokenization (e.g. byte-pair encoding) breaks code into tokens. *Pros:* No transformation needed; all textual content (including identifiers, keywords) is available. *Cons:* Lacks explicit structure; very long files may exceed token limits.  

- **Abstract Syntax Trees (ASTs):** ASTs represent code syntax hierarchically. Some systems flatten ASTs into linear “paths” or trees for embedding【22†L53-L60】. AST-based chunks can be indexed or embedded. *Pros:* Encodes structural syntax; LLMs can in principle parse them easily. *Cons:* Requires a parser; abstracted from actual text so some details (formatting) are lost. (One study found LLMs excel at syntax parsing – behaving much like AST parsers【22†L53-L60】 – but struggle with semantics beyond syntax.)  

- **Code Graphs / Code Property Graphs (CPGs):** These include control-flow graphs, data-flow graphs, call graphs, or richer CPGs (e.g. Joern’s CPG) that merge AST+control flow+data flow. They encode cross-file relationships (function calls, inheritance, taints). *Pros:* Powerful for semantic queries (e.g. vulnerability analysis)【27†L60-L69】【27†L119-L127】. *Cons:* Complex to build; LLMs cannot directly ingest them without a translation layer. For example, Lekssays et al. (2026) integrate Joern’s CPG to provide slicing/taint tools to the LLM instead of raw graph queries【27†L146-L154】.  

- **Bytecode/Intermediate Code:** Representing compiled code (Java bytecode, .NET IL, Python bytecode) may help low-level analysis (e.g. security). Few LLM projects use this directly, since it’s hard for LLMs to read and it loses high-level context.  

- **Docstrings and Comments:** These natural-language annotations (function docstrings, inline comments) should be preserved. They often serve as pseudo-requirements. For example, each HumanEval problem includes a docstring describing the task【38†L74-L81】. *Pros:* Provide semantic cues to LLM. *Cons:* Quality depends on author; may be outdated or missing.  

- **Type Hints and Annotations:** In languages like Python or TypeScript, type annotations add static information. They can disambiguate and reduce errors. LLMs can use them to reason about expected data types.  

In sum, combining representations often works best: e.g. provide raw code lines with comments, supplemented by an AST-derived summary or graph features. Table 3 compares common representations:

| Representation      | Content                                     | Pros                                    | Cons                               |
|---------------------|---------------------------------------------|-----------------------------------------|------------------------------------|
| Raw Code (text)     | Source lines, tokens                         | Complete textual context; LLM-friendly  | No explicit structure; large size |
| Token Embeddings    | Vector embedding of code snippets【17†L346-L355】 | Captures semantic similarity           | Loses structure if isolated chunks |
| AST-based           | Parsed tree nodes, tokens (e.g., code2vec paths)【22†L53-L60】 | Syntax structured; LLMs mimic AST parsing | Hard to maintain alignment to source text |
| Control/Data Flow Graphs | Nodes (statements) + edges (flow)       | Captures runtime semantics; good for cross-file links | Complex to query; tool support needed |
| CPG (Joern)         | Combined AST+flow (e.g. CPG)【27†L60-L69】 | Powerful for security queries; tool-supported | Opaque to LLM; requires special tooling |
| Bytecode/IL        | Compiled code (Java .class, .NET IL)        | Low-level semantics, uniform syntax     | Hard for LLMs; contextually divorced |
| Docstrings/Comments | Natural-language descriptions in code      | Semantics/intent hints【38†L74-L81】     | May be incomplete or outdated      |
| Type Annotations   | Static types (Python hints, Java types)      | Clarifies usage; aids correctness       | Not present in all code; partial info |

## 4. Retrieval and Indexing Strategies  
Efficiently searching a large codebase requires indexing and chunking strategies:

- **Vector Databases:** Precompute embeddings for code chunks (functions, classes, sliding windows) using a code model (e.g. CodeBERT, GraphCodeBERT). Store these in a vector index (e.g. FAISS, Pinecone, Weaviate). At query time, embed the query and retrieve nearest neighbors. Dense retrieval excels when semantic relevance (not exact keyword match) is needed【17†L346-L355】. *Implementation:* Each file can be split into logical chunks (functions or N-token blocks) before embedding to fit model input limits. Embeddings should include metadata (file path, function name).  

- **Sparse Retrieval / Keyword Search:** Use traditional IR (TF-IDF, BM25) on code text or docs. This is fast and memory-light, and works well when precise terms (identifiers, error strings) are known【17†L336-L344】. Often used in tandem: first filter by keywords, then refine by embeddings.  

- **Hierarchical Retrieval:** Implement a multi-stage search. For instance, first retrieve relevant files or classes (coarse), then within those, retrieve specific functions or lines (fine). HCAG (2024) proposes building a **hierarchical semantic summary** of the repo (e.g. an architectural outline) so LLMs can retrieve *architectural knowledge*【31†L141-L149】. In practice, one might first retrieve by high-level topics (module descriptions), then drill down.  

- **Chunking Strategies:** Code must be divided into retrievable units. Strategies include: function-level (natural, but functions vary widely in length), fixed-size sliding windows (e.g. 512-token windows with overlap), or AST-based subtrees. Care is needed to preserve logical boundaries (don’t split a function in half) and to avoid overly large chunks that hit token limits.  

- **Metadata and Caching:** Store extra info with each chunk: language, module name, docstring snippet, commit timestamp. This enables filtering (e.g. only Python files, or only recent code). Caching recent queries or frequently accessed results (in-memory) can speed repetitive tasks (e.g. in an IDE).  

- **Freshness and Updates:** In dynamic projects, the index must update as code changes. Options include: periodic re-indexing (daily), incremental updates (on commit), or on-demand crawling. A freshness timestamp field helps agents prefer latest versions.  

**Trade-offs:** Vector indices handle semantic search but can miss the “latest” context if not refreshed. Sparse indices are instant but superficial. Hierarchical and hybrid methods (combining sparse + dense + graph) seek balanced recall/precision. Implementers often combine multiple backends (e.g. Elasticsearch + FAISS + custom graph queries) and fuse results. 

## 5. Context Window and Long-Range Solutions  
Codebases often exceed even extended LLM context lengths. Techniques to manage long-range context include:

- **Windowing / Chunking:** Divide the context (e.g. the repository) into chunks and only load the most relevant ones. For a given query, retrieve just those chunks that fit in the window. For iterative tasks, maintain a sliding window of active context.  

- **Retrieval-Augmented Generation (RAG):** Rather than pre-loading all context, the model issues retrieval queries as needed. Each generation step can trigger a new retrieval (like an “attention” to an external DB). Systems like MemLong (Liu et al. 2024) explicitly do this: store all past info in an external memory and retrieve relevant “key-value” pairs as additional input, effectively allowing up to ~80k token histories【33†L48-L57】【33†L114-L118】. This turns the long-range problem into many short-range retrievals.  

- **Memory Mechanisms:** Aside from a vector memory bank (as in MemLong), some agents use streaming memory (saving summaries of past context). For code, this might mean summarizing a file’s role or test results into a sentence and adding it to an “agent memory”. New LLMs (GPT-5 etc.) may have native memory features. 

- **Retrieval-Augmented Attention:** A variant where retrieval is integrated into the model’s attention mechanism. (MemLong’s “retrieval attention” is one example【33†L48-L57】.)  

- **Extended-Context LLMs:** Use models designed for long sequences (e.g. GPT-4o with 128K tokens, Claude with 100K+). These can directly process more code at once. However, cost grows and even 100K tokens may not cover a large repo.  

- **Summarization / Abstraction:** Pre-compute summaries of files or modules. For example, run an LLM to generate a one-paragraph summary or extract key points (functions, dependencies) of each file. Then use those summaries as proxies during retrieval (“look at file X: [summary]”). Code folding (like collapsing function bodies) in the prompt also compresses context.  

- **Tool-driven Exploration:** Rather than reading everything linearly, allow the agent to *query* the code (e.g. “show me the definition of class X”). Systems like codebadger provide high-level queries (e.g. “get_program_slice”) that extract minimal relevant snippets for the task【27†L146-L154】. This is akin to skipping irrelevant text.  

No single method suffices alone. In practice, a combination is used: an extended-context LLM for short-horizon tasks, retrieval and memory for long-horizon, and summarization to guide retrieval.  

## 6. Evaluation Metrics and Benchmarks  
Measuring agent performance requires varied benchmarks and metrics:

- **Benchmarks:**  
  - *CodeXGLUE* (2021): 10+ code intelligence tasks (clone detection, defect detection, code completion, summarization, translation, code search, etc.) across 14 datasets【49†L25-L33】. It is a broad suite for function/file-level tasks.  
  - *HumanEval* (OpenAI, 2021): 164 Python programming problems with unit tests【38†L21-L29】【38†L119-L124】. Focuses on functional correctness: code is correct if it passes all tests.  
  - *MBPP (Mostly Basic Programming Problems)*: ~974 short Python tasks targeting novice-level problems【40†L273-L281】. Used in “Program Synthesis with LLMs” (Austin et al. 2021).  
  - *CodeSearchNet* (Husain et al. 2019): Code–text retrieval benchmark (e.g. match NL queries to code snippets). Includes six languages.  
  - *Repo-level/CodeRepair Benchmarks*: Newer datasets evaluate multi-file reasoning. Example: **RepoFixEval** (ICLR’25): 160 real-world Python bugs with issue reports and unit tests【42†L32-L40】. It measures an agent’s ability to discover issues, localize faults, and generate fixes across files.  
  - *Others*: Code summarization (Docstring generation), mutation testing benchmarks, and company-specific datasets (often proprietary).  

- **Metrics:**  
  - **Functional Correctness (pass@k):** Used by HumanEval. If an agent generates *k* programs, pass@k is the fraction where at least one passes the tests【38†L119-L124】. This directly measures execution success.  
  - **Exact Match / BLEU / CodeBLEU:** String-based metrics comparing generated code to a reference. CodeBLEU (Zhang et al. 2020) extends BLEU for code by adding AST and data flow similarity. These capture partial overlap but can be gamed by trivial edits.  
  - **Test Coverage / Static Analysis:** For generated or fixed code, one can measure whether unit tests pass or if static type/checker warnings exist. For example, requiring “all unit tests pass” is a strict correctness criterion.  
  - **Precision/Recall/F1:** On tasks like clone detection or defect classification. E.g. CodeXGLUE uses F1 for clone detection and accuracy for defect detection【36†L774-L782】.  
  - **Developer-Centric Metrics:** Emerging proposals suggest metrics like developer satisfaction (surveys), time to complete a task, or maintainability scores. These are more subjective but arguably more realistic【48†L2252-L2260】.  

**Pros and Cons of Metrics:** Pass@k and test-based metrics measure real utility but require runnable code and tests (expensive). BLEU/CodeBLEU are easy but can reward semantically incorrect code. Clone/defect tasks use standard classification metrics. Real-world evaluation often combines multiple metrics.  

## 7. Optimization Techniques for Code Agents  
To improve agent performance on code tasks, one can apply ML and engineering optimizations:

- **Fine-tuning:** Continue training a pretrained model on code-specific corpora or tasks (e.g. GitHub code, LeetCode problems). In-domain fine-tuning improves accuracy (e.g., Codex was fine-tuned on code). *Notes:* Requires data licensing care.  

- **Instruction Tuning:** Finetune on “instructions + code” pairs so the model follows prompts better. Code-specific instruction datasets (e.g. HumanEval problems) can be used.  

- **Parameter-Efficient Tuning (LoRA, Adapters):** Instead of full fine-tuning, add low-rank adapters (LoRA) or adapter layers. This drastically reduces compute/storage. E.g. adding LoRA to a code LLM may tailor it to a project’s style.  

- **Distillation:** Train a smaller model to mimic a larger code model’s behavior. Speeds inference for embedded or on-device use. (For code, distillation must preserve correctness.)  

- **Prompt Engineering:** Design prompts to elicit the best performance. This includes chain-of-thought prompts, few-shot examples, or structured templates (function signatures and docstrings). E.g., adding an explicit docstring in the prompt helps guide generation【38†L74-L81】.  

- **Tool-Use and External Checks:** Integrate external tools into the prompt or pipeline. Example: *Toolformer* (Schick et al. 2023) augmented GPT with calls to external APIs. In code, an agent might run a compiler or linter on its output and feed results back into the model (like a self-check). CodeBadger provides built-in tools (slicing, taint tracking) so the model “calls” them rather than manually generating queries【27†L146-L154】. *Grounding via Tests:* One can integrate unit tests into the feedback loop (generate code, run tests, refine on failures). This has shown promise in research on self-debugging code LLMs.  

- **Chain-of-Thought Prompting:** Explicit reasoning prompts can be seen as an optimization. Empirically, reasoning prompts (like ReAct) improve performance on multi-step tasks (by breaking the problem down)【16†L90-L98】.  

- **Static Analysis Integration:** Use static analysis results as features or inputs. For instance, type errors or lint warnings can be included in the prompt to steer generation away from mistakes. CodeBadger’s approach (providing program slicing operations) is one example of integrating analysis into the agent loop【27†L146-L154】.  

Implementers must tune prompt length, example quality, sampling temperature, and tune memory bank parameters (for retrieval). Often, few-shot exemplars (especially unit-test-driven examples) are crucial for guiding the model on the desired output format.

## 8. Tooling and Integrations  
Effective code agents interoperate with existing developer tools:

- **Language Server Protocol (LSP):** A language server (e.g. PyLSP for Python, clangd for C/C++) provides APIs for code introspection (symbol definitions, references, completions, diagnostics). Agents can query an LSP to quickly locate code symbols or get type information. (Some projects like [44] are experimenting with LSP agents.)  

- **Static Analyzers:** Tools like linters (ESLint, PyLint), type checkers (mypy, TypeScript), and code scanners (Bandit, Flake8) detect issues. An agent can run these on generated code to catch errors, or treat them as “tools” in a ReAct loop. For example, CodeQL (GitHub) can answer codebase queries for vulnerabilities. 

- **Symbolic Execution / Formal Tools:** Engines like Z3 or KLEE can prove properties of code. In theory, an agent could use symbolic exec to validate a generated fix. E.g., when fixing an integer overflow, a symbolic tool could confirm that no overflow remains (akin to Lekssays et al. calling “find_bounds_checks”【27†L155-L163】). However, using these requires heavy integration and is still experimental.  

- **Test Runners:** Automated test frameworks (JUnit, pytest) should be callable by the agent. A common pattern: propose a code patch, run the test suite, and feed pass/fail feedback into the model for refinement. This “generate-and-verify” loop grounds the agent in functional correctness. 

- **Continuous Integration (CI) Pipelines:** Agents in practice might trigger CI jobs. For example, an agent updating dependencies could test in a container with real CI. Logging CI results (build failures, coverage drops) into the agent’s context helps assess patch viability. 

- **Version Control (Git) Interfaces:** Being aware of branches and commits is vital. Agents can invoke Git commands (like `git log`, `git diff`) to fetch context. For example, a prompt might include the diff from a failing build. Some platforms (AutoGen’s “MCP”) envision LLMs making API calls to version-control services.  

Integration notes: Many agent frameworks (LangChain, AutoGen, CrewAI) allow defining *tools* with function signatures. One typically wraps code search, file I/O, code execution, etc. as tools the LLM can call. Test runners and language servers can be integrated similarly.  

## 9. Privacy, Security, and Licensing Concerns  
LLM code agents raise significant legal and security issues:

- **Data Privacy:** Code often contains proprietary or sensitive data (secret keys, algorithms). Sending repo content to external LLM APIs risks leaks. Companies must use on-premise models or ensure data is encrypted/injected safely. Also, LLMs can unintentionally memorize training data; if private code was in the training set (or small corpora), it might appear in outputs.  

- **Security of Generated Code:** LLMs may produce insecure code (buffer overflows, injection flaws). Without static checking or sandboxing, a generated patch could introduce vulnerabilities. Agents should vet code with security analyzers. Moreover, adversarial inputs or malicious prompts could cause the LLM to execute unintended actions (prompt injection attacks).  

- **Intellectual Property / Licensing:** Many LLMs were trained on vast amounts of open-source code (e.g. on GitHub). They may *regurgitate* copyrighted code. Xu et al. (2024) found that even top LLMs can output code extremely similar to training data without attribution【46†L46-L53】. Crucially, they usually omit license notices. For example, code under GPL or Apache must include license text if reused. This poses compliance risk【46†L46-L53】【46†L79-L88】. Enterprises must audit LLM outputs for license conflicts, and some LLM providers offer “copyleft detection” tools.  

- **Model Security:** If an LLM or its tools are compromised, malicious code could be injected. Also, placing too much automation could concentrate risk (e.g. if one agent auto-merges PRs).  

- **Mitigations:** Always review LLM-suggested code as a human; treat LLM outputs as untrusted until verified. Use corpora that respect licenses for fine-tuning. Obfuscate or filter sensitive identifiers before external calls. Have strict access controls on any automated agent.  

## 10. Open Research Gaps and Future Directions  
Despite rapid progress, many challenges remain【48†L2209-L2218】【48†L2245-L2254】:

- **Multimodal Context:** Current agents primarily use text. Future work should fuse code with other modalities: design docs, UML diagrams, issue discussion threads, screenshots, or even audio notes. For example, [48] notes integrating architectural diagrams and logs could “significantly improve grounding” in complex tasks【48†L2209-L2218】.  

- **Graph-Agent Integration:** Rich code graphs (ASTs, CPGs) need tighter coupling with LLM reasoning. Agents that can navigate code graphs (e.g. to plan a cross-file change) are still experimental. Exploring interactive agents that *walk* the call graph or dependency graph, invoking LLM at key nodes, is an open area【48†L2216-L2224】.  

- **Memory-Efficient Long Context:** Even with RAG, reasoning over entire repos is hard. Future architectures (sparse attention, hierarchical transformers) and better summarization (file/module sketches) are needed【48†L2223-L2231】. MemLong-style retrieval-augmented attention is promising but largely untested on code.  

- **Multilingual Repositories:** Projects often mix languages (e.g. Python backend, JavaScript frontend, SQL, etc.). Agents must seamlessly query heterogeneous code. Cross-language models and universal schemas (e.g. graph ontologies) are underexplored【48†L2230-L2238】.  

- **Coordinated Multi-file Editing:** Tasks like migrating a library or refactoring across many modules require planning a series of dependent edits. Recent work (e.g. CodePlan) starts to address this, but benchmarks and methods are scarce. [48] calls for focusing on “repository-wide coordinated editing” (package migration, API changes)【48†L2237-L2245】.  

- **Realistic Benchmarks:** Most benchmarks still use isolated tasks. There is a need for *system-level* evaluation (e.g. complete bug triage/fix from issue report, end-to-end code review) that mirror developer workflows【48†L2245-L2254】.  

- **Holistic Metrics:** Beyond pass@k, future metrics should measure integration: code compilability, performance regressions, compliance with style guides, or developer acceptance. [48] suggests metrics like integration-test pass rates and static-analysis success to better reflect “true value”【48†L2252-L2260】.  

- **Retrieval-Generation Coupling:** Bridging IR-based and generation paradigms is core to RAG’s promise. How to make retrieved artifacts *dynamically inform* generation (e.g. constrain generation paths) is largely open【48†L2259-L2268】.  

In summary, advancing LLM code agents will involve interdisciplinary research, combining NLP, software engineering, security, and human factors. The literature points to many promising directions, but robust, general-purpose solutions are still in development.

## 11. Comparative Tables  

**Table 1: Agent Architectures (see §1)** already shown above.  

**Table 2: Retrieval/Indexing Methods (see §2-4)**  

| Retrieval/Index Method    | Example Use Case                                    | Pros                                  | Cons                                  |
|---------------------------|-----------------------------------------------------|---------------------------------------|---------------------------------------|
| **Identifier Matching**   | Find files containing a known function/class name【17†L336-L344】 | Extremely fast; high precision if term is unique | Misses synonyms; no semantic match      |
| **Sparse Search (BM25)**  | Keyword search in code/comments【17†L336-L344】    | Well-understood; index is small       | No sense of meaning; vulnerable to irrelevant hits |
| **Dense Retrieval (Embeddings)** | Semantic code search using CodeBERT【17†L346-L355】 | Finds conceptually similar code; robust to wording changes | Requires heavy indexing; less interpretable |
| **Graph-based Retrieval** | AST or call-graph query (e.g. find callers of X)【25†L99-L107】 | Captures precise structural relations | Complex implementation; language-specific |
| **Hybrid**                | Combine BM25 + embeddings + AST          | Balances recall/precision             | Increased system complexity            |
| **Hierarchical**          | Multi-stage: module → file → snippet【31†L141-L149】 | Efficient for very large codebases    | Needs curated hierarchy or summaries  |

**Table 3: Data Representations (see §3)**  

| Representation          | Example/Tool                   | Pros                                          | Cons                                          |
|-------------------------|--------------------------------|-----------------------------------------------|-----------------------------------------------|
| Raw code text          | LLM prompt                     | Full context; any language features present    | Unstructured; context window limits            |
| Tokenized code (BPE)   | CodeLlama tokenizer           | LLM-native representation; captures identifiers | Limited token budget; semantic relations implicit |
| AST paths             | code2vec, CodeBERT (uses AST) | Explicit syntax; tree structure                | Must flatten or serialize for model            |
| Control/Data Graphs   | Code property graph (Joern)   | Encodes program semantics (flows, deps)        | Not directly LLM-readable; tooling required    |
| Bytecode/IR          | Java bytecode, LLVM IR        | Language-neutral semantics for some tasks      | Hard to interpret; often too low-level         |
| Docstrings/Comments    | HumanEval problems【38†L74-L81】 | Human-readable intent, guides generation      | Variable quality; may not exist                |
| Type Annotations      | Python typing, TS/Flow types  | Adds semantic constraints                     | Partial coverage; not in all languages         |

**Table 4: Evaluation Benchmarks**  

| Benchmark       | Year | Tasks / Focus                             | Metrics                                | References |
|-----------------|------|-------------------------------------------|----------------------------------------|------------|
| CodeXGLUE       | 2021 | 10 tasks: clone, defect, completion, summarization, translation, search, etc. | F1 (clone), Acc (defect), BLEU/Exact (NLP-type tasks)【49†L25-L33】 | [49], [36] |
| HumanEval       | 2021 | 164 Python code generation problems (function completion) | pass@k (functional correctness)【38†L119-L124】 | [38] |
| MBPP            | 2021 | ~974 Python programming problems (algorithmic) | Exact match / pass@k                  | [40] |
| CodeSearchNet   | 2019 | Code–text retrieval (six languages)       | MRR, Recall@k                          | (Husain et al.) |
| RepoFixEval     | 2024 | 160 real-world Python bugs (multi-file APR)【42†L32-L40】 | Fix success rate (patch compiles & tests pass) | [42] |
| Others (todo)   | –    | E.g. CodeDefect, SE benchmarks (e.g. kBench) | Various (accuracy, BLEU, etc.)         | – |

## 12. Experimental Plan and Best Practices  
**Goal:** Evaluate LLM agents on realistic code tasks.  

- **Models:** Use both closed-source (e.g. GPT-4o, Claude-Code, Google Gemini) and open LLMs (CodeLlama, StarCoder, Qwen) as baselines. Consider fine-tuned versions (e.g. Codex) if available.  

- **Tasks & Datasets:**  
  - *Small scope:* HumanEval, MBPP for basic generation metrics.  
  - *Repo-scale:* RepoFixEval (bug-fixing), or an in-house dataset of issues/PRs.  
  - *Code search:* CodeSearchNet or a custom codebase with queries.  
  - *Comprehension:* Questions about code behavior (could simulate e.g. “What does this module do?”).  
  - *Mixed tasks:* end-to-end workflows (e.g. answer a bug report by proposing code changes and running tests).  

- **Metrics:** Combine: pass@k (functional correctness)【38†L119-L124】, CodeBLEU, exact-match on small tasks; static analysis (error count) on generated code; execution-based metrics (test pass rates); and user-centric metrics (time to task completion, qualitative quality).  

- **Baseline vs. Variants:** Compare (a) plain LLM prompt (with code context in prompt if fits), (b) RAG pipeline (retrieve relevant code chunks then prompt), (c) Agentic loop (ReAct with search and exec tools), and (d) retrieval+chain-of-thought vs retrieval only. Also compare with/without memory (e.g. MemLong).  

- **Ablation Studies:**  
  - **Retrieval Method:** Try sparse vs dense vs hybrid retrieval for context.  
  - **Representation:** Feed raw code vs AST summaries vs graph queries.  
  - **Context Window:** Vary how much of the repo is given (simulate small vs large repos).  
  - **Tool Use:** With vs without static analysis or test-run feedback.  
  - **Prompt Style:** CoT vs direct prompts; with/without relevant examples.  

- **Procedure:** For code generation tasks, automatically check compilability and run unit tests for functional correctness. Track metrics like success rate and time taken. For code search, measure hit-rate or rank of true answer. For comprehension/QA, use human or heuristic evaluation (if possible).  

- **Reporting:** Report metrics for each configuration. Use tables and charts to compare strategies. Analyze failure cases qualitatively (e.g. hallucinated code, missed dependencies).  

- **Reproducibility:** Open-source all prompts, retrieval settings, and evaluation scripts.  

Adhering to recent literature, ensure any fine-tuned or LLMs and training data comply with licenses【46†L46-L53】.  

# Appendix A — Source List

This appendix deduplicates the original 39 inline citations into a clean source list.

## Primary sources

1. **A First Look at License Compliance Capability of LLMs in Code Generation**  
   URL: https://arxiv.org/html/2408.02487v1  
   Original citation numbers: 1, 2

2. **Retrieval-Augmented Code Generation: A Survey with Focus on Repository-Level Approaches**  
   URL: https://arxiv.org/html/2510.04905v1  
   Original citation numbers: 3, 4, 5, 6, 7, 8, 9, 17, 18, 37, 38, 39

3. **Reliable Graph-RAG for Codebases: AST-Derived Graphs vs LLM-Extracted Knowledge Graphs**  
   URL: https://arxiv.org/html/2601.08773v1  
   Original citation numbers: 21

4. **LLMs: Understanding Code Syntax and Semantics for Code Analysis**  
   URL: https://arxiv.org/pdf/2305.12138  
   Original citation numbers: 22

5. **Bridging Code Property Graphs and Language Models for Program Analysis**  
   URL: https://arxiv.org/html/2603.24837v1  
   Original citation numbers: 23, 24, 25, 36

6. **HCAG: Hierarchical Abstraction and Retrieval-Augmented Generation on Theoretical Repositories with LLMs**  
   URL: https://arxiv.org/html/2603.20299v1  
   Original citation numbers: 26

7. **MemLong: Memory-Augmented Retrieval for Long Text Modeling**  
   URL: https://arxiv.org/html/2408.16967v1  
   Original citation numbers: 27, 28

8. **CodeXGLUE: A Machine Learning Benchmark Dataset for Code Understanding and Generation**  
   URL: https://arxiv.org/pdf/2102.04664  
   Original citation numbers: 29, 34

9. **ReAct: Synergizing Reasoning and Acting in Language Models**  
   URL: https://ar5iv.labs.arxiv.org/html/2210.03629  
   Original citation numbers: 10, 11, 12, 35

10. **RepoFixEval: A Repository-Level Program Repair Benchmark From Issue Discovering to Bug Fixing**  
    URL: https://openreview.net/forum?id=LaNCeNmoHR  
    Original citation numbers: 33

## Benchmarks, documentation, and supporting material

11. **What Is HumanEval?**  
    Publisher: IBM  
    URL: https://www.ibm.com/think/topics/humaneval  
    Original citation numbers: 20, 30, 31

12. **Basic Programming Problems (MBPP) — lm-evaluation-harness README**  
    Publisher: GitHub / EleutherAI  
    URL: https://github.com/EleutherAI/lm-evaluation-harness/blob/main/lm_eval/tasks/mbpp/README.md  
    Original citation numbers: 32

13. **Code Researcher** *(title inferred from PDF filename)*  
    Publisher: Microsoft Research  
    URL: https://www.microsoft.com/en-us/research/wp-content/uploads/2025/06/Code_Researcher-1.pdf  
    Original citation numbers: 19

## Secondary / contextual source

14. **AI Design Patterns: Engineering Modular ML Pipelines and Agentic Systems**  
    Author: Riddhi Shah  
    Publisher: Medium  
    URL: https://medium.com/@shahriddhi717/ai-design-patterns-engineering-modular-ml-pipelines-and-agentic-systems-c5f9f7ca29db  
    Original citation numbers: 13, 14, 15, 16