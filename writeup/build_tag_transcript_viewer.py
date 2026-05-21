#!/usr/bin/env python3
"""Build a static transcript viewer for OLMo think-scaffold eval logs."""

from __future__ import annotations

import glob
import json
import os
import zipfile


ROOT = "/mnt/filesystem-z4/cc_workspace_mats/stage1_eval_logs"
OUT = "writeup/tag_transcript_viewer.html"
MAX_QUESTIONS = 200
MODELS = [
    ("base", "Base"),
    ("custom_sft", "Speed-run SFT"),
    ("sft", "Full Think-SFT"),
    ("stage1_ep4", "Pre-midtrain SFT ep4"),
]
MODEL_ORDER = {model: index for index, (model, _label) in enumerate(MODELS)}


def completion(sample: dict) -> str:
    out = sample.get("output") or {}
    if isinstance(out, dict) and "completion" in out:
        return out.get("completion") or ""
    try:
        return out["choices"][0]["message"].get("content") or ""
    except Exception:
        return ""


def score_value(sample: dict):
    scores = sample.get("scores") or {}
    if "rubric_scorer" in scores:
        return scores["rubric_scorer"].get("value")
    return None


def classify(text: str) -> dict:
    close_count = text.count("</think>")
    open_count = text.count("<think>")
    first_close = text.find("</think>")
    answer_after = text[first_close + len("</think>") :].strip() if first_close != -1 else ""
    valid = close_count == 1 and open_count == 0 and bool(answer_after)

    reasons: list[str] = []
    if close_count == 0:
        reasons.append("missing </think>")
    if close_count > 1:
        reasons.append(f"multiple </think> ({close_count})")
    if open_count > 0:
        reasons.append(f"generated extra <think> ({open_count})")
    if first_close != -1 and not answer_after:
        reasons.append("no answer after </think>")
    if not text.strip():
        reasons.append("empty completion")

    return {
        "valid": valid,
        "close_count": close_count,
        "open_count": open_count,
        "reason": "; ".join(reasons) if reasons else "valid",
    }


def load_records() -> dict:
    records_by_model = {}
    stats_by_model = {}

    for model, label in MODELS:
        files = sorted(glob.glob(f"{ROOT}/{model}/*.eval"))
        rows = []
        total = 0
        valid = 0

        for path in files:
            with zipfile.ZipFile(path) as archive:
                sample_names = [
                    name
                    for name in archive.namelist()
                    if name.startswith("samples/") and name.endswith(".json")
                ]
                for sample_name in sample_names:
                    sample = json.loads(archive.read(sample_name))
                    text = completion(sample)
                    verdict = classify(text)
                    total += 1
                    valid += int(verdict["valid"])

                    messages = sample.get("messages") or []
                    system = "\n\n".join(
                        message.get("content", "")
                        for message in messages
                        if message.get("role") == "system"
                    )
                    user = "\n\n".join(
                        message.get("content", "")
                        for message in messages
                        if message.get("role") == "user"
                    ) or str(sample.get("input", ""))

                    rows.append(
                        {
                            "model": model,
                            "modelLabel": label,
                            "modelOrder": MODEL_ORDER[model],
                            "valid": verdict["valid"],
                            "reason": verdict["reason"],
                            "closeCount": verdict["close_count"],
                            "openCount": verdict["open_count"],
                            "evalFile": os.path.basename(path),
                            "samplePath": sample_name,
                            "sampleId": sample.get("id", sample_name),
                            "questionKey": sample.get("id", sample_name),
                            "score": score_value(sample),
                            "system": system,
                            "user": user,
                            "completion": text,
                        }
                    )

        records_by_model[model] = rows
        stats_by_model[model] = {
            "model": model,
            "label": label,
            "total": total,
            "valid": valid,
            "failures": total - valid,
        }

    grouped: dict[str, dict[str, dict]] = {}
    for model, rows in records_by_model.items():
        for row in rows:
            grouped.setdefault(row["questionKey"], {})[model] = row

    common_keys = [
        key
        for key, by_model in grouped.items()
        if all(model in by_model for model, _label in MODELS)
    ]

    def priority(key: str) -> tuple:
        by_model = grouped[key]
        full_or_speed_failure = (
            not by_model["custom_sft"]["valid"] or not by_model["sft"]["valid"]
        )
        base_failure = not by_model["base"]["valid"]
        failure_count = sum(not by_model[model]["valid"] for model, _label in MODELS)
        if full_or_speed_failure:
            tier = 0
        elif base_failure:
            tier = 1
        else:
            tier = 2
        return (tier, -failure_count, key)

    selected_keys = sorted(common_keys, key=priority)[:MAX_QUESTIONS]
    records = []
    for question_rank, key in enumerate(selected_keys, start=1):
        comparison_failures = sum(
            not grouped[key][model]["valid"] for model, _label in MODELS
        )
        for model, _label in MODELS:
            row = dict(grouped[key][model])
            row["questionRank"] = question_rank
            row["comparisonFailures"] = comparison_failures
            records.append(row)

    summary = []
    for model, label in MODELS:
        selected_rows = [row for row in records if row["model"] == model]
        included_failures = sum(not row["valid"] for row in selected_rows)
        summary.append(
            {
                **stats_by_model[model],
                "included": len(selected_rows),
                "includedFailures": included_failures,
                "includedValid": len(selected_rows) - included_failures,
            }
        )

    return {
        "summary": summary,
        "records": records,
        "selection": {
            "selectedQuestions": len(selected_keys),
            "commonQuestions": len(common_keys),
            "maxQuestions": MAX_QUESTIONS,
        },
    }


HTML_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Think Scaffold Transcript Viewer</title>
<style>
:root { color-scheme: light; --bg:#f7f7f4; --panel:#ffffff; --ink:#202124; --muted:#666b73; --line:#d8dadd; --bad:#b42318; --good:#087443; --tag:#6f3cc3; }
* { box-sizing: border-box; }
body { margin: 0; font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: var(--bg); color: var(--ink); }
header { position: sticky; top: 0; z-index: 2; background: rgba(247,247,244,.96); border-bottom: 1px solid var(--line); padding: 14px 18px 12px; backdrop-filter: blur(8px); }
h1 { margin: 0 0 10px; font-size: 20px; font-weight: 700; letter-spacing: 0; }
.controls { display: grid; grid-template-columns: minmax(180px, 1fr) repeat(3, max-content); gap: 10px; align-items: center; }
input, select, button { height: 34px; border: 1px solid var(--line); background: #fff; color: var(--ink); border-radius: 6px; font: inherit; padding: 0 10px; }
button { cursor: pointer; }
main { padding: 16px 18px 32px; max-width: 1400px; margin: 0 auto; }
.summary { display: grid; grid-template-columns: repeat(3, minmax(220px,1fr)); gap: 12px; margin-bottom: 14px; }
.summary-card { background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 12px; }
.summary-card h2 { margin: 0 0 8px; font-size: 15px; }
.metric { display: flex; justify-content: space-between; gap: 12px; color: var(--muted); font-size: 13px; margin-top: 4px; }
.metric strong { color: var(--ink); }
.layout { display: grid; grid-template-columns: 360px minmax(0,1fr); gap: 14px; align-items: start; }
.list { background: var(--panel); border: 1px solid var(--line); border-radius: 8px; overflow: hidden; max-height: calc(100vh - 178px); overflow-y: auto; }
.row { display: block; width: 100%; text-align: left; border: 0; border-bottom: 1px solid var(--line); border-radius: 0; height: auto; padding: 10px 12px; background: #fff; }
.row:hover, .row.active { background: #eef4fc; }
.row-title { display: flex; align-items: center; gap: 8px; font-size: 13px; font-weight: 650; }
.badge { display: inline-flex; align-items: center; height: 20px; padding: 0 7px; border-radius: 999px; font-size: 11px; font-weight: 700; }
.badge.fail { color: var(--bad); background: #fee4df; }
.badge.pass { color: var(--good); background: #dcfce7; }
.row-meta { color: var(--muted); font-size: 12px; margin-top: 6px; line-height: 1.35; }
.detail { background: var(--panel); border: 1px solid var(--line); border-radius: 8px; min-height: 520px; overflow: hidden; }
.detail-head { padding: 14px 16px; border-bottom: 1px solid var(--line); display: grid; gap: 8px; }
.detail-title { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; font-weight: 700; }
.detail-meta { color: var(--muted); font-size: 12px; line-height: 1.45; }
.sections { padding: 0 16px 16px; }
section { border-top: 1px solid var(--line); padding-top: 14px; margin-top: 14px; }
section:first-child { border-top: 0; }
h3 { margin: 0 0 8px; font-size: 13px; color: var(--muted); text-transform: uppercase; letter-spacing: .04em; }
pre { margin: 0; white-space: pre-wrap; overflow-wrap: anywhere; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, "Liberation Mono", monospace; font-size: 13px; line-height: 1.5; background: #fbfbfa; border: 1px solid var(--line); border-radius: 6px; padding: 12px; }
.tag { color: var(--tag); font-weight: 800; }
.empty { color: var(--muted); padding: 24px; }
@media (max-width: 900px) { .summary, .layout { grid-template-columns: 1fr; } .controls { grid-template-columns: 1fr 1fr; } .list { max-height: 360px; } }
</style>
</head>
<body>
<header>
  <h1>Think Scaffold Transcript Viewer</h1>
  <div class="controls">
    <input id="search" type="search" placeholder="Search prompt, completion, reason, file">
    <select id="model"><option value="all">All models</option></select>
    <select id="status"><option value="fail">Failures first</option><option value="all">All included</option><option value="pass">Valid only</option></select>
    <button id="nextFail" type="button">Next Failure</button>
  </div>
</header>
<main>
  <div id="summary" class="summary"></div>
  <div class="layout">
    <div id="list" class="list"></div>
    <div id="detail" class="detail"><div class="empty">Select a transcript.</div></div>
  </div>
</main>
<script id="payload" type="application/json">__DATA__</script>
<script>
const payload = JSON.parse(document.getElementById("payload").textContent);
const records = payload.records;
let filtered = [];
let selected = null;
const els = { search: document.getElementById("search"), model: document.getElementById("model"), status: document.getElementById("status"), list: document.getElementById("list"), detail: document.getElementById("detail"), summary: document.getElementById("summary"), nextFail: document.getElementById("nextFail") };
function pct(a,b){ return b ? (100*a/b).toFixed(1)+"%" : "0.0%"; }
function escapeHtml(s){ return String(s ?? "").replace(/[&<>]/g, ch => ({"&":"&amp;","<":"&lt;",">":"&gt;"}[ch])); }
function highlightTags(s){ return escapeHtml(s).replace(/(&lt;\\/?(?:think|answer)&gt;)/g, "<span class=\\"tag\\">$1</span>"); }
function renderSummary(){
  els.summary.innerHTML = payload.summary.map(s => `<div class="summary-card"><h2>${escapeHtml(s.label)}</h2><div class="metric"><span>Strict valid</span><strong>${s.valid}/${s.total} (${pct(s.valid,s.total)})</strong></div><div class="metric"><span>Failures</span><strong>${s.failures}</strong></div><div class="metric"><span>Included here</span><strong>${s.included} (${s.includedFailures} failures, ${s.includedValid} valid)</strong></div></div>`).join("");
  for (const s of payload.summary) {
    const opt = document.createElement("option");
    opt.value = s.model;
    opt.textContent = s.label;
    els.model.appendChild(opt);
  }
}
function applyFilters(){
  const q = els.search.value.trim().toLowerCase();
  const m = els.model.value;
  const st = els.status.value;
  filtered = records.filter(r => {
    if (m !== "all" && r.model !== m) return false;
    if (st === "fail" && r.valid) return false;
    if (st === "pass" && !r.valid) return false;
    if (!q) return true;
    return [r.modelLabel,r.reason,r.evalFile,r.sampleId,r.user,r.completion].join("\\n").toLowerCase().includes(q);
  });
  filtered.sort((a,b) => Number(a.valid)-Number(b.valid) || a.modelLabel.localeCompare(b.modelLabel) || a.evalFile.localeCompare(b.evalFile) || a.sampleId.localeCompare(b.sampleId));
  if (!filtered.includes(selected)) selected = filtered[0] || null;
  renderList();
  renderDetail();
}
function renderList(){
  if (!filtered.length) { els.list.innerHTML = `<div class="empty">No matching transcripts.</div>`; return; }
  els.list.innerHTML = filtered.map((r,i) => `<button class="row ${r===selected ? "active" : ""}" data-i="${i}" type="button"><div class="row-title"><span class="badge ${r.valid ? "pass" : "fail"}">${r.valid ? "valid" : "failure"}</span><span>${escapeHtml(r.modelLabel)}</span></div><div class="row-meta">${escapeHtml(r.reason)}<br>${escapeHtml(r.sampleId)}<br>${escapeHtml(r.evalFile)}</div></button>`).join("");
  els.list.querySelectorAll(".row").forEach(btn => btn.addEventListener("click", () => { selected = filtered[Number(btn.dataset.i)]; renderList(); renderDetail(); }));
}
function renderDetail(){
  if (!selected) { els.detail.innerHTML = `<div class="empty">Select a transcript.</div>`; return; }
  const r = selected;
  els.detail.innerHTML = `<div class="detail-head"><div class="detail-title"><span class="badge ${r.valid ? "pass" : "fail"}">${r.valid ? "valid" : "failure"}</span><span>${escapeHtml(r.modelLabel)}</span><span>${escapeHtml(r.sampleId)}</span></div><div class="detail-meta"><strong>Reason:</strong> ${escapeHtml(r.reason)}<br><strong>Counts:</strong> generated &lt;think&gt;=${r.openCount}, generated &lt;/think&gt;=${r.closeCount}, score=${escapeHtml(r.score ?? "n/a")}<br><strong>File:</strong> ${escapeHtml(r.evalFile)} / ${escapeHtml(r.samplePath)}</div></div><div class="sections"><section><h3>System</h3><pre>${highlightTags(r.system)}</pre></section><section><h3>User</h3><pre>${highlightTags(r.user)}</pre></section><section><h3>Completion</h3><pre>${highlightTags(r.completion)}</pre></section></div>`;
}
function nextFailure(){
  if (!filtered.length) return;
  const start = selected ? filtered.indexOf(selected)+1 : 0;
  const idx = filtered.findIndex((r,i) => i >= start && !r.valid);
  selected = idx >= 0 ? filtered[idx] : filtered.find(r => !r.valid) || selected;
  renderList();
  renderDetail();
}
els.search.addEventListener("input", applyFilters);
els.model.addEventListener("change", applyFilters);
els.status.addEventListener("change", applyFilters);
els.nextFail.addEventListener("click", nextFailure);
renderSummary();
applyFilters();
</script>
</body>
</html>
"""


def main() -> None:
    data = load_records()
    json_data = json.dumps(data, ensure_ascii=False).replace("</script>", "<\\/script>")
    html_text = HTML_TEMPLATE.replace("__DATA__", json_data)
    with open(OUT, "w", encoding="utf-8") as handle:
        handle.write(html_text)

    print(OUT)
    for item in data["summary"]:
        print(
            "{label}: total={total} valid={valid} failures={failures} "
            "included={included} included_failures={includedFailures} "
            "included_valid={includedValid}".format(**item)
        )


if __name__ == "__main__":
    main()
