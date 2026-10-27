import errno
import io
import os
import re
import shutil
import socket
import subprocess
import tempfile
from contextlib import contextmanager
from pathlib import Path

from bs4 import BeautifulSoup
from flask import Flask, abort, render_template, request, send_file
from livereload import Server
from markdown_it import MarkdownIt
from mdit_py_plugins.footnote import footnote_plugin

from mdviewer.safe_paths import document_root, open_document

from mdviewer.search.fd_search import search_filenames
from mdviewer.search.rg_search import search_content

BASE_DIR = os.path.dirname(__file__)

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "templates"),
    static_folder=os.path.join(BASE_DIR, "static"),
)
md = (
    MarkdownIt("commonmark", {"html": False})
    .enable("table", "strikethrough")
    .use(footnote_plugin, inline=False)
)
MARKDOWN_ROOT = os.path.abspath(".")
EXCLUDED_DIRS = {'.git', '.venv', '__pycache__', 'node_modules', '.ruff_cache'}
LATEX_REPO = os.environ.get(
    "MDVIEWER_LATEX_REPO", "/Volumes/Work/repos/md-to-lualatex"
)


def find_available_port(host, preferred_port):
    port = preferred_port
    while port < 65536:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind((host, port))
            except OSError as exc:
                if exc.errno != errno.EADDRINUSE:
                    raise
                port += 1
            else:
                return port
    raise OSError(f"No available ports found starting at {preferred_port}")


def slugify_heading(text):
    text = text.strip().lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"\s+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text or "section"


def add_heading_ids(soup):
    used_ids = {tag["id"] for tag in soup.find_all(id=True)}

    for heading in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
        if heading.get("id"):
            continue

        base_id = slugify_heading(heading.get_text())
        heading_id = base_id
        index = 1

        while heading_id in used_ids:
            heading_id = f"{base_id}-{index}"
            index += 1

        heading["id"] = heading_id
        used_ids.add(heading_id)


@contextmanager
def document_path(relative=""):
    try:
        with open_document(MARKDOWN_ROOT, relative) as opened:
            yield opened
    except PermissionError:
        abort(403)
    except (FileNotFoundError, NotADirectoryError):
        abort(404)


def build_tree(root_dir):
    def visit(relative):
        tree = {}
        try:
            with open_document(root_dir, relative) as directory:
                entries = list(directory.entries())
        except OSError:
            return tree
        for name, is_dir in entries:
            child = relative + "/" + name if relative else name
            if is_dir and name not in EXCLUDED_DIRS:
                tree[name] = visit(child)
            elif not is_dir and name.endswith(".md"):
                tree[name] = child
        return tree
    return visit("")


# Flask routes
@app.route("/")
def index():
    file_tree = build_tree(MARKDOWN_ROOT)
    return render_template(
        "index.html", tree=file_tree, initial_file=app.config.get("INITIAL_FILE")
    )


@app.route("/files/<path:filepath>")
def serve_file(filepath):
    with document_path(filepath) as opened:
        if opened.is_dir:
            abort(404)
        stream = opened.binary_stream()
    try:
        response = send_file(stream, download_name=os.path.basename(filepath))
    except Exception:
        stream.close()
        raise
    response.call_on_close(stream.close)
    # Raw documents (including HTML and SVG) have no script or origin authority.
    response.headers["Content-Security-Policy"] = (
        "sandbox; default-src 'none'; img-src data:; style-src 'unsafe-inline'"
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@app.route("/view/<path:filename>")
def view_markdown(filename):
    with document_path(filename) as opened:
        if opened.is_dir:
            entries = []
            for item, is_dir in opened.entries():
                if item.startswith("."):
                    continue
                item_path = filename + "/" + item
                if is_dir:
                    entries.append((item + "/", item_path))
                elif item.endswith(".md"):
                    entries.append((item, item_path))
            return render_template(
                "viewer.html", folder=filename, entries=entries,
                content=None, filename=filename,
            )
        with opened.binary_stream() as stream:
            content_md = stream.read().decode("utf-8")
    html = md.render(content_md)

    soup = BeautifulSoup(html, "html.parser")
    add_heading_ids(soup)
    for img in soup.find_all("img"):
        src = img.get("src")
        if src and not src.startswith("http") and not src.startswith("/files/"):
            img_path = os.path.normpath(
                os.path.join(os.path.dirname(filename), src)
            )
            img["src"] = f"/files/{img_path}"

    return render_template(
        "viewer.html", content=str(soup), entries=None, filename=filename
    )


@app.route("/export/latex/<path:filename>")
def export_latex(filename):
    """Compile the selected Markdown file with the md-to-lualatex project."""
    with document_path(filename) as opened:
        if opened.is_dir or not filename.lower().endswith(".md"):
            abort(404)
        with opened.binary_stream() as stream:
            markdown = stream.read()

    repo = Path(LATEX_REPO)
    required = [
        "build.sh", "main.tex", "preamble.tex", "metadata.tex", "emoji.lua"
    ]
    if (
        not all((repo / name).is_file() for name in required)
        or not (repo / "style").is_dir()
        or not (repo / "fonts").is_dir()
    ):
        return "LaTeX export is unavailable: md-to-lualatex files were not found.", 503

    with tempfile.TemporaryDirectory(prefix="mdviewer-latex-") as work:
        workdir = Path(work)
        for name in required:
            shutil.copy2(repo / name, workdir / name)
        shutil.copytree(repo / "style", workdir / "style")
        shutil.copytree(repo / "fonts", workdir / "fonts")
        source = workdir / Path(filename).name
        source.write_bytes(markdown)
        output = workdir / (source.stem + ".pdf")

        # The upstream build script opens Preview on macOS; suppress that UI side effect.
        bin_dir = workdir / "bin"
        bin_dir.mkdir()
        opener = bin_dir / "open"
        opener.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        opener.chmod(0o755)
        env = os.environ.copy()
        env["PATH"] = str(bin_dir) + os.pathsep + env.get("PATH", "")
        try:
            result = subprocess.run(
                ["bash", str(workdir / "build.sh"), "--force", "-o", str(output), str(source)],
                cwd=workdir,
                env=env,
                capture_output=True,
                text=True,
                timeout=180,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return f"LaTeX export failed: {exc}", 503
        if result.returncode or not output.is_file():
            detail = (result.stderr or result.stdout or "LaTeX compilation failed.")[-3000:]
            log_path = workdir / "main.log"
            if log_path.is_file():
                detail += "\n\n--- LaTeX log (tail) ---\n"
                detail += log_path.read_text(errors="replace")[-6000:]
            return detail, 500
        return send_file(
            io.BytesIO(output.read_bytes()),
            mimetype="application/pdf",
            as_attachment=True,
            download_name=source.stem + ".pdf",
        )


# Search functionality
@app.route("/search")
def search():
    query = request.args.get("q", "").strip()
    mode = request.args.get("mode", "fd")  # switch between fd or rg
    results = []

    if query:
        if mode == "rg":
            results = search_content(query, MARKDOWN_ROOT)
        else:
            results = search_filenames(query, MARKDOWN_ROOT)

    return render_template("search.html", results=results, query=query, mode=mode)


def start_server(markdown_root, open_file=None, port=5000):
    global MARKDOWN_ROOT
    MARKDOWN_ROOT = os.path.abspath(markdown_root)
    document_root(MARKDOWN_ROOT)
    app.config["INITIAL_FILE"] = open_file
    host = "127.0.0.1"
    active_port = find_available_port(host, port)

    server = Server(app.wsgi_app)

    # 🔁 Watch templates, static files, and markdown
    server.watch("templates/**/*.html")
    server.watch("static/**/*.js")
    server.watch("static/**/*.css")
    server.watch("**/*.md")

    if active_port != port:
        print(f"⚠️ Port {port} is busy, using {active_port} instead.")
    if open_file:
        print(f"📄 Opening file: {open_file}")

    server.serve(port=active_port, host=host, debug=True)


if __name__ == "__main__":
    document_root(MARKDOWN_ROOT)
    host = "127.0.0.1"
    port = find_available_port(host, 5000)
    server = Server(app.wsgi_app)

    # Watch all .md files starting from the project root
    server.watch("**/*.md")

    # Watch template changes
    server.watch("templates/*.html")

    # Optionally watch static JS/CSS too
    server.watch("static/*.js")
    # server.watch("static/*.css")

    if port != 5000:
        print(f"⚠️ Port 5000 is busy, using {port} instead.")
    server.serve(port=port, host=host, debug=True)
