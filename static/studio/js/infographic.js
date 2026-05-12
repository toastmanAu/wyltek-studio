// /studio/infographic — template loader + form generator + render submit.
// (Form generator arrives in Task 15; submit + poll in Task 16.)

const els = {
  select: document.getElementById('template-select'),
  form: document.getElementById('slot-form'),
  renderBtn: document.getElementById('render-btn'),
  previewStatus: document.getElementById('preview-status'),
  tierInputs: () => Array.from(document.querySelectorAll('input[name="tier"]')),
};

import {PreviewCanvas} from './canvas-edit.js';

const state = { templates: {}, current: null };

const previewCanvas = new PreviewCanvas(document.getElementById('preview-canvas'));
const canvasTools = document.getElementById('canvas-tools');

async function loadTemplates() {
  const r = await fetch('/api/infographic/templates');
  if (!r.ok) throw new Error(`templates fetch: ${r.status}`);
  const list = await r.json();
  state.templates = Object.fromEntries(list.map((t) => [t.id, t]));
  // Safe: clearing the select element before repopulating with trusted option elements.
  while (els.select.firstChild) {
    els.select.removeChild(els.select.firstChild);
  }
  for (const t of list) {
    const opt = document.createElement('option');
    opt.value = t.id;
    opt.textContent = t.name;
    els.select.appendChild(opt);
  }
  els.select.disabled = false;
  if (list.length) {
    state.current = list[0];
    els.select.value = list[0].id;
    // Use the wrapped onTemplateChange (set up after Task 15 wiring) so the
    // initial form is built. Falls back to the local function if for some
    // reason the wrap hasn't happened yet (defensive — should never hit).
    (window.onTemplateChange || onTemplateChange)();
  }
}

function onTemplateChange() {
  state.current = state.templates[els.select.value];
  els.renderBtn.disabled = !state.current;
  // Form generation is added in Task 15.
}

els.select.addEventListener('change', onTemplateChange);
loadTemplates().catch((e) => {
  els.previewStatus.textContent = `Failed to load templates: ${e.message}`;
});

// ── Worker lifecycle + precheck — installation, GPU tenancy, cancel ──────

const precheckEls = {
  banner: document.getElementById('precheck-banner'),
};

const workerEls = {
  bar: document.getElementById('worker-bar'),
  sensePill: document.getElementById('sense-pill'),
  comfyPill: document.getElementById('comfy-pill'),
  senseStart: document.getElementById('sense-start'),
  senseStop: document.getElementById('sense-stop'),
  senseRestart: document.getElementById('sense-restart'),
  comfyStart: document.getElementById('comfy-start'),
  comfyStop: document.getElementById('comfy-stop'),
  vramReadout: document.getElementById('vram-readout'),
  cancelBtn: document.getElementById('cancel-btn'),
};

// Tracks the last precheck result so the auto-start logic can read it
// without re-issuing the request.
let lastPrecheck = null;
// One-shot guard so we don't repeatedly auto-start the worker if the user
// explicitly stopped it.
let autoStartFired = false;
// While a render is in flight, the Cancel button targets this job id.
let activeJobId = null;

function clearChildren(node) {
  while (node.firstChild) node.removeChild(node.firstChild);
}

// ── Worker status pill rendering ─────────────────────────────────────────

function setPill(pillEl, name, status) {
  // status: {state, listening, detail: {loaded, vram_gb, vram_max_gb}}
  if (!pillEl) return;
  const state = (status && status.state) || 'unknown';
  pillEl.classList.remove(
    'state-running', 'state-starting', 'state-stopped',
    'state-crashed', 'state-unknown'
  );
  pillEl.classList.add(`state-${state}`);

  const labelEl = pillEl.querySelector('.label');
  const niceState = ({
    running: 'running',
    starting: 'starting (loading)',
    stopped: 'stopped',
    crashed: 'crashed',
    unknown: 'unknown',
  })[state] || state;
  if (labelEl) labelEl.textContent = `${name}: ${niceState}`;
}

function updateButtonStates(workers) {
  if (!workers) return;
  const sense = workers.sensenova || {};
  const comfy = workers.comfyui || {};

  // Worker action buttons. Disable during transient states so users can't
  // double-fire start while it's already starting.
  workerEls.senseStart.disabled = sense.state === 'running' || sense.state === 'starting';
  workerEls.senseStop.disabled = sense.state === 'stopped' || sense.state === 'unknown';
  workerEls.senseRestart.disabled = sense.state === 'stopped' || sense.state === 'unknown';

  workerEls.comfyStart.disabled = comfy.state === 'running' || comfy.state === 'starting';
  workerEls.comfyStop.disabled = comfy.state === 'stopped' || comfy.state === 'unknown';

  // VRAM readout from the SenseNova worker /status (when up).
  const d = sense.detail || {};
  if (d.vram_gb != null && d.vram_max_gb != null) {
    workerEls.vramReadout.textContent =
      `GPU: ${d.vram_gb.toFixed(1)} / ${d.vram_max_gb.toFixed(1)} GB`;
  } else {
    workerEls.vramReadout.textContent = '';
  }
}

async function refreshWorkers() {
  try {
    const r = await fetch('/api/workers/status');
    if (!r.ok) return null;
    const w = await r.json();
    setPill(workerEls.sensePill, 'SenseNova worker', w.sensenova);
    setPill(workerEls.comfyPill, 'ComfyUI', w.comfyui);
    updateButtonStates(w);
    return w;
  } catch {
    return null;
  }
}

// Poll workers every 3s while page is in view, every 15s when hidden.
function startWorkerPolling() {
  refreshWorkers();
  let interval = setInterval(refreshWorkers, 3000);
  document.addEventListener('visibilitychange', () => {
    clearInterval(interval);
    interval = setInterval(refreshWorkers, document.hidden ? 15000 : 3000);
  });
}
startWorkerPolling();

// ── Lifecycle button handlers ────────────────────────────────────────────

async function postJSON(url) {
  const r = await fetch(url, {method: 'POST'});
  if (!r.ok) throw new Error(`${url}: ${r.status}`);
  return r.json();
}

async function lifecycleAction(url, btn, optimisticLabel) {
  // Optimistic feedback so the user knows the click registered while
  // systemctl takes its ~0.5-1s to return.
  const prev = btn.textContent;
  btn.disabled = true;
  if (optimisticLabel) btn.textContent = optimisticLabel;
  try {
    const result = await postJSON(url);
    if (!result.ok) {
      const msg = result.error || `rc=${result.rc}`;
      els.previewStatus.hidden = false;
      els.previewStatus.textContent = `Lifecycle action failed: ${msg}`;
    }
  } catch (e) {
    els.previewStatus.hidden = false;
    els.previewStatus.textContent = `Lifecycle action failed: ${e.message}`;
  } finally {
    btn.textContent = prev;
    await refreshWorkers();
    initPrecheck();
  }
}

workerEls.senseStart.addEventListener('click',
  () => lifecycleAction('/api/sensenova/worker/start', workerEls.senseStart, 'Starting…'));
workerEls.senseStop.addEventListener('click',
  () => { autoStartFired = true; return lifecycleAction('/api/sensenova/worker/stop', workerEls.senseStop, 'Stopping…'); });
workerEls.senseRestart.addEventListener('click',
  () => lifecycleAction('/api/sensenova/worker/restart', workerEls.senseRestart, 'Restarting…'));
workerEls.comfyStart.addEventListener('click',
  () => lifecycleAction('/api/comfyui/start', workerEls.comfyStart, 'Starting…'));
workerEls.comfyStop.addEventListener('click',
  () => lifecycleAction('/api/comfyui/stop', workerEls.comfyStop, 'Stopping…'));

// ── Precheck banner ──────────────────────────────────────────────────────

function renderPrecheck(state) {
  lastPrecheck = state;
  const el = precheckEls.banner;
  if (!el) return;

  clearChildren(el);

  if (state.ready) {
    el.hidden = true;
    els.renderBtn.disabled = !state.current;
    return;
  }

  el.hidden = false;
  const notInstalled = state.installed === false;
  el.style.background = notInstalled ? 'rgba(220,80,80,0.12)' : 'rgba(255,165,0,0.10)';
  el.style.borderColor = notInstalled ? 'rgba(220,80,80,0.55)' : 'rgba(255,165,0,0.5)';

  const heading = document.createElement('strong');
  heading.textContent = notInstalled
    ? 'SenseNova-U1 is not installed on this machine'
    : 'SenseNova-U1 cannot render right now';
  el.appendChild(heading);

  const list = document.createElement('ul');
  for (const msg of state.blockers || []) {
    const li = document.createElement('li');
    li.textContent = msg;
    list.appendChild(li);
  }
  el.appendChild(list);

  if (notInstalled) {
    const help = document.createElement('p');
    help.style.margin = '8px 0 0';
    help.style.fontSize = '12px';
    help.style.opacity = '0.85';
    help.textContent = (
      'SenseNova-U1-8B-MoT is a ~16B-parameter unified multimodal model. ' +
      'It needs ~32 GB of BF16 weights on disk and a 24 GB GPU (with ' +
      'CPU offload) to run. If your hardware can’t host it, the ' +
      'rest of Wyltek Studio works without this page.'
    );
    el.appendChild(help);

    const hint = (state.details && state.details.install_hint) || './scripts/setup-sensenova.sh';
    const cmd = document.createElement('pre');
    cmd.style.margin = '8px 0 0';
    cmd.style.padding = '8px 10px';
    cmd.style.background = 'rgba(0,0,0,0.35)';
    cmd.style.borderRadius = '6px';
    cmd.style.fontSize = '12px';
    cmd.style.overflow = 'auto';
    cmd.textContent = hint;
    el.appendChild(cmd);
  }

  // Inline action buttons — replaces the old "open a terminal" instructions.
  const actions = document.createElement('div');
  actions.className = 'inline-actions';

  const d = state.details || {};
  const comfyState = d.comfyui && d.comfyui.state;
  const workerState = d.worker && d.worker.state;

  if (!notInstalled && (comfyState === 'running' || comfyState === 'starting')) {
    const stopComfy = document.createElement('button');
    stopComfy.type = 'button';
    stopComfy.textContent = 'Stop ComfyUI';
    stopComfy.addEventListener('click', async () => {
      stopComfy.disabled = true;
      stopComfy.textContent = 'Stopping…';
      await postJSON('/api/comfyui/stop').catch(() => {});
      autoStartFired = false; // Let auto-start retry the worker once GPU is free.
      await refreshWorkers();
      initPrecheck();
    });
    actions.appendChild(stopComfy);
  }

  if (!notInstalled && (workerState === 'stopped' || workerState === 'crashed')) {
    const startWorker = document.createElement('button');
    startWorker.type = 'button';
    startWorker.textContent = workerState === 'crashed' ? 'Restart worker' : 'Start worker';
    startWorker.addEventListener('click', async () => {
      startWorker.disabled = true;
      startWorker.textContent = 'Starting…';
      const url = workerState === 'crashed'
        ? '/api/sensenova/worker/restart'
        : '/api/sensenova/worker/start';
      await postJSON(url).catch(() => {});
      await refreshWorkers();
      initPrecheck();
    });
    actions.appendChild(startWorker);
  }

  const recheck = document.createElement('button');
  recheck.type = 'button';
  recheck.className = 'secondary';
  recheck.textContent = 'Recheck';
  recheck.addEventListener('click', () => { initPrecheck(); });
  actions.appendChild(recheck);

  el.appendChild(actions);

  // Hard-block render only when not installed. Other states are UI-resolvable.
  if (notInstalled) {
    els.renderBtn.disabled = true;
    els.renderBtn.title = 'SenseNova-U1 is not installed on this machine.';
  } else {
    // Soft-block: button enabled iff worker reports running. The actual
    // render call will fail informatively otherwise, but disabling the
    // button avoids accidental clicks that produce a misleading error.
    els.renderBtn.disabled = workerState !== 'running' || !state.current;
    els.renderBtn.title = workerState !== 'running'
      ? `SenseNova worker is ${workerState}. Use the worker bar above to start it.`
      : '';
  }

  // Auto-start path (user picked this in setup). Conditions:
  //  - installed
  //  - ComfyUI not blocking (state stopped/unknown)
  //  - worker explicitly stopped (NOT crashed — crashes get a manual button
  //    so loops don't go unnoticed)
  //  - we haven't already fired once this session
  if (!autoStartFired
      && !notInstalled
      && (comfyState === 'stopped' || comfyState === 'unknown')
      && workerState === 'stopped') {
    autoStartFired = true;
    postJSON('/api/sensenova/worker/start')
      .then(refreshWorkers)
      .then(initPrecheck)
      .catch(() => {});
  }
}

async function initPrecheck() {
  try {
    const r = await fetch('/api/sensenova/precheck');
    if (!r.ok) throw new Error(`precheck ${r.status}`);
    renderPrecheck(await r.json());
  } catch (e) {
    renderPrecheck({
      ready: false,
      installed: null,
      blockers: [`Could not reach /api/sensenova/precheck: ${e.message}`],
      details: {},
    });
  }
}

initPrecheck();
// Recheck precheck periodically so 'starting' → 'running' transitions clear
// the banner without the user clicking Recheck.
setInterval(() => { if (!document.hidden) initPrecheck(); }, 5000);

// ── Cancel button ────────────────────────────────────────────────────────

function setRenderRunningUI(running, jobId) {
  activeJobId = running ? jobId : null;
  workerEls.cancelBtn.hidden = !running;
  els.renderBtn.disabled = running;
}

workerEls.cancelBtn.addEventListener('click', async () => {
  if (!activeJobId) return;
  const btn = workerEls.cancelBtn;
  btn.disabled = true;
  const prev = btn.textContent;
  btn.textContent = 'Cancelling…';
  try {
    const r = await fetch(`/api/job/${activeJobId}/cancel`, {method: 'POST'});
    const body = await r.json();
    els.previewStatus.hidden = false;
    els.previewStatus.textContent = body.ok
      ? 'Cancelled. Worker restart pending — GPU will be free in ~2s.'
      : `Cancel returned: ${JSON.stringify(body)}`;
  } catch (e) {
    els.previewStatus.hidden = false;
    els.previewStatus.textContent = `Cancel failed: ${e.message}`;
  } finally {
    btn.textContent = prev;
    btn.disabled = false;
    setRenderRunningUI(false, null);
    refreshWorkers();
  }
});

// ── Task 15: Form generator from slot schema ──────────────────────────────

function fieldId(path) {
  return `slot__${path.replace(/[^a-z0-9_]/gi, '_')}`;
}

function renderSlot(slot, path, value) {
  const id = fieldId(path);
  const wrap = document.createElement('div');
  wrap.className = 'slot slot-' + slot.type;
  const label = slot.label || slot.id;

  if (slot.type === 'text') {
    const lab = document.createElement('label');
    lab.htmlFor = id;
    lab.textContent = label + (slot.required ? ' *' : '');
    wrap.appendChild(lab);
    const input = (slot.max_len && slot.max_len > 60)
      ? document.createElement('textarea')
      : document.createElement('input');
    input.id = id;
    input.name = path;
    if (slot.max_len) input.setAttribute('maxlength', slot.max_len);
    if (value != null) input.value = value;
    wrap.appendChild(input);
  } else if (slot.type === 'color') {
    const lab = document.createElement('label');
    lab.htmlFor = id;
    lab.textContent = label;
    wrap.appendChild(lab);
    const input = document.createElement('input');
    input.type = 'color';
    input.id = id;
    input.name = path;
    if (value) input.value = value;
    wrap.appendChild(input);
  } else if (slot.type === 'enum') {
    const lab = document.createElement('label');
    lab.htmlFor = id;
    lab.textContent = label;
    wrap.appendChild(lab);
    const sel = document.createElement('select');
    sel.id = id;
    sel.name = path;
    for (const choice of slot.choices || []) {
      const o = document.createElement('option');
      o.value = o.textContent = choice;
      sel.appendChild(o);
    }
    if (value) sel.value = value;
    wrap.appendChild(sel);
  } else if (slot.type === 'list') {
    const fs = document.createElement('fieldset');
    fs.className = 'list-slot';
    const legend = document.createElement('legend');
    legend.textContent = label;
    fs.appendChild(legend);
    const items = document.createElement('div');
    items.className = 'list-items';
    items.dataset.path = path;   // unique per list slot in the form; harvest/fill use this
    fs.appendChild(items);
    const initial = Array.isArray(value)
      ? value
      : Array.from({length: slot.min || 1}, () => ({}));
    for (const [i, item] of initial.entries()) addListItem(slot, path, items, i, item);
    const addBtn = document.createElement('button');
    addBtn.type = 'button';
    addBtn.textContent = '+ Add row';
    addBtn.addEventListener('click', () => {
      const idx = items.children.length;
      if (slot.max && idx >= slot.max) return;
      addListItem(slot, path, items, idx, {});
    });
    fs.appendChild(addBtn);
    wrap.appendChild(fs);
  }
  return wrap;
}

function addListItem(parentSlot, parentPath, container, idx, value) {
  const item = document.createElement('div');
  item.className = 'list-item';
  for (const sub of parentSlot.item_slots || []) {
    item.appendChild(renderSlot(sub, `${parentPath}[${idx}].${sub.id}`, value[sub.id]));
  }
  const rm = document.createElement('button');
  rm.type = 'button';
  rm.className = 'remove-row';
  rm.textContent = '×';
  rm.addEventListener('click', () => item.remove());
  item.appendChild(rm);
  container.appendChild(item);
}

function buildForm(template) {
  while (els.form.firstChild) els.form.removeChild(els.form.firstChild);
  for (const slot of template.slots) {
    els.form.appendChild(renderSlot(slot, slot.id, null));
  }
}

// Wire it into onTemplateChange. The function from Task 14 only updated
// state.current and the render button — extend it to also rebuild the form.
const _origOnTemplateChange = onTemplateChange;
window.onTemplateChange = function () {
  _origOnTemplateChange();
  if (state.current) buildForm(state.current);
  updateTemplatePreview();
};

function updateTemplatePreview() {
  const prev = document.getElementById('template-preview');
  if (!prev) return;
  if (state.current && state.current.preview) {
    prev.onerror = () => {
      // Preview file missing — just hide instead of showing broken-image icon.
      prev.hidden = true;
      prev.onerror = null;
    };
    prev.onload = () => { prev.hidden = false; };
    prev.src = '/' + state.current.preview;
  } else {
    prev.hidden = true;
    prev.removeAttribute('src');
  }
}
els.select.removeEventListener('change', onTemplateChange);
els.select.addEventListener('change', window.onTemplateChange);
window.onTemplateChange();

// ── Task 16: Slot harvest + render submit + job poll ──────────────────────────

function harvestForm(template) {
  // Walk the template recursively. Each list slot's `.list-items` container
  // carries `data-path="<full path>"` so we can find it unambiguously even
  // for deeply-nested lists (e.g. comparison's left[0].bullets, hierarchy's
  // levels[0].nodes). Plain text/color/enum slots are looked up by their
  // full `name` attribute, which renderSlot built path-style.
  function harvestSlot(slot, basePath, scope) {
    const fullPath = basePath ? `${basePath}.${slot.id}` : slot.id;
    if (slot.type === 'list') {
      const container = scope.querySelector(
        `.list-items[data-path="${cssEscape(fullPath)}"]`
      );
      if (!container) return [];
      const list = [];
      const items = container.querySelectorAll(':scope > .list-item');
      items.forEach((itemEl, idx) => {
        const itemVal = {};
        for (const sub of slot.item_slots || []) {
          const v = harvestSlot(sub, `${fullPath}[${idx}]`, itemEl);
          if (v !== undefined) itemVal[sub.id] = v;
        }
        list.push(itemVal);
      });
      return list;
    }
    // text / color / enum scalar slot
    const input = scope.querySelector(`[name="${cssEscape(fullPath)}"]`);
    return input && input.value ? input.value : undefined;
  }

  const result = {};
  for (const slot of template.slots) {
    const v = harvestSlot(slot, '', els.form);
    if (v !== undefined) result[slot.id] = v;
  }
  return result;
}

// Minimal CSS attribute-value escaping for selectors. Path strings contain
// brackets and dots which are valid inside an attribute-value string but
// quotes themselves must be escaped. renderSlot never puts quotes in paths,
// so this is conservative.
function cssEscape(s) {
  return String(s).replace(/"/g, '\\"');
}

function getTier() {
  const checked = els.tierInputs().find((i) => i.checked);
  return checked ? checked.value : 'draft';
}

async function submitRender() {
  const tpl = state.current;
  if (!tpl) return;
  els.renderBtn.disabled = true;
  els.previewStatus.textContent = 'Submitting…';
  els.previewStatus.hidden = false;
  // Don't hide the canvas during a new render — it's nice to keep the
  // previous result visible while waiting. Status div will overlay.
  try {
    const styleNotesEl = document.getElementById('style-notes');
    const body = {
      template_id: tpl.id,
      tier: getTier(),
      aspect: document.getElementById('aspect-select').value,
      slots: harvestForm(tpl),
      image_refs: [],
      style_notes: styleNotesEl ? styleNotesEl.value.trim() : '',
    };
    const r = await fetch('/api/infographic/render', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(body),
    });
    if (!r.ok) {
      const text = await r.text();
      throw new Error(`render: ${r.status} ${text}`);
    }
    const {job_id} = await r.json();
    state.lastRenderId = job_id;
    setRenderRunningUI(true, job_id);
    els.previewStatus.textContent = `Job ${job_id} submitted; polling…`;
    pollJob(job_id);
  } catch (e) {
    els.previewStatus.textContent = `Error: ${e.message}`;
    setRenderRunningUI(false, null);
  }
}

async function pollJob(jobId) {
  while (true) {
    await new Promise((r) => setTimeout(r, 2000));
    const r = await fetch(`/api/job/${jobId}`);
    if (!r.ok) {
      els.previewStatus.textContent = `Job poll failed: ${r.status}`;
      els.renderBtn.disabled = false;
      return;
    }
    const job = await r.json();
    const pct = job.progress != null ? job.progress : '';
    const msg = job.message ? ` ${job.message}` : '';
    els.previewStatus.textContent = `${job.status} ${pct}%${msg}`;

    if (job.status === 'complete') {
      const url = job.output_url || `/outputs/infographic/${jobId}/out.png`;
      await previewCanvas.setBase(url + `?t=${Date.now()}`);
      canvasTools.hidden = false;
      els.previewStatus.hidden = true;
      setRenderRunningUI(false, null);
      return;
    }
    if (job.status === 'error' || job.status === 'failed') {
      els.previewStatus.textContent = `Failed: ${job.error || job.message || 'unknown'}`;
      setRenderRunningUI(false, null);
      return;
    }
    if (job.status === 'cancelled') {
      els.previewStatus.textContent = 'Cancelled.';
      setRenderRunningUI(false, null);
      return;
    }
  }
}

els.renderBtn.addEventListener('click', submitRender);

async function uploadImage(file) {
  const fd = new FormData();
  fd.append('file', file);
  const r = await fetch('/api/infographic/upload', {method: 'POST', body: fd});
  if (!r.ok) throw new Error(`upload: ${r.status} ${await r.text()}`);
  return await r.json();   // {url, path}
}

// ── Task 30: Render history list + click-to-load ──────────────────────────────

async function loadHistory() {
  const ul = document.getElementById('history-list');
  if (!ul) return;
  try {
    const r = await fetch('/api/infographic/history?limit=30');
    if (!r.ok) return;
    const list = await r.json();
    while (ul.firstChild) ul.removeChild(ul.firstChild);
    for (const entry of list) {
      const li = document.createElement('li');
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'history-item';
      btn.dataset.job = entry.job_id;

      const img = document.createElement('img');
      img.src = entry.png_url;
      img.alt = '';
      btn.appendChild(img);

      const lab = document.createElement('span');
      const tplId = (entry.sidecar && entry.sidecar.template_id) || 'render';
      const title = (entry.sidecar && entry.sidecar.slots && entry.sidecar.slots.title) || entry.job_id;
      lab.textContent = `${tplId} — ${title}`;
      btn.appendChild(lab);

      btn.addEventListener('click', () => loadFromHistory(entry));
      li.appendChild(btn);
      ul.appendChild(li);
    }
  } catch (e) {
    console.warn('history load failed:', e);
  }
}

async function loadFromHistory(entry) {
  const sc = entry.sidecar || {};

  // 1. Switch template if needed.
  if (sc.template_id && state.current?.id !== sc.template_id) {
    if (!state.templates[sc.template_id]) {
      els.previewStatus.hidden = false;
      els.previewStatus.textContent = `Template "${sc.template_id}" no longer available.`;
      return;
    }
    els.select.value = sc.template_id;
    window.onTemplateChange();
  }

  // 2. Repopulate slot values.
  if (state.current && sc.slots) {
    fillFormFromSlots(state.current.slots, sc.slots);
  }

  // 3. Load preview.
  if (entry.png_url) {
    await previewCanvas.setBase(entry.png_url + `?t=${Date.now()}`);
    canvasTools.hidden = false;
    els.previewStatus.hidden = true;
  }

  state.lastRenderId = entry.job_id;
}

function fillFormFromSlots(slotDefs, values) {
  // Recursive mirror of harvestForm: walk the template, look up each list
  // slot's `.list-items` by `data-path`, rebuild from the saved values, and
  // recurse into nested lists. addListItem already prefills leaf values
  // passed via the `value` arg, so for fully-flat lists this is one re-render.
  function fillSlot(slot, basePath, scope, value) {
    const fullPath = basePath ? `${basePath}.${slot.id}` : slot.id;
    if (slot.type === 'list') {
      if (!Array.isArray(value)) return;
      const container = scope.querySelector(
        `.list-items[data-path="${cssEscape(fullPath)}"]`
      );
      if (!container) return;
      while (container.firstChild) container.removeChild(container.firstChild);
      for (const [i, item] of value.entries()) {
        addListItem(slot, fullPath, container, i, item);
      }
      return;
    }
    const input = scope.querySelector(`[name="${cssEscape(fullPath)}"]`);
    if (input && value != null) input.value = value;
  }

  for (const slot of slotDefs) {
    fillSlot(slot, '', els.form, values?.[slot.id]);
  }
}

// Refresh history after every successful render.
const _origPollJob = pollJob;
pollJob = async function (jobId) {
  await _origPollJob(jobId);
  loadHistory();
};

// Initial load.
loadHistory();

// ── Task 32/33: Delete button + keyboard delete for selected canvas layer ─────

const _canvasDeleteBtn = document.getElementById('canvas-delete');
if (_canvasDeleteBtn) {
  _canvasDeleteBtn.addEventListener('click', () => previewCanvas.deleteSelected());
}

document.addEventListener('keydown', (e) => {
  if ((e.key === 'Delete' || e.key === 'Backspace') &&
      previewCanvas.selected >= 0 &&
      !['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement?.tagName)) {
    e.preventDefault();
    previewCanvas.deleteSelected();
  }
});

// ── Task 34: Paste image from clipboard ──────────────────────────────────────

const _canvasPasteBtn = document.getElementById('canvas-paste');
if (_canvasPasteBtn) {
  _canvasPasteBtn.addEventListener('click', () => previewCanvas.pasteFromClipboard());
}
document.addEventListener('paste', (e) => {
  // Ignore if user is typing in a form field.
  if (['INPUT', 'TEXTAREA'].includes(document.activeElement?.tagName)) return;
  for (const it of (e.clipboardData?.items || [])) {
    if (it.type.startsWith('image/')) {
      const blob = it.getAsFile();
      if (blob) previewCanvas.addLayerFromBlob(blob, 60, 60);
      e.preventDefault();
      return;
    }
  }
});

// ── Download current canvas to device (mobile-friendly: <a download>) ───────

const _canvasDownloadBtn = document.getElementById('canvas-download');
if (_canvasDownloadBtn) {
  _canvasDownloadBtn.addEventListener('click', async () => {
    // Mobile browsers don't expose long-press → save on canvas elements,
    // so we synthesise a download via a hidden anchor. Works on iOS Safari
    // (opens preview, user taps "Download" / share-sheet), Android Chrome
    // (direct download), and desktop (file save dialog).
    const blob = await previewCanvas.toBlob();
    if (!blob) return;
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    const ts = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
    a.download = `infographic-${ts}.png`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  });
}


// ── Task 35: Save composite as new render ────────────────────────────────────

const _canvasSaveBtn = document.getElementById('canvas-save');
if (_canvasSaveBtn) {
  _canvasSaveBtn.addEventListener('click', async () => {
    const blob = await previewCanvas.toBlob();
    if (!blob) return;
    const fd = new FormData();
    fd.append('file', blob, 'composite.png');
    fd.append('base_render_id', state.lastRenderId || '');
    try {
      const r = await fetch('/api/infographic/composite', {method: 'POST', body: fd});
      if (!r.ok) {
        const text = await r.text();
        throw new Error(`save: ${r.status} ${text}`);
      }
      const body = await r.json();
      els.previewStatus.hidden = false;
      els.previewStatus.textContent = `Composite saved as ${body.job_id}.`;
      await loadHistory();
    } catch (e) {
      els.previewStatus.hidden = false;
      els.previewStatus.textContent = `Save failed: ${e.message}`;
    }
  });
}
