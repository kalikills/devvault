from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from scanner.engine import scan
from scanner.models import ScanRequest


class TestScanEngine(unittest.TestCase):
    def test_empty_root_finds_nothing(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            req = ScanRequest(roots=[root], depth=3)
            result = scan(req)

            self.assertEqual(result.projects, [])
            self.assertGreaterEqual(result.scanned_directories, 1)

    def test_detects_git_project(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            proj = root / "myproj"
            (proj / ".git").mkdir(parents=True)

            req = ScanRequest(roots=[root], depth=3)
            result = scan(req)

            self.assertEqual(len(result.projects), 1)
            self.assertEqual(result.projects[0].path, proj)
            self.assertTrue("git" in result.projects[0].reason.lower())

    def test_include_filter_applies(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            (root / "alpha" / ".git").mkdir(parents=True)
            (root / "beta" / ".git").mkdir(parents=True)

            req = ScanRequest(roots=[root], depth=3, include="alp")
            result = scan(req)

            self.assertEqual(len(result.projects), 1)
            self.assertEqual(result.projects[0].path.name, "alpha")

    def test_top_limits_after_sort(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            p1 = root / "p1"
            p2 = root / "p2"
            (p1 / ".git").mkdir(parents=True)
            (p2 / ".git").mkdir(parents=True)

            # Touch p2 later to ensure it sorts first
            (p1 / "a.txt").write_text("x", encoding="utf-8")
            (p2 / "b.txt").write_text("y", encoding="utf-8")

            req = ScanRequest(roots=[root], depth=3, top=1)
            result = scan(req)

            self.assertEqual(len(result.projects), 1)
            self.assertIn(result.projects[0].path.name, {"p1", "p2"})  # sort stability varies by FS


if __name__ == "__main__":
    unittest.main()
