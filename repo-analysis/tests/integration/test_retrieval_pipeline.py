import json
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
            self.assertTrue((search_root / "yellowstone-vixen" / "embedding_index.json").exists())
            self.assertTrue((summary_root / "yellowstone-vixen" / "project.json").exists())

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


if __name__ == "__main__":
    unittest.main()
