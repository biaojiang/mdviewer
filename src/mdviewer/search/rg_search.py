import subprocess
import os
import shutil

from mdviewer.search.python_search import search_python


def search_content(query, root):
    executable = shutil.which("rg")
    if executable is None:
        return search_python(query, root, content=True)
    try:
        result = subprocess.run(
            [executable, "--files-with-matches", "-i", "-t", "md", "-e", query, "--", root],
            capture_output=True,
            text=True,
        )
        matches = result.stdout.strip().split("\n")
        return [os.path.relpath(m, root).replace(os.sep, "/") for m in matches if m]
    except FileNotFoundError:
        return search_python(query, root, content=True)
    except Exception as e:
        print("[RG ERROR]", e)
        return []
