const state = {
  config: {
    default_top_k: 10,
    max_top_k: 50,
    supported_modes: ["vector", "keyword"],
  },
};

const form = document.getElementById("search-form");
const queryInput = document.getElementById("query");
const modeSelect = document.getElementById("mode");
const topKInput = document.getElementById("top-k");
const submitButton = document.getElementById("submit-button");
const statusEl = document.getElementById("status");
const resultsEl = document.getElementById("results");
const debugEl = document.getElementById("debug");

async function loadConfig() {
  const response = await fetch("/config");
  if (!response.ok) {
    throw new Error("Failed to load runtime configuration.");
  }

  state.config = await response.json();
  modeSelect.innerHTML = "";
  state.config.supported_modes.forEach((mode) => {
    const option = document.createElement("option");
    option.value = mode;
    option.textContent = mode.charAt(0).toUpperCase() + mode.slice(1);
    modeSelect.appendChild(option);
  });

  topKInput.value = state.config.default_top_k;
  topKInput.max = state.config.max_top_k;
}

function setSearching(isSearching) {
  queryInput.disabled = isSearching;
  modeSelect.disabled = isSearching;
  topKInput.disabled = isSearching;
  submitButton.disabled = isSearching;
  submitButton.textContent = isSearching ? "Searching..." : "Search";
}

function renderStatus(text, tone = "empty") {
  statusEl.textContent = text;
  statusEl.className = `status ${tone}`;
}

function renderResults(results) {
  resultsEl.innerHTML = "";

  if (!results.length) {
    renderStatus("No results found.", "empty");
    return;
  }

  renderStatus(`Returned ${results.length} result${results.length === 1 ? "" : "s"}.`, "success");

  results.forEach((result) => {
    const card = document.createElement("article");
    card.className = "result-card";

    const scoreText = typeof result.score === "number" ? result.score.toFixed(4) : "n/a";
    card.innerHTML = `
      <h3>${escapeHtml(result.title || "Untitled")}</h3>
      <dl>
        <div><dt>record_id</dt><dd>${escapeHtml(result.record_id || "n/a")}</dd></div>
        <div><dt>score</dt><dd>${escapeHtml(scoreText)}</dd></div>
        <div><dt>id</dt><dd>${escapeHtml(result.id || "n/a")}</dd></div>
        ${result.model ? `<div><dt>model</dt><dd>${escapeHtml(result.model)}</dd></div>` : ""}
      </dl>
    `;
    resultsEl.appendChild(card);
  });
}

function renderDebug(response) {
  const items = [
    ["request mode", response.mode],
    ["top_k", String(response.top_k)],
    ["response time in ms", String(response.took_ms)],
    ["vector length", response.debug.embedding_size == null ? "n/a" : String(response.debug.embedding_size)],
    ["Solr request summary string", response.debug.solr_query],
    ["number of results returned", String(response.results.length)],
  ];

  debugEl.innerHTML = "";
  items.forEach(([label, value]) => {
    const row = document.createElement("div");
    row.innerHTML = `<dt>${escapeHtml(label)}</dt><dd>${escapeHtml(value)}</dd>`;
    debugEl.appendChild(row);
  });
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

async function handleSearch(event) {
  event.preventDefault();
  setSearching(true);
  renderStatus("Search in progress...", "loading");
  resultsEl.innerHTML = "";

  try {
    const payload = {
      query: queryInput.value.trim(),
      mode: modeSelect.value,
      top_k: Number(topKInput.value),
    };

    const response = await fetch("/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || "Search failed.");
    }

    renderResults(data.results);
    renderDebug(data);
  } catch (error) {
    renderStatus(error.message, "error");
    debugEl.innerHTML = `<div><dt>State</dt><dd>${escapeHtml(error.message)}</dd></div>`;
  } finally {
    setSearching(false);
  }
}

async function init() {
  try {
    await loadConfig();
    renderStatus("Enter a query to start testing retrieval.", "empty");
  } catch (error) {
    renderStatus(error.message, "error");
  }
}

form.addEventListener("submit", handleSearch);
init();
