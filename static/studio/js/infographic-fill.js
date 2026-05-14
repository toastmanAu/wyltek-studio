// Manual logo-placement page for sentinel-detected infographic slots.
//
// Flow: read ?job=<id> → GET /api/infographic-fill/job/<id> →
//   render image + slot overlays in percentage coordinates so they track
//   responsive scaling → tap-to-focus a slot, tap-to-assign a logo →
//   POST /api/infographic-fill/composite to render out.filled.png.
//
// Tap-to-select is used instead of HTML5 drag-and-drop because the latter
// is unreliable on iOS Safari (drop events frequently never fire for
// pointer-based gestures). Tap works identically across devices.
//
// No innerHTML anywhere — gallery thumbnails and slot overlays are built
// with createElement so a malicious filename can't yield XSS.

const $ = (id) => document.getElementById(id);

const els = {
  status: $('status-line'),
  saveBtn: $('save-btn'),
  clearBtn: $('clear-btn'),
  canvasPane: document.querySelector('.canvas-pane'),
  stage: $('canvas-stage'),
  img: $('output-img'),
  gallery: $('gallery'),
  uploadInput: $('upload-input'),
  jobReadout: $('job-id-readout'),
};

// ── State ───────────────────────────────────────────────────────────────────
const state = {
  jobId: null,
  canvas: [0, 0],          // [w, h] in image pixels
  slots: [],               // [{id, bbox:[x,y,w,h], center:[x,y], area_px}]
  assignments: new Map(),  // slot_id → logo_filename
  focusedSlot: null,       // slot id currently selected for assignment
  galleryEntries: [],
};

function setStatus(text) { els.status.textContent = text; }

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

// ── Bootstrapping ───────────────────────────────────────────────────────────
async function init() {
  const params = new URLSearchParams(location.search);
  const jobId = params.get('job');
  if (!jobId) {
    setStatus('Missing job id — open this page from a finished render.');
    return;
  }
  state.jobId = jobId;
  els.jobReadout.textContent = `job ${jobId}`;

  try {
    const [jobRes, galleryRes] = await Promise.all([
      fetch(`/api/infographic-fill/job/${encodeURIComponent(jobId)}`),
      fetch('/api/logos/list'),
    ]);
    if (!jobRes.ok) throw new Error(`job lookup failed (${jobRes.status})`);
    if (!galleryRes.ok) throw new Error(`gallery lookup failed (${galleryRes.status})`);
    const jobData = await jobRes.json();
    const galleryData = await galleryRes.json();

    hydrateJob(jobData);
    hydrateGallery(galleryData.entries || []);
    els.canvasPane.classList.remove('is-loading');
  } catch (e) {
    setStatus(`error: ${e.message}`);
    els.canvasPane.classList.remove('is-loading');
  }
}

function hydrateJob(data) {
  state.canvas = data.slots?.canvas || [0, 0];
  state.slots = data.slots?.slots || [];

  // Pre-populate from a prior save (re-opened page).
  if (data.prior_assignments?.assignments) {
    for (const a of data.prior_assignments.assignments) {
      state.assignments.set(a.slot_id, a.logo);
    }
  }

  els.img.src = data.image_url;
  els.img.addEventListener('load', renderSlotOverlays, { once: true });

  const detected = state.slots.length;
  const requested = data.slots?.requested ?? detected;
  setStatus(
    detected === requested
      ? `${detected} slot${detected === 1 ? '' : 's'} detected — tap a slot to start`
      : `${detected}/${requested} slots detected (model under-produced)`,
  );
  refreshSaveBtn();
}

function renderSlotOverlays() {
  // Remove any stale overlays (init can rerun if we hot-reload during dev).
  for (const old of els.stage.querySelectorAll('.slot')) old.remove();

  const [cw, ch] = state.canvas;
  if (cw <= 0 || ch <= 0) return;

  // Auto-focus the first unfilled slot for one-tap entry.
  if (state.focusedSlot == null) {
    const firstEmpty = state.slots.find(s => !state.assignments.has(s.id));
    state.focusedSlot = firstEmpty ? firstEmpty.id : state.slots[0]?.id ?? null;
  }

  for (const slot of state.slots) {
    const [x, y, w, h] = slot.bbox;
    const node = el('div', {
      cls: 'slot',
      attrs: { 'data-slot-id': String(slot.id) },
      on: { click: () => focusSlot(slot.id) },
    });
    node.style.left = `${(x / cw) * 100}%`;
    node.style.top = `${(y / ch) * 100}%`;
    node.style.width = `${(w / cw) * 100}%`;
    node.style.height = `${(h / ch) * 100}%`;

    node.appendChild(el('span', { cls: 'slot__badge', text: `#${slot.id}` }));

    const assigned = state.assignments.get(slot.id);
    if (assigned) {
      node.classList.add('is-filled');
      node.appendChild(el('img', {
        cls: 'slot__preview',
        attrs: { src: `/static/assets/logos/${encodeURIComponent(assigned)}`, alt: assigned },
      }));
    }
    if (slot.id === state.focusedSlot) node.classList.add('is-focused');
    els.stage.appendChild(node);
  }
}

function focusSlot(id) {
  state.focusedSlot = id;
  renderSlotOverlays();
}

// ── Gallery ─────────────────────────────────────────────────────────────────
function hydrateGallery(entries) {
  state.galleryEntries = entries;
  clear(els.gallery);
  if (entries.length === 0) {
    els.gallery.appendChild(el('p', {
      cls: 'upload-hint',
      text: 'Gallery is empty — add an image to get started.',
    }));
    return;
  }
  for (const e of entries) {
    const tile = el('div', {
      cls: 'logo-tile',
      attrs: { 'data-filename': e.filename, title: e.filename },
      on: { click: () => assignLogo(e.filename) },
    }, [
      el('img', { attrs: { src: e.url, alt: e.filename } }),
    ]);
    els.gallery.appendChild(tile);
  }
}

function assignLogo(filename) {
  if (state.focusedSlot == null) {
    setStatus('Tap a slot first, then tap a logo.');
    return;
  }
  state.assignments.set(state.focusedSlot, filename);
  // Auto-advance to the next empty slot so the user can place a sequence
  // of logos with one tap each. Falls back to staying put if everything
  // is filled (last placement).
  const order = state.slots.map(s => s.id);
  const idx = order.indexOf(state.focusedSlot);
  const next = order.slice(idx + 1).concat(order.slice(0, idx))
    .find(id => !state.assignments.has(id));
  state.focusedSlot = next ?? state.focusedSlot;
  renderSlotOverlays();
  setStatus(`Placed ${filename}${next ? ' — next slot ready' : ' — all slots filled'}`);
  refreshSaveBtn();
}

// ── Upload ──────────────────────────────────────────────────────────────────
els.uploadInput.addEventListener('change', async (e) => {
  const file = e.target.files?.[0];
  if (!file) return;
  setStatus(`Uploading ${file.name}…`);
  const form = new FormData();
  form.append('file', file);
  try {
    const r = await fetch('/api/logos/upload', { method: 'POST', body: form });
    if (!r.ok) {
      const txt = await r.text().catch(() => '');
      throw new Error(`upload failed (${r.status}): ${txt.slice(0, 160)}`);
    }
    const data = await r.json();
    hydrateGallery(data.entries || []);
    setStatus(`Added ${data.saved?.filename || file.name}`);
  } catch (err) {
    setStatus(`error: ${err.message}`);
  } finally {
    // Reset so the same filename can be picked again (mobile camera reuses
    // the same temp name on each shot).
    els.uploadInput.value = '';
  }
});

// ── Clear / Save ────────────────────────────────────────────────────────────
els.clearBtn.addEventListener('click', () => {
  state.assignments.clear();
  state.focusedSlot = state.slots[0]?.id ?? null;
  renderSlotOverlays();
  refreshSaveBtn();
  setStatus('Cleared. Tap a slot to start over.');
});

function refreshSaveBtn() {
  els.saveBtn.disabled = state.assignments.size === 0;
}

els.saveBtn.addEventListener('click', async () => {
  if (state.assignments.size === 0) return;
  const payload = {
    job_id: state.jobId,
    assignments: Array.from(state.assignments.entries()).map(
      ([slot_id, logo_filename]) => ({ slot_id, logo_filename }),
    ),
  };
  setStatus(`Compositing ${payload.assignments.length} logo${payload.assignments.length === 1 ? '' : 's'}…`);
  els.saveBtn.disabled = true;
  try {
    const r = await fetch('/api/infographic-fill/composite', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!r.ok) {
      const txt = await r.text().catch(() => '');
      throw new Error(`composite failed (${r.status}): ${txt.slice(0, 160)}`);
    }
    const data = await r.json();
    // Replace the preview with the filled version (cache-busted).
    els.img.src = `${data.output_url}?t=${Date.now()}`;
    setStatus(`Saved → ${data.output_url}`);
  } catch (err) {
    setStatus(`error: ${err.message}`);
  } finally {
    els.saveBtn.disabled = false;
  }
});

init();
