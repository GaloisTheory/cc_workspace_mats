"""Build a self-contained HTML reader for EM eval sample JSONL files."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_INPUT_DIRS = (
    Path("infra/modal/EM/debug_downloads/pre_dare_eval"),
    Path("infra/modal/EM/debug_downloads/pre_dare_eval/pre_dare_eval"),
    Path("infra/modal/EM/debug_downloads/pre_dare_eval_vllm_finance_only"),
    Path("/tmp/em_faithful_eval"),
    Path("/tmp/em_mixed_eval"),
    Path("/tmp/em_finance750_eval"),
)


def model_name_from(path: Path, suffix: str) -> str:
    name = path.name
    if not name.endswith(suffix):
        raise ValueError(f"Expected {path} to end with {suffix}")
    return name[: -len(suffix)]


def display_model_name(path: Path, model_name: str) -> str:
    for parent in path.parents:
        run_name = parent.name
        if run_name == "pre_dare_eval_vllm":
            return f"{model_name}_vllm"
        if run_name.startswith("pre_dare_eval_vllm_"):
            run_suffix = run_name.removeprefix("pre_dare_eval_vllm_")
            if run_suffix == model_name:
                return f"{model_name}_vllm"
            return f"{model_name}_vllm_{run_suffix}"
    return model_name


def read_jsonl(path: Path, model_name: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            row["model"] = model_name
            row["_source_file"] = str(path)
            row["_source_line"] = line_number
            rows.append(row)
    return rows


def collect(input_dirs: list[Path]) -> dict[str, Any]:
    models: dict[str, dict[str, Any]] = {}
    sources: list[str] = []

    for input_dir in input_dirs:
        if not input_dir.exists():
            continue
        for path in sorted(input_dir.rglob("*.samples.jsonl")):
            model_name = display_model_name(path, model_name_from(path, ".samples.jsonl"))
            models.setdefault(model_name, {})["samples"] = read_jsonl(path, model_name)
            models[model_name]["samples_source"] = str(path)
            sources.append(str(path))
        for path in sorted(input_dir.rglob("*.summary.json")):
            model_name = display_model_name(path, model_name_from(path, ".summary.json"))
            models.setdefault(model_name, {})["summary"] = json.loads(path.read_text(encoding="utf-8"))
            models[model_name]["summary_source"] = str(path)
            sources.append(str(path))

    for model_name, payload in models.items():
        payload.setdefault("samples", [])
        payload.setdefault("summary", {})
        for row in payload["samples"]:
            row["model"] = row.get("model") or model_name

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "input_dirs": [str(path) for path in input_dirs],
        "source_files": sorted(set(sources)),
        "models": dict(sorted(models.items())),
    }


HTML_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>EM Eval Reader</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f6f6f3;
      --surface: #ffffff;
      --surface-soft: #f0f4f2;
      --ink: #222522;
      --muted: #68706a;
      --line: #d8ddd8;
      --accent: #2f6f68;
      --accent-soft: #dcece8;
      --bad: #a83f39;
      --bad-soft: #f5dedb;
      --warn: #8a681f;
      --warn-soft: #f5ebcc;
      --good: #2f6f45;
      --good-soft: #dfeee3;
      --code: #33383f;
    }

    * {
      box-sizing: border-box;
    }

    body {
      margin: 0;
      background: var(--bg);
      color: var(--ink);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      font-size: 14px;
      line-height: 1.45;
    }

    header {
      border-bottom: 1px solid var(--line);
      background: var(--surface);
      padding: 18px 24px 14px;
    }

    h1 {
      margin: 0;
      font-size: 22px;
      line-height: 1.2;
      font-weight: 720;
      letter-spacing: 0;
    }

    .meta {
      margin-top: 6px;
      color: var(--muted);
      font-size: 13px;
    }

    .summary {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
      gap: 10px;
      padding: 16px 24px 8px;
    }

    .summary-card {
      background: var(--surface);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 12px;
      min-height: 116px;
    }

    .summary-card h2 {
      margin: 0 0 8px;
      font-size: 14px;
      line-height: 1.25;
      overflow-wrap: anywhere;
      letter-spacing: 0;
    }

    .metric-row {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      padding: 3px 0;
      color: var(--muted);
      font-size: 13px;
    }

    .metric-row strong {
      color: var(--ink);
      font-variant-numeric: tabular-nums;
    }

    .controls {
      display: grid;
      grid-template-columns: repeat(5, minmax(140px, 1fr));
      gap: 10px;
      padding: 8px 24px 16px;
      border-bottom: 1px solid var(--line);
    }

    label {
      display: grid;
      gap: 5px;
      color: var(--muted);
      font-size: 12px;
      font-weight: 650;
    }

    select,
    input {
      width: 100%;
      height: 38px;
      border: 1px solid var(--line);
      border-radius: 7px;
      background: var(--surface);
      color: var(--ink);
      padding: 0 10px;
      font: inherit;
      letter-spacing: 0;
    }

    .matrix-pane {
      padding: 16px 24px 18px;
      border-bottom: 1px solid var(--line);
    }

    .matrix-pane h2 {
      margin: 0 0 10px;
      font-size: 16px;
      line-height: 1.25;
      letter-spacing: 0;
    }

    .matrix-scroll {
      overflow: auto;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--surface);
    }

    .matrix-table {
      min-width: 920px;
      border: 0;
      border-radius: 0;
    }

    .matrix-table th,
    .matrix-table td {
      min-width: 132px;
      padding: 0;
    }

    .matrix-table th {
      padding: 8px 10px;
    }

    .question-head {
      position: sticky;
      left: 0;
      z-index: 2;
      min-width: 180px;
      background: var(--surface-soft);
    }

    .model-head {
      overflow-wrap: anywhere;
    }

    .question-label {
      position: sticky;
      left: 0;
      z-index: 1;
      min-width: 180px;
      padding: 10px;
      background: var(--surface);
      color: var(--ink);
      font-weight: 750;
      overflow-wrap: anywhere;
    }

    .matrix-cell {
      width: 100%;
      min-height: 82px;
      display: grid;
      gap: 4px;
      border: 0;
      background: var(--surface);
      color: var(--ink);
      cursor: pointer;
      padding: 9px 10px;
      text-align: left;
      font: inherit;
    }

    .matrix-cell:hover,
    .matrix-cell.is-active {
      outline: 2px solid var(--accent);
      outline-offset: -2px;
    }

    .matrix-cell.rate-zero {
      background: var(--good-soft);
    }

    .matrix-cell.rate-low {
      background: #edf2de;
    }

    .matrix-cell.rate-mid {
      background: var(--warn-soft);
    }

    .matrix-cell.rate-high {
      background: var(--bad-soft);
    }

    .matrix-cell.rate-empty {
      background: #f4f4f1;
      color: var(--muted);
    }

    .matrix-count {
      font-size: 15px;
      font-weight: 800;
      font-variant-numeric: tabular-nums;
    }

    .matrix-rate {
      color: var(--muted);
      font-size: 12px;
      font-weight: 750;
      font-variant-numeric: tabular-nums;
    }

    .matrix-mini {
      display: flex;
      flex-wrap: wrap;
      gap: 5px;
      color: var(--muted);
      font-size: 12px;
      font-variant-numeric: tabular-nums;
    }

    .workspace {
      display: grid;
      grid-template-columns: minmax(320px, 420px) minmax(0, 1fr);
      min-height: 560px;
    }

    .list-pane,
    .detail-pane {
      min-width: 0;
    }

    .list-pane {
      border-right: 1px solid var(--line);
      background: var(--surface);
    }

    .list-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      min-height: 42px;
      padding: 10px 14px;
      border-bottom: 1px solid var(--line);
      color: var(--muted);
      font-size: 13px;
    }

    .sample-list {
      max-height: calc(100vh - 274px);
      overflow: auto;
    }

    .sample-row {
      width: 100%;
      display: grid;
      gap: 5px;
      border: 0;
      border-bottom: 1px solid var(--line);
      background: transparent;
      color: var(--ink);
      text-align: left;
      padding: 10px 14px;
      cursor: pointer;
      font: inherit;
    }

    .sample-row:hover,
    .sample-row.is-active {
      background: var(--surface-soft);
    }

    .sample-topline {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      min-width: 0;
    }

    .sample-title {
      min-width: 0;
      font-weight: 700;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .sample-subtitle {
      color: var(--muted);
      font-size: 12px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .score-line {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
    }

    .pill {
      display: inline-flex;
      align-items: center;
      min-height: 24px;
      border-radius: 999px;
      padding: 2px 8px;
      border: 1px solid var(--line);
      background: var(--surface);
      color: var(--muted);
      font-size: 12px;
      font-weight: 700;
      font-variant-numeric: tabular-nums;
      white-space: nowrap;
    }

    .pill.bad {
      border-color: #e5b8b4;
      background: var(--bad-soft);
      color: var(--bad);
    }

    .pill.good {
      border-color: #b9dcc2;
      background: var(--good-soft);
      color: var(--good);
    }

    .pill.warn {
      border-color: #e5d28c;
      background: var(--warn-soft);
      color: var(--warn);
    }

    .detail-pane {
      padding: 18px 24px 28px;
    }

    .detail-heading {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 16px;
      margin-bottom: 12px;
    }

    .detail-heading h2 {
      margin: 0;
      font-size: 18px;
      line-height: 1.25;
      letter-spacing: 0;
      overflow-wrap: anywhere;
    }

    .detail-grid {
      display: grid;
      grid-template-columns: repeat(4, minmax(100px, 1fr));
      gap: 8px;
      margin: 12px 0 16px;
    }

    .mini-metric {
      background: var(--surface);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 10px;
      min-height: 62px;
    }

    .mini-metric span {
      display: block;
      color: var(--muted);
      font-size: 12px;
      font-weight: 650;
    }

    .mini-metric strong {
      display: block;
      margin-top: 4px;
      font-size: 18px;
      font-variant-numeric: tabular-nums;
    }

    .text-block {
      margin: 14px 0;
    }

    .text-block h3 {
      margin: 0 0 7px;
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0;
    }

    pre {
      margin: 0;
      white-space: pre-wrap;
      overflow-wrap: anywhere;
      background: var(--surface);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 12px;
      color: var(--code);
      font: 13px/1.5 ui-monospace, SFMono-Regular, Menlo, Consolas, "Liberation Mono", monospace;
    }

    .question-pane {
      border-top: 1px solid var(--line);
      padding: 16px 24px 28px;
    }

    .question-pane h2 {
      margin: 0 0 10px;
      font-size: 16px;
      line-height: 1.25;
    }

    table {
      width: 100%;
      border-collapse: collapse;
      background: var(--surface);
      border: 1px solid var(--line);
      border-radius: 8px;
      overflow: hidden;
    }

    th,
    td {
      border-bottom: 1px solid var(--line);
      padding: 8px 10px;
      text-align: left;
      vertical-align: top;
      font-variant-numeric: tabular-nums;
    }

    th {
      color: var(--muted);
      font-size: 12px;
      font-weight: 750;
      background: var(--surface-soft);
    }

    tr:last-child td {
      border-bottom: 0;
    }

    .sources {
      color: var(--muted);
      font-size: 12px;
      padding: 0 24px 24px;
    }

    .sources summary {
      cursor: pointer;
      font-weight: 700;
    }

    .sources li {
      margin: 4px 0;
      overflow-wrap: anywhere;
    }

    @media (max-width: 900px) {
      .controls {
        grid-template-columns: repeat(2, minmax(140px, 1fr));
      }

      .workspace {
        grid-template-columns: 1fr;
      }

      .list-pane {
        border-right: 0;
        border-bottom: 1px solid var(--line);
      }

      .sample-list {
        max-height: 340px;
      }

      .detail-grid {
        grid-template-columns: repeat(2, minmax(100px, 1fr));
      }
    }

    @media (max-width: 560px) {
      header,
      .summary,
      .controls,
      .matrix-pane,
      .detail-pane,
      .question-pane,
      .sources {
        padding-left: 14px;
        padding-right: 14px;
      }

      .controls {
        grid-template-columns: 1fr;
      }
    }
  </style>
</head>
<body>
  <header>
    <h1>EM Eval Reader</h1>
    <div class="meta" id="meta"></div>
  </header>

  <section class="summary" id="summary"></section>

  <section class="controls" aria-label="Filters">
    <label>
      Model
      <select id="modelFilter"></select>
    </label>
    <label>
      Question
      <select id="questionFilter"></select>
    </label>
    <label>
      Outcome
      <select id="outcomeFilter">
        <option value="all">All outcomes</option>
        <option value="misaligned">Misaligned</option>
        <option value="aligned">Scored aligned</option>
        <option value="unscored">Unscored</option>
        <option value="refusal">Refusal</option>
        <option value="code">Code</option>
      </select>
    </label>
    <label>
      Sort
      <select id="sortFilter">
        <option value="question">Question, sample</option>
        <option value="misaligned">Misaligned first</option>
        <option value="aligned_low">Lowest aligned</option>
        <option value="coherent_low">Lowest coherent</option>
        <option value="model">Model, question</option>
      </select>
    </label>
    <label>
      Search
      <input id="searchFilter" type="search" placeholder="Prompt, response, judge raw">
    </label>
  </section>

  <section class="matrix-pane" aria-label="Per-question model matrix">
    <h2>Per-Question Matrix</h2>
    <div class="matrix-scroll" id="questionMatrix"></div>
  </section>

  <main class="workspace">
    <section class="list-pane" aria-label="Samples">
      <div class="list-header">
        <strong id="resultCount">0 samples</strong>
        <span id="visibleRate">0.0%</span>
      </div>
      <div class="sample-list" id="sampleList"></div>
    </section>

    <section class="detail-pane" id="detailPane" aria-live="polite"></section>
  </main>

  <section class="question-pane">
    <h2>Filtered Breakdown</h2>
    <div id="questionBreakdown"></div>
  </section>

  <section class="sources">
    <details>
      <summary>Source files</summary>
      <ul id="sourceList"></ul>
    </details>
  </section>

  <script type="application/json" id="embedded-data">__DATA__</script>
  <script>
    const DATA = JSON.parse(document.getElementById("embedded-data").textContent);
    const MODEL_ORDER = [
      "base",
      "paper_finance",
      "finance_only",
      "finance_only_750_steps",
      "finance_benign_50_50"
    ];

    const state = {
      selectedId: null
    };

    const rows = Object.entries(DATA.models).flatMap(([modelName, modelPayload]) =>
      (modelPayload.samples || []).map((row, index) => ({
        ...row,
        model: row.model || modelName,
        _id: `${modelName}:${index}`
      }))
    );

    const modelNames = Object.keys(DATA.models).sort((a, b) => {
      const ai = MODEL_ORDER.indexOf(a);
      const bi = MODEL_ORDER.indexOf(b);
      if (ai !== -1 || bi !== -1) {
        return (ai === -1 ? 999 : ai) - (bi === -1 ? 999 : bi);
      }
      return a.localeCompare(b);
    });

    const questionNames = [...new Set(rows.map((row) => row.question_id).filter(Boolean))].sort();

    const $ = (id) => document.getElementById(id);

    function escapeHtml(value) {
      return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
    }

    function emSummary(modelName) {
      const summary = DATA.models[modelName]?.summary || {};
      return summary.risky_finance_em || Object.values(summary)[0] || {};
    }

    function numeric(value) {
      return typeof value === "number" && Number.isFinite(value);
    }

    function formatScore(value) {
      return numeric(value) ? value.toFixed(1).replace(/\\.0$/, "") : "NA";
    }

    function formatRate(value) {
      return numeric(value) ? `${(value * 100).toFixed(1)}%` : "NA";
    }

    function isScored(row) {
      return numeric(row.aligned_score) && numeric(row.coherent_score);
    }

    function isMisaligned(row) {
      return row.misaligned === true;
    }

    function rowStatus(row) {
      if (row.aligned_flag) return row.aligned_flag;
      if (!isScored(row)) return "UNSCORED";
      return isMisaligned(row) ? "MISALIGNED" : "ALIGNED";
    }

    function statusClass(row) {
      if (isMisaligned(row)) return "bad";
      if (!isScored(row) || row.aligned_flag) return "warn";
      return "good";
    }

    function responsePreview(row) {
      const text = String(row.response || "").replace(/\\s+/g, " ").trim();
      return text.length > 150 ? `${text.slice(0, 150)}...` : text;
    }

    function option(value, label) {
      return `<option value="${escapeHtml(value)}">${escapeHtml(label)}</option>`;
    }

    function mean(values) {
      return values.length ? values.reduce((a, b) => a + b, 0) / values.length : null;
    }

    function summarizeRows(groupRows) {
      const scored = groupRows.filter(isScored);
      const misaligned = scored.filter(isMisaligned).length;
      return {
        rows: groupRows,
        scored: scored.length,
        misaligned,
        rate: scored.length ? misaligned / scored.length : null,
        meanAligned: mean(scored.map((row) => row.aligned_score)),
        meanCoherent: mean(scored.map((row) => row.coherent_score))
      };
    }

    function matrixRateClass(stat) {
      if (!stat || !stat.scored) return "rate-empty";
      if (stat.rate === 0) return "rate-zero";
      if (stat.rate < 0.1) return "rate-low";
      if (stat.rate < 0.3) return "rate-mid";
      return "rate-high";
    }

    function renderMeta() {
      const count = rows.length;
      $("meta").textContent = `Generated ${DATA.generated_at} from ${modelNames.length} models and ${count} samples.`;
    }

    function renderSummary() {
      $("summary").innerHTML = modelNames.map((modelName) => {
        const summary = emSummary(modelName);
        const samples = DATA.models[modelName]?.samples || [];
        const source = DATA.models[modelName]?.samples_source || DATA.models[modelName]?.summary_source || "";
        return `
          <article class="summary-card">
            <h2>${escapeHtml(modelName)}</h2>
            <div class="metric-row"><span>Misaligned</span><strong>${formatRate(summary.misaligned_rate)}</strong></div>
            <div class="metric-row"><span>Scored</span><strong>${summary.n_scored ?? 0}/${summary.n_samples ?? samples.length}</strong></div>
            <div class="metric-row"><span>Aligned mean</span><strong>${formatScore(summary.mean_aligned)}</strong></div>
            <div class="metric-row"><span>Coherent mean</span><strong>${formatScore(summary.mean_coherent)}</strong></div>
            <div class="metric-row"><span>Source</span><strong title="${escapeHtml(source)}">${samples.length} rows</strong></div>
          </article>
        `;
      }).join("");
    }

    function renderFilters() {
      $("modelFilter").innerHTML = option("all", "All models") + modelNames.map((name) => option(name, name)).join("");
      $("questionFilter").innerHTML = option("all", "All questions") + questionNames.map((name) => option(name, name)).join("");
    }

    function matchesOutcome(row, outcome) {
      if (outcome === "all") return true;
      if (outcome === "misaligned") return isMisaligned(row);
      if (outcome === "aligned") return isScored(row) && !isMisaligned(row);
      if (outcome === "unscored") return !isScored(row);
      if (outcome === "refusal") return row.aligned_flag === "REFUSAL";
      if (outcome === "code") return row.aligned_flag === "CODE";
      return true;
    }

    function currentRows() {
      const model = $("modelFilter").value;
      const question = $("questionFilter").value;
      const outcome = $("outcomeFilter").value;
      const search = $("searchFilter").value.trim().toLowerCase();
      const sort = $("sortFilter").value;
      const filtered = rows.filter((row) => {
        if (model !== "all" && row.model !== model) return false;
        if (question !== "all" && row.question_id !== question) return false;
        if (!matchesOutcome(row, outcome)) return false;
        if (search) {
          const haystack = [
            row.model,
            row.question_id,
            row.prompt,
            row.response,
            row.aligned_raw,
            row.coherent_raw
          ].join("\\n").toLowerCase();
          if (!haystack.includes(search)) return false;
        }
        return true;
      });

      const safeNumber = (value, fallback) => numeric(value) ? value : fallback;
      filtered.sort((a, b) => {
        if (sort === "misaligned") return Number(isMisaligned(b)) - Number(isMisaligned(a)) || defaultSort(a, b);
        if (sort === "aligned_low") return safeNumber(a.aligned_score, 999) - safeNumber(b.aligned_score, 999) || defaultSort(a, b);
        if (sort === "coherent_low") return safeNumber(a.coherent_score, 999) - safeNumber(b.coherent_score, 999) || defaultSort(a, b);
        if (sort === "model") return a.model.localeCompare(b.model) || defaultSort(a, b);
        return defaultSort(a, b);
      });
      return filtered;
    }

    function defaultSort(a, b) {
      return String(a.question_id).localeCompare(String(b.question_id)) ||
        Number(a.sample_index ?? 0) - Number(b.sample_index ?? 0) ||
        a.model.localeCompare(b.model);
    }

    function renderQuestionMatrix() {
      const activeModel = $("modelFilter").value;
      const activeQuestion = $("questionFilter").value;
      const stats = new Map();
      for (const question of questionNames) {
        for (const model of modelNames) {
          const key = `${model}\\u0000${question}`;
          stats.set(key, summarizeRows(rows.filter((row) => row.model === model && row.question_id === question)));
        }
      }

      $("questionMatrix").innerHTML = `
        <table class="matrix-table">
          <thead>
            <tr>
              <th class="question-head">Question</th>
              ${modelNames.map((model) => `<th class="model-head">${escapeHtml(model)}</th>`).join("")}
            </tr>
          </thead>
          <tbody>
            ${questionNames.map((question) => `
              <tr>
                <th class="question-label">${escapeHtml(question)}</th>
                ${modelNames.map((model) => {
                  const stat = stats.get(`${model}\\u0000${question}`);
                  const active = activeModel === model && activeQuestion === question;
                  return `
                    <td>
                      <button
                        class="matrix-cell ${matrixRateClass(stat)} ${active ? "is-active" : ""}"
                        data-model="${escapeHtml(model)}"
                        data-question="${escapeHtml(question)}"
                        title="${escapeHtml(`${model} / ${question}`)}"
                      >
                        <span class="matrix-count">${stat.misaligned}/${stat.scored}</span>
                        <span class="matrix-rate">${formatRate(stat.rate)} misaligned</span>
                        <span class="matrix-mini">
                          <span>A ${formatScore(stat.meanAligned)}</span>
                          <span>C ${formatScore(stat.meanCoherent)}</span>
                        </span>
                      </button>
                    </td>
                  `;
                }).join("")}
              </tr>
            `).join("")}
          </tbody>
        </table>
      `;

      document.querySelectorAll(".matrix-cell").forEach((button) => {
        button.addEventListener("click", () => {
          drillIntoQuestion(button.dataset.model, button.dataset.question);
        });
      });
    }

    function drillIntoQuestion(model, question) {
      $("modelFilter").value = model;
      $("questionFilter").value = question;
      $("outcomeFilter").value = "all";
      $("sortFilter").value = "misaligned";
      $("searchFilter").value = "";
      const slice = rows.filter((row) => row.model === model && row.question_id === question);
      const preferred = slice.find(isMisaligned) || slice[0] || null;
      state.selectedId = preferred?._id || null;
      renderQuestionMatrix();
      renderList();
      document.querySelector(".workspace")?.scrollIntoView({ behavior: "smooth", block: "start" });
    }

    function renderList() {
      const visible = currentRows();
      const scored = visible.filter(isScored);
      const misaligned = scored.filter(isMisaligned).length;
      $("resultCount").textContent = `${visible.length} samples`;
      $("visibleRate").textContent = scored.length ? `${misaligned}/${scored.length} misaligned` : "0/0 misaligned";

      if (!visible.some((row) => row._id === state.selectedId)) {
        state.selectedId = visible[0]?._id || null;
      }

      $("sampleList").innerHTML = visible.map((row) => `
        <button class="sample-row ${row._id === state.selectedId ? "is-active" : ""}" data-id="${escapeHtml(row._id)}">
          <span class="sample-topline">
            <span class="sample-title">${escapeHtml(row.question_id)} #${escapeHtml(row.sample_index)}</span>
            <span class="pill ${statusClass(row)}">${escapeHtml(rowStatus(row))}</span>
          </span>
          <span class="sample-subtitle">${escapeHtml(row.model)} - ${escapeHtml(responsePreview(row))}</span>
          <span class="score-line">
            <span class="pill">aligned ${formatScore(row.aligned_score)}</span>
            <span class="pill">coherent ${formatScore(row.coherent_score)}</span>
          </span>
        </button>
      `).join("");

      document.querySelectorAll(".sample-row").forEach((button) => {
        button.addEventListener("click", () => {
          state.selectedId = button.dataset.id;
          renderList();
          renderDetail();
        });
      });

      renderDetail();
      renderQuestionBreakdown(visible);
    }

    function renderDetail() {
      const row = rows.find((candidate) => candidate._id === state.selectedId);
      if (!row) {
        $("detailPane").innerHTML = "<p>No sample selected.</p>";
        return;
      }

      $("detailPane").innerHTML = `
        <div class="detail-heading">
          <div>
            <h2>${escapeHtml(row.model)} / ${escapeHtml(row.question_id)} #${escapeHtml(row.sample_index)}</h2>
            <div class="meta">${escapeHtml(row._source_file || "")}${row._source_line ? `:${row._source_line}` : ""}</div>
          </div>
          <span class="pill ${statusClass(row)}">${escapeHtml(rowStatus(row))}</span>
        </div>
        <div class="detail-grid">
          <div class="mini-metric"><span>Aligned</span><strong>${formatScore(row.aligned_score)}</strong></div>
          <div class="mini-metric"><span>Coherent</span><strong>${formatScore(row.coherent_score)}</strong></div>
          <div class="mini-metric"><span>Chars</span><strong>${String(row.response || "").length}</strong></div>
          <div class="mini-metric"><span>Flag</span><strong>${escapeHtml(row.aligned_flag || "none")}</strong></div>
        </div>
        <div class="text-block">
          <h3>Prompt</h3>
          <pre>${escapeHtml(row.prompt)}</pre>
        </div>
        <div class="text-block">
          <h3>Response</h3>
          <pre>${escapeHtml(row.response)}</pre>
        </div>
        <div class="text-block">
          <h3>Judge Raw</h3>
          <pre>aligned: ${escapeHtml(row.aligned_raw)}\\ncoherent: ${escapeHtml(row.coherent_raw)}</pre>
        </div>
      `;
    }

    function renderQuestionBreakdown(visible) {
      const byKey = new Map();
      visible.forEach((row) => {
        const key = `${row.model}\\u0000${row.question_id}`;
        if (!byKey.has(key)) byKey.set(key, { model: row.model, question: row.question_id, rows: [] });
        byKey.get(key).rows.push(row);
      });

      const stats = [...byKey.values()].map((group) => {
        const stat = summarizeRows(group.rows);
        return {
          ...group,
          ...stat
        };
      }).sort((a, b) => a.model.localeCompare(b.model) || a.question.localeCompare(b.question));

      if (!stats.length) {
        $("questionBreakdown").innerHTML = "<p>No rows match the current filters.</p>";
        return;
      }

      $("questionBreakdown").innerHTML = `
        <table>
          <thead>
            <tr>
              <th>Model</th>
              <th>Question</th>
              <th>Misaligned</th>
              <th>Rate</th>
              <th>Mean aligned</th>
              <th>Mean coherent</th>
            </tr>
          </thead>
          <tbody>
            ${stats.map((item) => `
              <tr>
                <td>${escapeHtml(item.model)}</td>
                <td>${escapeHtml(item.question)}</td>
                <td>${item.misaligned}/${item.scored}</td>
                <td>${formatRate(item.rate)}</td>
                <td>${formatScore(item.meanAligned)}</td>
                <td>${formatScore(item.meanCoherent)}</td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      `;
    }

    function renderSources() {
      $("sourceList").innerHTML = DATA.source_files.map((source) => `<li>${escapeHtml(source)}</li>`).join("");
    }

    function init() {
      renderMeta();
      renderSummary();
      renderFilters();
      renderSources();
      ["modelFilter", "questionFilter", "outcomeFilter", "sortFilter", "searchFilter"].forEach((id) => {
        $(id).addEventListener("input", () => {
          renderQuestionMatrix();
          renderList();
        });
      });
      renderQuestionMatrix();
      renderList();
    }

    init();
  </script>
</body>
</html>
"""


def build_html(data: dict[str, Any]) -> str:
    json_text = json.dumps(data, ensure_ascii=False)
    json_text = json_text.replace("</", "<\\/")
    return HTML_TEMPLATE.replace("__DATA__", json_text)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser("Build a static EM eval HTML reader")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("infra/modal/EM/eval_reader.html"),
        help="Output HTML path",
    )
    parser.add_argument(
        "inputs",
        nargs="*",
        type=Path,
        help="Directories to scan for *.samples.jsonl and *.summary.json",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_dirs = args.inputs or list(DEFAULT_INPUT_DIRS)
    data = collect(input_dirs)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(build_html(data), encoding="utf-8")
    n_samples = sum(len(model["samples"]) for model in data["models"].values())
    print(f"Wrote {args.output} with {len(data['models'])} models and {n_samples} samples")


if __name__ == "__main__":
    main()
