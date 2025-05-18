import subprocess
import os


def search_filenames(query, root):
    try:
        result = subprocess.run(
            ["fd", "--type", "f", "--extension", "md", query, root],
            capture_output=True,
            text=True,
        )
        matches = result.stdout.strip().split("\n")
        return [os.path.relpath(m, root) for m in matches if m]
    except Exception as e:
        print("[FD ERROR]", e)
        return []
