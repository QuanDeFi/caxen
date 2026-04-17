import json
import sqlite3
import subprocess
import tempfile
import unittest
from pathlib import Path


class RetrievalPipelineIntegrationTest(unittest.TestCase):
    def test_cli_builds_search_and_summaries_and_answers_symbol_queries(self) -> None:
        workspace_root = Path(__file__).resolve().parents[3]
        cli = workspace_root / "repo-analysis" / "src" / "cli" / "main.py"

        with tempfile.TemporaryDirectory() as tmpdir:
            temp_root = Path(tmpdir)
            raw_root = temp_root / "raw"
            parsed_root = temp_root / "parsed"
            graph_root = temp_root / "graph"
            search_root = temp_root / "search"
            summary_root = temp_root / "summaries"
            eval_root = temp_root / "eval"

            subprocess.run(
                [
                    "python3",
                    str(cli),
                    "parse-repos",
                    "--workspace-root",
                    str(workspace_root),
                    "--output-root",
                    str(raw_root),
                    "--repo",
                    "yellowstone-vixen",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                [
                    "python3",
                    str(cli),
                    "build-index",
                    "--workspace-root",
                    str(workspace_root),
                    "--raw-root",
                    str(raw_root),
                    "--parsed-root",
                    str(parsed_root),
                    "--graph-root",
                    str(graph_root),
                    "--repo",
                    "yellowstone-vixen",
                    "--path-prefix",
                    "crates/proc-macro/src",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertTrue((graph_root / "yellowstone-vixen" / "graph.sqlite3").exists())
            self.assertTrue((parsed_root / "yellowstone-vixen" / "query_manifest.json").exists())
            subprocess.run(
                [
                    "python3",
                    str(cli),
                    "build-search",
                    "--workspace-root",
                    str(workspace_root),
                    "--raw-root",
                    str(raw_root),
                    "--parsed-root",
                    str(parsed_root),
                    "--search-root",
                    str(search_root),
                    "--repo",
                    "yellowstone-vixen",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                [
                    "python3",
                    str(cli),
                    "build-summaries",
                    "--raw-root",
                    str(raw_root),
                    "--parsed-root",
                    str(parsed_root),
                    "--graph-root",
                    str(graph_root),
                    "--summary-root",
                    str(summary_root),
                    "--repo",
                    "yellowstone-vixen",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                [
                    "python3",
                    str(cli),
                    "build-embeddings",
                    "--search-root",
                    str(search_root),
                    "--repo",
                    "yellowstone-vixen",
                ],
                check=True,
                capture_output=True,
                text=True,
            )

            self.assertTrue((search_root / "yellowstone-vixen" / "search.sqlite3").exists())
            self.assertTrue((search_root / "yellowstone-vixen" / "tantivy").exists())
            self.assertTrue((search_root / "yellowstone-vixen" / "embedding_index.json").exists())
            self.assertTrue((summary_root / "yellowstone-vixen" / "summary.sqlite3").exists())

            find_symbol = subprocess.run(
                [
                    "python3",
                    str(cli),
                    "find-symbol",
                    "--search-root",
                    str(search_root),
                    "--repo",
                    "yellowstone-vixen",
                    "vixen",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            symbol_lookup = json.loads(find_symbol.stdout)
            self.assertTrue(any(item["name"] == "vixen" for item in symbol_lookup["results"]))

            find_file = subprocess.run(
                [
                    "python3",
                    str(cli),
                    "find-file",
                    "--search-root",
                    str(search_root),
                    "--repo",
                    "yellowstone-vixen",
                    "crates/proc-macro/src/lib.rs",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            file_lookup = json.loads(find_file.stdout)
            self.assertTrue(any(item["path"] == "crates/proc-macro/src/lib.rs" for item in file_lookup["results"]))

            lexical_search = subprocess.run(
                [
                    "python3",
                    str(cli),
                    "search-lexical",
                    "--search-root",
                    str(search_root),
                    "--repo",
                    "yellowstone-vixen",
                    "--kind",
                    "package",
                    "proc macro",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            lexical_payload = json.loads(lexical_search.stdout)
            self.assertGreater(len(lexical_payload["results"]), 0)

            embedding_search = subprocess.run(
                [
                    "python3",
                    str(cli),
                    "embedding-search",
                    "--search-root",
                    str(search_root),
                    "--repo",
                    "yellowstone-vixen",
                    "proc macro attribute",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            embedding_lookup = json.loads(embedding_search.stdout)
            self.assertGreater(len(embedding_lookup["results"]), 0)

            repo_overview = subprocess.run(
                [
                    "python3",
                    str(cli),
                    "repo-overview",
                    "--summary-root",
                    str(summary_root),
                    "--repo",
                    "yellowstone-vixen",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            overview = json.loads(repo_overview.stdout)
            self.assertEqual(overview["repo"], "yellowstone-vixen")
            self.assertIn("Rust files", overview["project"]["summary"])

            prepare_context = subprocess.run(
                [
                    "python3",
                    str(cli),
                    "prepare-context",
                    "--search-root",
                    str(search_root),
                    "--summary-root",
                    str(summary_root),
                    "--graph-root",
                    str(graph_root),
                    "--parsed-root",
                    str(parsed_root),
                    "--repo",
                    "yellowstone-vixen",
                    "proc macro attribute",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            context = json.loads(prepare_context.stdout)
            self.assertEqual(context["contexts"][0]["repo"], "yellowstone-vixen")
            self.assertGreater(len(context["contexts"][0]["selected_context"]), 0)

            plan_query = subprocess.run(
                [
                    "python3",
                    str(cli),
                    "plan-query",
                    "--search-root",
                    str(search_root),
                    "--graph-root",
                    str(graph_root),
                    "--parsed-root",
                    str(parsed_root),
                    "--summary-root",
                    str(summary_root),
                    "--repo",
                    "yellowstone-vixen",
                    "proc macro attribute",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            plan_payload = json.loads(plan_query.stdout)
            self.assertEqual(plan_payload["plans"][0]["repo"], "yellowstone-vixen")

            where_defined = subprocess.run(
                [
                    "python3",
                    str(cli),
                    "where-defined",
                    "--search-root",
                    str(search_root),
                    "--parsed-root",
                    str(parsed_root),
                    "--repo",
                    "yellowstone-vixen",
                    "vixen_parser",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            definitions = json.loads(where_defined.stdout)
            self.assertTrue(any(item["name"] == "vixen_parser" for item in definitions["matches"]))

            adjacent = subprocess.run(
                [
                    "python3",
                    str(cli),
                    "adjacent-symbols",
                    "--search-root",
                    str(search_root),
                    "--parsed-root",
                    str(parsed_root),
                    "--graph-root",
                    str(graph_root),
                    "--repo",
                    "yellowstone-vixen",
                    "include_vixen_parser",
                    "--edge-type",
                    "CALLS",
                    "--edge-type",
                    "USES",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            adjacent_payload = json.loads(adjacent.stdout)
            self.assertGreaterEqual(len(adjacent_payload["matches"]), 1)

            imports = subprocess.run(
                [
                    "python3",
                    str(cli),
                    "who-imports",
                    "--search-root",
                    str(search_root),
                    "--parsed-root",
                    str(parsed_root),
                    "--graph-root",
                    str(graph_root),
                    "--repo",
                    "yellowstone-vixen",
                    "vixen_parser",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            imports_payload = json.loads(imports.stdout)
            self.assertGreaterEqual(len(imports_payload["matches"]), 1)

            graph_query = subprocess.run(
                [
                    "python3",
                    str(cli),
                    "graph-query",
                    "--search-root",
                    str(search_root),
                    "--parsed-root",
                    str(parsed_root),
                    "--graph-root",
                    str(graph_root),
                    "--repo",
                    "yellowstone-vixen",
                    "--operation",
                    "callers_of",
                    "--seed",
                    "vixen",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            graph_payload = json.loads(graph_query.stdout)
            self.assertEqual(graph_payload["operation"], "callers_of")

            refs = subprocess.run(
                [
                    "python3",
                    str(cli),
                    "refs-of",
                    "--search-root",
                    str(search_root),
                    "--parsed-root",
                    str(parsed_root),
                    "--graph-root",
                    str(graph_root),
                    "--repo",
                    "yellowstone-vixen",
                    "vixen_parser",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            refs_payload = json.loads(refs.stdout)
            self.assertGreaterEqual(len(refs_payload["neighbors"]), 1)

            signature = subprocess.run(
                [
                    "python3",
                    str(cli),
                    "get-symbol-signature",
                    "--search-root",
                    str(search_root),
                    "--parsed-root",
                    str(parsed_root),
                    "--repo",
                    "yellowstone-vixen",
                    "vixen_parser",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            signature_payload = json.loads(signature.stdout)
            self.assertIsNotNone(signature_payload["signature"])

            body = subprocess.run(
                [
                    "python3",
                    str(cli),
                    "get-symbol-body",
                    "--search-root",
                    str(search_root),
                    "--parsed-root",
                    str(parsed_root),
                    "--repo",
                    "yellowstone-vixen",
                    "include_vixen_parser",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            body_payload = json.loads(body.stdout)
            self.assertIsNotNone(body_payload["body"])

            context_lookup = subprocess.run(
                [
                    "python3",
                    str(cli),
                    "get-enclosing-context",
                    "--search-root",
                    str(search_root),
                    "--summary-root",
                    str(summary_root),
                    "--graph-root",
                    str(graph_root),
                    "--parsed-root",
                    str(parsed_root),
                    "--repo",
                    "yellowstone-vixen",
                    "vixen_parser",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            context_payload = json.loads(context_lookup.stdout)
            self.assertIsNotNone(context_payload["context"])

            expand = subprocess.run(
                [
                    "python3",
                    str(cli),
                    "expand-subgraph",
                    "--search-root",
                    str(search_root),
                    "--parsed-root",
                    str(parsed_root),
                    "--graph-root",
                    str(graph_root),
                    "--repo",
                    "yellowstone-vixen",
                    "vixen_parser",
                    "--edge-type",
                    "CALLS",
                    "--edge-type",
                    "USES_TYPE",
                    "--depth",
                    "2",
                    "--budget",
                    "10",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            expand_payload = json.loads(expand.stdout)
            self.assertEqual(expand_payload["operation"], "neighbors")

            with sqlite3.connect(graph_root / "yellowstone-vixen" / "graph.sqlite3") as connection:
                cursor = connection.cursor()
                node_kinds = {row[0] for row in cursor.execute("SELECT DISTINCT kind FROM nodes").fetchall()}
                edge_types = {row[0] for row in cursor.execute("SELECT DISTINCT type FROM edges").fetchall()}
            self.assertIn("directory", node_kinds)
            self.assertIn("package", node_kinds)
            self.assertIn("project_summary", node_kinds)
            self.assertIn("SUMMARIZED_BY", edge_types)

            path_between = subprocess.run(
                [
                    "python3",
                    str(cli),
                    "path-between",
                    "--search-root",
                    str(search_root),
                    "--parsed-root",
                    str(parsed_root),
                    "--graph-root",
                    str(graph_root),
                    "--repo",
                    "yellowstone-vixen",
                    "include_vixen_parser",
                    "vixen_parser",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            path_payload = json.loads(path_between.stdout)
            self.assertGreaterEqual(len(path_payload["paths"]), 1)

            statement_slice = subprocess.run(
                [
                    "python3",
                    str(cli),
                    "statement-slice",
                    "--search-root",
                    str(search_root),
                    "--parsed-root",
                    str(parsed_root),
                    "--graph-root",
                    str(graph_root),
                    "--repo",
                    "yellowstone-vixen",
                    "include_vixen_parser",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            statement_payload = json.loads(statement_slice.stdout)
            self.assertGreaterEqual(len(statement_payload["statements"]), 1)

            prepare_bundle = subprocess.run(
                [
                    "python3",
                    str(cli),
                    "prepare-answer-bundle",
                    "--search-root",
                    str(search_root),
                    "--summary-root",
                    str(summary_root),
                    "--graph-root",
                    str(graph_root),
                    "--parsed-root",
                    str(parsed_root),
                    "--repo",
                    "yellowstone-vixen",
                    "proc macro attribute",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            bundle_payload = json.loads(prepare_bundle.stdout)
            self.assertGreater(len(bundle_payload["bundles"][0]["evidence"]), 0)
            eval_root.mkdir(parents=True, exist_ok=True)
            (eval_root / "prior_bundle.json").write_text(json.dumps(bundle_payload), encoding="utf-8")

            retrieve_iterative = subprocess.run(
                [
                    "python3",
                    str(cli),
                    "retrieve-iterative",
                    "--search-root",
                    str(search_root),
                    "--summary-root",
                    str(summary_root),
                    "--graph-root",
                    str(graph_root),
                    "--parsed-root",
                    str(parsed_root),
                    "--repo",
                    "yellowstone-vixen",
                    "--prior-bundle",
                    str(eval_root / "prior_bundle.json"),
                    "--hint",
                    "macro",
                    "proc macro attribute",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            iterative_payload = json.loads(retrieve_iterative.stdout)
            self.assertEqual(iterative_payload["iteration"]["iteration_count"], 1)

            benchmarks = subprocess.run(
                [
                    "python3",
                    str(cli),
                    "run-benchmarks",
                    "--search-root",
                    str(search_root),
                    "--graph-root",
                    str(graph_root),
                    "--parsed-root",
                    str(parsed_root),
                    "--summary-root",
                    str(summary_root),
                    "--eval-root",
                    str(eval_root),
                    "--repo",
                    "yellowstone-vixen",
                    "--mode",
                    "lexical_graph_vector_rerank_summaries",
                    "--mode",
                    "selective_on",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            benchmark_payload = json.loads(benchmarks.stdout)
            self.assertGreaterEqual(len(benchmark_payload["summary"]["modes"]), 2)
            self.assertIn("avg_answer_score", benchmark_payload["summary"]["modes"][0])
            self.assertIn("answer_quality", benchmark_payload["runs"][0])
            self.assertTrue((eval_root / "benchmarks.json").exists())
            self.assertIn("consumer_readiness", benchmark_payload["summary"])

            prompt_exports = subprocess.run(
                [
                    "python3",
                    str(cli),
                    "export-benchmark-prompts",
                    "--search-root",
                    str(search_root),
                    "--graph-root",
                    str(graph_root),
                    "--parsed-root",
                    str(parsed_root),
                    "--summary-root",
                    str(summary_root),
                    "--eval-root",
                    str(eval_root),
                    "--repo",
                    "yellowstone-vixen",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            prompt_payload = json.loads(prompt_exports.stdout)
            self.assertGreaterEqual(prompt_payload["summary"]["exports"], 1)
            self.assertTrue((eval_root / "eval.sqlite3").exists())

            bundle_scores = subprocess.run(
                [
                    "python3",
                    str(cli),
                    "score-answer-bundles",
                    "--search-root",
                    str(search_root),
                    "--graph-root",
                    str(graph_root),
                    "--parsed-root",
                    str(parsed_root),
                    "--summary-root",
                    str(summary_root),
                    "--eval-root",
                    str(eval_root),
                    "--repo",
                    "yellowstone-vixen",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            bundle_score_payload = json.loads(bundle_scores.stdout)
            self.assertGreater(bundle_score_payload["summary"]["avg_bundle_score"], 0)

            answers_path = eval_root / "answers.json"
            answers_path.write_text(
                json.dumps(
                    {
                        "answers": [
                            {
                                "name": "yellowstone_vixen_attr_macro",
                                "answer": "The vixen proc macro attribute is defined in crates/proc-macro/src/lib.rs.",
                                "cited_paths": ["crates/proc-macro/src/lib.rs"],
                                "cited_symbols": ["vixen"],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            external_scores = subprocess.run(
                [
                    "python3",
                    str(cli),
                    "score-external-answers",
                    "--eval-root",
                    str(eval_root),
                    "--answers-path",
                    str(answers_path),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            external_payload = json.loads(external_scores.stdout)
            self.assertGreaterEqual(external_payload["summary"]["cases"], 1)


if __name__ == "__main__":
    unittest.main()
