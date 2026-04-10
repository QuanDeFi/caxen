import json
import subprocess
import tempfile
import unittest
from pathlib import Path


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

            symbols_path = parsed_root / "yellowstone-vixen" / "symbols.json"
            graph_path = graph_root / "yellowstone-vixen" / "graph.json"

            self.assertTrue(symbols_path.exists(), symbols_path)
            self.assertTrue(graph_path.exists(), graph_path)

            symbols = json.loads(symbols_path.read_text(encoding="utf-8"))
            graph = json.loads(graph_path.read_text(encoding="utf-8"))

            self.assertEqual(symbols["repo"], "yellowstone-vixen")
            self.assertEqual(symbols["summary"]["rust_files"], 1)
            self.assertGreater(symbols["summary"]["symbols"], 0)
            self.assertIn(
                "yellowstone_vixen_proc_macro::vixen",
                {item["qualified_name"] for item in symbols["symbols"]},
            )

            self.assertEqual(graph["repo"], "yellowstone-vixen")
            self.assertGreater(graph["summary"]["nodes"], 0)
            self.assertIn("DEFINES", {edge["type"] for edge in graph["edges"]})


if __name__ == "__main__":
    unittest.main()
