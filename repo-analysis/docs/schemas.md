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

## Parsed Symbol Schema

The first Phase 3 slice writes `data/parsed/<repo>/symbols.json`.

High-level shape:

```json
{
  "schema_version": "0.2.0",
  "repo": "yellowstone-vixen",
  "generated_at": "2026-04-10T12:00:00Z",
  "parser": "rust-simple-v1",
  "source_roots": ["crates/proc-macro/src"],
  "path_prefixes": ["crates/proc-macro/src/lib.rs"],
  "files": [
    {
      "path": "crates/proc-macro/src/lib.rs",
      "crate": "yellowstone-vixen-proc-macro",
      "module_path": "yellowstone_vixen_proc_macro",
      "language": "Rust",
      "symbols": 7,
      "imports": 2
    }
  ],
  "symbols": [
    {
      "symbol_id": "sym:abc123",
      "repo": "yellowstone-vixen",
      "path": "crates/proc-macro/src/lib.rs",
      "crate": "yellowstone-vixen-proc-macro",
      "module_path": "yellowstone_vixen_proc_macro",
      "language": "Rust",
      "kind": "function",
      "name": "vixen",
      "qualified_name": "yellowstone_vixen_proc_macro::vixen",
      "span": {
        "start_line": 23,
        "start_column": 8,
        "end_line": 28,
        "end_column": 2
      },
      "signature": "pub fn vixen(attr: TokenStream, item: TokenStream) -> TokenStream {",
      "docstring": null,
      "visibility": "pub",
      "container_symbol_id": null,
      "container_qualified_name": null,
      "statement_id": null,
      "scope_symbol_id": null,
      "reference_target_symbol_id": null,
      "attributes": ["proc_macro_attribute"],
      "is_test": false,
      "impl_target": null,
      "impl_trait": null
    }
  ],
  "imports": [
    {
      "import_id": "imp:def456",
      "repo": "yellowstone-vixen",
      "path": "crates/proc-macro/src/lib.rs",
      "crate": "yellowstone-vixen-proc-macro",
      "module_path": "yellowstone_vixen_proc_macro",
      "language": "Rust",
      "visibility": "private",
      "signature": "use proc_macro::TokenStream;",
      "target": "proc_macro::TokenStream",
      "span": {
        "start_line": 1,
        "start_column": 1,
        "end_line": 1,
        "end_column": 30
      },
      "container_symbol_id": null,
      "container_qualified_name": null
    }
  ],
  "summary": {
    "rust_files": 1,
    "symbols": 7,
    "imports": 2,
    "kind_counts": [
      {
        "kind": "function",
        "count": 2
      }
    ]
  }
}
```

## Graph Schema

The first Phase 3 slice writes `data/graph/<repo>/graph.json`.

High-level shape:

```json
{
  "schema_version": "0.1.0",
  "repo": "yellowstone-vixen",
  "generated_at": "2026-04-10T12:00:00Z",
  "nodes": [
    {
      "node_id": "repo:abc123",
      "kind": "repository",
      "repo": "yellowstone-vixen",
      "name": "yellowstone-vixen"
    },
    {
      "node_id": "file:def456",
      "kind": "file",
      "repo": "yellowstone-vixen",
      "path": "crates/proc-macro/src/lib.rs",
      "crate": "yellowstone-vixen-proc-macro",
      "module_path": "yellowstone_vixen_proc_macro",
      "language": "Rust"
    }
  ],
  "edges": [
    {
      "edge_id": "edge:ghi789",
      "type": "DEFINES",
      "from": "file:def456",
      "to": "sym:jkl012",
      "metadata": {
        "path": "crates/proc-macro/src/lib.rs"
      }
    }
  ],
  "summary": {
    "nodes": 11,
    "edges": 10
  }
}
```

## Phase 3 Notes

- The current parser is intentionally deterministic and Rust-only.
- The current graph is structural rather than fully semantic.
- Future phases can add higher-fidelity parsers and richer graph edges without replacing the JSON-first contract.
