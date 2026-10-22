"""Search without external executables, using confined document reads."""
import os
from time import monotonic

import regex as re

from mdviewer.safe_paths import open_document

MATCH_TIMEOUT = 0.1
SEARCH_TIMEOUT = 5.0
MAX_PATTERN_LENGTH = 4096

EXCLUDED_DIRS = {'.git', '.venv', '__pycache__', 'node_modules', '.ruff_cache'}


def markdown_files(root, relative=''):
    try:
        with open_document(root, relative) as directory:
            entries = list(directory.entries())
    except OSError:
        return
    for name, is_dir in entries:
        if name.startswith('.') or name in EXCLUDED_DIRS:
            continue
        child = relative + '/' + name if relative else name
        if is_dir:
            yield from markdown_files(root, child)
        elif name.lower().endswith('.md'):
            yield child


def search_python(query, root, content=False):
    # fd uses smart case; rg's content adapter explicitly uses ignore case.
    flags = re.IGNORECASE if content or not any(c.isupper() for c in query) else 0
    if len(query) > MAX_PATTERN_LENGTH:
        return []
    try:
        pattern = re.compile(query, flags | re.VERSION0)
    except (re.error, RecursionError):
        return []
    deadline = monotonic() + SEARCH_TIMEOUT

    def matches(text):
        remaining = deadline - monotonic()
        if remaining <= 0:
            raise TimeoutError('Search time limit reached')
        return pattern.search(text, timeout=min(MATCH_TIMEOUT, remaining))

    results = []
    for relative in markdown_files(root):
        if monotonic() >= deadline:
            return []
        if not content:
            target = relative if '/' in query else relative.rsplit('/', 1)[-1]
            try:
                if matches(target):
                    results.append(os.path.normpath(relative))
            except TimeoutError:
                return []
            continue
        try:
            with open_document(root, relative) as opened:
                if opened.is_dir:
                    continue
                with opened.binary_stream() as stream:
                    data = stream.read()
            if b'\x00' in data:
                continue
            text = data.decode('utf-8', errors='replace')
            if any(matches(line) for line in text.splitlines()):
                results.append(os.path.normpath(relative))
        except TimeoutError:
            return []
        except OSError:
            # A file can disappear or become a symlink during a live edit.
            continue
    return results
