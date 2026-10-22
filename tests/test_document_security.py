import importlib
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from bs4 import BeautifulSoup
from mdviewer.safe_paths import close_document_roots, document_root, open_document

viewer = importlib.import_module('mdviewer.app')


class DocumentSecurityTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.addCleanup(close_document_roots)
        self.root = Path(self.temp.name) / 'docs'
        self.root.mkdir()
        self.outside = Path(self.temp.name) / 'outside'
        self.outside.mkdir()
        (self.outside / 'secret.md').write_text('OUTSIDE SECRET')
        self.root_patch = patch.object(viewer, 'MARKDOWN_ROOT', str(self.root))
        self.root_patch.start()
        self.addCleanup(self.root_patch.stop)
        self.client = viewer.app.test_client()

    def get_bytes(self, url):
        with self.client.get(url) as response:
            return response.status_code, response.data

    def test_markdown_cannot_introduce_active_html(self):
        payloads = [
            '<script>window.evil=1</script>',
            '<img src=x onerror="window.evil=1">',
            '<svg onload="window.evil=1"></svg>',
            '<iframe srcdoc="<script>evil()</script>"></iframe>',
            '[bad](javascript:alert%281%29)',
            '<a href="javascript:evil()">bad</a>',
        ]
        for payload in payloads:
            with self.subTest(payload=payload):
                (self.root / 'test.md').write_text(payload)
                status, body = self.get_bytes('/view/test.md')
                self.assertEqual(status, 200)
                content = BeautifulSoup(body, 'html.parser').select_one('.markdown-body')
                self.assertFalse(content.select('script, img, svg, iframe, a'))

    def test_normal_markdown_math_tables_footnotes_and_images(self):
        (self.root / 'nested').mkdir()
        (self.root / 'nested/guide.md').write_text(
            '# Heading\n\n**Bold** and $x^2$.[^1]\n\n'
            '| A | B |\n|---|---|\n| 1 | 2 |\n\n'
            '![Diagram](../image.svg)\n\n[^1]: Footnote\n')
        status, body = self.get_bytes('/view/nested/guide.md')
        self.assertEqual(status, 200)
        soup = BeautifulSoup(body, 'html.parser')
        self.assertIsNotNone(soup.select_one('h1#heading'))
        self.assertIsNotNone(soup.select_one('table'))
        self.assertIsNotNone(soup.select_one('strong'))
        self.assertIsNotNone(soup.select_one('.footnote-ref'))
        self.assertIn('$x^2$', soup.get_text())
        self.assertEqual(soup.select_one('.markdown-body img')['src'], '/files/image.svg')
        self.assertEqual(self.get_bytes('/view/nested')[0], 200)
        self.assertEqual(self.get_bytes('/')[0], 200)

    def test_raw_active_assets_have_no_script_or_origin_authority(self):
        for name, body in [('active.html', '<script>evil()</script>'),
                           ('image.svg', '<svg xmlns="http://www.w3.org/2000/svg" onload="evil()"/>'),
                           ('image.png', 'image bytes')]:
            (self.root / name).write_text(body)
            with self.client.get('/files/' + name) as response:
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.data, body.encode())
                policy = response.headers['Content-Security-Policy']
                self.assertIn('sandbox;', policy)
                self.assertNotIn('allow-scripts', policy)
                self.assertNotIn('allow-same-origin', policy)
                self.assertIn("default-src 'none'", policy)
                self.assertEqual(response.headers['X-Content-Type-Options'], 'nosniff')

    def test_leaf_and_directory_symlinks_are_denied_on_both_routes(self):
        (self.root / 'external.md').symlink_to(self.outside / 'secret.md')
        (self.root / 'external').symlink_to(self.outside, target_is_directory=True)
        (self.root / 'ordinary.md').write_text('ordinary')
        (self.root / 'internal.md').symlink_to(self.root / 'ordinary.md')
        for path in ['external.md', 'external', 'external/secret.md', 'internal.md']:
            for route in ['view', 'files']:
                with self.subTest(path=path, route=route):
                    status, body = self.get_bytes('/' + route + '/' + path)
                    self.assertEqual(status, 403)
                    self.assertNotIn(b'OUTSIDE SECRET', body)
        self.assertEqual(viewer.build_tree(str(self.root)), {'ordinary.md': 'ordinary.md'})

    def test_traversal_and_missing_files(self):
        for route in ['view', 'files']:
            for path in ['../outside/secret.md', '%2e%2e/outside/secret.md', '..%5coutside%5csecret.md']:
                self.assertIn(self.get_bytes('/' + route + '/' + path)[0], (403, 404))
            self.assertEqual(self.get_bytes('/' + route + '/missing.md')[0], 404)

    @unittest.skipIf(os.name == 'nt', 'POSIX descriptor replacement race')
    def test_swap_to_symlink_before_final_open_is_denied(self):
        path = self.root / 'race.md'
        path.write_text('safe')
        original_open = os.open
        def race_open(name, flags, *args, **kwargs):
            if name == 'race.md' and kwargs.get('dir_fd') is not None:
                path.unlink()
                path.symlink_to(self.outside / 'secret.md')
            return original_open(name, flags, *args, **kwargs)
        for route in ['view', 'files']:
            if path.is_symlink():
                path.unlink()
                path.write_text('safe')
            with patch('mdviewer.safe_paths.os.open', side_effect=race_open):
                self.assertEqual(self.get_bytes('/' + route + '/race.md')[0], 403)

    @unittest.skipIf(os.name == 'nt', 'POSIX descriptor pinning')
    def test_opened_file_and_directory_remain_pinned_after_replacement(self):
        folder = self.root / 'nested'
        folder.mkdir()
        (folder / 'safe.md').write_text('safe')
        with open_document(str(self.root), 'nested/safe.md') as opened:
            (folder / 'safe.md').unlink()
            (folder / 'safe.md').symlink_to(self.outside / 'secret.md')
            with opened.binary_stream() as stream:
                self.assertEqual(stream.read(), b'safe')
        with open_document(str(self.root), 'nested') as opened:
            folder.rename(self.root / 'moved')
            folder.symlink_to(self.outside, target_is_directory=True)
            self.assertNotIn(('secret.md', False), list(opened.entries()))

    @unittest.skipIf(os.name == 'nt', 'Windows denies renaming a pinned root')
    def test_selected_root_cannot_be_retargeted_between_requests(self):
        (self.root / 'safe.md').write_text('safe')
        document_root(str(self.root))
        self.root.rename(Path(self.temp.name) / 'moved-root')
        self.root.symlink_to(self.outside, target_is_directory=True)
        for route in ['view', 'files']:
            self.assertEqual(self.get_bytes('/' + route + '/secret.md')[0], 404)
            self.assertEqual(self.get_bytes('/' + route + '/safe.md')[0], 200)

    def test_selected_root_may_be_a_symlink(self):
        alias = Path(self.temp.name) / 'alias'
        alias.symlink_to(self.root, target_is_directory=True)
        (self.root / 'safe.md').write_text('safe')
        with open_document(str(alias), 'safe.md') as opened:
            with opened.binary_stream() as stream:
                self.assertEqual(stream.read(), b'safe')


if __name__ == '__main__':
    unittest.main()
