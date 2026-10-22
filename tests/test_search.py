import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from mdviewer.search.fd_search import search_filenames
from mdviewer.search.rg_search import search_content


class SearchBoundaryTest(unittest.TestCase):
    def test_queries_are_bound_as_patterns(self):
        cases = [
            (search_filenames, "mdviewer.search.fd_search.subprocess.run",
             ["fd", "--type", "f", "--extension", "md", "--"]),
            (search_content, "mdviewer.search.rg_search.subprocess.run",
             ["rg", "--files-with-matches", "-i", "-t", "md", "-e"]),
        ]
        for search, target, prefix in cases:
            for query in ["--exec=/bin/rm", "--pre=/bin/sh", "-e", "--", "guide.*"]:
                with self.subTest(search=search.__name__, query=query):
                    with patch(target) as run:
                        run.return_value.stdout = "/docs/guide.md\n"
                        self.assertEqual(search(query, "/docs"), ["guide.md"])
                        suffix = [query, "/docs"] if search is search_filenames else [query, "--", "/docs"]
                        self.assertEqual(run.call_args.args[0], prefix + suffix)

    def test_real_tools_preserve_patterns_and_explicit_root(self):
        for tool, search in [("fd", search_filenames), ("rg", search_content)]:
            with self.subTest(tool=tool):
                if not shutil.which(tool):
                    self.skipTest(tool + " is not installed")
                with tempfile.TemporaryDirectory() as directory:
                    root = Path(directory) / "docs"
                    root.mkdir()
                    marker = Path(directory) / "executed"
                    # If rg interprets --pre, this harmless script creates a marker.
                    (root / "guide.md").write_text("touch " + str(marker) + "\n# Ordinary Needle\n")
                    (root / "--exec=echo.md").write_text("--pre=echo\n")
                    (root / "ignored.txt").write_text("Ordinary Needle\n")
                    self.assertEqual(search("guide" if tool == "fd" else "ordinary needle", str(root)), ["guide.md"])
                    self.assertEqual(search("--exec=echo" if tool == "fd" else "--pre=echo", str(root)), ["--exec=echo.md"])
                    for query in ["--exec=/bin/echo", "--pre=/bin/sh", "-Xecho", "--"]:
                        search(query, str(root))
                    self.assertFalse(marker.exists())
                    self.assertTrue((root / "guide.md").exists())


if __name__ == "__main__":
    unittest.main()
