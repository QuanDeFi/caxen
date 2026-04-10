import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path


SRC_ROOT = Path(__file__).resolve().parents[2] / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from graph.builder import build_graph_artifact
from symbols.indexer import build_symbol_index
from symbols.persistence import write_symbol_database, write_symbol_parquet_bundle


class SymbolSnapshotTest(unittest.TestCase):
    def test_semantic_fixture_matches_golden_snapshot(self) -> None:
        tests_root = Path(__file__).resolve().parents[1]
        fixture_path = tests_root / "fixtures" / "rust" / "semantic_sample.rs"
        golden_path = tests_root / "golden" / "rust" / "semantic_sample.snapshot.json"

        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            repo_root = workspace / "demo"
            raw_root = workspace / "raw"

            (repo_root / "src").mkdir(parents=True)
            (repo_root / "Cargo.toml").write_text(
                '[package]\nname = "demo-crate"\nversion = "0.1.0"\n',
                encoding="utf-8",
            )
            (repo_root / "src" / "lib.rs").write_text(
                fixture_path.read_text(encoding="utf-8"),
                encoding="utf-8",
            )

            (raw_root / "demo").mkdir(parents=True)
            (raw_root / "demo" / "manifest.json").write_text(
                json.dumps({"parser_relevant_source_roots": ["src"]}),
                encoding="utf-8",
            )

            artifact = build_symbol_index(
                "demo",
                repo_root,
                raw_root,
                path_prefixes=("src/lib.rs",),
            )
            graph = build_graph_artifact(artifact)

            snapshot = {
                "summary": artifact["summary"],
                "symbols": [
                    {
                        "kind": symbol["kind"],
                        "qualified_name": symbol["qualified_name"],
                    }
                    for symbol in artifact["symbols"]
                ],
                "imports": [
                    {
                        "target": entry["target"],
                        "target_qualified_name": entry["target_qualified_name"],
                    }
                    for entry in artifact["imports"]
                ],
                "references": [
                    {
                        "kind": entry["kind"],
                        "container": entry["container_qualified_name"],
                        "target": entry["target_qualified_name"],
                    }
                    for entry in artifact["references"]
                ],
                "graph_edge_counts": graph["summary"]["edge_counts"],
            }

            expected = json.loads(golden_path.read_text(encoding="utf-8"))
            self.assertEqual(snapshot, expected)

    def test_persistence_writes_sqlite_and_parquet_status(self) -> None:
        tests_root = Path(__file__).resolve().parents[1]
        fixture_path = tests_root / "fixtures" / "rust" / "semantic_sample.rs"

        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            repo_root = workspace / "demo"
            raw_root = workspace / "raw"
            output_root = workspace / "parsed"

            (repo_root / "src").mkdir(parents=True)
            (repo_root / "Cargo.toml").write_text(
                '[package]\nname = "demo-crate"\nversion = "0.1.0"\n',
                encoding="utf-8",
            )
            (repo_root / "src" / "lib.rs").write_text(
                fixture_path.read_text(encoding="utf-8"),
                encoding="utf-8",
            )

            (raw_root / "demo").mkdir(parents=True)
            (raw_root / "demo" / "manifest.json").write_text(
                json.dumps({"parser_relevant_source_roots": ["src"]}),
                encoding="utf-8",
            )

            artifact = build_symbol_index(
                "demo",
                repo_root,
                raw_root,
                path_prefixes=("src/lib.rs",),
            )

            write_symbol_database(output_root, "demo", artifact)
            write_symbol_parquet_bundle(output_root, "demo", artifact)

            sqlite_path = output_root / "demo" / "symbols.sqlite3"
            parquet_status_path = output_root / "demo" / "parquet_status.json"

            self.assertTrue(sqlite_path.exists(), sqlite_path)
            self.assertTrue(parquet_status_path.exists(), parquet_status_path)

            with sqlite3.connect(sqlite_path) as connection:
                cursor = connection.cursor()
                cursor.execute("SELECT COUNT(*) FROM symbols")
                self.assertEqual(cursor.fetchone()[0], artifact["summary"]["symbols"])
                cursor.execute("SELECT COUNT(*) FROM imports")
                self.assertEqual(cursor.fetchone()[0], artifact["summary"]["imports"])
                cursor.execute("SELECT COUNT(*) FROM symbol_references")
                self.assertEqual(cursor.fetchone()[0], artifact["summary"]["references"])

            parquet_status = json.loads(parquet_status_path.read_text(encoding="utf-8"))
            self.assertIn("available", parquet_status)
            if parquet_status["available"]:
                self.assertIn("symbols.parquet", parquet_status["artifacts"])
            else:
                self.assertTrue(parquet_status["reason"])
