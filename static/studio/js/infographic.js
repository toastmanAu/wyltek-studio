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
  }
  // image_ref intentionally omitted in this task; Task 20 wires it.
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
};
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
