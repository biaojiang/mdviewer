import argparse
import os
import webbrowser
from mdviewer.app import start_server  # make app.py expose a `start_server(path)`


def main():
    parser = argparse.ArgumentParser(
        prog="mdv", description="📘 mdviewer — GitHub-style Markdown viewer"
    )
    parser.add_argument(
        "-o",
        "--open",
        action="store_true",
        help="Open in browser after starting server (default: off)",
    )
    parser.add_argument(
        "target", nargs="?", default="README.md", help="Markdown file or folder to view"
    )
    parser.add_argument(
        "--version", action='store_true', help="output version information and exit"
    )

    args = parser.parse_args()
    if args.version:
        _version_and_exit()

    # Expand ~ and resolve absolute path
    target = os.path.abspath(os.path.expanduser(args.target))

    if not os.path.exists(target):
        print(f"❌ Error: Path not found: {target}")
        return

    # Determine root (folder) and optional file
    root = target if os.path.isdir(target) else os.path.dirname(target)
    open_file = target if os.path.isfile(target) else None

    print(f"📂 Serving: {root}")
    print("🛑 Press Ctrl-C to stop server.")
    print("❗ Tip: Close the browser tab before restarting the server.")
    print("   Leaving it open may cause 'localhost access denied' errors.")

    start_server(markdown_root=root, open_file=open_file)

    print("🌐 Open in browser: http://127.0.0.1:5000")
    print("🛑 Press Ctrl-C to stop server.")
    print("❗ Remember to close the browser tab before restarting.")

    if args.open:
        webbrowser.open_new_tab("http://127.0.0.1:5000")


def _version_and_exit():
    # pylint: disable=import-outside-toplevel
    from importlib.metadata import version as get_version
    import sys
    print(f"mdviewer {get_version('mdviewer')}")
    sys.exit(0)


if __name__ == "__main__":
    main()
