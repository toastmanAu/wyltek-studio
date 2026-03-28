/**
 * Open Palette — frontend application
 */

const state = {
  backends: {},
  activeBackend: null,
  refImages: [null, null, null, null],
  currentRefSlot: null,
  currentJobId: null,
  ws: null,
};

// --- Init ---

document.addEventListener('DOMContentLoaded', async () => {
  await loadBackends();
  await loadGallery();
  initWebSocket();
  bindEvents();
});

async function loadBackends() {
  try {
    const resp = await fetch('/api/backends');
    state.backends = await resp.json();
    renderBackendChips();
    // Auto-select first backend
    const names = Object.keys(state.backends);
    if (names.length > 0) selectBackend(names[0]);
  } catch (e) {
    toast('Failed to load backends', 'error');
  }
}

async function loadGallery() {
  try {
    const resp = await fetch('/api/gallery');
    const items = await resp.json();
    renderGallery(items);
  } catch (e) { /* silent */ }
}

function initWebSocket() {
  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
  state.ws = new WebSocket(`${proto}//${location.host}/ws`);
  state.ws.onmessage = (e) => {
    const msg = JSON.parse(e.data);
    if (msg.type === 'job_update') handleJobUpdate(msg);
  };
  state.ws.onclose = () => setTimeout(initWebSocket, 3000);
}

// --- Backend selection ---

function renderBackendChips() {
  const container = document.getElementById('backend-selector');
  container.innerHTML = '';
  for (const [name, info] of Object.entries(state.backends)) {
    const chip = document.createElement('button');
    chip.className = 'backend-chip';
    chip.dataset.backend = name;
    chip.innerHTML = `<span class="dot ${info.type}"></span>${name}`;
    chip.onclick = () => selectBackend(name);
    container.appendChild(chip);
  }
}

function selectBackend(name) {
  state.activeBackend = name;

  // Update chip styling
  document.querySelectorAll('.backend-chip').forEach(c => {
    c.classList.toggle('active', c.dataset.backend === name);
  });

  // Update model dropdown
  const info = state.backends[name];
  const modelSelect = document.getElementById('model-select');
  modelSelect.innerHTML = '';

  const models = info.models || [];
  if (models.length === 0) {
    modelSelect.innerHTML = '<option value="">Default</option>';
  } else {
    models.forEach(m => {
      const opt = document.createElement('option');
      opt.value = typeof m === 'string' ? m : m.id;
      opt.textContent = typeof m === 'string' ? m : m.label;
      modelSelect.appendChild(opt);
    });
  }

  // Update model info
  updateModelInfo();

  // Update IP-Adapter options (ComfyUI only for now)
  const ipSelect = document.getElementById('ip-adapter-select');
  ipSelect.innerHTML = '<option value="">None (text only)</option>';
  if (name === 'comfyui' && info.model_categories?.ip_adapters) {
    info.model_categories.ip_adapters.forEach(m => {
      const opt = document.createElement('option');
      opt.value = m.id;
      opt.textContent = m.label;
      ipSelect.appendChild(opt);
    });
  }

  // Update upscaler options
  const upSelect = document.getElementById('upscaler-select');
  upSelect.innerHTML = '<option value="">None</option>';
  if (name === 'comfyui' && info.model_categories?.upscalers) {
    info.model_categories.upscalers.forEach(m => {
      const opt = document.createElement('option');
      opt.value = m.id;
      opt.textContent = m.label;
      upSelect.appendChild(opt);
    });
  }
}

function updateModelInfo() {
  const info = state.backends[state.activeBackend];
  const modelId = document.getElementById('model-select').value;
  const models = info.models || [];
  const model = models.find(m => (typeof m === 'string' ? m : m.id) === modelId);
  const el = document.getElementById('model-info');
  if (model && typeof model === 'object' && model.vram) {
    el.innerHTML = `<span class="vram">VRAM: ${model.vram}</span>`;
  } else {
    el.innerHTML = '';
  }
}

// --- Reference images ---

function bindEvents() {
  // Ref image slots
  document.querySelectorAll('.ref-slot').forEach(slot => {
    slot.addEventListener('click', (e) => {
      if (e.target.classList.contains('remove-ref')) {
        e.stopPropagation();
        const idx = parseInt(slot.dataset.index);
        removeRefImage(idx);
        return;
      }
      state.currentRefSlot = parseInt(slot.dataset.index);
      document.getElementById('ref-file-input').click();
    });
  });

  document.getElementById('ref-file-input').addEventListener('change', (e) => {
    const file = e.target.files[0];
    if (!file || state.currentRefSlot === null) return;
    setRefImage(state.currentRefSlot, file);
    e.target.value = '';
  });

  // Advanced toggle
  document.getElementById('advanced-toggle').addEventListener('click', () => {
    document.getElementById('advanced-content').classList.toggle('open');
  });

  // Range sliders
  document.getElementById('steps').addEventListener('input', (e) => {
    document.getElementById('steps-val').textContent = e.target.value;
  });
  document.getElementById('cfg-scale').addEventListener('input', (e) => {
    document.getElementById('cfg-val').textContent = parseFloat(e.target.value).toFixed(1);
  });
  document.getElementById('ip-strength').addEventListener('input', (e) => {
    document.getElementById('ip-val').textContent = parseFloat(e.target.value).toFixed(2);
  });

  // Model change
  document.getElementById('model-select').addEventListener('change', updateModelInfo);

  // Generate
  document.getElementById('btn-generate').addEventListener('click', generate);

  // Keyboard shortcut
  document.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') generate();
  });

  // Result actions
  document.getElementById('btn-save').addEventListener('click', saveImage);
  document.getElementById('btn-copy-url').addEventListener('click', copyImageUrl);
  document.getElementById('btn-use-as-ref').addEventListener('click', useAsRef);
}

function setRefImage(index, file) {
  state.refImages[index] = file;
  const slot = document.querySelector(`.ref-slot[data-index="${index}"]`);
  slot.classList.add('has-image');
  // Show preview
  const reader = new FileReader();
  reader.onload = (e) => {
    let img = slot.querySelector('img');
    if (!img) {
      img = document.createElement('img');
      slot.insertBefore(img, slot.firstChild);
    }
    img.src = e.target.result;
  };
  reader.readAsDataURL(file);
  slot.querySelector('.plus').style.display = 'none';
}

function removeRefImage(index) {
  state.refImages[index] = null;
  const slot = document.querySelector(`.ref-slot[data-index="${index}"]`);
  slot.classList.remove('has-image');
  const img = slot.querySelector('img');
  if (img) img.remove();
  slot.querySelector('.plus').style.display = '';
}

// --- Generate ---

async function generate() {
  const prompt = document.getElementById('prompt').value.trim();
  if (!prompt) {
    toast('Please enter a prompt', 'error');
    return;
  }

  const btn = document.getElementById('btn-generate');
  btn.disabled = true;
  btn.textContent = 'Generating...';

  const formData = new FormData();
  formData.append('prompt', prompt);
  formData.append('negative_prompt', document.getElementById('negative-prompt').value);
  formData.append('backend', state.activeBackend);
  formData.append('model', document.getElementById('model-select').value);
  formData.append('width', document.getElementById('width').value);
  formData.append('height', document.getElementById('height').value);
  formData.append('steps', document.getElementById('steps').value);
  formData.append('cfg_scale', document.getElementById('cfg-scale').value);
  formData.append('seed', document.getElementById('seed').value);
  formData.append('ip_adapter_model', document.getElementById('ip-adapter-select').value);
  formData.append('ip_adapter_strength', document.getElementById('ip-strength').value);
  formData.append('upscaler', document.getElementById('upscaler-select').value);

  // Attach reference images
  state.refImages.forEach((file) => {
    if (file) formData.append('reference_images', file);
  });

  try {
    const resp = await fetch('/api/generate', { method: 'POST', body: formData });
    const data = await resp.json();
    if (data.error) throw new Error(data.error);

    state.currentJobId = data.job_id;
    showProgress(0, 'Queued...');
  } catch (e) {
    toast(`Generation failed: ${e.message}`, 'error');
    btn.disabled = false;
    btn.textContent = 'Generate';
  }
}

// --- Progress & results ---

function handleJobUpdate(msg) {
  if (msg.job_id !== state.currentJobId) return;

  if (msg.status === 'running') {
    showProgress(msg.progress, msg.message || 'Generating...');
  } else if (msg.status === 'complete') {
    hideProgress();
    showResult(msg.output_url);
    loadGallery();
    const btn = document.getElementById('btn-generate');
    btn.disabled = false;
    btn.textContent = 'Generate';
    toast('Image generated!', 'success');
  } else if (msg.status === 'error') {
    hideProgress();
    toast(`Error: ${msg.error}`, 'error');
    const btn = document.getElementById('btn-generate');
    btn.disabled = false;
    btn.textContent = 'Generate';
  }
}

function showProgress(pct, message) {
  const container = document.getElementById('progress');
  container.classList.add('active');
  document.getElementById('progress-fill').style.width = pct + '%';
  document.getElementById('progress-pct').textContent = pct + '%';
  document.getElementById('progress-status').textContent = message;
}

function hideProgress() {
  document.getElementById('progress').classList.remove('active');
}

function showResult(url) {
  document.getElementById('placeholder').style.display = 'none';
  const container = document.getElementById('result-container');
  container.classList.add('visible');
  const img = document.getElementById('result-image');
  img.src = url + '?t=' + Date.now();  // bust cache
  img.dataset.url = url;
}

// --- Gallery ---

function renderGallery(items) {
  const strip = document.getElementById('gallery-strip');
  strip.innerHTML = '';
  items.forEach(item => {
    const thumb = document.createElement('div');
    thumb.className = 'gallery-thumb';
    thumb.innerHTML = `<img src="${item.url}" alt="">`;
    thumb.onclick = () => showResult(item.url);
    strip.appendChild(thumb);
  });
}

// --- Result actions ---

function saveImage() {
  const img = document.getElementById('result-image');
  if (!img.src) return;
  const a = document.createElement('a');
  a.href = img.dataset.url;
  a.download = `open-palette-${Date.now()}.png`;
  a.click();
}

function copyImageUrl() {
  const img = document.getElementById('result-image');
  if (!img.dataset.url) return;
  const fullUrl = location.origin + img.dataset.url;
  navigator.clipboard.writeText(fullUrl).then(() => {
    toast('URL copied to clipboard', 'success');
  });
}

function useAsRef() {
  const img = document.getElementById('result-image');
  if (!img.src) return;

  // Find first empty ref slot
  const idx = state.refImages.findIndex(r => r === null);
  if (idx === -1) {
    toast('All reference slots full — remove one first', 'error');
    return;
  }

  // Fetch image as blob and set as ref
  fetch(img.dataset.url)
    .then(r => r.blob())
    .then(blob => {
      const file = new File([blob], 'reference.png', { type: 'image/png' });
      setRefImage(idx, file);
      toast(`Added to reference slot ${idx + 1}`, 'success');
    });
}

// --- Toast ---

function toast(message, type = 'info') {
  const container = document.getElementById('toasts');
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  el.textContent = message;
  container.appendChild(el);
  setTimeout(() => el.remove(), 4000);
}
