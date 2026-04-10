from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import DefaultDict, Dict, Iterable, List, Optional, Sequence, Tuple

from common.inventory import is_generated_path
from parsers.rust import (
    ParsedRustFile,
    RustSymbol,
    TextSpan,
    clean_rust_source_lines,
    parse_rust_file,
)


CALL_EXPR_RE = re.compile(
    r"(?<![A-Za-z0-9_])"
    r"(?P<expr>(?:crate|super|Self|[A-Za-z_][A-Za-z0-9_]*)(?:::[A-Za-z_][A-Za-z0-9_]*)*)"
    r"\s*(?:::<[^()\n]*>)?\s*\("
)
FIELD_RE = re.compile(
    r"^\s*(?P<vis>pub(?:\([^)]*\))?\s+)?(?P<name>[a-z_][A-Za-z0-9_]*)\s*:\s*.+?(?:,\s*)?$"
)
GENERIC_ANGLE_RE = re.compile(r"<[^<>]*>")
LET_RE = re.compile(r"\blet\s+(?:mut\s+)?(?P<name>[a-z_][A-Za-z0-9_]*)\b")
PACKAGE_NAME_RE = re.compile(r'^\s*name\s*=\s*"([^"]+)"\s*$', re.M)
PACKAGE_BLOCK_RE = re.compile(r"\[package\](.*?)(?:\n\[|$)", re.S)
PATH_TOKEN_RE = re.compile(
    r"(?<![A-Za-z0-9_])"
    r"(?P<expr>(?:crate|super|Self|[A-Za-z_][A-Za-z0-9_]*)(?:::[A-Za-z_][A-Za-z0-9_]*)*)"
    r"(?![A-Za-z0-9_])"
)
QUALIFIED_PATH_RE = re.compile(
    r"(?<![A-Za-z0-9_])"
    r"(?P<expr>(?:crate|super|Self|[A-Za-z_][A-Za-z0-9_]*)(?:::[A-Za-z_][A-Za-z0-9_]*)+)"
    r"(?![A-Za-z0-9_])"
)
VARIANT_RE = re.compile(
    r"^\s*(?P<name>[A-Z][A-Za-z0-9_]*)\b(?:\s*(?:\(|\{|=|,|$).*)?$"
)

FUNCTION_LIKE_KINDS = {"function", "method"}
KEYWORDS = {
    "Self",
    "as",
    "async",
    "await",
    "break",
    "const",
    "continue",
    "crate",
    "dyn",
    "else",
    "enum",
    "extern",
    "false",
    "fn",
    "for",
    "if",
    "impl",
    "in",
    "let",
    "loop",
    "match",
    "mod",
    "move",
    "mut",
    "pub",
    "ref",
    "return",
    "self",
    "static",
    "struct",
    "super",
    "trait",
    "true",
    "type",
    "union",
    "unsafe",
    "use",
    "where",
    "while",
}
PRIMITIVE_TYPES = {
    "bool",
    "char",
    "f32",
    "f64",
    "i8",
    "i16",
    "i32",
    "i64",
    "i128",
    "isize",
    "str",
    "u8",
    "u16",
    "u32",
    "u64",
    "u128",
    "usize",
}


@dataclass
class ParsedFileContext:
    parsed: ParsedRustFile
    source: str
    source_lines: List[str]
    cleaned_lines: List[str]
    crate_root: str
    symbol_id_by_local: Dict[int, str]
    import_aliases: Dict[str, List[str]]


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
    contexts = [parse_rust_source_file(repo_root, path, package_cache) for path in rust_files]

    for context in contexts:
        enrich_context_symbols(context)

    file_records: List[Dict[str, object]] = []
    symbol_records: List[Dict[str, object]] = []
    context_by_path = {context.parsed.path: context for context in contexts}

    for context in contexts:
        context.symbol_id_by_local = {
            symbol.local_id: stable_id(
                "sym",
                repo_name,
                context.parsed.path,
                symbol.kind,
                symbol.qualified_name,
                str(symbol.span.start_line),
                str(symbol.span.start_column),
            )
            for symbol in context.parsed.symbols
        }
        file_records.append(
            {
                "path": context.parsed.path,
                "crate": context.parsed.crate_name,
                "module_path": context.parsed.module_path,
                "language": "Rust",
                "symbols": len(context.parsed.symbols),
                "imports": len(context.parsed.imports),
            }
        )
        for symbol in context.parsed.symbols:
            symbol_records.append(symbol_to_record(repo_name, context, symbol))

    resolution_index = build_resolution_index(symbol_records)
    import_records = build_import_records(repo_name, contexts, resolution_index)
    resolve_impl_symbols(symbol_records, context_by_path, resolution_index)
    reference_records = build_reference_records(repo_name, contexts, resolution_index)

    kind_counts = rollup_counts(item["kind"] for item in symbol_records)
    reference_kind_counts = rollup_counts(item["kind"] for item in reference_records)

    return {
        "schema_version": "0.3.0",
        "repo": repo_name,
        "generated_at": timestamp_now(),
        "parser": "rust-simple-v2",
        "source_roots": parser_roots,
        "path_prefixes": list(normalize_prefixes(path_prefixes)),
        "files": file_records,
        "symbols": symbol_records,
        "imports": import_records,
        "references": reference_records,
        "summary": {
            "rust_files": len(file_records),
            "symbols": len(symbol_records),
            "imports": len(import_records),
            "references": len(reference_records),
            "kind_counts": kind_counts,
            "reference_kind_counts": reference_kind_counts,
        },
    }


def build_import_records(
    repo_name: str,
    contexts: Sequence[ParsedFileContext],
    resolution_index: Dict[str, object],
) -> List[Dict[str, object]]:
    import_records: List[Dict[str, object]] = []

    for context in contexts:
        context.import_aliases = {}
        for rust_import in context.parsed.imports:
            expanded_targets = expand_use_targets(rust_import.path)
            if not expanded_targets:
                expanded_targets = [(rust_import.path, None)]

            for expanded_target, alias in expanded_targets:
                normalized_target = normalize_path_expression(
                    expanded_target,
                    context.parsed.module_path,
                    context.crate_root,
                    {},
                    None,
                )
                alias_name = alias or normalized_target.split("::")[-1]
                if alias_name:
                    context.import_aliases.setdefault(alias_name, [])
                    if normalized_target not in context.import_aliases[alias_name]:
                        context.import_aliases[alias_name].append(normalized_target)

                resolved_symbol = resolve_expression(
                    expanded_target,
                    {
                        "crate": context.parsed.crate_name,
                        "module_path": context.parsed.module_path,
                        "path": context.parsed.path,
                        "container_qualified_name": rust_import.container_qualified_name,
                    },
                    resolution_index,
                    context.import_aliases,
                    context.crate_root,
                    None,
                    None,
                )

                import_records.append(
                    {
                        "import_id": stable_id(
                            "imp",
                            repo_name,
                            context.parsed.path,
                            expanded_target,
                            str(rust_import.span.start_line),
                            str(rust_import.span.start_column),
                            alias or "",
                        ),
                        "repo": repo_name,
                        "path": context.parsed.path,
                        "crate": context.parsed.crate_name,
                        "module_path": rust_import.module_path,
                        "language": "Rust",
                        "visibility": rust_import.visibility,
                        "signature": rust_import.signature,
                        "raw_target": rust_import.path,
                        "target": expanded_target,
                        "normalized_target": normalized_target,
                        "alias": alias,
                        "span": span_to_dict(rust_import.span),
                        "container_symbol_id": context.symbol_id_by_local.get(rust_import.container_local_id),
                        "container_qualified_name": rust_import.container_qualified_name,
                        "target_symbol_id": resolved_symbol["target_symbol_id"],
                        "target_qualified_name": resolved_symbol["target_qualified_name"],
                        "target_kind": resolved_symbol["target_kind"],
                    }
                )

    return import_records


def build_reference_records(
    repo_name: str,
    contexts: Sequence[ParsedFileContext],
    resolution_index: Dict[str, object],
) -> List[Dict[str, object]]:
    reference_records: Dict[str, Dict[str, object]] = {}

    for context in contexts:
        symbol_records = {
            context.symbol_id_by_local[symbol.local_id]: symbol_to_record(repo_name, context, symbol)
            for symbol in context.parsed.symbols
        }
        for symbol in symbol_records.values():
            if symbol["kind"] not in FUNCTION_LIKE_KINDS and symbol["kind"] not in {"struct", "enum", "trait", "field"}:
                continue

            self_target = infer_self_target(symbol, resolution_index)

            for candidate, line_number, column in extract_signature_reference_candidates(
                symbol["signature"],
                symbol["name"],
                symbol["span"]["start_line"],
            ):
                resolved = resolve_expression(
                    candidate,
                    symbol,
                    resolution_index,
                    context.import_aliases,
                    context.crate_root,
                    symbol["symbol_id"],
                    self_target,
                )
                add_reference_record(
                    reference_records,
                    repo_name,
                    symbol,
                    kind="use",
                    candidate=candidate,
                    line_number=line_number,
                    column=column,
                    resolved=resolved,
                )

            if symbol["kind"] not in FUNCTION_LIKE_KINDS:
                continue

            call_positions = set()
            for candidate, line_number, column in extract_body_call_candidates(
                context.cleaned_lines,
                symbol["span"],
            ):
                call_positions.add((candidate, line_number, column))
                resolved = resolve_expression(
                    candidate,
                    symbol,
                    resolution_index,
                    context.import_aliases,
                    context.crate_root,
                    symbol["symbol_id"],
                    self_target,
                )
                add_reference_record(
                    reference_records,
                    repo_name,
                    symbol,
                    kind="call",
                    candidate=candidate,
                    line_number=line_number,
                    column=column,
                    resolved=resolved,
                )

            for candidate, line_number, column in extract_body_use_candidates(
                context.cleaned_lines,
                symbol["span"],
            ):
                if (candidate, line_number, column) in call_positions:
                    continue
                resolved = resolve_expression(
                    candidate,
                    symbol,
                    resolution_index,
                    context.import_aliases,
                    context.crate_root,
                    symbol["symbol_id"],
                    self_target,
                )
                add_reference_record(
                    reference_records,
                    repo_name,
                    symbol,
                    kind="use",
                    candidate=candidate,
                    line_number=line_number,
                    column=column,
                    resolved=resolved,
                )

    return sorted(reference_records.values(), key=lambda item: (item["path"], item["span"]["start_line"], item["kind"], item["name"]))


def build_resolution_index(symbol_records: Sequence[Dict[str, object]]) -> Dict[str, object]:
    by_id: Dict[str, Dict[str, object]] = {}
    by_qname: Dict[str, Dict[str, object]] = {}
    by_name: DefaultDict[str, List[Dict[str, object]]] = defaultdict(list)
    locals_by_scope: DefaultDict[str, DefaultDict[str, List[Dict[str, object]]]] = defaultdict(lambda: defaultdict(list))

    for symbol in symbol_records:
        by_id[symbol["symbol_id"]] = symbol
        by_qname.setdefault(symbol["qualified_name"], symbol)
        by_name[symbol["name"]].append(symbol)
        if symbol["kind"] == "local" and symbol["scope_symbol_id"]:
            locals_by_scope[symbol["scope_symbol_id"]][symbol["name"]].append(symbol)

    return {
        "by_id": by_id,
        "by_qname": by_qname,
        "by_name": by_name,
        "locals_by_scope": locals_by_scope,
    }


def resolve_impl_symbols(
    symbol_records: Sequence[Dict[str, object]],
    context_by_path: Dict[str, ParsedFileContext],
    resolution_index: Dict[str, object],
) -> None:
    for symbol in symbol_records:
        if symbol["kind"] != "impl":
            continue

        context = context_by_path[symbol["path"]]
        impl_target = resolve_expression(
            symbol["impl_target"],
            symbol,
            resolution_index,
            context.import_aliases,
            context.crate_root,
            symbol["symbol_id"],
            None,
        )
        impl_trait = resolve_expression(
            symbol["impl_trait"],
            symbol,
            resolution_index,
            context.import_aliases,
            context.crate_root,
            symbol["symbol_id"],
            None,
        )

        symbol["resolved_impl_target_symbol_id"] = impl_target["target_symbol_id"]
        symbol["resolved_impl_target_qualified_name"] = impl_target["target_qualified_name"]
        symbol["resolved_impl_trait_symbol_id"] = impl_trait["target_symbol_id"]
        symbol["resolved_impl_trait_qualified_name"] = impl_trait["target_qualified_name"]


def resolve_expression(
    expression: Optional[str],
    current_symbol: Dict[str, object],
    resolution_index: Dict[str, object],
    import_aliases: Dict[str, List[str]],
    crate_root: str,
    scope_symbol_id: Optional[str],
    self_target: Optional[str],
) -> Dict[str, Optional[str]]:
    if not expression:
        return empty_resolution()

    candidate = strip_expression_noise(expression)
    if not candidate or candidate in KEYWORDS or candidate in PRIMITIVE_TYPES:
        return empty_resolution()

    if scope_symbol_id and "::" not in candidate:
        local_matches = resolution_index["locals_by_scope"].get(scope_symbol_id, {}).get(candidate, [])
        if len(local_matches) == 1:
            local_symbol = local_matches[0]
            return {
                "target_symbol_id": local_symbol["symbol_id"],
                "target_qualified_name": local_symbol["qualified_name"],
                "target_kind": local_symbol["kind"],
                "qualified_name_hint": local_symbol["qualified_name"],
            }

    preferred_paths = expand_reference_candidates(
        candidate,
        current_symbol["module_path"],
        crate_root,
        import_aliases,
        self_target,
    )

    for preferred_path in preferred_paths:
        exact_match = resolution_index["by_qname"].get(preferred_path)
        if exact_match:
            return {
                "target_symbol_id": exact_match["symbol_id"],
                "target_qualified_name": exact_match["qualified_name"],
                "target_kind": exact_match["kind"],
                "qualified_name_hint": preferred_path,
            }

    simple_name = candidate.split("::")[-1]
    candidates = resolution_index["by_name"].get(simple_name, [])
    best_match = pick_best_symbol_candidate(
        candidates,
        preferred_paths,
        current_symbol,
        self_target,
    )
    if best_match:
        return {
            "target_symbol_id": best_match["symbol_id"],
            "target_qualified_name": best_match["qualified_name"],
            "target_kind": best_match["kind"],
            "qualified_name_hint": best_match["qualified_name"],
        }

    return {
        "target_symbol_id": None,
        "target_qualified_name": preferred_paths[0] if preferred_paths else candidate,
        "target_kind": None,
        "qualified_name_hint": preferred_paths[0] if preferred_paths else candidate,
    }


def enrich_context_symbols(context: ParsedFileContext) -> None:
    normalize_method_qualified_names(context)
    extract_struct_fields(context)
    extract_enum_variants(context)
    extract_local_variables(context)


def normalize_method_qualified_names(context: ParsedFileContext) -> None:
    symbols_by_local = {symbol.local_id: symbol for symbol in context.parsed.symbols}

    for symbol in context.parsed.symbols:
        if symbol.kind != "method" or symbol.container_local_id is None:
            continue
        container = symbols_by_local.get(symbol.container_local_id)
        if not container:
            continue

        if container.kind == "impl" and container.impl_target:
            owner = normalize_path_expression(
                container.impl_target,
                symbol.module_path,
                context.crate_root,
                {},
                None,
            )
            if owner:
                symbol.qualified_name = f"{owner}::{symbol.name}"
        elif container.kind == "trait":
            symbol.qualified_name = f"{container.qualified_name}::{symbol.name}"


def extract_struct_fields(context: ParsedFileContext) -> None:
    next_local_id = next_symbol_local_id(context.parsed.symbols)
    for symbol in list(context.parsed.symbols):
        if symbol.kind != "struct":
            continue
        for line_number in range(symbol.span.start_line + 1, symbol.span.end_line):
            raw_line = context.source_lines[line_number - 1]
            cleaned_line = context.cleaned_lines[line_number - 1]
            stripped = cleaned_line.strip()
            if not stripped or stripped.startswith("#") or stripped.startswith("//"):
                continue
            match = FIELD_RE.match(cleaned_line)
            if not match:
                continue
            field_name = match.group("name")
            context.parsed.symbols.append(
                RustSymbol(
                    local_id=next_local_id,
                    kind="field",
                    name=field_name,
                    qualified_name=f"{symbol.qualified_name}::{field_name}",
                    module_path=symbol.module_path,
                    span=TextSpan(
                        start_line=line_number,
                        start_column=raw_line.find(field_name) + 1,
                        end_line=line_number,
                        end_column=len(raw_line.rstrip()) + 1,
                    ),
                    signature=cleaned_line.strip(),
                    visibility=normalize_visibility(match.group("vis")),
                    docstring=None,
                    container_local_id=symbol.local_id,
                    container_qualified_name=symbol.qualified_name,
                    is_test=symbol.is_test,
                )
            )
            next_local_id += 1


def extract_enum_variants(context: ParsedFileContext) -> None:
    next_local_id = next_symbol_local_id(context.parsed.symbols)
    for symbol in list(context.parsed.symbols):
        if symbol.kind != "enum":
            continue
        for line_number in range(symbol.span.start_line + 1, symbol.span.end_line):
            raw_line = context.source_lines[line_number - 1]
            cleaned_line = context.cleaned_lines[line_number - 1]
            stripped = cleaned_line.strip()
            if not stripped or stripped.startswith("#") or stripped in {"{", "}"}:
                continue
            match = VARIANT_RE.match(cleaned_line)
            if not match:
                continue
            variant_name = match.group("name")
            context.parsed.symbols.append(
                RustSymbol(
                    local_id=next_local_id,
                    kind="variant",
                    name=variant_name,
                    qualified_name=f"{symbol.qualified_name}::{variant_name}",
                    module_path=symbol.module_path,
                    span=TextSpan(
                        start_line=line_number,
                        start_column=raw_line.find(variant_name) + 1,
                        end_line=line_number,
                        end_column=len(raw_line.rstrip()) + 1,
                    ),
                    signature=cleaned_line.strip().rstrip(","),
                    visibility="public",
                    docstring=None,
                    container_local_id=symbol.local_id,
                    container_qualified_name=symbol.qualified_name,
                    is_test=symbol.is_test,
                )
            )
            next_local_id += 1


def extract_local_variables(context: ParsedFileContext) -> None:
    next_local_id = next_symbol_local_id(context.parsed.symbols)
    for symbol in list(context.parsed.symbols):
        if symbol.kind not in FUNCTION_LIKE_KINDS:
            continue
        seen_locals: set[Tuple[int, str]] = set()
        for line_number in range(symbol.span.start_line, symbol.span.end_line + 1):
            raw_line = context.source_lines[line_number - 1]
            cleaned_line = context.cleaned_lines[line_number - 1]
            for match in LET_RE.finditer(cleaned_line):
                local_name = match.group("name")
                local_key = (line_number, local_name)
                if local_key in seen_locals:
                    continue
                seen_locals.add(local_key)
                context.parsed.symbols.append(
                    RustSymbol(
                        local_id=next_local_id,
                        kind="local",
                        name=local_name,
                        qualified_name=f"{symbol.qualified_name}::{local_name}@L{line_number}",
                        module_path=symbol.module_path,
                        span=TextSpan(
                            start_line=line_number,
                            start_column=match.start("name") + 1,
                            end_line=line_number,
                            end_column=match.end("name") + 1,
                        ),
                        signature=raw_line.strip(),
                        visibility="private",
                        docstring=None,
                        container_local_id=symbol.local_id,
                        container_qualified_name=symbol.qualified_name,
                        is_test=symbol.is_test,
                    )
                )
                next_local_id += 1


def add_reference_record(
    reference_records: Dict[str, Dict[str, object]],
    repo_name: str,
    symbol: Dict[str, object],
    kind: str,
    candidate: str,
    line_number: int,
    column: int,
    resolved: Dict[str, Optional[str]],
) -> None:
    qualified_name_hint = resolved["qualified_name_hint"] or candidate
    if qualified_name_hint == symbol["qualified_name"]:
        return

    reference_id = stable_id(
        "ref",
        repo_name,
        symbol["path"],
        symbol["symbol_id"],
        kind,
        qualified_name_hint,
        str(line_number),
    )
    reference_records[reference_id] = {
        "reference_id": reference_id,
        "repo": repo_name,
        "path": symbol["path"],
        "crate": symbol["crate"],
        "module_path": symbol["module_path"],
        "language": symbol["language"],
        "kind": kind,
        "name": candidate.split("::")[-1],
        "qualified_name_hint": qualified_name_hint,
        "span": {
            "start_line": line_number,
            "start_column": column,
            "end_line": line_number,
            "end_column": column + len(candidate),
        },
        "container_symbol_id": symbol["symbol_id"],
        "container_qualified_name": symbol["qualified_name"],
        "scope_symbol_id": symbol["symbol_id"] if symbol["kind"] in FUNCTION_LIKE_KINDS else symbol["scope_symbol_id"],
        "target_symbol_id": resolved["target_symbol_id"],
        "target_qualified_name": resolved["target_qualified_name"] or qualified_name_hint,
        "target_kind": resolved["target_kind"],
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


def expand_reference_candidates(
    expression: str,
    module_path: str,
    crate_root: str,
    import_aliases: Dict[str, List[str]],
    self_target: Optional[str],
) -> List[str]:
    candidates: List[str] = []
    expr = strip_expression_noise(expression)
    if not expr:
        return candidates

    if expr == "Self" and self_target:
        return [self_target]

    if "::" not in expr:
        for alias_target in import_aliases.get(expr, []):
            candidates.append(alias_target)
        if self_target and expr[:1].islower():
            candidates.append(f"{self_target}::{expr}")
        candidates.append(f"{module_path}::{expr}")
        if expr[:1].isupper():
            candidates.append(f"{crate_root}::{expr}")
        candidates.append(expr)
        return unique_values(candidates)

    if expr.startswith("Self::") and self_target:
        candidates.append(f"{self_target}{expr[4:]}")
    elif expr.startswith("crate::"):
        candidates.append(f"{crate_root}{expr[5:]}")
    elif expr.startswith("super::"):
        current = module_path
        remainder = expr
        while remainder.startswith("super::"):
            current = current.rsplit("::", 1)[0] if "::" in current else crate_root
            remainder = remainder[len("super::") :]
        candidates.append(f"{current}::{remainder}")

    first_segment, _, remainder = expr.partition("::")
    if first_segment in import_aliases:
        for alias_target in import_aliases[first_segment]:
            candidate = alias_target
            if remainder:
                candidate = f"{alias_target}::{remainder}"
            candidates.append(candidate)

    candidates.append(expr)
    return unique_values(normalize_path_expression(candidate, module_path, crate_root, {}, self_target) for candidate in candidates if candidate)


def expand_use_targets(target: str) -> List[Tuple[str, Optional[str]]]:
    value = target.strip().rstrip(";")
    if not value:
        return []

    base, alias = split_top_level_alias(value)
    brace_open, brace_close = find_top_level_braces(base)
    if brace_open is None or brace_close is None:
        return [(collapse_whitespace(base), alias)]

    prefix = base[:brace_open].strip().rstrip(":")
    inner = base[brace_open + 1 : brace_close]
    suffix = base[brace_close + 1 :].strip()
    expanded: List[Tuple[str, Optional[str]]] = []

    for part in split_top_level(inner):
        if not part:
            continue
        if part == "self":
            candidate = prefix
        else:
            joiner = "::" if prefix else ""
            candidate = f"{prefix}{joiner}{part}"
        if suffix:
            candidate = f"{candidate}{suffix}"
        expanded.extend(expand_use_targets(candidate))

    return expanded


def extract_body_call_candidates(
    cleaned_lines: Sequence[str],
    span: Dict[str, int],
) -> List[Tuple[str, int, int]]:
    candidates: List[Tuple[str, int, int]] = []
    for line_number in range(span["start_line"], span["end_line"] + 1):
        cleaned_line = cleaned_lines[line_number - 1]
        for match in CALL_EXPR_RE.finditer(cleaned_line):
            expression = strip_expression_noise(match.group("expr"))
            if expression in KEYWORDS or expression in PRIMITIVE_TYPES:
                continue
            candidates.append((expression, line_number, match.start("expr") + 1))
    return unique_positioned_values(candidates)


def extract_body_use_candidates(
    cleaned_lines: Sequence[str],
    span: Dict[str, int],
) -> List[Tuple[str, int, int]]:
    candidates: List[Tuple[str, int, int]] = []
    for line_number in range(span["start_line"], span["end_line"] + 1):
        cleaned_line = cleaned_lines[line_number - 1]
        for match in QUALIFIED_PATH_RE.finditer(cleaned_line):
            expression = strip_expression_noise(match.group("expr"))
            if expression in KEYWORDS:
                continue
            candidates.append((expression, line_number, match.start("expr") + 1))
    return filter_shadowed_simple_tokens(unique_positioned_values(candidates))


def extract_signature_reference_candidates(
    signature: str,
    symbol_name: str,
    line_number: int,
) -> List[Tuple[str, int, int]]:
    candidates: List[Tuple[str, int, int]] = []
    for match in PATH_TOKEN_RE.finditer(signature):
        expression = strip_expression_noise(match.group("expr"))
        if not expression or expression == symbol_name:
            continue
        if expression in KEYWORDS or expression in PRIMITIVE_TYPES:
            continue
        if "::" not in expression and not expression[:1].isupper() and expression != "Self":
            continue
        candidates.append((expression, line_number, match.start("expr") + 1))
    return filter_shadowed_simple_tokens(unique_positioned_values(candidates))


def find_top_level_braces(value: str) -> Tuple[Optional[int], Optional[int]]:
    depth = 0
    open_index: Optional[int] = None
    for index, char in enumerate(value):
        if char == "{":
            if depth == 0:
                open_index = index
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0 and open_index is not None:
                return open_index, index
    return None, None


def infer_self_target(symbol: Dict[str, object], resolution_index: Dict[str, object]) -> Optional[str]:
    container_symbol_id = symbol.get("container_symbol_id")
    if not container_symbol_id:
        return None

    container_symbol = resolution_index["by_id"].get(container_symbol_id)
    if not container_symbol or container_symbol["kind"] != "impl":
        return None

    return (
        container_symbol.get("resolved_impl_target_qualified_name")
        or container_symbol.get("impl_target")
        or container_symbol.get("qualified_name")
    )


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


def next_symbol_local_id(symbols: Sequence[RustSymbol]) -> int:
    return max((symbol.local_id for symbol in symbols), default=0) + 1


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


def normalize_path_expression(
    expression: str,
    module_path: str,
    crate_root: str,
    import_aliases: Dict[str, List[str]],
    self_target: Optional[str],
) -> str:
    expr = strip_expression_noise(expression)
    if not expr:
        return ""

    if expr == "Self" and self_target:
        return self_target
    if expr.startswith("Self::") and self_target:
        return f"{self_target}{expr[4:]}"
    if expr.startswith("crate::"):
        return f"{crate_root}{expr[5:]}"
    if expr.startswith("super::"):
        current = module_path
        remainder = expr
        while remainder.startswith("super::"):
            current = current.rsplit("::", 1)[0] if "::" in current else crate_root
            remainder = remainder[len("super::") :]
        return f"{current}::{remainder}"

    first_segment, _, remainder = expr.partition("::")
    if first_segment in import_aliases and import_aliases[first_segment]:
        target = import_aliases[first_segment][0]
        return f"{target}::{remainder}" if remainder else target

    if "::" not in expr and expr[:1].isupper():
        return f"{module_path}::{expr}"
    return expr


def normalize_visibility(value: Optional[str]) -> str:
    return value.strip() if value else "private"


def parse_rust_source_file(
    repo_root: Path,
    source_path: Path,
    package_cache: Dict[Path, Tuple[Path, str]],
) -> ParsedFileContext:
    crate_root, crate_name = nearest_cargo_package(source_path, repo_root, package_cache)
    module_path = derive_module_path(crate_name, source_path, crate_root)
    relative_path = source_path.relative_to(repo_root).as_posix()
    source = source_path.read_text(encoding="utf-8")
    source_lines = source.splitlines()
    parsed = parse_rust_file(relative_path, source, crate_name, module_path)
    return ParsedFileContext(
        parsed=parsed,
        source=source,
        source_lines=source_lines,
        cleaned_lines=clean_rust_source_lines(source),
        crate_root=module_path.split("::")[0],
        symbol_id_by_local={},
        import_aliases={},
    )


def pick_best_symbol_candidate(
    candidates: Sequence[Dict[str, object]],
    preferred_paths: Sequence[str],
    current_symbol: Dict[str, object],
    self_target: Optional[str],
) -> Optional[Dict[str, object]]:
    best_candidate = None
    best_score = None
    tie = False
    preferred = set(preferred_paths)

    for candidate in candidates:
        score = 0
        if candidate["qualified_name"] in preferred:
            score += 100
        if candidate["crate"] == current_symbol["crate"]:
            score += 20
        if candidate["path"] == current_symbol["path"]:
            score += 15
        if candidate["module_path"] == current_symbol["module_path"]:
            score += 15
        if candidate["qualified_name"].startswith(f"{current_symbol['module_path']}::"):
            score += 10
        if current_symbol.get("container_qualified_name") and candidate["qualified_name"].startswith(
            f"{current_symbol['container_qualified_name']}::"
        ):
            score += 25
        if self_target and candidate["qualified_name"].startswith(f"{self_target}::"):
            score += 25
        if candidate["name"] == current_symbol["name"]:
            score -= 5

        if best_score is None or score > best_score:
            best_candidate = candidate
            best_score = score
            tie = False
        elif score == best_score:
            tie = True

    if tie or best_score is None or best_score <= 0:
        return None
    return best_candidate


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


def empty_resolution() -> Dict[str, Optional[str]]:
    return {
        "target_symbol_id": None,
        "target_qualified_name": None,
        "target_kind": None,
        "qualified_name_hint": None,
    }


def span_to_dict(span: TextSpan) -> Dict[str, int]:
    return {
        "start_line": span.start_line,
        "start_column": span.start_column,
        "end_line": span.end_line,
        "end_column": span.end_column,
    }


def split_top_level(value: str) -> List[str]:
    depth = 0
    current: List[str] = []
    items: List[str] = []

    for char in value:
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
        elif char == "," and depth == 0:
            item = "".join(current).strip()
            if item:
                items.append(item)
            current = []
            continue
        current.append(char)

    tail = "".join(current).strip()
    if tail:
        items.append(tail)
    return items


def split_top_level_alias(value: str) -> Tuple[str, Optional[str]]:
    depth = 0
    for index in range(len(value) - 1):
        char = value[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
        elif depth == 0 and value[index : index + 4] == " as ":
            return value[:index].strip(), value[index + 4 :].strip()
    return value, None


def stable_id(prefix: str, *parts: str) -> str:
    payload = "|".join(parts).encode("utf-8")
    return f"{prefix}:{hashlib.sha1(payload).hexdigest()[:16]}"


def strip_expression_noise(expression: str) -> str:
    value = collapse_whitespace(expression)
    previous = None
    while previous != value:
        previous = value
        value = GENERIC_ANGLE_RE.sub("", value)

    value = value.replace("&", " ").replace("*", " ")
    value = re.sub(r"\b(?:dyn|impl|mut|ref)\b", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value.strip(",;(){}[] ")


def symbol_to_record(repo_name: str, context: ParsedFileContext, symbol: RustSymbol) -> Dict[str, object]:
    scope_symbol_id = context.symbol_id_by_local.get(symbol.container_local_id) if symbol.kind == "local" else None
    return {
        "symbol_id": context.symbol_id_by_local[symbol.local_id],
        "repo": repo_name,
        "path": context.parsed.path,
        "crate": context.parsed.crate_name,
        "module_path": symbol.module_path,
        "language": "Rust",
        "kind": symbol.kind,
        "name": symbol.name,
        "qualified_name": symbol.qualified_name,
        "span": span_to_dict(symbol.span),
        "signature": symbol.signature,
        "docstring": symbol.docstring,
        "visibility": symbol.visibility,
        "container_symbol_id": context.symbol_id_by_local.get(symbol.container_local_id),
        "container_qualified_name": symbol.container_qualified_name,
        "statement_id": None,
        "scope_symbol_id": scope_symbol_id,
        "reference_target_symbol_id": None,
        "attributes": list(symbol.attributes),
        "is_test": symbol.is_test,
        "impl_target": symbol.impl_target,
        "impl_trait": symbol.impl_trait,
        "resolved_impl_target_symbol_id": None,
        "resolved_impl_target_qualified_name": None,
        "resolved_impl_trait_symbol_id": None,
        "resolved_impl_trait_qualified_name": None,
    }


def timestamp_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def unique_positioned_values(values: Iterable[Tuple[str, int, int]]) -> List[Tuple[str, int, int]]:
    seen = set()
    ordered = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered


def unique_values(values: Iterable[str]) -> List[str]:
    ordered: List[str] = []
    seen = set()
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered


def filter_shadowed_simple_tokens(values: List[Tuple[str, int, int]]) -> List[Tuple[str, int, int]]:
    qualified_by_line: Dict[int, List[str]] = defaultdict(list)
    for expression, line_number, _column in values:
        if "::" in expression:
            qualified_by_line[line_number].append(expression)

    filtered = []
    for expression, line_number, column in values:
        if "::" not in expression and any(path.endswith(f"::{expression}") for path in qualified_by_line[line_number]):
            continue
        filtered.append((expression, line_number, column))
    return filtered


def collapse_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def write_symbol_index(output_root: Path, repo_name: str, payload: Dict[str, object]) -> None:
    repo_output = output_root / repo_name
    repo_output.mkdir(parents=True, exist_ok=True)
    target = repo_output / "symbols.json"
    with target.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=False)
        handle.write("\n")
