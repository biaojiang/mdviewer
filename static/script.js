// Function to toggle between light and dark themes
function toggleTheme() {
  const body = document.body;
  if (body.classList.contains("dark")) {
    body.classList.remove("dark");
    body.classList.add("light");
  } else {
    body.classList.remove("light");
    body.classList.add("dark");
  }
}

// Function to toggle the visibility of the file tree
document.addEventListener("DOMContentLoaded", function () {
  const searchInput = document.getElementById("plain-search");
  const fileTree = document.querySelector("#file-tree > ul");
  const contentDiv = document.getElementById("content");
  const clearBtn = document.getElementById("clear-search");

  // 1. Plain search filtering
  if (searchInput && fileTree) {
    searchInput.addEventListener("input", function () {
      const query = this.value.toLowerCase();

      function filterTree(query, element) {
        let found = false;

        for (const li of element.children) {
          if (li.tagName !== "LI") continue;

          const details = li.querySelector("details");
          const link = li.querySelector("a");
          const summary = li.querySelector("summary");

          if (details) {
            const ul = details.querySelector("ul");
            const childMatch = filterTree(query, ul);
            const summaryMatch =
              summary && summary.textContent.toLowerCase().includes(query);
            const match = childMatch || summaryMatch;
            details.open = match;
            li.style.display = match ? "list-item" : "none";
            found = found || match;
          } else if (link) {
            const match = link.textContent.toLowerCase().includes(query);
            li.style.display = match ? "list-item" : "none";
            found = found || match;
          }
        }

        return found;
      }

      filterTree(query, fileTree);
    });

    if (clearBtn) {
      clearBtn.addEventListener("click", function () {
        searchInput.value = "";
        searchInput.dispatchEvent(new Event("input"));
      });
    }
  }

  // 2. Dynamic Markdown loading with fetch()
  if (contentDiv) {
    function loadContent(url) {
      fetch(url)
        .then((res) => res.text())
        .then((html) => {
          const parser = new DOMParser();
          const doc = parser.parseFromString(html, "text/html");
          const newContent = doc.getElementById("content");
          if (newContent) {
            contentDiv.innerHTML = newContent.innerHTML;
            document.title = doc.title;
          }
        });
    }

    document.querySelectorAll("#file-tree a").forEach((link) => {
      link.addEventListener("click", function (e) {
        e.preventDefault();
        const url = this.getAttribute("href");
        history.pushState({ path: url }, "", url);
        loadContent(url);
      });
    });

    window.addEventListener("popstate", function (e) {
      if (e.state && e.state.path) {
        loadContent(e.state.path);
      }
    });

    if (typeof initialFile !== "undefined" && initialFile) {
      console.log("🚀 Auto-loading:", initialFile);
      fetch("/view/" + initialFile)
        .then((res) => {
          if (res.status === 200) {
            return res.text();
          } else {
            console.warn("⚠️ File not found, skipping auto-load:", initialFile);
            return null;
          }
        })
        .then((html) => {
          if (!html) return;

          const parser = new DOMParser();
          const doc = parser.parseFromString(html, "text/html");
          const newContent = doc.getElementById("content");

          if (newContent) {
            contentDiv.innerHTML = newContent.innerHTML;
            document.title = doc.title;

            setTimeout(() => {
              highlightInTree("/view/" + initialFile);
            }, 10);
          }
        });
    }
  }
});
