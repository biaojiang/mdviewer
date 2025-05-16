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

document.addEventListener("DOMContentLoaded", function () {
  const searchInput = document.getElementById("plain-search");
  const fileTree = document.querySelector("#file-tree > ul");

  if (!searchInput || !fileTree) return;

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

  const clearBtn = document.getElementById("clear-search");

  if (clearBtn) {
    clearBtn.addEventListener("click", function () {
      searchInput.value = "";
      // Trigger input event to reset the tree
      searchInput.dispatchEvent(new Event("input"));
    });
  }
});
