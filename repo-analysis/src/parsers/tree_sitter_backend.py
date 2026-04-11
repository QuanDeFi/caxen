from __future__ import annotations

import importlib
import time
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple


ITEM_NODE_TYPES = {
    "const": {"const_item"},
    "enum": {"enum_item"},
    "function": {"function_item"},
    "impl": {"impl_item"},
    "module": {"mod_item"},
    "static": {"static_item"},
    "struct": {"struct_item"},
    "trait": {"trait_item"},
    "type": {"type_item", "type_alias"},
    "union": {"union_item"},
    "use": {"use_declaration"},
}

STATEMENT_NODE_TYPES = {
    "expr": {"expression_statement"},
    "let": {"let_declaration"},
    "return": {"return_expression"},
}

CONTROL_NODE_TYPES = {
    "for": {"for_expression"},
    "if": {"if_expression"},
    "loop": {"loop_expression"},
    "match": {"match_expression"},
    "while": {"while_expression"},
}


def probe_tree_sitter(path: Path, source: str) -> Dict[str, object]:
    started = time.perf_counter()
    parser, diagnostics = load_rust_parser()
    if parser is None:
        return unavailable_payload(path, diagnostics, started)

    try:
        tree = parser.parse(source.encode("utf-8"))
    except Exception as exc:  # pragma: no cover - depends on optional backend
        return {
            "backend": "tree-sitter-rust",
            "available": True,
            "used": True,
            "parsed": False,
            "path": path.as_posix(),
            "latency_ms": round((time.perf_counter() - started) * 1000, 3),
            "item_counts": [],
            "statement_counts": [],
            "control_counts": [],
            "error_nodes": 0,
            "diagnostics": [f"tree-sitter parse failed: {exc}"],
        }

    root = tree.root_node
    node_types = list(iter_node_types(root))
    return {
        "backend": "tree-sitter-rust",
        "available": True,
        "used": True,
        "parsed": not root.has_error,
        "path": path.as_posix(),
        "latency_ms": round((time.perf_counter() - started) * 1000, 3),
        "item_counts": summarize_counts(node_types, ITEM_NODE_TYPES),
        "statement_counts": summarize_counts(node_types, STATEMENT_NODE_TYPES),
        "control_counts": summarize_counts(node_types, CONTROL_NODE_TYPES),
        "error_nodes": sum(1 for node_type in node_types if node_type == "ERROR"),
        "diagnostics": diagnostics,
    }


def aggregate_tree_sitter_probes(file_probes: Iterable[Dict[str, object]]) -> Dict[str, object]:
    probes = list(file_probes)
    available = any(probe.get("available") for probe in probes) or bool(load_rust_parser()[0])
    parsed_files = sum(1 for probe in probes if probe.get("parsed"))
    return {
        "backend": "tree-sitter-rust",
        "available": available,
        "used": bool(probes),
        "files": len(probes),
        "parsed_files": parsed_files,
        "item_counts": aggregate_counts(probes, "item_counts"),
        "statement_counts": aggregate_counts(probes, "statement_counts"),
        "control_counts": aggregate_counts(probes, "control_counts"),
        "error_nodes": sum(int(probe.get("error_nodes") or 0) for probe in probes),
        "samples": [
            {
                "path": probe["path"],
                "parsed": probe["parsed"],
                "latency_ms": probe["latency_ms"],
            }
            for probe in probes[:10]
        ],
    }


def load_rust_parser() -> Tuple[object | None, List[str]]:
    diagnostics: List[str] = []

    try:
        module = importlib.import_module("tree_sitter_languages")
        parser = module.get_parser("rust")
        return parser, ["loaded parser from tree_sitter_languages"]
    except Exception as exc:  # pragma: no cover - optional import path
        diagnostics.append(f"tree_sitter_languages unavailable: {exc}")

    try:
        tree_sitter = importlib.import_module("tree_sitter")
        parser = tree_sitter.Parser()
    except Exception as exc:  # pragma: no cover - optional import path
        diagnostics.append(f"tree_sitter unavailable: {exc}")
        return None, diagnostics

    language = load_tree_sitter_rust_language(diagnostics)
    if language is None:
        return None, diagnostics

    try:
        if hasattr(parser, "set_language"):
            parser.set_language(language)
        else:  # tree-sitter >= 0.22
            parser.language = language
    except Exception as exc:  # pragma: no cover - optional backend
        diagnostics.append(f"failed to configure tree-sitter parser: {exc}")
        return None, diagnostics
    return parser, diagnostics


def load_tree_sitter_rust_language(diagnostics: List[str]) -> object | None:
    for module_name in ("tree_sitter_rust", "tree_sitter_languages"):
        try:
            module = importlib.import_module(module_name)
        except Exception as exc:  # pragma: no cover - optional import path
            diagnostics.append(f"{module_name} unavailable: {exc}")
            continue

        try:
            if module_name == "tree_sitter_rust" and hasattr(module, "language"):
                tree_sitter = importlib.import_module("tree_sitter")
                if hasattr(tree_sitter, "Language"):
                    return tree_sitter.Language(module.language())
            if module_name == "tree_sitter_languages" and hasattr(module, "get_language"):
                return module.get_language("rust")
        except Exception as exc:  # pragma: no cover - optional backend
            diagnostics.append(f"failed loading rust language from {module_name}: {exc}")
    return None


def unavailable_payload(path: Path, diagnostics: List[str], started: float) -> Dict[str, object]:
    return {
        "backend": "tree-sitter-rust",
        "available": False,
        "used": False,
        "parsed": False,
        "path": path.as_posix(),
        "latency_ms": round((time.perf_counter() - started) * 1000, 3),
        "item_counts": [],
        "statement_counts": [],
        "control_counts": [],
        "error_nodes": 0,
        "diagnostics": diagnostics or ["tree-sitter rust grammar is not available"],
    }


def iter_node_types(node: object) -> Iterable[str]:
    stack = [node]
    while stack:
        current = stack.pop()
        yield str(getattr(current, "type"))
        children = list(getattr(current, "children", []))
        stack.extend(reversed(children))


def summarize_counts(node_types: Iterable[str], mapping: Dict[str, set[str]]) -> List[Dict[str, object]]:
    counts: List[Dict[str, object]] = []
    values = list(node_types)
    for kind, node_type_names in sorted(mapping.items()):
        count = sum(1 for node_type in values if node_type in node_type_names)
        if count:
            counts.append({"kind": kind, "count": count})
    return counts


def aggregate_counts(file_probes: Iterable[Dict[str, object]], field: str) -> List[Dict[str, object]]:
    counts: Dict[str, int] = {}
    for probe in file_probes:
        for item in probe.get(field, []):
            kind = str(item["kind"])
            counts[kind] = counts.get(kind, 0) + int(item["count"])
    return [{"kind": kind, "count": count} for kind, count in sorted(counts.items())]
