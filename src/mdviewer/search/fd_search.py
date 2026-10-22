import subprocess
import os
import shutil

from mdviewer.search.python_search import search_python


def search_filenames(query, root):
    executable = shutil.which("fd") or shutil.which("fdfind")
    if executable is None:
        return search_python(query, root, content=False)
    try:
        result = subprocess.run(
            [executable, "--type", "f", "--extension", "md", "--", query, root],
            capture_output=True,
            text=True,
        )
        matches = result.stdout.strip().split("\n")
        return [os.path.relpath(m, root) for m in matches if m]
    except FileNotFoundError:
        return search_python(query, root, content=False)
    except Exception as e:
        print("[FD ERROR]", e)
        return []
