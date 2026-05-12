// Infographic Builder v2 — gallery-driven freeform prompt editor.
//
// Replaces the template-field flow with: pick an example from the gallery,
// edit its prompt in a single textarea, render. The repo's own showcase
// images double as gallery thumbnails (see scripts/build-sensenova-examples.py).
//
// DOM construction uses createElement + textContent everywhere — no innerHTML
// — so corpus entries (whose `title` is derived from upstream prompts we
// don't author) can't ever yield XSS.

const CORPUS_URL = '/static/studio/sensenova-examples.json';

// ── State ───────────────────────────────────────────────────────────────────
let corpus = null;
let currentEntry = null;
let currentJobId = null;
let activeFilter = 'all';
let ws = null;

// ── DOM ─────────────────────────────────────────────────────────────────────
const $ = (id) => document.getElementById(id);
const els = {
  galleryWrap: $('gallery-wrap'),
  gallery: $('gallery'),
  filterRow: $('filter-row'),
  corpusHint: $('corpus-hint'),
  editorWrap: $('editor-wrap'),
  backLink: $('back-link'),
  refImg: $('reference-img'),
  refCaption: $('reference-caption'),
  promptArea: $('prompt-area'),
  widthInput: $('width-input'),
  heightInput: $('height-input'),
  seedInput: $('seed-input'),
  stepsInput: $('steps-input'),
  renderBtn: $('render-btn'),
  cancelBtn: $('cancel-btn'),
  renderStatus: $('render-status'),
  progressFill: $('progress-fill'),
  outputPreview: $('output-preview'),
  outputActions: $('output-actions'),
  downloadLink: $('download-link'),
  // Worker bar
  sensePill: $('sense-pill'),
  senseStart: $('sense-start'),
  senseStop: $('sense-stop'),
  senseRestart: $('sense-restart'),
  vramReadout: $('vram-readout'),
};

// ── Small DOM helpers (createElement + textContent only) ────────────────────
function el(tag, opts = {}, children = []) {
  const n = document.createElement(tag);
  if (opts.cls) n.className = opts.cls;
  if (opts.text != null) n.textContent = opts.text;
  if (opts.attrs) for (const [k, v] of Object.entries(opts.attrs)) n.setAttribute(k, v);
  if (opts.on) for (const [k, v] of Object.entries(opts.on)) n.addEventListener(k, v);
  for (const c of children) if (c) n.appendChild(c);
  return n;
}

function clear(node) { while (node.firstChild) node.removeChild(node.firstChild); }

// ── Load corpus + render gallery ────────────────────────────────────────────
async function loadCorpus() {
  const r = await fetch(CORPUS_URL);
  corpus = await r.json();
  renderFilterChips();
  renderGallery();
  els.corpusHint.textContent = `${corpus.entries.length} examples`;
}

function renderFilterChips() {
  const totals = { all: corpus.entries.length };
  for (const e of corpus.entries) totals[e.category] = (totals[e.category] || 0) + 1;

  clear(els.filterRow);
  const makeChip = (id, label, count) => {
    const countSpan = el('span', { cls: 'count', text: String(count) });
    const chip = el('button', {
      cls: 'filter-chip' + (id === activeFilter ? ' active' : ''),
      attrs: { type: 'button', 'data-filter': id },
      on: { click: () => { activeFilter = id; renderFilterChips(); renderGallery(); } },
    });
    chip.appendChild(document.createTextNode(label + ' '));
    chip.appendChild(countSpan);
    els.filterRow.appendChild(chip);
  };
  makeChip('all', 'All', totals.all);
  for (const cat of corpus.categories) makeChip(cat.id, cat.label, totals[cat.id] || 0);
  els.filterRow.appendChild(els.corpusHint);
}

function renderGallery() {
  const visible = activeFilter === 'all'
    ? corpus.entries
    : corpus.entries.filter(e => e.category === activeFilter);

  clear(els.gallery);
  for (const e of visible) {
    const thumb = el('img', {
      cls: 'thumb',
      attrs: { loading: 'lazy', src: e.thumbnail, alt: e.title },
    });
    const thumbWrap = el('div', { cls: 'thumb-wrap' }, [thumb]);
    const title = el('div', { cls: 'title', text: e.title });
    const dims = el('div', { cls: 'dims', text: `${e.width} × ${e.height}` });
    const meta = el('div', { cls: 'meta' }, [title, dims]);
    const card = el('div', {
      cls: 'card',
      on: { click: () => openEditor(e) },
    }, [thumbWrap, meta]);
    els.gallery.appendChild(card);
  }
}

// ── Editor view ─────────────────────────────────────────────────────────────
function openEditor(entry) {
  currentEntry = entry;
  els.refImg.src = entry.thumbnail;
  els.refImg.alt = entry.title;
  els.refCaption.textContent = `Reference: ${entry.title} • ${entry.source}`;
  els.promptArea.value = entry.prompt;
  els.widthInput.value = entry.width;
  els.heightInput.value = entry.height;
  els.seedInput.value = 42;
  els.stepsInput.value = '50';
  els.renderStatus.textContent = '';
  els.progressFill.style.width = '0%';
  els.outputPreview.hidden = true;
  els.outputActions.hidden = true;
  els.galleryWrap.hidden = true;
  els.editorWrap.hidden = false;
  window.scrollTo(0, 0);
}

function backToGallery() {
  els.editorWrap.hidden = true;
  els.galleryWrap.hidden = false;
  currentEntry = null;
}

els.backLink.addEventListener('click', backToGallery);

// ── Render submission ───────────────────────────────────────────────────────
async function startRender() {
  const body = {
    prompt: els.promptArea.value.trim(),
    width: parseInt(els.widthInput.value, 10),
    height: parseInt(els.heightInput.value, 10),
    seed: parseInt(els.seedInput.value, 10),
    num_steps: parseInt(els.stepsInput.value, 10),
  };
  if (!body.prompt) {
    els.renderStatus.textContent = 'Prompt is empty.';
    return;
  }

  els.renderBtn.disabled = true;
  els.cancelBtn.hidden = false;
  els.outputPreview.hidden = true;
  els.outputActions.hidden = true;
  els.progressFill.style.width = '0%';
  els.renderStatus.textContent = 'queued…';

  try {
    const r = await fetch('/api/sensenova/render', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!r.ok) {
      const err = await r.text().catch(() => '');
      throw new Error(`render request failed (${r.status}): ${err.slice(0, 200)}`);
    }
    const { job_id } = await r.json();
    currentJobId = job_id;
    els.renderStatus.textContent = `running (job ${job_id})…`;
  } catch (e) {
    els.renderStatus.textContent = `error: ${e.message}`;
    els.renderBtn.disabled = false;
    els.cancelBtn.hidden = true;
  }
}

async function cancelRender() {
  if (!currentJobId) return;
  els.cancelBtn.disabled = true;
  try {
    await fetch(`/api/job/${currentJobId}/cancel`, { method: 'POST' });
    els.renderStatus.textContent = 'cancel requested — worker is restarting';
  } catch (e) {
    els.renderStatus.textContent = `cancel failed: ${e.message}`;
  } finally {
    els.cancelBtn.disabled = false;
  }
}

els.renderBtn.addEventListener('click', startRender);
els.cancelBtn.addEventListener('click', cancelRender);

// ── WS — progress + completion ──────────────────────────────────────────────
function connectWS() {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  ws = new WebSocket(`${proto}://${location.host}/ws`);
  ws.addEventListener('message', (ev) => {
    let msg;
    try { msg = JSON.parse(ev.data); } catch { return; }
    if (msg.type !== 'job_update') return;
    if (msg.job_id !== currentJobId) return;

    if (msg.status === 'running') {
      const pct = msg.progress || 0;
      els.progressFill.style.width = `${pct}%`;
      els.renderStatus.textContent = msg.message ? `${msg.message} (${pct}%)` : `rendering ${pct}%…`;
    } else if (msg.status === 'complete') {
      els.progressFill.style.width = '100%';
      els.renderStatus.textContent = 'done';
      els.outputPreview.src = `${msg.output_url}?t=${Date.now()}`;
      els.outputPreview.hidden = false;
      els.outputActions.hidden = false;
      els.downloadLink.href = msg.output_url;
      els.renderBtn.disabled = false;
      els.cancelBtn.hidden = true;
      currentJobId = null;
    } else if (msg.status === 'error') {
      els.renderStatus.textContent = `error: ${msg.error || 'unknown'}`;
      els.renderBtn.disabled = false;
      els.cancelBtn.hidden = true;
      currentJobId = null;
    }
  });
  ws.addEventListener('close', () => setTimeout(connectWS, 2000));
}

// ── Worker lifecycle — minimal subset of v1 (start/stop/restart + VRAM) ─────
function setPill(node, label, w) {
  node.classList.remove('state-running','state-starting','state-stopped','state-crashed','state-unknown');
  node.classList.add(`state-${w.state || 'unknown'}`);
  node.querySelector('.label').textContent = `${label}: ${w.state || 'unknown'}`;
}

async function pollWorker() {
  try {
    const r = await fetch('/api/workers/status');
    const { workers: w } = await r.json();
    const sense = w.sensenova || {};
    setPill(els.sensePill, 'SenseNova', sense);
    els.senseStart.disabled = ['running', 'starting'].includes(sense.state);
    els.senseStop.disabled = ['stopped', 'unknown'].includes(sense.state);
    els.senseRestart.disabled = ['stopped', 'unknown'].includes(sense.state);
    if (typeof sense.vram_gb === 'number') {
      const max = typeof sense.vram_max_gb === 'number' ? sense.vram_max_gb : 0;
      els.vramReadout.textContent = `${sense.vram_gb.toFixed(1)} GiB / ${max.toFixed(1)} GiB`;
    } else {
      els.vramReadout.textContent = '';
    }
  } catch { /* keep last state */ }
}

async function workerAction(url, btn, busyLabel) {
  const orig = btn.textContent;
  btn.disabled = true;
  btn.textContent = busyLabel;
  try {
    await fetch(url, { method: 'POST' });
  } finally {
    btn.textContent = orig;
    pollWorker();
  }
}

els.senseStart.addEventListener('click',
  () => workerAction('/api/sensenova/worker/start', els.senseStart, 'Starting…'));
els.senseStop.addEventListener('click',
  () => workerAction('/api/sensenova/worker/stop', els.senseStop, 'Stopping…'));
els.senseRestart.addEventListener('click',
  () => workerAction('/api/sensenova/worker/restart', els.senseRestart, 'Restarting…'));

setInterval(pollWorker, 3000);

// ── Boot ────────────────────────────────────────────────────────────────────
loadCorpus().catch(e => {
  clear(els.gallery);
  els.gallery.appendChild(el('div', {
    cls: 'error',
    text: `Failed to load corpus: ${String(e)}`,
    attrs: { style: 'padding:24px;color:#ffb3b3' },
  }));
});
connectWS();
pollWorker();
