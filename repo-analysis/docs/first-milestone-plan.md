# First Milestone Plan

## Goal

Turn the workspace from a documented scaffold into a commit-worthy first milestone that can be resumed on the RPC node.

## Scope

- harden workspace bootstrap and submodule verification
- document the current architecture and JSON schemas for raw repo inventory
- implement Phase 2 inventory adapters for:
  - `carbon`
  - `yellowstone-vixen`
- expose a CLI-driven `parse-repos` flow
- add tests for the first inventory slice

## Explicitly Out Of Scope

- parser-first symbol extraction
- graph construction
- lexical or vector retrieval
- summary generation
- benchmark execution beyond inventory validation

## Deliverables

- trustworthy `bootstrap.sh` and `sync_repos.sh`
- `parse_repos.sh` backed by Python code instead of a TODO stub
- `manifest.json` and `repo_map.json` outputs under `data/raw/<repo>/`
- initial architecture/schema docs that describe the implemented slice
- a short RPC-node handoff note

## Rationale

This gives the project a durable base:

- upstream repos stay intact
- the shared analysis layer gets a real executable starting point
- the next machine can resume from normalized inventory rather than from scratch
