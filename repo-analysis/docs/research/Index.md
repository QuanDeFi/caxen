# Research Index

Topical index for the research documents in this folder.

Think of each research document as a chapter:

- use the **Chapter Key** to map shorthand like `R6` to a file
- use the **Topic Index** to jump to the documents most relevant to a subject

## Chapter Key

- `R1`: [Research 1.md](Research%201.md) - broad survey of repository agents, retrieval, benchmarks, optimization, tooling, and best practices
- `R2`: [Research 2.md](Research%202.md) - embeddings, where they help, where they fail, and how they should fit into the system
- `R3`: [Research 3.md](Research%203.md) - parser-first indexing, graph index, hybrid retrieval, summaries, and selective retrieval
- `R4`: [Research 4.md](Research%204.md) - why conventional methods stop scaling and what a structured stack should look like
- `R5`: [Research 5.md](Research%205.md) - retrieval noise, structural signals, staged retrieval, and gating
- `R6`: [Research 6.md](Research%206.md) - academic-source-only design memo, literature map, architecture implications, and evaluation rubric
- `R7`: [Research 7.md](Research%207.md) - retrieval quality, long-horizon memory, anti-memorization benchmarks, and execution-aware feature understanding
- `R8`: [Research 8.md](Research%208.md) - structure-aware retrieval, dependency-preserving compression, exploration policy, and change-impact analysis
- `R9`: [Research 9.md](Research%209.md) - minimal-sufficient evidence, utilization metrics, project-state memory, feature reasoning, and evaluation
- `R10`: [Research 10.md](Research%2010.md) - multi-view graphs, set-level evidence utility, traversal policy, and execution grounding
- `R11`: [Research 11.md](Research%2011.md) - sufficiency estimators, utilization-aware attribution, repository-native memory, execution evidence compression, and evaluation
- `R12`: [Research 12.md](Research%2012.md) - graph schema ablations, set-level utility, traversal policies, and execution-aware ranking
- `R13`: [Research 13.md](Research%2013.md) - sufficiency, project memory, attribution, execution-derived signals, and process-aware evaluation
- `R14`: [Research 14.md](Research%2014.md) - control-theory framing and cost-aware sequential decision making for repo agents
- `R15`: [Research 15.md](Research%2015.md) - latest evidence-control synthesis: sufficiency, attribution, memory, execution signals, and harder evaluation
- `RSrc`: [Research Sources.md](Research%20Sources.md) - source bibliography for the research set
- `RSum`: [Research Summaries.md](Research%20Summaries.md) - per-source summaries aligned to `Research Sources.md`
- `RLog`: [Research Change Log.md](Research%20Change%20Log.md) - maintenance history for the research folder

## Topic Index

### A

- `Agent architectures and reasoning patterns`: `R1`, `R6`, `R14`
- `Artifact-level attribution`: `R11`, `R13`, `R15`

### B

- `Benchmarks, repository-level`: `R1`, `R6`, `R7`, `R9`, `R11`, `R13`, `R15`, `RSrc`, `RSum`
- `Build/test/environment grounding`: `R10`, `R12`, `R15`

### C

- `Change-impact analysis`: `R8`, `R10`, `RSrc`, `RSum`
- `Chunk retrieval, limits of flat chunking`: `R3`, `R4`, `R5`
- `Coarse-to-fine retrieval`: `R3`, `R4`, `R5`
- `Compression and pruning`: `R4`, `R7`, `R8`, `R13`, `R15`
- `Context sufficiency`: `R7`, `R9`, `R11`, `R13`, `R14`, `R15`
- `Context utilization`: `R7`, `R9`, `R11`, `R13`, `R15`
- `Control theory / sequential decision`: `R14`

### D

- `Dependency-preserving compression`: `R8`, `R13`

### E

- `Embeddings`: `R2`, `R3`, `R4`
- `Evaluation, leakage-resistant`: `R7`, `R9`, `R11`, `R13`, `R15`
- `Evaluation, process-aware`: `R9`, `R11`, `R13`, `R15`
- `Evidence coalitions / set-level utility`: `R10`, `R12`, `R14`, `R15`
- `Evidence retrieval, minimal-sufficient`: `R9`, `R11`, `R13`, `R15`
- `Execution-aware ranking`: `R10`, `R12`
- `Execution-derived intermediate signals`: `R11`, `R13`, `R15`

### F

- `Feature-level reasoning / feature development`: `R7`, `R9`, `R15`

### G

- `Graph indexing`: `R1`, `R3`, `R4`, `R10`, `R12`
- `Graph propagation`: `R5`
- `Graph schema ablations`: `R10`, `R12`
- `Graph traversal policy`: `R10`, `R12`, `R14`

### H

- `Hierarchical summaries`: `R3`, `R4`, `R6`
- `History / commit signals`: `R3`, `R7`, `R11`, `R13`
- `Hybrid retrieval`: `R3`, `R4`, `R5`, `R6`

### I

- `Impact-driven filtering`: `R8`, `R10`, `R12`, `R13`, `R15`

### L

- `Licensing, privacy, and security`: `R1`
- `Long-horizon project memory`: `R7`, `R9`, `R11`, `R13`, `R15`

### M

- `Memory, repository-native`: `R11`, `R13`, `R15`
- `Multi-view graphs`: `R10`, `R12`, `R14`

### P

- `Parser-first indexing`: `R3`, `R4`, `R6`
- `Planning and exploration`: `R1`, `R6`, `R8`, `R10`, `R12`, `R14`

### Q

- `Query planning / retrieval planning`: `R1`, `R6`, `R14`

### R

- `Reranking`: `R1`, `R5`, `R6`, `R10`, `R12`
- `Research bibliography`: `RSrc`, `RSum`
- `Research maintenance history`: `RLog`
- `Retrieval gating / selective retrieval`: `R3`, `R4`, `R5`, `R6`, `R13`, `R15`
- `Retrieval noise`: `R5`

### S

- `Structure-aware retrieval`: `R5`, `R8`, `R10`, `R12`
- `Sufficiency estimation`: `R11`, `R13`, `R14`, `R15`
- `Summaries, source-by-source`: `RSum`
- `Symbol indexing`: `R3`, `R4`

### T

- `Token efficiency`: `R2`, `R6`, `R8`, `R13`, `R15`
- `Topic roadmap / future directions`: `R1`, `R6`, `R7`, `R8`, `R10`, `R11`, `R12`, `R13`, `R14`, `R15`

### U

- `Utilization-aware attribution`: `R11`, `R13`, `R15`

## Fast Paths

- `Current system design`: `R3`, `R4`, `R5`, `R6`, `R10`, `R14`, `R15`
- `Memory and long-horizon work`: `R7`, `R9`, `R11`, `R13`, `R15`
- `Execution-grounded repo understanding`: `R7`, `R9`, `R10`, `R11`, `R12`, `R13`, `R15`
- `Evaluation design and benchmark quality`: `R6`, `R7`, `R9`, `R11`, `R13`, `R15`
