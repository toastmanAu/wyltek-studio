// Catalog mode for /studio/infographic. State machine + two dropdowns +
// pick strip with re-roll + render flow that subscribes to the same WS
// channel the freeform flow uses.
//
// DOM construction uses textContent everywhere — never innerHTML — to
// keep XSS exposure at zero (catalog content is vendored but the user
// prompt is user input and could end up echoed back via the expanded
// prompt).

const STATE = {
  EMPTY: 'EMPTY',
  READY_TO_PICK: 'READY_TO_PICK',
  PICKED: 'PICKED',
  RENDERING: 'RENDERING',
  RENDERED: 'RENDERED',
};

const STORAGE_DATA_TYPE = 'infographic.dataType';
const STORAGE_TONE = 'infographic.tone';

// In-memory cache of `kind/name → first-paragraph` for the selection-details
// box. Catalog md files don't change at runtime, so a per-page cache is fine.
const mdParagraphCache = new Map();

const state = {
  state: STATE.EMPTY,
  dataType: null,
  tone: null,
  layout: null,
  style: null,
  fromPool: { layout: null, style: null },
  jobId: null,
  ws: null,
  pollTimer: null,
  lastWsAt: 0,
};

const POLL_INTERVAL_MS = 3000;
const WS_STALENESS_MS = 8000;

const $ = (id) => document.getElementById(id);
const els = {
  userPrompt: () => $('cat-user-prompt'),
  dataTypeSel: () => $('cat-data-type'),
  toneSel: () => $('cat-tone'),
  pickStrip: () => $('cat-pick-strip'),
  layoutName: () => $('cat-layout-name'),
  styleName: () => $('cat-style-name'),
  layoutBadge: () => $('cat-layout-badge'),
  styleBadge: () => $('cat-style-badge'),
  rerollLayout: () => $('cat-reroll-layout'),
  rerollStyle: () => $('cat-reroll-style'),
  layoutDetailTitle: () => $('cat-layout-detail-title'),
  styleDetailTitle: () => $('cat-style-detail-title'),
  layoutDetail: () => $('cat-layout-detail'),
  styleDetail: () => $('cat-style-detail'),
  backend: () => $('cat-backend'),
  steps: () => $('cat-steps'),
  width: () => $('cat-width'),
  height: () => $('cat-height'),
  pickBtn: () => $('cat-pick-btn'),
  renderBtn: () => $('cat-render-btn'),
  fallbackChip: () => $('cat-fallback-chip'),
  expandedWrap: () => $('cat-expanded-wrap'),
  expanded: () => $('cat-expanded'),
  renderStatus: () => $('cat-render-status'),
  progressFill: () => $('cat-progress-fill'),
  outputPreview: () => $('cat-output-preview'),
  outputActions: () => $('cat-output-actions'),
  downloadLink: () => $('cat-download-link'),
};

function fillSelect(selectEl, options, selected) {
  while (selectEl.firstChild) selectEl.removeChild(selectEl.firstChild);
  const placeholder = document.createElement('option');
  placeholder.value = '';
  placeholder.textContent = '— Choose —';
  selectEl.appendChild(placeholder);
  for (const opt of options) {
    const o = document.createElement('option');
    o.value = opt;
    o.textContent = opt;
    if (opt === selected) o.selected = true;
    selectEl.appendChild(o);
  }
  selectEl.disabled = false;
}

function setBadge(el, kind) {
  el.classList.remove('primary', 'alternative', 'outsider', 'fallback');
  if (!kind) { el.textContent = ''; return; }
  el.classList.add(kind);
  el.textContent = kind;
}

async function fetchFirstParagraph(kind, name) {
  if (!/^[\w-]+$/.test(name)) return '';
  const key = `${kind}/${name}`;
  if (mdParagraphCache.has(key)) return mdParagraphCache.get(key);
  try {
    const r = await fetch(`/static/studio/catalogs/${kind}/${name}.md`);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const text = await r.text();
    const para = firstParagraph(text);
    mdParagraphCache.set(key, para);
    return para;
  } catch {
    return '';
  }
}

function firstParagraph(md) {
  for (const block of md.split('\n\n')) {
    const t = block.trim();
    if (!t || t.startsWith('#')) continue;
    return t.replace(/\n/g, ' ');
  }
  return '';
}

function transitionTo(next) {
  state.state = next;
  els.pickBtn().disabled = true;
  els.renderBtn().disabled = true;
  els.rerollLayout().disabled = true;
  els.rerollStyle().disabled = true;

  if (next === STATE.EMPTY) {
    els.pickStrip().hidden = true;
  } else if (next === STATE.READY_TO_PICK) {
    els.pickBtn().disabled = false;
  } else if (next === STATE.PICKED) {
    els.pickBtn().disabled = false;
    els.renderBtn().disabled = false;
    els.rerollLayout().disabled = false;
    els.rerollStyle().disabled = false;
  } else if (next === STATE.RENDERING) {
    // all four stay disabled
  } else if (next === STATE.RENDERED) {
    els.pickBtn().disabled = false;
    els.renderBtn().disabled = false;
    els.rerollLayout().disabled = false;
    els.rerollStyle().disabled = false;
  }
}

function updateReadyState() {
  if (state.state === STATE.RENDERING) return;
  if (state.dataType && state.tone) {
    transitionTo(preservableState() ? state.state : STATE.READY_TO_PICK);
  } else {
    transitionTo(STATE.EMPTY);
  }
}

function preservableState() {
  return state.state === STATE.PICKED || state.state === STATE.RENDERED;
}

async function loadCatalog() {
  try {
    const r = await fetch('/api/infographic/catalog');
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const data = await r.json();
    const storedDataType = localStorage.getItem(STORAGE_DATA_TYPE);
    const storedTone = localStorage.getItem(STORAGE_TONE);
    state.dataType = data.data_types.includes(storedDataType) ? storedDataType : null;
    state.tone = data.contexts.includes(storedTone) ? storedTone : null;
    fillSelect(els.dataTypeSel(), data.data_types, state.dataType);
    fillSelect(els.toneSel(), data.contexts, state.tone);
    updateReadyState();
  } catch (e) {
    els.renderStatus().textContent = `Catalog unavailable: ${e.message}`;
  }
}

async function doPick(lock = null) {
  const body = {
    data_type: state.dataType,
    tone: state.tone,
    lock,
    current: lock
      ? { layout: state.layout, style: state.style }
      : null,
  };
  try {
    const r = await fetch('/api/infographic/pick', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!r.ok) {
      const err = await r.json().catch(() => ({ detail: r.statusText }));
      els.renderStatus().textContent = `Pick failed: ${err.detail}`;
      return;
    }
    const data = await r.json();
    state.layout = data.layout;
    state.style = data.style;
    state.fromPool.layout = data.from_pool.layout;
    state.fromPool.style = data.from_pool.style;
    await paintPickStrip();
    els.pickStrip().hidden = false;
    transitionTo(STATE.PICKED);
  } catch (e) {
    els.renderStatus().textContent = `Pick error: ${e.message}`;
  }
}

async function paintPickStrip() {
  els.layoutName().textContent = state.layout;
  els.styleName().textContent = state.style;
  setBadge(els.layoutBadge(), state.fromPool.layout);
  setBadge(els.styleBadge(), state.fromPool.style);
  els.layoutDetailTitle().textContent = `Layout: ${state.layout}`;
  els.styleDetailTitle().textContent = `Style: ${state.style}`;
  els.layoutDetail().textContent = '…';
  els.styleDetail().textContent = '…';
  const [layoutPara, stylePara] = await Promise.all([
    fetchFirstParagraph('layouts', state.layout),
    fetchFirstParagraph('styles', state.style),
  ]);
  els.layoutDetail().textContent = layoutPara || '(no description)';
  els.styleDetail().textContent = stylePara || '(no description)';
}

async function doRender() {
  const userPrompt = els.userPrompt().value.trim();
  if (!userPrompt) {
    els.renderStatus().textContent = 'Enter a prompt first.';
    return;
  }
  transitionTo(STATE.RENDERING);
  els.fallbackChip().hidden = true;
  els.expandedWrap().hidden = true;
  els.outputPreview().hidden = true;
  els.outputActions().hidden = true;
  els.progressFill().style.width = '0%';
  els.renderStatus().textContent = 'expanding prompt…';

  const body = {
    user_prompt: userPrompt,
    data_type: state.dataType,
    tone: state.tone,
    layout: state.layout,
    style: state.style,
    backend: els.backend().value,
    width: parseInt(els.width().value, 10),
    height: parseInt(els.height().value, 10),
    num_steps: parseInt(els.steps().value, 10),
  };
  try {
    const r = await fetch('/api/infographic/render', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!r.ok) {
      const err = await r.json().catch(() => ({ detail: r.statusText }));
      throw new Error(err.detail);
    }
    const data = await r.json();
    state.jobId = data.job_id;
    state.lastWsAt = Date.now();
    els.expanded().textContent = data.expanded_prompt;
    els.expandedWrap().hidden = false;
    if (data.expansion.fallback_used) els.fallbackChip().hidden = false;
    const elapsed = data.expansion.elapsed_s.toFixed(1);
    els.renderStatus().textContent =
      `expanded via ${data.expansion.model} (${elapsed}s) — rendering…`;
    startPolling();
  } catch (e) {
    els.renderStatus().textContent = `Render failed: ${e.message}`;
    transitionTo(STATE.PICKED);
  }
}

function applyJobUpdate(msg) {
  if (msg.type !== 'job_update') return;
  if (msg.job_id !== state.jobId) return;
  if (msg.status === 'running') {
    const pct = msg.progress || 0;
    els.progressFill().style.width = `${pct}%`;
    els.renderStatus().textContent = msg.message ? `${msg.message} (${pct}%)` : `rendering ${pct}%…`;
  } else if (msg.status === 'complete') {
    els.progressFill().style.width = '100%';
    els.outputPreview().src = `${msg.output_url}?t=${Date.now()}`;
    els.outputPreview().hidden = false;
    els.outputActions().hidden = false;
    els.downloadLink().href = msg.output_url;
    els.renderStatus().textContent = 'done';
    transitionTo(STATE.RENDERED);
    state.jobId = null;
    stopPolling();
  } else if (msg.status === 'error') {
    els.renderStatus().textContent = `error: ${msg.error || 'unknown'}`;
    transitionTo(STATE.PICKED);
    state.jobId = null;
    stopPolling();
  } else if (msg.status === 'cancelled') {
    els.renderStatus().textContent = 'cancelled';
    transitionTo(STATE.PICKED);
    state.jobId = null;
    stopPolling();
  }
}

function connectWs() {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  state.ws = new WebSocket(`${proto}://${location.host}/ws`);
  state.ws.addEventListener('message', (ev) => {
    let msg; try { msg = JSON.parse(ev.data); } catch { return; }
    if (msg.type !== 'job_update') return;
    if (msg.job_id !== state.jobId) return;
    state.lastWsAt = Date.now();
    applyJobUpdate(msg);
  });
  state.ws.addEventListener('close', () => setTimeout(connectWs, 2000));
}

function startPolling() {
  stopPolling();
  state.pollTimer = setInterval(async () => {
    if (!state.jobId) { stopPolling(); return; }
    if (Date.now() - state.lastWsAt < WS_STALENESS_MS) return;
    try {
      const r = await fetch(`/api/job/${state.jobId}`);
      if (!r.ok) return;
      const j = await r.json();
      applyJobUpdate({
        type: 'job_update', job_id: state.jobId,
        status: j.status, progress: j.progress, message: j.message,
        output_url: j.output_url, error: j.error,
      });
    } catch { /* next tick */ }
  }, POLL_INTERVAL_MS);
}

function stopPolling() {
  if (state.pollTimer) { clearInterval(state.pollTimer); state.pollTimer = null; }
}

let booted = false;
export function initCatalogMode() {
  if (booted) return;
  booted = true;

  els.dataTypeSel().addEventListener('change', () => {
    state.dataType = els.dataTypeSel().value || null;
    if (state.dataType) localStorage.setItem(STORAGE_DATA_TYPE, state.dataType);
    updateReadyState();
  });
  els.toneSel().addEventListener('change', () => {
    state.tone = els.toneSel().value || null;
    if (state.tone) localStorage.setItem(STORAGE_TONE, state.tone);
    updateReadyState();
  });
  els.pickBtn().addEventListener('click', () => doPick(null));
  els.renderBtn().addEventListener('click', doRender);
  els.rerollLayout().addEventListener('click', () => doPick('style'));
  els.rerollStyle().addEventListener('click', () => doPick('layout'));

  loadCatalog();
  connectWs();
}
