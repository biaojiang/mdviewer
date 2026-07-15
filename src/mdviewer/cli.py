import argparse
import os
import webbrowser
from importlib.metadata import version
from urllib.parse import quote

from mdviewer.app import build_tree, find_available_port, start_server


def contains_markdown_files(root):
    return bool(build_tree(root))


def should_open_browser(open_browser, has_markdown):
    return has_markdown if open_browser is None else open_browser


def main():
    parser = argparse.ArgumentParser(
        description="📘 mdviewer — GitHub-style Markdown viewer",
        epilog="Command aliases: mdviewer, mdv",
    )
    parser.add_argument(
        "target", nargs="?", default=".", help="Markdown file or folder to view"
    )
    browser_group = parser.add_mutually_exclusive_group()
    browser_group.add_argument(
        "-o",
        "--open",
        dest="open_browser",
        action="store_true",
        help="Open in browser even when no Markdown files are found",
    )
    browser_group.add_argument(
        "--no-open",
        dest="open_browser",
        action="store_false",
        help="Do not open a browser automatically",
    )
    parser.set_defaults(open_browser=None)
    parser.add_argument(
        "-p",
        "--port",
        type=int,
        default=5000,
        help="Port to serve on (default: 5000; uses the next free port if busy)",
    )
    parser.add_argument(
        "-V",
        "--version",
        action="version",
        version=f"%(prog)s {version('mdviewer')}",
        help="output version information and exit",
    )

    args = parser.parse_args()

    # Expand ~ and resolve absolute path
    target = os.path.abspath(os.path.expanduser(args.target))

    if not os.path.exists(target):
        print(f"❌ Error: Path not found: {target}")
        return

    # Determine root (folder) and optional file
    root = target if os.path.isdir(target) else os.path.dirname(target)
    open_file = os.path.relpath(target, root) if os.path.isfile(target) else None
    has_markdown = contains_markdown_files(root)
    open_browser = should_open_browser(args.open_browser, has_markdown)
    host = "127.0.0.1"
    port = find_available_port(host, args.port)
    browser_path = f"/view/{quote(open_file)}" if open_file else "/"
    browser_url = f"http://{host}:{port}{browser_path}"

    print(f"📂 Serving: {root}")
    if port != args.port:
        print(f"⚠️ Port {args.port} is busy, using {port} instead.")
    print(f"🌐 Open in browser: {browser_url}")
    print("🛑 Press Ctrl-C to stop server.")
    print("❗ Tip: Close the browser tab before restarting the server.")
    print("   Leaving it open may cause 'localhost access denied' errors.")

    if open_browser:
        webbrowser.open_new_tab(browser_url)
    elif not has_markdown and args.open_browser is None:
        print("⚠️ No Markdown files found; browser was not opened automatically.")

    start_server(markdown_root=root, open_file=open_file, port=port)


if __name__ == "__main__":
    main()
