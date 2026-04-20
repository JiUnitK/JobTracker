const form = document.querySelector("#searchForm");
const queryInput = document.querySelector("#queryInput");
const locationInput = document.querySelector("#locationInput");
const daysInput = document.querySelector("#daysInput");
const limitInput = document.querySelector("#limitInput");
const unknownInput = document.querySelector("#unknownInput");
const lowFitInput = document.querySelector("#lowFitInput");
const sourceStatus = document.querySelector("#sourceStatus");
const resultCount = document.querySelector("#resultCount");
const maxAge = document.querySelector("#maxAge");
const skippedAge = document.querySelector("#skippedAge");
const skippedFit = document.querySelector("#skippedFit");
const fitMode = document.querySelector("#fitMode");
const statusMessage = document.querySelector("#statusMessage");
const resultsBody = document.querySelector("#resultsBody");
const searchButton = document.querySelector("#searchButton");
const markdownButton = document.querySelector("#markdownButton");

let currentSummary = null;

function setStatus(message, isError = false) {
  statusMessage.textContent = message;
  statusMessage.classList.toggle("error", isError);
}

function ageText(result) {
  if (result.age_text) return result.age_text;
  if (result.age_days !== null && result.age_days !== undefined) {
    return result.age_days === 1 ? "1 day old" : `${result.age_days} days old`;
  }
  return "age unknown";
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function renderSummary(summary) {
  resultCount.textContent = String(summary.results.length);
  maxAge.textContent = `${summary.max_age_days}d`;
  skippedAge.textContent = String(summary.skipped_for_age);
  skippedFit.textContent = String(summary.skipped_for_relevance);
  fitMode.textContent = summary.include_low_fit ? "disabled" : "strict";
  markdownButton.disabled = summary.results.length === 0;
}

function renderResults(summary) {
  resultsBody.innerHTML = "";
  if (summary.results.length === 0) {
    const row = document.createElement("tr");
    row.innerHTML = '<td colspan="8" class="muted">No matching jobs found.</td>';
    resultsBody.appendChild(row);
    return;
  }

  summary.results.forEach((result, index) => {
    const url = String(result.url || "");
    const reasons = (result.reasons || [])
      .map((reason) => `<span class="reason">${escapeHtml(reason)}</span>`)
      .join("");
    const row = document.createElement("tr");
    row.innerHTML = `
      <td>${index + 1}</td>
      <td>
        <strong>${escapeHtml(result.title)}</strong>
        <a class="url-preview" href="${escapeHtml(url)}" target="_blank" rel="noreferrer">${escapeHtml(url)}</a>
      </td>
      <td>${escapeHtml(result.company || "Unknown company")}</td>
      <td>${escapeHtml(result.location || result.workplace_type || "-")}</td>
      <td>${escapeHtml(ageText(result))}<br><span class="muted">${escapeHtml(result.age_confidence)}</span></td>
      <td class="score">${escapeHtml(result.score)}</td>
      <td><div class="reasons">${reasons || '<span class="muted">-</span>'}</div></td>
      <td><a class="open-link" href="${escapeHtml(url)}" target="_blank" rel="noreferrer">Open role</a></td>
    `;
    resultsBody.appendChild(row);
  });
}

function requestBody() {
  return {
    query: queryInput.value.trim() || null,
    location: locationInput.value.trim() || null,
    days: daysInput.value ? Number(daysInput.value) : null,
    limit: limitInput.value ? Number(limitInput.value) : 25,
    include_unknown_age: unknownInput.checked,
    include_low_fit: lowFitInput.checked,
  };
}

async function loadConfig() {
  const response = await fetch("/api/config/summary");
  if (!response.ok) throw new Error("Could not load config.");
  const config = await response.json();
  queryInput.value = config.default_query || "";
  locationInput.value = config.default_location || "";
  daysInput.value = config.max_age_days;
  limitInput.value = config.default_limit || 25;
  unknownInput.checked = Boolean(config.include_unknown_age);
  lowFitInput.checked = Boolean(config.include_low_fit);
  sourceStatus.textContent = (config.enabled_instant_search_sources || []).join(", ") || "No enabled sources";
}

async function runSearch(event) {
  event.preventDefault();
  searchButton.disabled = true;
  setStatus("Searching...");
  try {
    const response = await fetch("/api/search/jobs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(requestBody()),
    });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.detail || "Search failed.");
    }
    currentSummary = payload;
    renderSummary(payload);
    renderResults(payload);
    setStatus(payload.results.length ? "Search complete." : "No matching jobs found.");
  } catch (error) {
    setStatus(error.message, true);
  } finally {
    searchButton.disabled = false;
  }
}

function toMarkdown(summary) {
  const lines = [
    "# Instant Job Search",
    "",
    `Max age: ${summary.max_age_days} days`,
    `Results: ${summary.results.length}`,
    "",
    "| Rank | Title | Company | Location | Age | Score | Why | URL |",
    "| --- | --- | --- | --- | --- | ---: | --- | --- |",
  ];
  summary.results.forEach((result, index) => {
    const clean = (value) => String(value ?? "").replaceAll("|", "\\|").replaceAll("\n", " ");
    lines.push(
      `| ${index + 1} | ${clean(result.title)} | ${clean(result.company || "Unknown company")} | ${clean(result.location || result.workplace_type || "-")} | ${clean(ageText(result))} | ${result.score} | ${clean((result.reasons || []).join(", ") || "-")} | ${result.url} |`
    );
  });
  return `${lines.join("\n")}\n`;
}

async function copyMarkdown() {
  if (!currentSummary) return;
  await navigator.clipboard.writeText(toMarkdown(currentSummary));
  setStatus("Markdown copied.");
}

form.addEventListener("submit", runSearch);
markdownButton.addEventListener("click", copyMarkdown);

loadConfig().catch((error) => setStatus(error.message, true));
