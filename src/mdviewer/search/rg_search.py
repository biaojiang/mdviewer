import subprocess
import os


def search_content(query, root):
    try:
        result = subprocess.run(
            ["rg", "--files-with-matches", "-i", "-t", "md", query, root],
            capture_output=True,
            text=True,
        )
        matches = result.stdout.strip().split("\n")
        return [os.path.relpath(m, root) for m in matches if m]
    except Exception as e:
        print("[RG ERROR]", e)
        return []
