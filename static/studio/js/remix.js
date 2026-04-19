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

const $ = (id) => document.getElementById(id);

async function loadCatalog() {
  try {
    const backends = await fetch('/api/backends').then(r => r.json());
    const comfy = backends.comfyui || {};
    state.models = (comfy.models || []).filter(m => /\.safetensors$|\.ckpt$/i.test(m));
    const modelSel = $('model');
    state.models.forEach(m => {
      const opt = document.createElement('option');
      opt.value = m; opt.textContent = m;
      modelSel.appendChild(opt);
    });
    const preferred = state.models.find(m => /juggernaut/i.test(m));
    if (preferred) modelSel.value = preferred;

    state.loras = comfy.loras || [];
    const loraSel = $('lora');
    const none = document.createElement('option');
    none.value = ''; none.textContent = '(none)';
    loraSel.appendChild(none);
    state.loras.forEach(l => {
      const opt = document.createElement('option');
      opt.value = l; opt.textContent = l;
      loraSel.appendChild(opt);
    });
    const pixelLora = state.loras.find(l => /pixel/i.test(l));
    if (pixelLora) loraSel.value = pixelLora;
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

function onBaseTileClick() {
  openGalleryModal();
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
  $('hidden-upload').onchange = (e) => {
    const f = e.target.files[0];
    if (!f) return;
    state.styleKind = 'upload';
    state.styleUploadFile = f;
    state.cryptoLogoId = '';
    const tile = $('style-tile');
    tile.classList.add('has-image');
    tile.innerHTML = `<img src="${URL.createObjectURL(f)}" alt="Style">`
      + '<button class="clear" onclick="clearStyle(event)">&times;</button>';
  };
  $('hidden-upload').click();
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
  if (!state.baseKind) {
    alert('Pick a base character first.');
    return;
  }
  if (!state.styleKind) {
    alert('Pick a style reference (upload or crypto logo).');
    return;
  }

  const form = new FormData();
  if (state.baseKind === 'upload') {
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
      });
    } else if (msg.status === 'error') {
      wrap.innerHTML = `<span class="placeholder" style="color:tomato">Error</span>`;
      const btn = tile.querySelector('.actions button');
      btn.disabled = true;
      btn.textContent = msg.message || 'Failed';
      btn.title = msg.message || '';
    }
    const allDone = Object.keys(state.jobs).every(id => {
      const t = state.jobs[id];
      const plc = t.querySelector('.placeholder');
      return !plc || /Error|Failed/.test(plc.textContent);
    });
    if (allDone) {
      $('btn-gen').disabled = false;
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

document.addEventListener('DOMContentLoaded', () => {
  bindRangeLabel('preserve', 'preserve-val');
  bindRangeLabel('strength', 'strength-val');
  bindRangeLabel('ip-start', 'ip-start-val');
  bindRangeLabel('ip-end', 'ip-end-val');
  bindRangeLabel('lora-strength', 'lora-strength-val');
  bindBaseDrop();
  loadCatalog();
  loadCryptoLogos();
  openWebSocket();
});
