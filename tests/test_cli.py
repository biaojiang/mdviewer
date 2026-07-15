import os
import tempfile
import unittest

from mdviewer.cli import contains_markdown_files, should_open_browser


class MarkdownDiscoveryTest(unittest.TestCase):
    def test_finds_markdown_files_recursively(self):
        with tempfile.TemporaryDirectory() as root:
            nested = os.path.join(root, "docs")
            os.mkdir(nested)
            with open(os.path.join(nested, "guide.md"), "w", encoding="utf-8"):
                pass

            self.assertTrue(contains_markdown_files(root))

    def test_ignores_excluded_directories(self):
        with tempfile.TemporaryDirectory() as root:
            excluded = os.path.join(root, ".git")
            os.mkdir(excluded)
            with open(os.path.join(excluded, "hidden.md"), "w", encoding="utf-8"):
                pass

            self.assertFalse(contains_markdown_files(root))

    def test_auto_open_requires_markdown_by_default(self):
        self.assertTrue(should_open_browser(None, has_markdown=True))
        self.assertFalse(should_open_browser(None, has_markdown=False))

    def test_explicit_browser_choice_overrides_discovery(self):
        self.assertTrue(should_open_browser(True, has_markdown=False))
        self.assertFalse(should_open_browser(False, has_markdown=True))


if __name__ == "__main__":
    unittest.main()
