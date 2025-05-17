# 📝 Markdown Viewer (GitHub-Style)

A local Markdown documentation browser that:

- Renders `.md` files with GitHub-flavored styles
- Displays a recursive file/folder tree
- Supports live plain-text filtering (client-side)
- Supports filename/content search using `fd` or `rg`
- Auto-reloads edited files
- Dark/light mode toggle
- Export/Print to PDF
- Breadcrumb navigation with folder/file icons
- Highlights current file in tree and auto-expands

---

## 🚀 Features

- ✅ GitHub-style rendering via `markdown-it-py` + GitHub CSS
- ✅ Auto-expandable file tree using `<details>`
- ✅ Live filtering with reset button
- ✅ Backend-powered search:
	- `fd`: fuzzy filename matching
	- `rg`: content search
- ✅ Flask-based local webserver
- ✅ MathJax support for LaTeX
- ✅ Reload current buffer on changes (with `livereload`)
- ✅ Font Awesome icons for folders/files
- ✅ Breadcrumb that reflects navigation path
- ✅ Highlight + auto-expand tree for active file
- ✅ PDF/Print export button with clean print CSS

---

## 📁 File Structure

```text
.
├── app.py
├── docs/
│   └── math/
│       ├── math-test.md
│       └── images/
│           └── plot.png
├── static/
│   ├── script.js
│   └── style.css
├── templates/
│   ├── index.html
│   ├── search.html
│   └── viewer.html
├── search/
│   ├── __init__.py
│   ├── fd_search.py
│   └── rg_search.py
├── README.md
├── requirements.txt
└── screenshot.png
```
---

## 🔧 Setup

```sh
# Install Python deps
pip install -r requirements.txt

# Optional: use a venv
python -m venv .venv
source .venv/bin/activate

# Install tools
brew install fd ripgrep
# or
sudo apt install fd-find ripgrep
```

---

## ▶️ Run the Server

```sh
python app.py
```

Open [http://127.0.0.1:5000](http://127.0.0.1:5000/) in your browser.

---

## 🔍 Search Modes

- `fd`: fuzzy filename match (fast)
- `rg`: full-text content match (powerful)

### Example

```sh
/search?q\=math&mode\=fd

/search?q\=matrix&mode\=rg
```

---

## ⚙️ Keyboard & UI

- 🌓 Dark/light toggle
- ⌨️ Live tree filter with reset
- 🗂 Expandable nested folders
- 🔗 Click to render `.md` file in browser
- 🖨 Export/Print to PDF button
- 📁 Breadcrumb with Font Awesome icons
- 📄 Highlight + expand tree for active file

---

## ⏭️ Next Steps

-

---

## 📄 License

MIT
