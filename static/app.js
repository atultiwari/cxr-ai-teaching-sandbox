"use strict";

const $ = id => document.getElementById(id);
const state = { sampleId: null, file: null, camLabel: null, samples: [] };

function setBusy(on) { $("busy").hidden = !on; }

function showError(message) {
  $("caption").textContent = "⚠ " + message;
}

function renderSamples(samples) {
  $("samples").replaceChildren(...samples.map(s => {
    const b = document.createElement("button");
    b.className = "sample"; b.type = "button"; b.dataset.id = s.id; b.setAttribute("aria-pressed", "false");
    const img = document.createElement("img"); img.src = "/samples/" + s.file; img.alt = "";
    const span = document.createElement("span"); span.textContent = s.title;
    b.append(img, span);
    b.addEventListener("click", () => selectSample(s.id));
    return b;
  }));
}

function renderLabels(labels) {
  const auto = new Option("top finding", "");
  $("camlabel").replaceChildren(auto, ...labels.map(l => new Option(l, l)));
}

function renderFindings(findings) {
  $("findings").replaceChildren(...findings.map(f => {
    const li = document.createElement("li");
    li.className = f.score >= 0.5 ? "over" : "";
    const name = document.createElement("span"); name.textContent = f.label.replace("_", " ");
    const val = document.createElement("span"); val.className = "val"; val.textContent = f.score.toFixed(2);
    const track = document.createElement("div"); track.className = "track";
    const fill = document.createElement("div"); fill.className = "fill"; fill.style.width = Math.min(100, f.score * 100) + "%";
    track.append(fill); li.append(name, val, track);
    return li;
  }));
}

function captionFor(result) {
  const s = state.samples.find(x => x.id === state.sampleId);
  const what = s ? `On the film: ${s.teaching_finding} ` : "";
  return `${what}Heatmap shows where the model looked for “${result.cam_label.replace("_", " ")}”.`;
}

async function run() {
  if (!state.sampleId && !state.file) return;
  const form = new FormData();
  if (state.sampleId) form.append("sample_id", state.sampleId);
  else form.append("file", state.file);
  if (state.camLabel) form.append("cam_label", state.camLabel);
  setBusy(true);
  try {
    const res = await fetch("/api/analyse", { method: "POST", body: form });
    const body = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(body.detail || `Request failed (${res.status})`);
    $("img").src = body.image; $("overlay").src = body.overlay; $("img").hidden = false;
    $("placeholder").hidden = true;
    $("overlay").hidden = !$("heat").checked;
    renderFindings(body.findings);
    $("caption").textContent = captionFor(body);
    document.body.dataset.ready = "true";
    document.body.dataset.cam = body.cam_label;
  } catch (err) {
    showError(err.message);
  } finally {
    setBusy(false);
  }
}

function selectSample(id) {
  state.sampleId = id; state.file = null; $("upload").value = "";
  document.querySelectorAll(".sample").forEach(b => b.setAttribute("aria-pressed", String(b.dataset.id === id)));
  run();
}

function setWhy(open) {
  $("mislead").hidden = !open;
  $("whybtn").setAttribute("aria-expanded", String(open));
}

function init() {
  $("whybtn").addEventListener("click", () => setWhy($("mislead").hidden));
  $("whyclose").addEventListener("click", () => setWhy(false));
  document.addEventListener("keydown", e => { if (e.key === "Escape") setWhy(false); });
  $("heat").addEventListener("change", () => { $("overlay").hidden = !$("heat").checked; });
  $("camlabel").addEventListener("change", () => { state.camLabel = $("camlabel").value || null; run(); });
  $("upload").addEventListener("change", () => {
    const f = $("upload").files[0];
    if (!f) return;
    if (f.size > 10 * 1024 * 1024) { showError("Image is larger than 10 MB."); return; }
    state.file = f; state.sampleId = null;
    document.querySelectorAll(".sample").forEach(b => b.setAttribute("aria-pressed", "false"));
    run();
  });
  fetch("/api/samples")
    .then(r => { if (!r.ok) throw new Error("Could not load samples"); return r.json(); })
    .then(data => { state.samples = data.samples; renderSamples(data.samples); renderLabels(data.labels); })
    .catch(err => showError(err.message));
}

init();
