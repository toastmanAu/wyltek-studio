// /studio/infographic — template loader + form generator + render submit.
// (Form generator arrives in Task 15; submit + poll in Task 16.)

const els = {
  select: document.getElementById('template-select'),
  form: document.getElementById('slot-form'),
  renderBtn: document.getElementById('render-btn'),
  previewImg: document.getElementById('preview-img'),
  previewStatus: document.getElementById('preview-status'),
  tierInputs: () => Array.from(document.querySelectorAll('input[name="tier"]')),
};

const state = { templates: {}, current: null };

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
    for (const slot of slots) {
      if (slot.type === 'list') {
        const fsIdx = template.slots.findIndex((s) => s.id === slot.id);
        const itemsContainer = els.form.querySelectorAll('.list-items')[fsIdx];
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
        // image_ref slots are wired in Task 20; ignored here.
        const input = els.form.querySelector(`[name="${slot.id}"]`);
        if (input && input.value) acc[slot.id] = input.value;
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
  els.previewImg.hidden = true;
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
      els.previewImg.src = url + `?t=${Date.now()}`;
      els.previewImg.hidden = false;
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
  els.renderBtn.disabled = true;
  els.previewStatus.hidden = false;
  els.previewStatus.textContent = 'Submitting…';
  els.previewImg.hidden = true;
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
