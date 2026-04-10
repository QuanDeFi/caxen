# Summaries

## Current Summary Artifacts

`src/summaries/builder.py` writes deterministic JSON summaries under `data/summaries/<repo>/`.

Files:

- `project.json`
- `directories.json`
- `files.json`
- `symbols.json`
- `summary_manifest.json`

## Summary Levels

Project summary includes:

- repo focus
- analysis surfaces
- parser-relevant roots
- build/test commands
- language mix
- high-level symbol counts

Directory summaries include:

- descendant file counts
- Rust file counts
- indexed symbol counts
- public symbol counts
- heuristic tags

File summaries include:

- crate and module path
- symbol and import counts
- top public symbols
- heuristic tags

Symbol summaries include:

- qualified name
- path and visibility
- container information
- incoming and outgoing graph edge counts

## Current Limitations

- summaries are deterministic rollups, not model-generated prose
- summaries do not currently refresh incrementally
- local-variable and statement-level summarization is not specialized yet
