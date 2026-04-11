import json
import sys
import tempfile
import unittest
from pathlib import Path


SRC_ROOT = Path(__file__).resolve().parents[2] / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from agents.toolkit import find_symbol, prepare_context, repo_overview, summarize_path, trace_calls
from embeddings.indexer import build_embedding_index, query_embedding_index
from evaluation.harness import run_benchmarks
from graph.builder import build_graph_artifact, write_graph_artifact
from retrieval.engine import retrieve_context
from search.indexer import build_search_index, search_documents
from summaries.builder import build_summary_artifacts, write_summary_artifacts
from symbols.indexer import build_symbol_index, write_symbol_index


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
                "pub fn helper() -> u64 {",
                "    7",
                "}",
                "",
                "pub struct Demo;",
                "",
                "impl Demo {",
                "    pub fn answer(&self) -> u64 {",
                "        helper()",
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
    graph = build_graph_artifact(symbol_index)
    write_graph_artifact(graph_root, "demo", graph)
    build_search_index("demo", repo_root, raw_root, parsed_root, search_root)
    build_embedding_index(search_root, "demo")
    summary_artifacts = build_summary_artifacts("demo", raw_root, parsed_root, graph_root)
    write_summary_artifacts(summary_root, "demo", summary_artifacts)

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

    def test_parser_probe_and_embedding_sidecar_are_available(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = seed_demo_workspace(Path(tmpdir))
            symbols = json.loads((paths["parsed_root"] / "demo" / "symbols.json").read_text(encoding="utf-8"))

            self.assertIn("parser_backends", symbols)
            self.assertTrue(symbols["parser_backends"]["rustc_ast_probe"]["available"])
            self.assertGreater(symbols["summary"]["statements"], 0)

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


if __name__ == "__main__":
    unittest.main()
