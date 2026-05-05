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
