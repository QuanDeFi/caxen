from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

from common.inventory import is_generated_path
from parsers.rust import ParsedRustFile, TextSpan, parse_rust_file


PACKAGE_NAME_RE = re.compile(r'^\s*name\s*=\s*"([^"]+)"\s*$', re.M)
PACKAGE_BLOCK_RE = re.compile(r"\[package\](.*?)(?:\n\[|$)", re.S)


def build_symbol_index(
    repo_name: str,
    repo_root: Path,
    raw_root: Path,
    path_prefixes: Sequence[str] = (),
) -> Dict[str, object]:
    manifest = load_raw_manifest(raw_root, repo_name)
    parser_roots = manifest.get("parser_relevant_source_roots", [])
    rust_files = discover_rust_files(repo_root, parser_roots, normalize_prefixes(path_prefixes))
    package_cache: Dict[Path, Tuple[Path, str]] = {}
    parsed_files = [parse_rust_source_file(repo_root, path, package_cache) for path in rust_files]

    file_records: List[Dict[str, object]] = []
    import_records: List[Dict[str, object]] = []
    symbol_records: List[Dict[str, object]] = []

    for parsed in parsed_files:
        file_records.append(
            {
                "path": parsed.path,
                "crate": parsed.crate_name,
                "module_path": parsed.module_path,
                "language": "Rust",
                "symbols": len(parsed.symbols),
                "imports": len(parsed.imports),
            }
        )

        local_to_symbol_id = {
            symbol.local_id: stable_id(
                "sym",
                repo_name,
                parsed.path,
                symbol.kind,
                symbol.qualified_name,
                str(symbol.span.start_line),
                str(symbol.span.start_column),
            )
            for symbol in parsed.symbols
        }

        for symbol in parsed.symbols:
            symbol_records.append(
                {
                    "symbol_id": local_to_symbol_id[symbol.local_id],
                    "repo": repo_name,
                    "path": parsed.path,
                    "crate": parsed.crate_name,
                    "module_path": symbol.module_path,
                    "language": "Rust",
                    "kind": symbol.kind,
                    "name": symbol.name,
                    "qualified_name": symbol.qualified_name,
                    "span": span_to_dict(symbol.span),
                    "signature": symbol.signature,
                    "docstring": symbol.docstring,
                    "visibility": symbol.visibility,
                    "container_symbol_id": local_to_symbol_id.get(symbol.container_local_id),
                    "container_qualified_name": symbol.container_qualified_name,
                    "statement_id": None,
                    "scope_symbol_id": None,
                    "reference_target_symbol_id": None,
                    "attributes": list(symbol.attributes),
                    "is_test": symbol.is_test,
                    "impl_target": symbol.impl_target,
                    "impl_trait": symbol.impl_trait,
                }
            )

        for rust_import in parsed.imports:
            import_records.append(
                {
                    "import_id": stable_id(
                        "imp",
                        repo_name,
                        parsed.path,
                        rust_import.path,
                        str(rust_import.span.start_line),
                        str(rust_import.span.start_column),
                    ),
                    "repo": repo_name,
                    "path": parsed.path,
                    "crate": parsed.crate_name,
                    "module_path": rust_import.module_path,
                    "language": "Rust",
                    "visibility": rust_import.visibility,
                    "signature": rust_import.signature,
                    "target": rust_import.path,
                    "span": span_to_dict(rust_import.span),
                    "container_symbol_id": local_to_symbol_id.get(rust_import.container_local_id),
                    "container_qualified_name": rust_import.container_qualified_name,
                }
            )

    kind_counts = rollup_counts(item["kind"] for item in symbol_records)

    return {
        "schema_version": "0.2.0",
        "repo": repo_name,
        "generated_at": timestamp_now(),
        "parser": "rust-simple-v1",
        "source_roots": parser_roots,
        "path_prefixes": list(normalize_prefixes(path_prefixes)),
        "files": file_records,
        "symbols": symbol_records,
        "imports": import_records,
        "summary": {
            "rust_files": len(file_records),
            "symbols": len(symbol_records),
            "imports": len(import_records),
            "kind_counts": kind_counts,
        },
    }


def discover_rust_files(repo_root: Path, parser_roots: Iterable[str], path_prefixes: Sequence[str]) -> List[Path]:
    candidates = []
    seen = set()

    for parser_root in parser_roots:
        absolute_root = repo_root / parser_root
        if not absolute_root.exists():
            continue
        for path in sorted(absolute_root.rglob("*.rs")):
            relative_path = path.relative_to(repo_root).as_posix()
            if relative_path in seen:
                continue
            if is_generated_path(relative_path):
                continue
            if path_prefixes and not matches_path_prefix(relative_path, path_prefixes):
                continue
            seen.add(relative_path)
            candidates.append(path)

    return sorted(candidates, key=lambda item: item.relative_to(repo_root).as_posix())


def load_cargo_package_name(manifest_path: Path) -> str:
    text = manifest_path.read_text(encoding="utf-8")
    block_match = PACKAGE_BLOCK_RE.search(text)
    if block_match:
        name_match = PACKAGE_NAME_RE.search(block_match.group(1))
        if name_match:
            return name_match.group(1)
    return manifest_path.parent.name


def load_raw_manifest(raw_root: Path, repo_name: str) -> Dict[str, object]:
    manifest_path = raw_root / repo_name / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(
            f"Missing raw inventory manifest for {repo_name}: {manifest_path}. Run parse-repos first."
        )
    with manifest_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def matches_path_prefix(relative_path: str, path_prefixes: Sequence[str]) -> bool:
    return any(
        relative_path == prefix or relative_path.startswith(f"{prefix}/")
        for prefix in path_prefixes
    )


def nearest_cargo_package(file_path: Path, repo_root: Path, cache: Dict[Path, Tuple[Path, str]]) -> Tuple[Path, str]:
    current = file_path.parent
    while True:
        manifest_path = current / "Cargo.toml"
        if manifest_path.exists():
            if manifest_path not in cache:
                cache[manifest_path] = (current, load_cargo_package_name(manifest_path))
            return cache[manifest_path]
        if current == repo_root:
            break
        current = current.parent
    return repo_root, repo_root.name


def normalize_prefixes(path_prefixes: Sequence[str]) -> Tuple[str, ...]:
    return tuple(
        sorted(
            {
                prefix.strip().lstrip("./").rstrip("/")
                for prefix in path_prefixes
                if prefix and prefix.strip().lstrip("./").rstrip("/")
            }
        )
    )


def parse_rust_source_file(
    repo_root: Path,
    source_path: Path,
    package_cache: Dict[Path, Tuple[Path, str]],
) -> ParsedRustFile:
    crate_root, crate_name = nearest_cargo_package(source_path, repo_root, package_cache)
    module_path = derive_module_path(crate_name, source_path, crate_root)
    relative_path = source_path.relative_to(repo_root).as_posix()
    source = source_path.read_text(encoding="utf-8")
    return parse_rust_file(relative_path, source, crate_name, module_path)


def derive_module_path(crate_name: str, source_path: Path, crate_root: Path) -> str:
    source_root = crate_root / "src"
    base_name = crate_name.replace("-", "_")

    if source_path.is_relative_to(source_root):
        relative = source_path.relative_to(source_root)
    else:
        relative = source_path.relative_to(crate_root)

    parts = list(relative.parts)
    if not parts:
        return base_name

    filename = parts[-1]
    if filename in {"lib.rs", "main.rs", "mod.rs"}:
        parts = parts[:-1]
    else:
        parts[-1] = Path(filename).stem

    normalized_parts = [base_name]
    normalized_parts.extend(part.replace("-", "_") for part in parts)
    return "::".join(part for part in normalized_parts if part)


def rollup_counts(values: Iterable[str]) -> List[Dict[str, object]]:
    counts: Dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return [
        {
            "kind": kind,
            "count": count,
        }
        for kind, count in sorted(counts.items(), key=lambda item: (item[0]))
    ]


def span_to_dict(span: TextSpan) -> Dict[str, int]:
    return {
        "start_line": span.start_line,
        "start_column": span.start_column,
        "end_line": span.end_line,
        "end_column": span.end_column,
    }


def stable_id(prefix: str, *parts: str) -> str:
    payload = "|".join(parts).encode("utf-8")
    return f"{prefix}:{hashlib.sha1(payload).hexdigest()[:16]}"


def timestamp_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def write_symbol_index(output_root: Path, repo_name: str, payload: Dict[str, object]) -> None:
    repo_output = output_root / repo_name
    repo_output.mkdir(parents=True, exist_ok=True)
    target = repo_output / "symbols.json"
    with target.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=False)
        handle.write("\n")
