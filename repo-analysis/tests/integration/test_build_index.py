import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[2] / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from symbols.persistence import load_symbol_index
from graph.query import load_graph_view_uncached


class BuildIndexIntegrationTest(unittest.TestCase):
    def test_build_index_writes_symbols_and_graph_for_a_scoped_upstream_path(self) -> None:
        workspace_root = Path(__file__).resolve().parents[3]
        cli = workspace_root / "repo-analysis" / "src" / "cli" / "main.py"

        with tempfile.TemporaryDirectory() as tmpdir:
            temp_root = Path(tmpdir)
            raw_root = temp_root / "raw"
            parsed_root = temp_root / "parsed"
            graph_root = temp_root / "graph"

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
                    "crates/proc-macro/src/lib.rs",
                ],
                check=True,
                capture_output=True,
                text=True,
            )

            metadata_path = parsed_root / "yellowstone-vixen" / "metadata.lmdb"
            graph_db_path = graph_root / "yellowstone-vixen" / "graph.db"

            self.assertTrue(metadata_path.exists(), metadata_path)
            self.assertTrue(graph_db_path.exists(), graph_db_path)

            symbols_payload = load_symbol_index(parsed_root, "yellowstone-vixen")
            summary = symbols_payload["summary"]
            self.assertEqual(symbols_payload["repo"], "yellowstone-vixen")
            self.assertEqual(summary["rust_files"], 1)
            self.assertGreater(summary["symbols"], 0)
            self.assertGreater(summary["references"], 0)
            self.assertEqual(len(symbols_payload["symbols"]), summary["symbols"])
            self.assertTrue(
                any(item["qualified_name"] == "yellowstone_vixen_proc_macro::vixen" for item in symbols_payload["symbols"])
            )

            graph_payload = load_graph_view_uncached(graph_root, "yellowstone-vixen")["payload"]
            graph_summary = graph_payload["summary"]
            self.assertEqual(graph_payload["repo"], "yellowstone-vixen")
            self.assertGreater(graph_summary["nodes"], 0)
            edge_types = {str(edge["type"]) for edge in graph_payload["edges"]}
            self.assertIn("DEFINES", edge_types)
            self.assertIn("IMPORTS", edge_types)

    def test_build_index_on_carbon_and_vixen_real_slices_emits_semantic_edges(self) -> None:
        workspace_root = Path(__file__).resolve().parents[3]
        cli = workspace_root / "repo-analysis" / "src" / "cli" / "main.py"

        with tempfile.TemporaryDirectory() as tmpdir:
            temp_root = Path(tmpdir)
            raw_root = temp_root / "raw"
            parsed_root = temp_root / "parsed"
            graph_root = temp_root / "graph"

            subprocess.run(
                [
                    "python3",
                    str(cli),
                    "parse-repos",
                    "--workspace-root",
                    str(workspace_root),
                    "--output-root",
                    str(raw_root),
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
                    "carbon",
                    "--path-prefix",
                    "crates/core/src/filter.rs",
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
                    "crates/bpf-loader-parser/src",
                ],
                check=True,
                capture_output=True,
                text=True,
            )

            for repo_name in ("carbon", "yellowstone-vixen"):
                symbols_payload = load_symbol_index(parsed_root, repo_name)
                self.assertGreater(symbols_payload["summary"]["references"], 0)
                reference_kinds = {str(row["kind"]) for row in symbols_payload["references"]}
                self.assertIn("call", reference_kinds)
                self.assertIn("use", reference_kinds)

                graph_payload = load_graph_view_uncached(graph_root, repo_name)["payload"]
                edge_types = {str(edge["type"]) for edge in graph_payload["edges"]}
                self.assertIn("CALLS", edge_types)
                self.assertIn("USES", edge_types)
                self.assertIn("IMPORTS", edge_types)


if __name__ == "__main__":
    unittest.main()
