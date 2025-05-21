import os

from bs4 import BeautifulSoup
from flask import Flask, abort, render_template, request, send_from_directory
from livereload import Server
from markdown_it import MarkdownIt

from mdviewer.search.fd_search import search_filenames
from mdviewer.search.rg_search import search_content

BASE_DIR = os.path.dirname(__file__)

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "templates"),
    static_folder=os.path.join(BASE_DIR, "static"),
)
md = MarkdownIt()
MARKDOWN_ROOT = os.path.abspath(".")
EXCLUDED_DIRS = {'.git', '.venv', '__pycache__', 'node_modules', '.ruff_cache'}


# build_tree function to create a directory tree
def build_tree(root_dir):
    tree = {}
    for dirpath, dirnames, filenames in os.walk(root_dir):
        rel_path = os.path.relpath(dirpath, root_dir)

        # Exclude unwanted directories
        dirnames[:] = [d for d in dirnames if d not in EXCLUDED_DIRS]

        node = tree
        if rel_path != ".":
            for part in rel_path.split(os.sep):
                node = node.setdefault(part, {})

        for filename in filenames:
            if filename.endswith(".md"):
                node[filename] = os.path.relpath(
                    os.path.join(dirpath, filename), root_dir
                )
    return tree


# Flask routes
@app.route("/")
def index():
    file_tree = build_tree(MARKDOWN_ROOT)
    return render_template(
        "index.html", tree=file_tree, initial_file=app.config.get("INITIAL_FILE")
    )


@app.route("/files/<path:filepath>")
def serve_file(filepath):
    full_path = os.path.join(MARKDOWN_ROOT, filepath)
    if not os.path.isfile(full_path):
        abort(404)
    return send_from_directory(MARKDOWN_ROOT, filepath)


@app.route("/view/<path:filename>")
def view_markdown(filename):
    full_path = os.path.abspath(os.path.join(MARKDOWN_ROOT, filename))

    if not full_path.startswith(MARKDOWN_ROOT):
        abort(403)

    if os.path.isdir(full_path):
        entries = []
        for item in sorted(os.listdir(full_path)):
            if item.startswith("."):
                continue  # Skip hidden files
            item_path = os.path.join(filename, item)
            if os.path.isdir(os.path.join(MARKDOWN_ROOT, item_path)):
                entries.append((item + "/", item_path))
            elif item.endswith(".md"):
                entries.append((item, item_path))
        return render_template(
            "viewer.html",
            folder=filename,
            entries=entries,
            content=None,
            filename=filename,
        )

    elif os.path.isfile(full_path):
        with open(full_path, encoding="utf-8") as f:
            content_md = f.read()
            html = md.render(content_md)

        # Fix image paths
        soup = BeautifulSoup(html, "html.parser")
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

    else:
        abort(404)


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


def start_server(markdown_root, open_file=None):
    global MARKDOWN_ROOT
    MARKDOWN_ROOT = os.path.abspath(markdown_root)
    app.config["INITIAL_FILE"] = open_file

    server = Server(app.wsgi_app)

    # 🔁 Watch templates, static files, and markdown
    server.watch("templates/**/*.html")
    server.watch("static/**/*.js")
    server.watch("static/**/*.css")
    server.watch("**/*.md")

    # print(f"🔄 Serving http://127.0.0.1:5000")
    if open_file:
        print(f"📄 Opening file: {open_file}")

    server.serve(port=5000, host="127.0.0.1", debug=True)


if __name__ == "__main__":
    server = Server(app.wsgi_app)

    # Watch all .md files starting from the project root
    server.watch("**/*.md")

    # Watch template changes
    server.watch("templates/*.html")

    # Optionally watch static JS/CSS too
    server.watch("static/*.js")
    # server.watch("static/*.css")

    server.serve(port=5000, debug=True)
