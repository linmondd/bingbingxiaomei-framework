import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PublicReleaseTests(unittest.TestCase):
    def read_text_files(self):
        ignored_parts = {".git", "__pycache__"}
        for path in ROOT.rglob("*"):
            if not path.is_file():
                continue
            if path.name == "test_public_release.py":
                continue
            if ignored_parts.intersection(path.parts):
                continue
            if path.suffix not in {".md", ".jsonl", ".py", ".yaml", ".yml", ".txt"}:
                continue
            yield path, path.read_text(encoding="utf-8")

    def test_release_docs_exist(self):
        for name in ["README.md", "LICENSE", "LICENSE-SCOPE.md", "NOTICE.md", "DISCLAIMER.md"]:
            self.assertTrue((ROOT / name).exists(), f"{name} should exist")

    def test_mit_license_and_mon_copyright(self):
        license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")
        self.assertIn("MIT License", license_text)
        self.assertIn("Copyright (c) 2026 Mon", license_text)

    def test_public_text_has_no_private_machine_paths_or_secret_markers(self):
        # Generic credential-leakage markers — no specific user paths,
        # service names, credential types, or internal project codenames.
        # Pre-release audit cleaned all previously present sensitive data
        # (see RELEASE_AUDIT.md for the scanned categories).
        forbidden = [
            "PRIVATE_KEY",
            "private_key",
            "CLIENT_SECRET",
            "client_secret",
        ]
        for path, text in self.read_text_files():
            with self.subTest(path=path.relative_to(ROOT)):
                for marker in forbidden:
                    self.assertNotIn(marker, text)

    def test_readme_is_public_release_ready(self):
        text = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("# 冰冰小美框架", text)
        self.assertIn("Copyright (c) 2026 Mon", text)
        self.assertIn("不构成投资建议", text)
        self.assertNotIn("整理桌", text)
        self.assertNotIn("尚未发布", text)

    def test_notice_has_rights_takedown_language(self):
        text = (ROOT / "NOTICE.md").read_text(encoding="utf-8")
        self.assertIn("收到有效通知后", text)
        self.assertIn("下架整个仓库", text)
        self.assertIn("不收录、不再分发、不替代原作者完整文章", text)
        self.assertIn("临时隐藏争议内容", text)
        self.assertIn("权利人身份", text)

    def test_license_scope_excludes_third_party_content(self):
        combined = "\n".join(
            (ROOT / name).read_text(encoding="utf-8")
            for name in ["README.md", "NOTICE.md", "LICENSE-SCOPE.md"]
        )
        self.assertIn("MIT License does not cover third-party content", combined)
        self.assertIn("不对这些内容进行再许可", combined)

    def test_no_local_file_urls_in_public_data(self):
        for name in ["claims.jsonl", "sources.jsonl", "unresolved-sources.jsonl"]:
            path = ROOT / "data" / name
            for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if not line.strip():
                    continue
                row = json.loads(line)
                blob = json.dumps(row, ensure_ascii=False)
                self.assertNotIn("/Users/", blob, f"{name}:{line_no}")
                self.assertNotIn("file://", blob, f"{name}:{line_no}")

    def test_public_release_audit_script_passes(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "audit_public_release.py")],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("public_release_valid", result.stdout)


if __name__ == "__main__":
    unittest.main()
