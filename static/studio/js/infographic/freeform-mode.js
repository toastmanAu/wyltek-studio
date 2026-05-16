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

// WS-fallback polling. The server broadcasts job_update over WS, but if the
// connection drops mid-render or a `complete` message is missed, the UI can
// get stuck at "saving (95%)" forever. The poll fires every POLL_INTERVAL_MS
// while a job is active; if a WS update arrived within the last
// WS_STALENESS_MS, the poll skips (no extra load when WS is healthy).
let lastWsAt = 0;
let pollTimer = null;
const POLL_INTERVAL_MS = 3000;
const WS_STALENESS_MS = 8000;

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
  aspectInput: $('aspect-input'),
  sizeInput: $('size-input'),
  sizeWrap: $('size-wrap'),
  widthWrap: $('width-wrap'),
  heightWrap: $('height-wrap'),
  widthInput: $('width-input'),
  heightInput: $('height-input'),
  seedInput: $('seed-input'),
  stepsInput: $('steps-input'),
  backendInput: $('backend-input'),
  useAgentInput: $('use-agent-input'),
  reserveSlotsInput: $('reserve-slots-input'),
  slotCountWrap: $('slot-count-wrap'),
  slotCountInput: $('slot-count-input'),
  renderBtn: $('render-btn'),
  cancelBtn: $('cancel-btn'),
  renderStatus: $('render-status'),
  progressFill: $('progress-fill'),
  outputPreview: $('output-preview'),
  outputActions: $('output-actions'),
  downloadLink: $('download-link'),
  fillLink: $('fill-link'),
  // Worker bar
  sensePill: $('sense-pill'),
  senseStart: $('sense-start'),
  senseStop: $('sense-stop'),
  senseRestart: $('sense-restart'),
  vramReadout: $('vram-readout'),
};

// ── Dim presets ─────────────────────────────────────────────────────────────
// SenseNova-U1 patchify requires width AND height to be /32-aligned. Rather
// than letting users free-type into W/H boxes (and risk picking an aspect
// the model wasn't trained on), the picker exposes ~7 training-distribution
// aspects × 4 size tiers = 28 valid combinations. Custom mode keeps the
// power-user escape hatch. See server.py:_align_to_patch — server also
// snaps as belt-and-suspenders.
const ALIGN = 32;
const ASPECTS = [
  { id: 'square',           ratio: 1,       label: 'Square 1:1' },
  { id: 'landscape-16-9',   ratio: 16 / 9,  label: 'Landscape 16:9' },
  { id: 'portrait-9-16',    ratio:  9 / 16, label: 'Portrait 9:16' },
  { id: 'landscape-4-3',    ratio:  4 / 3,  label: 'Landscape 4:3' },
  { id: 'portrait-3-4',     ratio:  3 / 4,  label: 'Portrait 3:4' },
  { id: 'wide-2-1',         ratio: 2,       label: 'Wide 2:1' },
  { id: 'tall-1-2',         ratio: 0.5,     label: 'Tall 1:2' },
];
const SIZES = [1024, 1536, 2048, 2720];  // long-edge tiers — match HTML <option> values
const PREFS_KEY = 'infographic.freeform.dims';

function snapFloor(v) { return Math.max(ALIGN, Math.floor(v / ALIGN) * ALIGN); }
function snapNearest(v) { return Math.max(ALIGN, Math.round(v / ALIGN) * ALIGN); }

// Derive concrete W×H from an aspect preset + a long-edge size tier.
// The long edge is set exactly; the short edge is the ratio-derived value
// snapped to the nearest /32 (so 16:9 at 2720 becomes 2720×1536 rather than
// the unrendable 2720×1530).
function presetDims(aspectId, sizeLong) {
  const a = ASPECTS.find(x => x.id === aspectId);
  if (!a) return null;
  if (a.ratio === 1) return { width: sizeLong, height: sizeLong };
  if (a.ratio > 1) {
    return { width: sizeLong, height: snapNearest(sizeLong / a.ratio) };
  }
  return { width: snapNearest(sizeLong * a.ratio), height: sizeLong };
}

// Round arbitrary W×H to the closest aspect+size preset. Both metrics use
// log distance so percentage differences are what's compared (not absolute
// pixels) — matches human perception. Without log on size, a 1280-wide
// entry is an exact pixel tie between 1024 and 1536; in log space 1280 is
// clearly closer to 1536, which avoids surprise downscaling on prefill.
function presetForDims(w, h) {
  const longEdge = Math.max(w, h);
  const ratio = w / h;
  let bestAspect = ASPECTS[0];
  let bestDist = Math.abs(Math.log(ratio) - Math.log(bestAspect.ratio));
  for (const a of ASPECTS.slice(1)) {
    const d = Math.abs(Math.log(ratio) - Math.log(a.ratio));
    if (d < bestDist) { bestAspect = a; bestDist = d; }
  }
  let bestSize = SIZES[0];
  let bestSizeDist = Math.abs(Math.log(longEdge) - Math.log(bestSize));
  for (const s of SIZES.slice(1)) {
    const d = Math.abs(Math.log(longEdge) - Math.log(s));
    if (d < bestSizeDist) { bestSize = s; bestSizeDist = d; }
  }
  return { aspect: bestAspect.id, size: bestSize };
}

function loadDimPrefs() {
  try {
    const raw = localStorage.getItem(PREFS_KEY);
    if (!raw) return null;
    const p = JSON.parse(raw);
    if (!p || typeof p !== 'object') return null;
    return p;
  } catch { return null; }
}

function saveDimPrefs(prefs) {
  try { localStorage.setItem(PREFS_KEY, JSON.stringify(prefs)); } catch {}
}

// Apply aspect+size (or custom W×H) to the DOM. Pure UI — the
// width-input / height-input remain the source of truth that startRender()
// submits, regardless of which mode produced them.
function applyDimsToUI(prefs) {
  els.aspectInput.value = prefs.aspect;
  if (prefs.aspect === 'custom') {
    els.sizeWrap.hidden = true;
    els.widthWrap.hidden = false;
    els.heightWrap.hidden = false;
    els.widthInput.value = prefs.width;
    els.heightInput.value = prefs.height;
  } else {
    els.sizeWrap.hidden = false;
    els.widthWrap.hidden = true;
    els.heightWrap.hidden = true;
    els.sizeInput.value = String(prefs.size);
    const { width, height } = presetDims(prefs.aspect, prefs.size);
    els.widthInput.value = width;
    els.heightInput.value = height;
  }
}

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

  // Round the entry's source dims to the closest aspect+size preset, then
  // persist so the next render keeps this state. The user can still flip
  // to Custom afterwards — and that custom value also persists.
  const matched = presetForDims(entry.width, entry.height);
  const prefs = { aspect: matched.aspect, size: matched.size };
  saveDimPrefs(prefs);
  applyDimsToUI(prefs);

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

// ── Picker change handlers ──────────────────────────────────────────────────
function onAspectChange() {
  const aspect = els.aspectInput.value;
  if (aspect === 'custom') {
    // Seed Custom mode with the current preset's resolved W×H so the user
    // starts from valid numbers rather than empty boxes.
    const current = loadDimPrefs() || { aspect: 'square', size: 2048 };
    const seed = current.aspect === 'custom'
      ? { width: current.width || 2048, height: current.height || 2048 }
      : presetDims(current.aspect, current.size);
    const prefs = { aspect: 'custom', width: seed.width, height: seed.height };
    saveDimPrefs(prefs);
    applyDimsToUI(prefs);
  } else {
    const size = parseInt(els.sizeInput.value, 10) || 2048;
    const prefs = { aspect, size };
    saveDimPrefs(prefs);
    applyDimsToUI(prefs);
  }
}

function onSizeChange() {
  if (els.aspectInput.value === 'custom') return;
  const prefs = { aspect: els.aspectInput.value, size: parseInt(els.sizeInput.value, 10) };
  saveDimPrefs(prefs);
  applyDimsToUI(prefs);
}

function onCustomDimBlur() {
  // Snap user-typed values to /32 (server snaps too, but on-blur snap gives
  // immediate UI feedback and keeps the persisted custom value valid).
  const w = parseInt(els.widthInput.value, 10);
  const h = parseInt(els.heightInput.value, 10);
  if (!Number.isFinite(w) || !Number.isFinite(h)) return;
  const width = snapFloor(w);
  const height = snapFloor(h);
  els.widthInput.value = width;
  els.heightInput.value = height;
  saveDimPrefs({ aspect: 'custom', width, height });
}

els.aspectInput.addEventListener('change', onAspectChange);
els.sizeInput.addEventListener('change', onSizeChange);
els.widthInput.addEventListener('blur', onCustomDimBlur);
els.heightInput.addEventListener('blur', onCustomDimBlur);

// Boot picker with persisted prefs (or sane default) BEFORE the user picks
// a gallery entry — so a direct render without entry click is still valid.
applyDimsToUI(loadDimPrefs() || { aspect: 'square', size: 2048 });

function backToGallery() {
  els.editorWrap.hidden = true;
  els.galleryWrap.hidden = false;
  currentEntry = null;
}

els.backLink.addEventListener('click', backToGallery);

// ── Render submission ───────────────────────────────────────────────────────
async function startRender() {
  const reserveSlots = els.reserveSlotsInput?.checked
    ? Math.max(2, Math.min(10, parseInt(els.slotCountInput.value, 10) || 0))
    : 0;
  const body = {
    prompt: els.promptArea.value.trim(),
    width: parseInt(els.widthInput.value, 10),
    height: parseInt(els.heightInput.value, 10),
    seed: parseInt(els.seedInput.value, 10),
    num_steps: parseInt(els.stepsInput.value, 10),
    backend: els.backendInput.value,
    use_prompt_agent: els.useAgentInput.checked,
    reserve_logo_slots: reserveSlots,
  };
  if (!body.prompt) {
    els.renderStatus.textContent = 'Prompt is empty.';
    return;
  }

  els.renderBtn.disabled = true;
  els.cancelBtn.hidden = false;
  els.outputPreview.hidden = true;
  els.outputActions.hidden = true;
  if (els.fillLink) els.fillLink.hidden = true;
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
    lastWsAt = Date.now();  // assume WS is healthy at submit; first poll skips
    startPolling();
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

if (els.reserveSlotsInput) {
  const syncSlotCount = () => {
    els.slotCountWrap.hidden = !els.reserveSlotsInput.checked;
  };
  els.reserveSlotsInput.addEventListener('change', syncSlotCount);
  syncSlotCount();
}

// ── Job update — applied from BOTH WS and the fallback poller ───────────────
// Both code paths produce/consume the same shape so the UI stays in sync
// regardless of channel. Idempotent: the `currentJobId` guard makes a late
// WS message after a poll-driven completion a harmless no-op.
function applyJobUpdate(msg) {
  if (msg.type !== 'job_update') return;
  if (msg.job_id !== currentJobId) return;

  if (msg.status === 'running') {
    const pct = msg.progress || 0;
    els.progressFill.style.width = `${pct}%`;
    els.renderStatus.textContent = msg.message ? `${msg.message} (${pct}%)` : `rendering ${pct}%…`;
  } else if (msg.status === 'complete') {
    els.progressFill.style.width = '100%';
    els.outputPreview.src = `${msg.output_url}?t=${Date.now()}`;
    els.outputPreview.hidden = false;
    els.outputActions.hidden = false;
    els.downloadLink.href = msg.output_url;
    // Sentinel-slot results: the server attaches a `slots` summary when
    // reserve_logo_slots was > 0. Surface the manual-fill link only when
    // detection actually found slots so a count-mismatch (model produced
    // fewer rectangles than requested) is visible in the status line.
    const slotInfo = msg.slots;
    if (slotInfo && (slotInfo.detected ?? 0) > 0) {
      const jobId = msg.job_id;
      els.fillLink.href = `/studio/infographic-fill?job=${encodeURIComponent(jobId)}`;
      els.fillLink.hidden = false;
      const mismatch = (slotInfo.requested ?? 0) !== slotInfo.detected
        ? ` (model produced ${slotInfo.detected}/${slotInfo.requested})`
        : '';
      els.renderStatus.textContent = `done — ${slotInfo.detected} logo slot${slotInfo.detected === 1 ? '' : 's'} ready${mismatch}`;
    } else if (slotInfo) {
      els.renderStatus.textContent = `done — no slots detected (requested ${slotInfo.requested}); try a different seed`;
    } else {
      els.renderStatus.textContent = 'done';
    }
    els.renderBtn.disabled = false;
    els.cancelBtn.hidden = true;
    currentJobId = null;
    stopPolling();
  } else if (msg.status === 'error') {
    els.renderStatus.textContent = `error: ${msg.error || 'unknown'}`;
    els.renderBtn.disabled = false;
    els.cancelBtn.hidden = true;
    currentJobId = null;
    stopPolling();
  } else if (msg.status === 'cancelled') {
    els.renderStatus.textContent = 'cancelled';
    els.renderBtn.disabled = false;
    els.cancelBtn.hidden = true;
    currentJobId = null;
    stopPolling();
  }
}

// ── WS — primary progress channel ───────────────────────────────────────────
function connectWS() {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  ws = new WebSocket(`${proto}://${location.host}/ws`);
  ws.addEventListener('message', (ev) => {
    let msg;
    try { msg = JSON.parse(ev.data); } catch { return; }
    if (msg.type !== 'job_update') return;
    if (msg.job_id !== currentJobId) return;
    lastWsAt = Date.now();
    applyJobUpdate(msg);
  });
  ws.addEventListener('close', () => setTimeout(connectWS, 2000));
}

// ── Fallback poll — covers WS drops + missed completion messages ────────────
// Fires every POLL_INTERVAL_MS while a job is active. Skips if a WS update
// arrived in the last WS_STALENESS_MS so a healthy WS connection means
// effectively zero extra requests. Synthesises a job_update-shaped object
// and routes it through applyJobUpdate for single-source-of-truth handling.
function startPolling() {
  stopPolling();
  pollTimer = setInterval(async () => {
    if (!currentJobId) { stopPolling(); return; }
    if (Date.now() - lastWsAt < WS_STALENESS_MS) return;
    try {
      const r = await fetch(`/api/job/${currentJobId}`);
      if (!r.ok) return;
      const j = await r.json();
      applyJobUpdate({
        type: 'job_update',
        job_id: currentJobId,
        status: j.status,
        progress: j.progress,
        message: j.message,
        output_url: j.output_url,
        error: j.error,
      });
    } catch {
      // Silent — next tick retries. A persistent failure is visible via the
      // WS reconnect path (and the user can always cancel from the UI).
    }
  }, POLL_INTERVAL_MS);
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
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
let booted = false;
export function initFreeformMode() {
  if (booted) return;
  booted = true;
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
}
