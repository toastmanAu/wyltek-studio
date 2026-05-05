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
    onTemplateChange();
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
    if (slot.max_len === undefined || slot.max_len > 60) {
      const chips = document.createElement('div');
      chips.className = 'image-chips';
      chips.dataset.target = id;
      chips.style.cssText = 'display:flex; flex-wrap:wrap; gap:4px; margin-top:4px;';
      wrap.appendChild(chips);
    }
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
  } else if (slot.type === 'image_ref') {
    const lab = document.createElement('label');
    lab.htmlFor = id;
    lab.textContent = label;
    wrap.appendChild(lab);
    const sel = document.createElement('select');
    sel.id = id;
    sel.name = path;
    sel.dataset.imageRef = '1';
    rebuildImageRefSelect(sel);
    if (value) sel.value = value;
    wrap.appendChild(sel);
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
  rebuildChips();
}

function rebuildImageRefSelect(sel) {
  const cur = sel.value;
  while (sel.firstChild) sel.removeChild(sel.firstChild);
  const noneOpt = document.createElement('option');
  noneOpt.value = '';
  noneOpt.textContent = '(none)';
  sel.appendChild(noneOpt);
  for (const [i, ref] of state.imageRefs.entries()) {
    const o = document.createElement('option');
    o.value = ref.path;            // server uses path (filesystem)
    o.textContent = `Image ${i + 1}`;
    sel.appendChild(o);
  }
  if (cur && Array.from(sel.options).some((o) => o.value === cur)) {
    sel.value = cur;
  }
}

function rebuildChips() {
  for (const cont of els.form.querySelectorAll('.image-chips')) {
    const targetId = cont.dataset.target;
    while (cont.firstChild) cont.removeChild(cont.firstChild);
    for (const i of state.imageRefs.keys()) {
      const b = document.createElement('button');
      b.type = 'button';
      b.className = 'chip';
      b.textContent = `Insert Image ${i + 1}`;
      b.addEventListener('click', () => {
        const ta = document.getElementById(targetId);
        if (!ta) return;
        const tok = `[Image ${i + 1}]`;
        const start = ta.selectionStart != null ? ta.selectionStart : ta.value.length;
        const end = ta.selectionEnd != null ? ta.selectionEnd : ta.value.length;
        ta.value = ta.value.slice(0, start) + tok + ta.value.slice(end);
        ta.focus();
        ta.selectionStart = ta.selectionEnd = start + tok.length;
      });
      cont.appendChild(b);
    }
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
  function walk(slots) {
    const acc = {};
    let listIdx = 0;
    const allListContainers = els.form.querySelectorAll('.list-items');
    for (const slot of slots) {
      if (slot.type === 'list') {
        const itemsContainer = allListContainers[listIdx++];
        const list = [];
        if (itemsContainer) {
          for (const itemEl of itemsContainer.querySelectorAll('.list-item')) {
            const itemVal = {};
            for (const sub of slot.item_slots || []) {
              const input = itemEl.querySelector(`[name$="${sub.id}"]`);
              if (input && input.value) itemVal[sub.id] = input.value;
            }
            list.push(itemVal);
          }
        }
        acc[slot.id] = list;
      } else if (slot.type !== 'image_ref') {
        const input = els.form.querySelector(`[name="${slot.id}"]`);
        if (input && input.value) acc[slot.id] = input.value;
      } else {
        // image_ref scalar slot — read the select dropdown if any.
        const sel = els.form.querySelector(`select[name="${slot.id}"][data-image-ref]`);
        if (sel && sel.value) acc[slot.id] = sel.value;
      }
    }
    return acc;
  }
  return walk(template.slots);
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
    const body = {
      template_id: tpl.id,
      tier: getTier(),
      aspect: document.getElementById('aspect-select').value,
      slots: harvestForm(tpl),
      image_refs: [],
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
    els.previewStatus.textContent = `Job ${job_id} submitted; polling…`;
    pollJob(job_id);
  } catch (e) {
    els.previewStatus.textContent = `Error: ${e.message}`;
    els.renderBtn.disabled = false;
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
      els.renderBtn.disabled = false;
      return;
    }
    if (job.status === 'error' || job.status === 'failed') {
      els.previewStatus.textContent = `Failed: ${job.error || job.message || 'unknown'}`;
      els.renderBtn.disabled = false;
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

// ── Task 19: Image-ref state model + Add Image button ────────────────────────

state.imageRefs = [];

function renderImageRefs() {
  const ul = document.getElementById('image-ref-list');
  while (ul.firstChild) ul.removeChild(ul.firstChild);
  for (const [i, ref] of state.imageRefs.entries()) {
    const li = document.createElement('li');
    li.className = 'image-ref';

    const img = document.createElement('img');
    img.src = ref.url;
    img.alt = `Image ${i + 1}`;
    li.appendChild(img);

    const lab = document.createElement('span');
    lab.className = 'ref-label';
    lab.textContent = `Image ${i + 1}`;
    li.appendChild(lab);

    const rm = document.createElement('button');
    rm.type = 'button';
    rm.className = 'remove';
    rm.textContent = '×';
    rm.addEventListener('click', () => {
      state.imageRefs.splice(i, 1);
      renderImageRefs();
      updateAspectDisabled();
    });
    li.appendChild(rm);

    ul.appendChild(li);
  }
  document.getElementById('image-ref-add').disabled = state.imageRefs.length >= 4;
  for (const sel of els.form.querySelectorAll('select[data-image-ref]')) rebuildImageRefSelect(sel);
  rebuildChips();
}

document.getElementById('image-ref-add').addEventListener('click', () => {
  document.getElementById('image-ref-input').click();
});

document.getElementById('image-ref-input').addEventListener('change', async (ev) => {
  const f = ev.target.files[0];
  if (!f || state.imageRefs.length >= 4) {
    ev.target.value = '';
    return;
  }
  try {
    const result = await uploadImage(f);   // {url, path}
    state.imageRefs.push(result);
    renderImageRefs();
    updateAspectDisabled();
  } catch (e) {
    els.previewStatus.hidden = false;
    els.previewStatus.textContent = `Upload failed: ${e.message}`;
  }
  ev.target.value = '';
});

function updateAspectDisabled() {
  const sel = document.getElementById('aspect-select');
  if (state.imageRefs.length > 0) {
    sel.disabled = true;
    sel.title = 'Output size auto-derived from Image 1 when refs are present';
  } else {
    sel.disabled = false;
    sel.removeAttribute('title');
  }
}

// Re-implement submitRender to include image_refs from state.imageRefs.
// The original (Task 16) sends image_refs: []. We shadow it here so all
// future renders carry the on-disk paths the SenseNova subprocess can read.
const _origSubmitRender = submitRender;
submitRender = async function () {
  const tpl = state.current;
  if (!tpl) return;
  // Precheck — if ComfyUI is running on driveThree-class hardware, block.
  const banner = document.getElementById('precheck-banner');
  try {
    const preR = await fetch('/api/sensenova/precheck');
    const pre = await preR.json();
    if (!pre.ready) {
      while (banner.firstChild) banner.removeChild(banner.firstChild);
      const strong = document.createElement('strong');
      strong.textContent = 'Cannot render:';
      banner.appendChild(strong);
      const ul = document.createElement('ul');
      for (const b of pre.blockers) {
        const li = document.createElement('li');
        li.textContent = b;
        ul.appendChild(li);
      }
      banner.appendChild(ul);
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.textContent = 'Recheck';
      btn.addEventListener('click', async () => {
        banner.hidden = true;
        await submitRender();
      }, {once: true});
      banner.appendChild(btn);
      banner.hidden = false;
      return;
    }
    banner.hidden = true;
  } catch (e) {
    // Precheck unreachable — let the user proceed; the actual render will surface errors.
    console.warn('precheck failed:', e);
  }
  els.renderBtn.disabled = true;
  els.previewStatus.hidden = false;
  els.previewStatus.textContent = 'Submitting…';
  // Don't hide the canvas during a new render — keep previous result visible.
  try {
    const body = {
      template_id: tpl.id,
      tier: getTier(),
      aspect: document.getElementById('aspect-select').value,
      slots: harvestForm(tpl),
      image_refs: state.imageRefs.map((r) => r.path),
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
    els.previewStatus.textContent = `Job ${job_id} submitted; polling…`;
    pollJob(job_id);
  } catch (e) {
    els.previewStatus.textContent = `Error: ${e.message}`;
    els.renderBtn.disabled = false;
  }
};
els.renderBtn.removeEventListener('click', _origSubmitRender);
els.renderBtn.addEventListener('click', submitRender);

renderImageRefs();

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
  let listIdx = 0;
  const allListContainers = els.form.querySelectorAll('.list-items');
  for (const slot of slotDefs) {
    const v = values?.[slot.id];
    if (slot.type === 'list' && Array.isArray(v)) {
      const items = allListContainers[listIdx++];
      if (items) {
        while (items.firstChild) items.removeChild(items.firstChild);
        for (const [i, item] of v.entries()) addListItem(slot, slot.id, items, i, item);
      }
    } else if (slot.type === 'list') {
      // List slot but no value to fill — still consume the index.
      listIdx++;
    } else if (slot.type !== 'image_ref') {
      const input = els.form.querySelector(`[name="${slot.id}"]`);
      if (input && v != null) input.value = v;
    } else {
      const sel = els.form.querySelector(`select[name="${slot.id}"][data-image-ref]`);
      if (sel && v != null) {
        if (Array.from(sel.options).some((o) => o.value === v)) sel.value = v;
      }
    }
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
