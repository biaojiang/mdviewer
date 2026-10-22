from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from mdviewer.safe_paths import document_root
from mdviewer.search.fd_search import search_filenames
from mdviewer.search.rg_search import search_content


class SearchFallbackTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.addCleanup(document_root.cache_clear)
        self.root = Path(self.temp.name) / 'docs'
        self.root.mkdir()
        (self.root / 'nested').mkdir()
        (self.root / 'Guide.md').write_text('Ordinary NEEDLE\nsecond line\n')
        (self.root / 'nested/lower.md').write_text('needle\n')
        (self.root / '--pre=echo.md').write_text('--exec=echo\n')
        (self.root / '.hidden.md').write_text('needle')
        (self.root / 'ignored.txt').write_text('needle')
        (self.root / 'node_modules').mkdir()
        (self.root / 'node_modules/hidden.md').write_text('needle')

    def fallback(self, search, query):
        with patch('shutil.which', return_value=None), patch('subprocess.run') as run:
            result = search(query, str(self.root))
            run.assert_not_called()
            return result

    def test_no_external_programs_required(self):
        self.assertEqual(self.fallback(search_filenames, 'guide'), ['Guide.md'])
        self.assertEqual(self.fallback(search_filenames, 'GUIDE'), [])
        self.assertEqual(set(self.fallback(search_content, 'needle')), {'Guide.md', 'nested/lower.md'})
        self.assertEqual(self.fallback(search_filenames, 'nested/low.*'), ['nested/lower.md'])
        self.assertEqual(self.fallback(search_content, '^Ordinary.*NEEDLE$'), ['Guide.md'])

    def test_option_like_patterns_are_data(self):
        self.assertEqual(self.fallback(search_filenames, '--pre=echo'), ['--pre=echo.md'])
        self.assertEqual(self.fallback(search_content, '--exec=echo'), ['--pre=echo.md'])
        for search in [search_filenames, search_content]:
            self.assertEqual(self.fallback(search, '--pre=/bin/sh'), [])
            self.assertEqual(self.fallback(search, '['), [])

    def test_expensive_patterns_are_bounded(self):
        (self.root / 'long.md').write_text('a' * 10000 + '!')
        with patch('mdviewer.search.python_search.MATCH_TIMEOUT', 0.001):
            self.assertEqual(self.fallback(search_content, '(a+)+$'), [])
        self.assertEqual(self.fallback(search_content, 'a' * 4097), [])
        with patch('mdviewer.search.python_search.SEARCH_TIMEOUT', 0):
            self.assertEqual(self.fallback(search_content, 'needle'), [])

    def test_fdfind_is_supported(self):
        with patch('shutil.which', side_effect=lambda name: '/usr/bin/fdfind' if name == 'fdfind' else None):
            with patch('mdviewer.search.fd_search.subprocess.run') as run:
                run.return_value.stdout = str(self.root / 'Guide.md')
                self.assertEqual(search_filenames('guide', str(self.root)), ['Guide.md'])
                self.assertEqual(run.call_args.args[0][0], '/usr/bin/fdfind')

    def test_program_removed_after_detection_uses_fallback(self):
        for search in [search_filenames, search_content]:
            with patch('shutil.which', return_value='/missing/program'), patch('subprocess.run', side_effect=FileNotFoundError):
                self.assertTrue(search('guide' if search is search_filenames else 'ordinary', str(self.root)))

    def test_outside_symlinks_and_binary_files_are_not_searched(self):
        outside = Path(self.temp.name) / 'secret.md'
        outside.write_text('outside-secret')
        (self.root / 'outside.md').symlink_to(outside)
        (self.root / 'outside-dir').symlink_to(Path(self.temp.name), target_is_directory=True)
        (self.root / 'binary.md').write_bytes(b'outside-secret\x00')
        self.assertEqual(self.fallback(search_content, 'outside-secret'), [])
        self.assertEqual(self.fallback(search_filenames, 'outside'), [])

    def test_common_patterns_agree_with_installed_tools(self):
        for tool, search, queries in [
            ('fd', search_filenames, ['guide', 'Guide', '^lower', '--pre=echo']),
            ('rg', search_content, ['^Ordinary NEEDLE$', '^Ordinary', 'second line', '--exec=echo']),
        ]:
            if not shutil.which(tool):
                continue
            for query in queries:
                with self.subTest(tool=tool, query=query):
                    expected = search(query, str(self.root))
                    self.assertEqual(set(self.fallback(search, query)), set(expected))


if __name__ == '__main__':
    unittest.main()
