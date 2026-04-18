import json
import sqlite3
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

            sqlite_path = parsed_root / "yellowstone-vixen" / "symbols.sqlite3"
            parquet_status_path = parsed_root / "yellowstone-vixen" / "parquet_status.json"
            graph_db_path = graph_root / "yellowstone-vixen" / "graph.db"

            self.assertTrue(sqlite_path.exists(), sqlite_path)
            self.assertTrue(parquet_status_path.exists(), parquet_status_path)
            self.assertTrue(graph_db_path.exists(), graph_db_path)

            with sqlite3.connect(sqlite_path) as connection:
                cursor = connection.cursor()
                metadata = dict(cursor.execute("SELECT key, value FROM metadata").fetchall())
                summary = json.loads(metadata["summary_json"])
                self.assertEqual(metadata["repo"], "yellowstone-vixen")
                self.assertEqual(summary["rust_files"], 1)
                self.assertGreater(summary["symbols"], 0)
                self.assertGreater(summary["references"], 0)
                cursor.execute("SELECT COUNT(*) FROM symbols")
                self.assertEqual(cursor.fetchone()[0], summary["symbols"])
                cursor.execute(
                    "SELECT COUNT(*) FROM symbols WHERE qualified_name = ?",
                    ["yellowstone_vixen_proc_macro::vixen"],
                )
                self.assertGreaterEqual(cursor.fetchone()[0], 1)

            parquet_status = json.loads(parquet_status_path.read_text(encoding="utf-8"))
            self.assertIn("available", parquet_status)

            with sqlite3.connect(graph_db_path) as connection:
                cursor = connection.cursor()
                metadata = dict(cursor.execute("SELECT key, value FROM metadata").fetchall())
                graph_summary = json.loads(metadata["summary_json"])
                self.assertEqual(metadata["repo"], "yellowstone-vixen")
                self.assertGreater(graph_summary["nodes"], 0)
                edge_types = {row[0] for row in cursor.execute("SELECT DISTINCT type FROM edges").fetchall()}
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
                with sqlite3.connect(parsed_root / repo_name / "symbols.sqlite3") as connection:
                    cursor = connection.cursor()
                    summary = json.loads(
                        dict(cursor.execute("SELECT key, value FROM metadata").fetchall())["summary_json"]
                    )
                    self.assertGreater(summary["references"], 0)
                    reference_kinds = {row[0] for row in cursor.execute("SELECT DISTINCT kind FROM symbol_references").fetchall()}
                    self.assertIn("call", reference_kinds)
                    self.assertIn("use", reference_kinds)

                with sqlite3.connect(graph_root / repo_name / "graph.db") as connection:
                    cursor = connection.cursor()
                    edge_types = {row[0] for row in cursor.execute("SELECT DISTINCT type FROM edges").fetchall()}
                    self.assertIn("CALLS", edge_types)
                    self.assertIn("USES", edge_types)
                    self.assertIn("IMPORTS", edge_types)


if __name__ == "__main__":
    unittest.main()
