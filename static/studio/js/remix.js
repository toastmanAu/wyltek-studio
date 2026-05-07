/* Style Remix page controller. */

const state = {
  baseKind: '',
  baseGalleryId: '',
  baseUploadFile: null,
  styleKind: '',
  styleUploadFile: null,
  cryptoLogoId: '',
  jobs: {},
  models: [],
  loras: [],
  cryptoLogos: [],
};

// 3D re-texture context (Path B). When the page is opened from the main
// app's "Style Remix Texture" button, retexture_glb identifies the source
// mesh that the remixed result should be applied to.
const _retextureParams = new URLSearchParams(window.location.search);
const RETEXTURE_GLB = _retextureParams.get('retexture_glb');

// Source-mode state. 'image' = existing flow; 'mesh' = atlas re-texture.
// In mesh mode, state.meshGlbUrl + state.meshAtlasUrl supply the base
// for /api/remix and the result tiles get an "Apply to Mesh" button.
state.sourceMode = 'image';
state.meshGlbUrl = '';
state.meshAtlasUrl = '';
state.meshAtlasBlob = null;  // fetched lazily; sent as multipart base_image
state.atlasNaturalW = 0;
state.atlasNaturalH = 0;
state.meshMaskBlob = null;   // PNG Blob at natural atlas dims (sent as mask_image)
// Hidden full-res canvas used to assemble the mask. The visible canvas
// only renders a scaled overlay; we keep the natural-dim copy here so
// the backend's composite step works against unmodified atlas pixels.
let _maskFullResCanvas = null;

function setSourceMode(mode) {
  state.sourceMode = mode;
  document.querySelectorAll('.mode-btn').forEach(b => {
    b.classList.toggle('active', b.dataset.sourceMode === mode);
  });
  $('mesh-source-block').classList.toggle('active', mode === 'mesh');
  document.querySelector('.ref-row').classList.toggle('mesh-mode', mode === 'mesh');
  document.querySelector('.ref-row').classList.toggle('image-mode', mode === 'image');
}

// ─── Mesh picker modal (mesh source mode) ──────────────────────────────
async function openMeshPicker() {
  const modal = $('mesh-picker-modal');
  const grid = $('mesh-picker-grid');
  // Use textContent + DOM-build only — never innerHTML with user data.
  while (grid.firstChild) grid.removeChild(grid.firstChild);
  const loading = document.createElement('div');
  loading.style.cssText = 'padding:20px;color:var(--text-dim)';
  loading.textContent = 'Loading...';
  grid.appendChild(loading);
  modal.classList.add('active');
  try {
    const items = await fetch('/api/gallery').then(r => r.json());
    // Tighten to URL extension rather than the type field — the gallery
    // strips texture-cache sidecars now, but defending here means a future
    // mis-classification (e.g. a new sidecar living in meshes/) can't sneak
    // a non-GLB path into pickMesh and crash pygltflib downstream.
    const meshes = items.filter(i => /\.(glb|gltf)(\?|$)/i.test(i.url || ''));
    while (grid.firstChild) grid.removeChild(grid.firstChild);
    if (!meshes.length) {
      const empty = document.createElement('div');
      empty.style.cssText = 'padding:20px;color:var(--text-dim)';
      empty.textContent = 'No 3D meshes in gallery yet — generate one first.';
      grid.appendChild(empty);
      return;
    }
    meshes.forEach(m => {
      const tile = document.createElement('div');
      tile.className = 'gallery-item';
      // Optimistic atlas preview — same trick as mesh-edit's picker.
      const previewUrl = (m.url || '').replace(/\.(glb|gltf)$/i, '.texture.png');
      const img = document.createElement('img');
      img.loading = 'lazy';
      img.src = previewUrl;
      img.alt = '';
      img.addEventListener('error', () => {
        img.style.display = 'none';
        const fallback = document.createElement('div');
        fallback.style.cssText = 'display:flex;align-items:center;justify-content:center;height:100%;font-size:24px';
        fallback.textContent = '▢';
        tile.appendChild(fallback);
      });
      tile.appendChild(img);
      tile.addEventListener('click', () => pickMesh(m.url));
      grid.appendChild(tile);
    });
  } catch (err) {
    while (grid.firstChild) grid.removeChild(grid.firstChild);
    const errEl = document.createElement('div');
    errEl.style.cssText = 'padding:20px;color:var(--text-dim)';
    errEl.textContent = `Failed to load gallery: ${err.message}`;
    grid.appendChild(errEl);
  }
}

function closeMeshPicker(event) {
  if (event && event.target.id !== 'mesh-picker-modal') return;
  $('mesh-picker-modal').classList.remove('active');
}

async function pickMesh(glbUrl) {
  state.meshGlbUrl = glbUrl;
  state.meshAtlasBlob = null;
  closeMeshPicker();

  // Show the GLB filename as a label on the thumb (live model-viewer
  // would tank the page if we ever showed multiple — for the picked
  // tile a single instance is fine).
  const thumb = $('mesh-thumb');
  while (thumb.firstChild) thumb.removeChild(thumb.firstChild);
  thumb.classList.add('has-mesh');
  const mv = document.createElement('model-viewer');
  mv.setAttribute('camera-controls', '');
  mv.setAttribute('auto-rotate', '');
  mv.setAttribute('shadow-intensity', '1');
  mv.setAttribute('exposure', '1');
  mv.setAttribute('environment-image', 'neutral');
  mv.src = glbUrl;
  thumb.appendChild(mv);

  // Extract atlas — populates state.meshAtlasUrl + the preview img.
  try {
    const resp = await fetch('/api/3d/extract-texture', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ source_glb: glbUrl }),
    });
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.error || `HTTP ${resp.status}`);
    state.meshAtlasUrl = data.texture_url;
    state.atlasNaturalW = data.width;
    state.atlasNaturalH = data.height;
    state.meshMaskBlob = null;
    $('atlas-canvas-wrap').classList.add('active');
    const preview = $('atlas-preview');
    preview.onload = () => initMaskCanvas(preview);
    preview.src = data.texture_url + '?t=' + Date.now();
    updateAtlasMeta();
  } catch (err) {
    alert('Atlas extract failed: ' + err.message);
  }
}

// ─── SAM-click mask editor (mesh mode only) ───────────────────────────
function updateAtlasMeta() {
  const has = !!state.meshMaskBlob;
  const meta = $('atlas-meta');
  if (!state.atlasNaturalW) { meta.textContent = ''; return; }
  if (has) {
    meta.textContent =
      `${state.atlasNaturalW} × ${state.atlasNaturalH} — masked region only`;
  } else {
    meta.textContent =
      `${state.atlasNaturalW} × ${state.atlasNaturalH} — whole atlas (no mask)`;
  }
  $('clear-mask-btn').disabled = !has;
}

function initMaskCanvas(previewImg) {
  // Size the visible mask canvas to match the displayed image's box.
  const dw = previewImg.clientWidth;
  const dh = previewImg.clientHeight;
  const canvas = $('atlas-mask-canvas');
  canvas.width = dw; canvas.height = dh;
  canvas.style.width = dw + 'px'; canvas.style.height = dh + 'px';
  canvas.getContext('2d').clearRect(0, 0, dw, dh);

  // Hidden full-res canvas — destination for the mask we send to the
  // backend. Sized to the atlas's natural dims so /api/remix's composite
  // step gets a mask that lines up with the base atlas pixel-for-pixel.
  _maskFullResCanvas = document.createElement('canvas');
  _maskFullResCanvas.width = state.atlasNaturalW;
  _maskFullResCanvas.height = state.atlasNaturalH;
  state.meshMaskBlob = null;
  updateAtlasMeta();
}

async function onAtlasClick(e) {
  if (!state.meshAtlasUrl) return;
  const canvas = $('atlas-mask-canvas');
  if (canvas.classList.contains('busy')) return;

  const rect = canvas.getBoundingClientRect();
  const cx = e.clientX - rect.left;
  const cy = e.clientY - rect.top;
  // Display-canvas → atlas-natural coords; SAM operates on natural.
  const x = Math.round(cx * state.atlasNaturalW / rect.width);
  const y = Math.round(cy * state.atlasNaturalH / rect.height);

  // Visual feedback while SAM thinks (first call cold-loads ~5-10s).
  const ctx = canvas.getContext('2d');
  ctx.save();
  ctx.fillStyle = 'rgba(255, 255, 100, 0.7)';
  ctx.beginPath();
  ctx.arc(cx, cy, 8, 0, Math.PI * 2);
  ctx.fill();
  ctx.restore();
  canvas.classList.add('busy');
  $('atlas-meta').textContent = 'SAM segmenting...';

  try {
    const resp = await fetch('/api/image/sam-segment', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        url: state.meshAtlasUrl,
        x, y,
        // Sensitivity: 'auto' uses SAM's confidence, 'small'/'medium'/'large'
        // pick the corresponding multi-mask output by area. Padding dilates
        // (+) or erodes (−) the result by N pixels via PIL morphology.
        mask_size: $('sam-size').value,
        dilate: parseInt($('sam-padding').value, 10) || 0,
      }),
    });
    const data = await resp.json();
    if (!data.mask_b64) throw new Error(data.error || 'no mask returned');

    await applySamMask(data.mask_b64, canvas);
  } catch (err) {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    alert('SAM failed: ' + err.message);
  } finally {
    canvas.classList.remove('busy');
    updateAtlasMeta();
  }
}

function applySamMask(mask_b64, canvas) {
  return new Promise((resolve) => {
    const maskImg = new Image();
    maskImg.onload = () => {
      // Persist the mask at full atlas resolution so the backend
      // composite step can blend against the base atlas precisely.
      const fctx = _maskFullResCanvas.getContext('2d');
      fctx.clearRect(0, 0, _maskFullResCanvas.width, _maskFullResCanvas.height);
      fctx.drawImage(maskImg, 0, 0,
        _maskFullResCanvas.width, _maskFullResCanvas.height);
      _maskFullResCanvas.toBlob((blob) => {
        state.meshMaskBlob = blob;
        resolve();
      }, 'image/png');

      // Visible overlay: tint the mask region red on the display canvas.
      // source-in keeps the red only where the (white) mask pixels land.
      const ctx = canvas.getContext('2d');
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.drawImage(maskImg, 0, 0, canvas.width, canvas.height);
      ctx.globalCompositeOperation = 'source-in';
      ctx.fillStyle = 'rgba(255, 60, 60, 0.55)';
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      ctx.globalCompositeOperation = 'source-over';
    };
    maskImg.src = 'data:image/png;base64,' + mask_b64;
  });
}

function clearMask() {
  const canvas = $('atlas-mask-canvas');
  canvas.getContext('2d').clearRect(0, 0, canvas.width, canvas.height);
  if (_maskFullResCanvas) {
    _maskFullResCanvas.getContext('2d').clearRect(
      0, 0, _maskFullResCanvas.width, _maskFullResCanvas.height);
  }
  state.meshMaskBlob = null;
  updateAtlasMeta();
}

// Lazy fetch the atlas as a Blob so we can send it as the base_image
// multipart upload. Cached per-pick on state.meshAtlasBlob.
async function getAtlasBlob() {
  if (state.meshAtlasBlob) return state.meshAtlasBlob;
  if (!state.meshAtlasUrl) return null;
  const resp = await fetch(state.meshAtlasUrl);
  if (!resp.ok) throw new Error(`atlas fetch failed: ${resp.status}`);
  state.meshAtlasBlob = await resp.blob();
  return state.meshAtlasBlob;
}

const $ = (id) => document.getElementById(id);

// Style Remix is wired against IP-Adapter-Plus-SDXL, so every combo in the
// dropdowns must be SDXL — other archs (Flux, Klein, PixArt, SD3/3.5) either
// have no matching IPAdapter weights here or use an entirely different
// conditioning path. GGUF checkpoints are excluded because the remix workflow
// uses CheckpointLoaderSimple, which can't load them.
async function loadCatalog() {
  try {
    const backends = await fetch('/api/backends').then(r => r.json());
    const comfy = backends.comfyui || {};
    const cats = comfy.model_categories || {};

    const isSdxlSafetensors = (m) =>
      m && m.available !== false
      && m.arch === 'sdxl'
      && /\.(safetensors|ckpt)$/i.test(m.id || '');

    state.models = (comfy.models || []).filter(isSdxlSafetensors);
    const modelSel = $('model');
    while (modelSel.firstChild) modelSel.removeChild(modelSel.firstChild);
    state.models.forEach(m => {
      const opt = document.createElement('option');
      opt.value = m.id;
      opt.textContent = m.label || m.id;
      modelSel.appendChild(opt);
    });
    const preferred = state.models.find(m => /juggernaut/i.test(m.id));
    if (preferred) modelSel.value = preferred.id;

    // LoRAs: SDXL-only (or "other", which the arch classifier treats as
    // wildcard-compatible). model_categories.loras — NOT top-level `loras`.
    state.loras = (cats.loras || []).filter(l =>
      l && l.available !== false && (l.arch === 'sdxl' || l.arch === 'other'));
    const loraSel = $('lora');
    while (loraSel.firstChild) loraSel.removeChild(loraSel.firstChild);
    const none = document.createElement('option');
    none.value = ''; none.textContent = '(none)';
    loraSel.appendChild(none);
    state.loras.forEach(l => {
      const opt = document.createElement('option');
      opt.value = l.id;
      opt.textContent = l.label || l.id;
      loraSel.appendChild(opt);
    });
    const pixelLora = state.loras.find(l => /pixel/i.test(l.id));
    if (pixelLora) loraSel.value = pixelLora.id;
  } catch (e) {
    console.warn('loadCatalog failed', e);
  }
}

async function loadCryptoLogos() {
  try {
    const resp = await fetch('/api/crypto-logos');
    if (!resp.ok) throw new Error('no endpoint');
    state.cryptoLogos = await resp.json();
    $('crypto-status').textContent = `${state.cryptoLogos.length} logos available`;
  } catch (e) {
    state.cryptoLogos = [];
    $('crypto-status').textContent = 'Logo list unavailable';
  }
}

function bindRangeLabel(inputId, labelId, digits = 2) {
  const inp = $(inputId); const lbl = $(labelId);
  const update = () => { lbl.textContent = Number(inp.value).toFixed(digits); };
  inp.addEventListener('input', update);
  update();
}

// Which tile is the action sheet currently configuring? Set when the
// user taps a ref-tile so the sheet's button handlers know whether to
// route the chosen file into base- or style-state.
let activeSheetTile = null;

function onBaseTileClick() {
  activeSheetTile = 'base';
  openSourceSheet({ withGallery: true, title: 'Base character source' });
}

function clearBase(event) {
  event.stopPropagation();
  state.baseKind = '';
  state.baseGalleryId = '';
  state.baseUploadFile = null;
  const tile = $('base-tile');
  tile.classList.remove('has-image');
  tile.innerHTML = '<span class="label">Click to pick from gallery<br>or drop an image</span>'
    + '<button class="clear" onclick="clearBase(event)">&times;</button>';
}

function setBaseImagePreview(src) {
  const tile = $('base-tile');
  tile.classList.add('has-image');
  tile.innerHTML = `<img src="${src}" alt="Base character">`
    + '<button class="clear" onclick="clearBase(event)">&times;</button>';
}

function bindBaseDrop() {
  const tile = $('base-tile');
  tile.addEventListener('dragover', e => { e.preventDefault(); });
  tile.addEventListener('drop', e => {
    e.preventDefault();
    const f = e.dataTransfer.files[0];
    if (!f) return;
    state.baseKind = 'upload';
    state.baseUploadFile = f;
    state.baseGalleryId = '';
    setBaseImagePreview(URL.createObjectURL(f));
  });
}

async function openGalleryModal() {
  const modal = $('gallery-modal');
  const grid = $('gallery-grid');
  grid.innerHTML = '<div style="padding:20px;color:var(--text-dim)">Loading...</div>';
  modal.classList.add('active');
  try {
    const items = await fetch('/api/gallery').then(r => r.json());
    grid.innerHTML = '';
    items.forEach(item => {
      const el = document.createElement('div');
      el.className = 'gallery-item';
      el.innerHTML = `<img src="${item.url}" alt="">`;
      el.onclick = () => pickGalleryImage(item);
      grid.appendChild(el);
    });
  } catch (e) {
    grid.innerHTML = `<div style="padding:20px;color:var(--text-dim)">Failed to load gallery: ${e.message}</div>`;
  }
}

function closeGalleryModal(event) {
  if (event && event.target.id !== 'gallery-modal') return;
  $('gallery-modal').classList.remove('active');
}

function pickGalleryImage(item) {
  state.baseKind = 'gallery';
  state.baseGalleryId = item.filename || item.url.split('/').pop();
  state.baseUploadFile = null;
  setBaseImagePreview(item.url);
  closeGalleryModal();
}

function onStyleTileClick() {
  activeSheetTile = 'style';
  openSourceSheet({ withGallery: false, title: 'Style reference source' });
}

// Apply a chosen File (from upload or camera) as the style image. Mirrors
// the old onStyleTileClick body so the upload-flow result is unchanged.
function applyStyleFile(f) {
  state.styleKind = 'upload';
  state.styleUploadFile = f;
  state.cryptoLogoId = '';
  const tile = $('style-tile');
  tile.classList.add('has-image');
  tile.innerHTML = `<img src="${URL.createObjectURL(f)}" alt="Style">`
    + '<button class="clear" onclick="clearStyle(event)">&times;</button>';
}

// Apply a chosen File as the base image. Same end-state as the gallery-
// pick path (preview shown, baseKind set), but with kind='upload' so the
// /api/remix endpoint receives the file rather than a gallery_id.
function applyBaseFile(f) {
  state.baseKind = 'upload';
  state.baseUploadFile = f;
  state.baseGalleryId = '';
  setBaseImagePreview(URL.createObjectURL(f));
}

// ─── Action sheet ─────────────────────────────────────────────────────
function openSourceSheet({ withGallery, title }) {
  const sheet = $('source-sheet');
  $('source-sheet-title').textContent = title;
  // Hide the gallery option for the style tile — gallery only contains
  // base-style images, not style references.
  $('sheet-gallery-btn').style.display = withGallery ? '' : 'none';
  sheet.classList.add('active');
}

function closeSourceSheet(event) {
  if (event && event.target.id !== 'source-sheet') return;
  $('source-sheet').classList.remove('active');
}

function onSheetPick(action) {
  closeSourceSheet();
  if (action === 'gallery') {
    if (activeSheetTile === 'base') openGalleryModal();
    return;
  }
  // Upload + camera both go through a hidden file input; only difference
  // is the `capture` attribute on the camera input which prompts mobile
  // browsers for the device camera vs. the file picker.
  const input = action === 'camera' ? $('hidden-camera') : $('hidden-upload');
  input.onchange = (e) => {
    const f = e.target.files[0];
    if (!f) return;
    if (activeSheetTile === 'base') applyBaseFile(f);
    else if (activeSheetTile === 'style') applyStyleFile(f);
    // Reset value so picking the same file twice still fires `change`.
    e.target.value = '';
  };
  input.click();
}

function clearStyle(event) {
  event.stopPropagation();
  state.styleKind = '';
  state.styleUploadFile = null;
  state.cryptoLogoId = '';
  const tile = $('style-tile');
  tile.classList.remove('has-image');
  tile.innerHTML = '<span class="label">Upload image</span>'
    + '<button class="clear" onclick="clearStyle(event)">&times;</button>';
}

function onCryptoSearch() {
  const q = $('crypto-search').value.trim().toLowerCase();
  const dd = $('crypto-dropdown');
  const matches = state.cryptoLogos.filter(l => l.slug.includes(q) || l.name.toLowerCase().includes(q)).slice(0, 30);
  if (!matches.length) { dd.style.display = 'none'; return; }
  dd.innerHTML = matches.map(l =>
    `<div class="item" onclick="pickCryptoLogo('${l.slug}','${l.name.replace(/'/g, "\\'")}')">${l.name}</div>`
  ).join('');
  dd.style.display = 'block';
}

function pickCryptoLogo(slug, name) {
  state.styleKind = 'crypto';
  state.cryptoLogoId = slug;
  state.styleUploadFile = null;
  $('crypto-dropdown').style.display = 'none';
  $('crypto-search').value = name;
  const tile = $('style-tile');
  tile.classList.add('has-image');
  tile.innerHTML = `<img src="/storage/crypto-logos/${slug}.png" alt="${name}">`
    + '<button class="clear" onclick="clearStyle(event)">&times;</button>';
}

async function submitRemix() {
  // In mesh mode the atlas takes the place of the base character; we
  // fetch it as a Blob and send it as base_image multipart.
  const isMesh = state.sourceMode === 'mesh';
  if (isMesh && !state.meshAtlasUrl) {
    alert('Pick a 3D mesh first.');
    return;
  }
  if (!isMesh && !state.baseKind) {
    alert('Pick a base character first.');
    return;
  }
  if (!state.styleKind) {
    alert('Pick a style reference (upload or crypto logo).');
    return;
  }

  const form = new FormData();
  if (isMesh) {
    const atlasBlob = await getAtlasBlob();
    if (!atlasBlob) {
      alert('Atlas not ready yet — try again.');
      return;
    }
    // The server saves the upload as the base image and runs IP-Adapter
    // remix on it. Filename is mostly cosmetic but keeps the suffix
    // sensible so the ComfyUI input copy preserves the .png extension.
    form.append('base_image', atlasBlob, 'atlas.png');
    // Region-aware re-texture: when the user marked a region with SAM,
    // ship the mask so the backend composites the result back into the
    // base atlas, leaving unmasked regions byte-stable.
    if (state.meshMaskBlob) {
      form.append('mask_image', state.meshMaskBlob, 'mask.png');
    }
  } else if (state.baseKind === 'upload') {
    form.append('base_image', state.baseUploadFile);
  } else {
    form.append('base_gallery_id', state.baseGalleryId);
  }
  if (state.styleKind === 'upload') {
    form.append('style_ref', state.styleUploadFile);
  } else {
    form.append('crypto_logo_id', state.cryptoLogoId);
  }
  form.append('preserve_character', $('preserve').value);
  form.append('style_strength', $('strength').value);
  form.append('ip_start', $('ip-start').value);
  form.append('ip_end', $('ip-end').value);
  form.append('blend_mode', $('blend-mode').value);
  form.append('model', $('model').value);
  form.append('lora_model', $('lora').value);
  form.append('lora_strength', $('lora-strength').value);
  form.append('batch_size', $('batch').value);
  form.append('steps', $('steps').value);
  form.append('cfg', $('cfg').value);
  form.append('seed', $('seed').value);
  form.append('hint', $('hint').value);

  $('btn-gen').disabled = true;
  $('progress').style.display = 'block';
  $('progress-fill').style.width = '2%';
  $('results').innerHTML = '';
  state.jobs = {};

  let body;
  try {
    const resp = await fetch('/api/remix', { method: 'POST', body: form });
    body = await resp.json();
    if (!resp.ok) {
      throw new Error(body.error || `HTTP ${resp.status}`);
    }
  } catch (e) {
    $('btn-gen').disabled = false;
    $('progress').style.display = 'none';
    alert(`Submit failed: ${e.message}`);
    return;
  }

  body.jobs.forEach(j => {
    const tile = document.createElement('div');
    tile.className = 'result-tile';
    tile.innerHTML = `
      <div class="image-wrap"><span class="placeholder">Queued...</span></div>
      <div class="actions">
        <button disabled>Use as new base</button>
      </div>`;
    $('results').appendChild(tile);
    state.jobs[j.job_id] = tile;
  });
}

// Re-enable Generate once every tile has reached a terminal state (complete
// or error). Previously this read back placeholder text, which raced the
// fetch that replaces the placeholder on completion — the last job often
// left the button ghosted. Use an explicit data-done flag instead.
function maybeEnableGenerate() {
  const tiles = Object.values(state.jobs);
  if (!tiles.length) return;
  const allDone = tiles.every(t => t.dataset.done === '1');
  if (allDone) $('btn-gen').disabled = false;
}

function openWebSocket() {
  const ws = new WebSocket(`ws://${location.host}/ws`);
  ws.onmessage = (ev) => {
    const msg = JSON.parse(ev.data);
    if (msg.type !== 'job_update') return;
    const tile = state.jobs[msg.job_id];
    if (!tile) return;
    const wrap = tile.querySelector('.image-wrap');
    if (msg.status === 'running') {
      const plc = wrap.querySelector('.placeholder');
      if (plc) plc.textContent = `${msg.progress}%`;
      const all = Object.values(state.jobs);
      let sum = 0;
      all.forEach(t => {
        const p = t.querySelector('.placeholder');
        if (p) {
          const m = /([\d.]+)%/.exec(p.textContent);
          if (m) sum += parseFloat(m[1]);
        } else {
          sum += 100;
        }
      });
      const pct = all.length ? (sum / all.length) : 0;
      $('progress-fill').style.width = `${pct}%`;
    } else if (msg.status === 'complete') {
      fetch(`/api/job/${msg.job_id}`).then(r => r.json()).then(jr => {
        const url = jr.output_url || `/storage/${msg.job_id}.png`;
        const filename = url.split('/').pop();
        wrap.innerHTML = `<img src="${url}" alt="Remix result">`;
        const btn = tile.querySelector('.actions button');
        btn.disabled = false;
        btn.textContent = 'Use as new base';
        btn.onclick = () => useAsNewBase(filename, url);
        // 3D re-texture mode: append a second per-tile button so the user
        // can pick whichever remix variant looks best as the new texture.
        // Either the page was opened with ?retexture_glb=… (mesh-edit
        // handoff) or the user picked a mesh in-page via the source
        // toggle — both supply the source GLB URL.
        const targetGlb = getActiveMeshUrl();
        if (targetGlb) {
          const applyBtn = document.createElement('button');
          applyBtn.textContent = 'Apply to Mesh';
          applyBtn.style.marginLeft = '6px';
          applyBtn.onclick = () => applyTileToMesh(applyBtn, url);
          tile.querySelector('.actions').appendChild(applyBtn);
        }
        tile.dataset.done = '1';
        maybeEnableGenerate();
      });
    } else if (msg.status === 'error') {
      wrap.innerHTML = `<span class="placeholder" style="color:tomato">Error</span>`;
      const btn = tile.querySelector('.actions button');
      btn.disabled = true;
      btn.textContent = msg.message || 'Failed';
      btn.title = msg.message || '';
      tile.dataset.done = '1';
      maybeEnableGenerate();
    }
  };
  ws.onclose = () => setTimeout(openWebSocket, 2000);
}

function useAsNewBase(filename, url) {
  state.baseKind = 'gallery';
  state.baseGalleryId = filename;
  state.baseUploadFile = null;
  setBaseImagePreview(url);
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

// Resolve which GLB the Apply-to-Mesh button should target. Two sources:
//   1. ?retexture_glb=… — page opened from mesh-edit's "Style Remix" handoff.
//   2. state.meshGlbUrl — user picked a mesh in-page via the source toggle.
// State takes precedence (in-page pick is more recent than URL param).
function getActiveMeshUrl() {
  return state.meshGlbUrl || RETEXTURE_GLB || null;
}

// Path B re-texture: take a remixed PNG (the URL of any tile's result),
// POST it through /api/3d/apply-texture as a swap for the source mesh's
// baseColor atlas, then land on /studio/mesh-edit?glb=… so the new GLB
// renders immediately in the viewer.
async function applyTileToMesh(btn, url) {
  const targetGlb = getActiveMeshUrl();
  if (!targetGlb) return;
  // Send the full URL (minus origin) — keep query string intact for
  // /api/frame/serve?path=<abs> URLs. Backend strips cache-bust `t=`.
  const editedUrl = url.replace(window.location.origin, '');
  btn.disabled = true;
  btn.textContent = 'Applying...';
  try {
    const resp = await fetch('/api/3d/apply-texture', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        source_glb: targetGlb,
        edited_texture: editedUrl,
      }),
    });
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.error || `HTTP ${resp.status}`);
    // Land on the mesh-edit page so the user sees the new GLB rendered.
    const params = new URLSearchParams({ glb: data.new_glb_url });
    window.location.href = `/studio/mesh-edit?${params.toString()}`;
  } catch (err) {
    btn.disabled = false;
    btn.textContent = 'Apply to Mesh';
    alert('Apply failed: ' + err.message);
  }
}

document.addEventListener('DOMContentLoaded', () => {
  bindRangeLabel('preserve', 'preserve-val');
  bindRangeLabel('strength', 'strength-val');
  bindRangeLabel('ip-start', 'ip-start-val');
  bindRangeLabel('ip-end', 'ip-end-val');
  bindRangeLabel('lora-strength', 'lora-strength-val');
  bindRangeLabel('sam-padding', 'sam-padding-val', 0);
  bindBaseDrop();
  loadCatalog();
  loadCryptoLogos();
  openWebSocket();

  // Mask editor wiring (mesh mode only — handlers no-op in image mode
  // because the canvas is hidden via .mesh-source-block.active).
  $('atlas-mask-canvas').addEventListener('click', onAtlasClick);
  $('clear-mask-btn').addEventListener('click', clearMask);
});
