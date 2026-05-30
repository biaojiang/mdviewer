import argparse
import os
import webbrowser
from mdviewer.app import find_available_port, start_server


def main():
    parser = argparse.ArgumentParser(
        prog="mdv", description="📘 mdviewer — GitHub-style Markdown viewer"
    )
    parser.add_argument(
        "target", nargs="?", default="README.md", help="Markdown file or folder to view"
    )
    parser.add_argument(
        "-o",
        "--open",
        action="store_true",
        help="Open in browser after starting server (default: off)",
    )
    parser.add_argument(
        "-p",
        "--port",
        type=int,
        default=5000,
        help="Port to serve on (default: 5000; uses the next free port if busy)",
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
    host = "127.0.0.1"
    port = find_available_port(host, args.port)

    print(f"📂 Serving: {root}")
    if port != args.port:
        print(f"⚠️ Port {args.port} is busy, using {port} instead.")
    print(f"🌐 Open in browser: http://{host}:{port}")
    print("🛑 Press Ctrl-C to stop server.")
    print("❗ Tip: Close the browser tab before restarting the server.")
    print("   Leaving it open may cause 'localhost access denied' errors.")

    if args.open:
        webbrowser.open_new_tab(f"http://{host}:{port}")

    start_server(markdown_root=root, open_file=open_file, port=port)


if __name__ == "__main__":
    main()
