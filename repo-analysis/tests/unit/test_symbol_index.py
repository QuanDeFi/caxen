import json
import sys
import tempfile
import unittest
from pathlib import Path


SRC_ROOT = Path(__file__).resolve().parents[2] / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from symbols.indexer import build_symbol_index


class SymbolIndexTest(unittest.TestCase):
    def test_build_symbol_index_uses_raw_roots_and_resolves_containers(self) -> None:
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
                "\n".join(
                    [
                        "use crate::support::Helper;",
                        "",
                        "pub struct Demo;",
                        "",
                        "impl Demo {",
                        "    pub fn answer(&self) -> u64 {",
                        "        42",
                        "    }",
                        "}",
                    ]
                )
                + "\n",
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

            self.assertEqual(artifact["summary"]["rust_files"], 1)
            self.assertEqual(artifact["files"][0]["crate"], "demo-crate")
            self.assertEqual(artifact["imports"][0]["target"], "crate::support::Helper")

            impl_symbol = next(item for item in artifact["symbols"] if item["kind"] == "impl")
            method_symbol = next(item for item in artifact["symbols"] if item["name"] == "answer")

            self.assertEqual(method_symbol["container_symbol_id"], impl_symbol["symbol_id"])
            self.assertEqual(method_symbol["module_path"], "demo_crate")


if __name__ == "__main__":
    unittest.main()
