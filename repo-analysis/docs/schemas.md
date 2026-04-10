# Schemas

## Raw Inventory Schemas

The first milestone produces two JSON documents per upstream repo.

## `manifest.json`

High-level shape:

```json
{
  "schema_version": "0.1.0",
  "repo": "carbon",
  "generated_at": "2026-04-10T12:00:00Z",
  "source": {
    "path": "/abs/path/to/repo",
    "git_ref": "commit",
    "git_branch": "branch-or-detached",
    "git_remote": "origin-url",
    "expected_ref": "origin/v1.0-rc"
  },
  "language_mix": [
    {
      "language": "Rust",
      "files": 100,
      "bytes": 123456
    }
  ],
  "file_inventory": {
    "tracked_files": 1000,
    "directories": 120,
    "by_extension": [
      {
        "extension": ".rs",
        "files": 800,
        "bytes": 987654
      }
    ],
    "largest_files": [
      {
        "path": "crates/runtime/src/lib.rs",
        "size": 12000
      }
    ]
  },
  "module_graph_seeds": {
    "analysis_surfaces": ["crates", "examples"],
    "workspace_manifests": ["Cargo.toml"],
    "crate_roots": ["crates/runtime"],
    "package_roots": [],
    "source_roots": ["crates/runtime/src"],
    "entrypoints": ["crates/runtime/src/lib.rs"]
  },
  "dependency_manifests": [
    {
      "path": "Cargo.toml",
      "kind": "cargo-workspace"
    }
  ],
  "test_commands": ["cargo test --workspace"],
  "build_commands": ["cargo build --workspace"],
  "parser_relevant_source_roots": ["crates/runtime/src"],
  "notes": ["repo-specific note"]
}
```

## `repo_map.json`

High-level shape:

```json
{
  "schema_version": "0.1.0",
  "repo": "yellowstone-vixen",
  "generated_at": "2026-04-10T12:00:00Z",
  "directories": [
    {
      "path": "crates/runtime",
      "depth": 2
    }
  ],
  "files": [
    {
      "path": "crates/runtime/src/lib.rs",
      "size": 1234,
      "extension": ".rs",
      "language": "Rust",
      "generated": false
    }
  ],
  "probable_package_roots": [
    {
      "path": "crates/runtime",
      "manifest": "crates/runtime/Cargo.toml",
      "kind": "cargo-package"
    }
  ],
  "crate_boundaries": [
    {
      "path": "crates/runtime",
      "manifest": "crates/runtime/Cargo.toml"
    }
  ],
  "generated_code_markers": [],
  "test_directories": ["tests", "examples/filtered-pipeline/tests"]
}
```

## Compatibility Notes

- The schemas are intentionally JSON-first for portability onto the RPC node.
- They are conservative and parser-agnostic.
- Later parser/symbol/graph stages should extend these artifacts rather than replace them.
