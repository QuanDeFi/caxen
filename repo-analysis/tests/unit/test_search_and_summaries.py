import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path


SRC_ROOT = Path(__file__).resolve().parents[2] / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from agents.toolkit import (
    execute_graph_query,
    expand_subgraph,
    find_file,
    find_symbol,
    get_enclosing_context,
    get_summary,
    get_symbol_body,
    get_symbol_signature,
    implements_of,
    path_between,
    plan_query,
    prepare_answer_bundle,
    prepare_context,
    refs_of,
    repo_overview,
    retrieve_iterative,
    search_lexical,
    statement_slice,
    summarize_path,
    trace_calls,
)
from common.query_manifest import load_query_manifest
from embeddings.indexer import build_embedding_index, query_embedding_index
from evaluation.harness import export_benchmark_prompts, run_benchmarks, score_answer_bundles, score_external_answers
from graph.builder import build_graph_artifact, write_graph_artifact
from graph.store import write_graph_database
from retrieval.engine import retrieve_context
from search.indexer import build_search_index, search_documents
from summaries.builder import build_summary_artifacts, sync_summary_state, write_summary_artifacts
from symbols.indexer import build_symbol_index, write_symbol_index
from symbols.persistence import write_symbol_database


def seed_demo_workspace(root: Path) -> dict[str, Path]:
    repo_root = root / "demo"
    raw_root = root / "raw"
    parsed_root = root / "parsed"
    graph_root = root / "graph"
    search_root = root / "search"
    summary_root = root / "summaries"

    (repo_root / "src").mkdir(parents=True)
    (repo_root / "Cargo.toml").write_text(
        '[package]\nname = "demo-crate"\nversion = "0.1.0"\n',
        encoding="utf-8",
    )
    (repo_root / "src" / "lib.rs").write_text(
        "\n".join(
            [
                "pub trait ProvidesAnswer {",
                "    fn answer(&self) -> u64;",
                "}",
                "",
                "/// Return the canonical demo answer.",
                "pub fn helper() -> u64 {",
                "    7",
                "}",
                "",
                "pub struct Demo;",
                "",
                "impl ProvidesAnswer for Demo {",
                "    fn answer(&self) -> u64 {",
                "        helper()",
                "    }",
                "}",
                "",
                "#[cfg(test)]",
                "mod tests {",
                "    use super::*;",
                "",
                "    #[test]",
                "    fn demo_answer() {",
                "        let demo = Demo;",
                "        assert_eq!(ProvidesAnswer::answer(&demo), 7);",
                "    }",
                "}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    (raw_root / "demo").mkdir(parents=True)
    (raw_root / "demo" / "manifest.json").write_text(
        json.dumps(
            {
                "repo": "demo",
                "notes": ["demo repo"],
                "language_mix": [{"language": "Rust", "files": 1, "bytes": 64}],
                "build_commands": ["cargo build"],
                "test_commands": ["cargo test"],
                "module_graph_seeds": {
                    "analysis_surfaces": ["src"],
                },
                "parser_relevant_source_roots": ["src"],
            }
        ),
        encoding="utf-8",
    )
    (raw_root / "demo" / "repo_map.json").write_text(
        json.dumps(
            {
                "repo": "demo",
                "directories": [
                    {"path": ".", "depth": 0},
                    {"path": "src", "depth": 1},
                ],
                "files": [
                    {
                        "path": "src/lib.rs",
                        "size": 120,
                        "extension": ".rs",
                        "language": "Rust",
                        "generated": False,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    symbol_index = build_symbol_index("demo", repo_root, raw_root, path_prefixes=("src/lib.rs",))
    write_symbol_index(parsed_root, "demo", symbol_index)
    write_symbol_database(parsed_root, "demo", symbol_index)
    graph = build_graph_artifact(symbol_index)
    write_graph_artifact(graph_root, "demo", graph)
    write_graph_database(graph_root, "demo", graph)
    build_search_index("demo", repo_root, raw_root, parsed_root, search_root)
    build_embedding_index(search_root, "demo")
    summary_artifacts = build_summary_artifacts("demo", raw_root, parsed_root, graph_root)
    write_summary_artifacts(summary_root, "demo", summary_artifacts)
    sync_summary_state(parsed_root, graph_root, "demo", summary_artifacts)

    return {
        "repo_root": repo_root,
        "raw_root": raw_root,
        "parsed_root": parsed_root,
        "graph_root": graph_root,
        "search_root": search_root,
        "summary_root": summary_root,
    }


class SearchAndSummaryTest(unittest.TestCase):
    def test_search_index_returns_symbol_hits(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = seed_demo_workspace(Path(tmpdir))
            results = search_documents(paths["search_root"], "demo", "helper", limit=5)
            symbol_hits = [item for item in results if item["kind"] == "symbol"]

            self.assertGreater(len(results), 0)
            self.assertTrue(any(item["name"] == "helper" for item in symbol_hits))
            self.assertTrue((paths["search_root"] / "demo" / "tantivy").exists())

    def test_parser_probe_and_embedding_sidecar_are_available(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = seed_demo_workspace(Path(tmpdir))
            symbols = json.loads((paths["parsed_root"] / "demo" / "symbols.json").read_text(encoding="utf-8"))
            query_manifest = load_query_manifest(paths["parsed_root"], "demo")

            self.assertIn("parser_backends", symbols)
            self.assertTrue(symbols["parser_backends"]["rustc_ast_probe"]["available"])
            self.assertGreater(symbols["summary"]["statements"], 0)
            self.assertIn("search_sqlite", query_manifest["artifacts"])
            self.assertTrue(all(item.get("summary_id") for item in symbols["symbols"]))
            self.assertTrue(all(item.get("normalized_body_hash") for item in symbols["symbols"]))

            with sqlite3.connect(paths["parsed_root"] / "demo" / "symbols.sqlite3") as connection:
                tables = {
                    row[0]
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type = 'table'"
                    ).fetchall()
                }
                self.assertIn("tests", tables)
                self.assertIn("summaries", tables)
                self.assertIn("index_runs", tables)

            embedding_results = query_embedding_index(paths["search_root"], "demo", "helper answer", limit=5)
            self.assertGreater(len(embedding_results), 0)
            self.assertTrue(any(item.get("name") in {"helper", "answer"} for item in embedding_results))

    def test_retrieval_and_toolkit_use_search_and_graph_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = seed_demo_workspace(Path(tmpdir))

            context = retrieve_context(
                paths["search_root"],
                paths["graph_root"],
                paths["parsed_root"],
                "demo",
                "answer helper",
                limit=5,
            )
            self.assertGreater(len(context["selected_context"]), 0)
            self.assertTrue(any(item.get("name") == "answer" for item in context["selected_context"]))

            symbol_lookup = find_symbol(paths["search_root"], "demo", "answer", limit=5)
            self.assertTrue(any(item["name"] == "answer" for item in symbol_lookup["results"]))

            call_trace = trace_calls(
                paths["search_root"],
                paths["graph_root"],
                paths["parsed_root"],
                "demo",
                "helper",
            )
            self.assertEqual(call_trace["resolved_symbol"]["name"], "helper")
            self.assertTrue(any(item["name"] == "answer" for item in call_trace["callers"]))

            prepared = prepare_context(
                paths["search_root"],
                paths["summary_root"],
                paths["graph_root"],
                paths["parsed_root"],
                "find the helper call path",
                repo_name="demo",
                limit=5,
            )
            self.assertEqual(prepared["contexts"][0]["repo"], "demo")
            self.assertGreater(len(prepared["contexts"][0]["selected_context"]), 0)

    def test_summary_outputs_cover_repo_and_path_rollups(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = seed_demo_workspace(Path(tmpdir))

            overview = repo_overview(paths["summary_root"], "demo")
            self.assertEqual(overview["repo"], "demo")
            self.assertIn("Rust files", overview["project"]["summary"])

            file_summary = summarize_path(paths["summary_root"], "demo", "src/lib.rs")
            self.assertEqual(file_summary["kind"], "file")
            self.assertEqual(file_summary["summary"]["path"], "src/lib.rs")

            directory_summary = summarize_path(paths["summary_root"], "demo", "src")
            self.assertEqual(directory_summary["kind"], "directory")
            self.assertEqual(directory_summary["summary"]["path"], "src")
            packages = json.loads((paths["summary_root"] / "demo" / "packages.json").read_text(encoding="utf-8"))
            self.assertTrue(any(item["package_name"] == "demo-crate" for item in packages))

    def test_benchmark_harness_reports_answer_quality(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            paths = seed_demo_workspace(root)
            eval_root = root / "eval"

            payload = run_benchmarks(
                paths["search_root"],
                paths["graph_root"],
                paths["parsed_root"],
                eval_root,
                summary_root=paths["summary_root"],
                repos=("demo",),
                modes=("lexical_graph_rerank_summaries",),
                benchmarks=[
                    {
                        "name": "demo_answer",
                        "repo": "demo",
                        "task_type": "symbol_lookup",
                        "query": "answer helper",
                        "expected_path": "src/lib.rs",
                        "expected_name": "answer",
                        "expected_terms": ["answer", "helper"],
                    }
                ],
            )

            run = payload["runs"][0]
            self.assertIn("answer_quality", run)
            self.assertGreater(run["answer_quality"]["score"], 0.5)
            self.assertIn("avg_answer_score", payload["summary"]["modes"][0])
            self.assertTrue((eval_root / "benchmarks.json").exists())

    def test_graph_query_and_bundle_planner_return_deterministic_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = seed_demo_workspace(Path(tmpdir))

            neighbors = execute_graph_query(
                paths["search_root"],
                paths["parsed_root"],
                paths["graph_root"],
                "demo",
                {
                    "operation": "callers_of",
                    "seed": "helper",
                    "limit": 5,
                },
            )
            self.assertEqual(neighbors["operation"], "callers_of")
            self.assertTrue(any(item["name"] == "answer" for item in neighbors["results"]))

            package_search = search_lexical(
                paths["search_root"],
                "demo",
                "demo-crate",
                limit=5,
                kinds=("package",),
            )
            self.assertTrue(any(item["kind"] == "package" for item in package_search["results"]))

            file_lookup = find_file(paths["search_root"], "demo", "src/lib.rs", limit=5)
            self.assertTrue(any(item["path"] == "src/lib.rs" for item in file_lookup["results"]))

            signature = get_symbol_signature(paths["search_root"], paths["parsed_root"], "demo", "helper")
            self.assertIn("helper()", signature["signature"])

            body = get_symbol_body(paths["search_root"], paths["parsed_root"], "demo", "answer")
            self.assertEqual(body["body"]["kind"], "function_body")

            context = get_enclosing_context(
                paths["search_root"],
                paths["summary_root"],
                paths["graph_root"],
                paths["parsed_root"],
                "demo",
                "answer",
            )
            self.assertEqual(context["context"]["symbol"]["name"], "answer")

            refs = refs_of(
                paths["search_root"],
                paths["parsed_root"],
                paths["graph_root"],
                "demo",
                "answer",
                limit=10,
            )
            self.assertGreaterEqual(len(refs["neighbors"]), 1)

            impls = implements_of(
                paths["search_root"],
                paths["parsed_root"],
                paths["graph_root"],
                "demo",
                "ProvidesAnswer",
                limit=10,
            )
            self.assertTrue(any(item["name"] == "Demo" or item["kind"] == "impl" for item in impls["neighbors"]))

            subgraph = expand_subgraph(
                paths["search_root"],
                paths["parsed_root"],
                paths["graph_root"],
                "demo",
                "helper",
                edge_types=("CALLS", "USES_TYPE", "NEIGHBOR"),
                depth=2,
                budget=10,
            )
            self.assertEqual(subgraph["operation"], "neighbors")

            graph_payload = json.loads((paths["graph_root"] / "demo" / "graph.json").read_text(encoding="utf-8"))
            node_kinds = {item["kind"] for item in graph_payload["nodes"]}
            self.assertIn("directory", node_kinds)
            self.assertIn("package", node_kinds)
            self.assertIn("test", node_kinds)
            self.assertIn("symbol_summary", node_kinds)
            edge_types = {item["type"] for item in graph_payload["edges"]}
            self.assertIn("SUMMARIZED_BY", edge_types)
            self.assertIn("OVERRIDES", edge_types)
            self.assertIn("NEIGHBOR", edge_types)

            summary_payload = get_summary(
                paths["search_root"],
                paths["summary_root"],
                paths["graph_root"],
                paths["parsed_root"],
                "demo",
                graph_payload["nodes"][0]["node_id"],
            )
            self.assertEqual(summary_payload["repo"], "demo")

            slice_payload = statement_slice(
                paths["search_root"],
                paths["parsed_root"],
                paths["graph_root"],
                "demo",
                "answer",
                limit=5,
            )
            self.assertGreater(len(slice_payload["statements"]), 0)
            self.assertTrue(any(item["calls"] for item in slice_payload["statements"]))

            path_payload = path_between(
                paths["search_root"],
                paths["parsed_root"],
                paths["graph_root"],
                "demo",
                "answer",
                "helper",
                limit=3,
            )
            self.assertGreater(len(path_payload["paths"]), 0)
            self.assertEqual(path_payload["paths"][0]["target"]["name"], "helper")

            plan_payload = plan_query(
                paths["search_root"],
                paths["graph_root"],
                paths["parsed_root"],
                "find the helper implementation",
                repo_name="demo",
                summary_root=paths["summary_root"],
                limit=5,
            )
            self.assertEqual(plan_payload["plans"][0]["repo"], "demo")

            bundle = prepare_answer_bundle(
                paths["search_root"],
                paths["summary_root"],
                paths["graph_root"],
                paths["parsed_root"],
                "find the helper call path",
                repo_name="demo",
                limit=5,
            )
            repo_bundle = bundle["bundles"][0]
            self.assertGreater(len(repo_bundle["evidence"]), 0)
            self.assertTrue(all(item["provenance"]["path"] for item in repo_bundle["evidence"]))

            refined = retrieve_iterative(
                paths["search_root"],
                paths["summary_root"],
                paths["graph_root"],
                paths["parsed_root"],
                "find the helper call path",
                repo_name="demo",
                limit=5,
                prior_bundle=bundle,
                refinement_hints=("answer method",),
            )
            self.assertEqual(refined["iteration"]["iteration_count"], 1)
            self.assertGreater(len(refined["bundles"][0]["selected_context"]), 0)

    def test_prompt_export_and_bundle_scoring_are_stable(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            paths = seed_demo_workspace(root)
            eval_root = root / "eval"
            benchmark = [
                {
                    "name": "demo_answer_bundle",
                    "repo": "demo",
                    "task_type": "symbol_lookup",
                    "query": "answer helper",
                    "expected_path": "src/lib.rs",
                    "expected_name": "answer",
                    "expected_terms": ["answer", "helper"],
                }
            ]

            prompts = export_benchmark_prompts(
                paths["search_root"],
                paths["graph_root"],
                paths["parsed_root"],
                paths["summary_root"],
                eval_root,
                repos=("demo",),
                limit=5,
                benchmarks=benchmark,
            )
            self.assertEqual(prompts["summary"]["exports"], 1)
            self.assertTrue((eval_root / "prompt_exports" / "demo_answer_bundle.json").exists())

            bundle_scores = score_answer_bundles(
                paths["search_root"],
                paths["graph_root"],
                paths["parsed_root"],
                paths["summary_root"],
                eval_root,
                repos=("demo",),
                limit=5,
                benchmarks=benchmark,
            )
            self.assertGreater(bundle_scores["scores"][0]["score"], 0.5)

            answers_path = eval_root / "answers.json"
            answers_path.write_text(
                json.dumps(
                    {
                        "answers": [
                            {
                                "name": "demo_answer_bundle",
                                "answer": "The answer method in src/lib.rs calls helper.",
                                "cited_paths": ["src/lib.rs"],
                                "cited_symbols": ["answer", "helper"],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            external_scores = score_external_answers(eval_root, answers_path, benchmarks=benchmark)
            self.assertGreater(external_scores["scores"][0]["score"], 0.7)


if __name__ == "__main__":
    unittest.main()
