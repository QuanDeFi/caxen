import json
import subprocess
import tempfile
import unittest
from pathlib import Path


class ParseReposIntegrationTest(unittest.TestCase):
    def test_parse_repos_writes_inventory_for_both_upstreams(self) -> None:
        workspace_root = Path(__file__).resolve().parents[3]
        cli = workspace_root / "repo-analysis" / "src" / "cli" / "main.py"

        with tempfile.TemporaryDirectory() as tmpdir:
            output_root = Path(tmpdir)
            subprocess.run(
                [
                    "python3",
                    str(cli),
                    "parse-repos",
                    "--workspace-root",
                    str(workspace_root),
                    "--output-root",
                    str(output_root),
                ],
                check=True,
                capture_output=True,
                text=True,
            )

            for repo_name in ("carbon", "yellowstone-vixen"):
                manifest_path = output_root / repo_name / "manifest.json"
                repo_map_path = output_root / repo_name / "repo_map.json"
                self.assertTrue(manifest_path.exists(), manifest_path)
                self.assertTrue(repo_map_path.exists(), repo_map_path)

                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                repo_map = json.loads(repo_map_path.read_text(encoding="utf-8"))

                self.assertEqual(manifest["repo"], repo_name)
                self.assertGreater(manifest["file_inventory"]["tracked_files"], 0)
                self.assertIn("files", repo_map)
                self.assertGreater(len(repo_map["files"]), 0)


if __name__ == "__main__":
    unittest.main()
