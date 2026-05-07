/**
 * Wyltek Studio — frontend application
 */

const state = {
  backends: {},
  activeBackend: null,
  refImages: [null, null, null, null],
  currentRefSlot: null,
  currentJobId: null,
  ws: null,
  pollTimer: null,
  compareJobs: [],  // [{job_id, backend, model, status}]
  comparePollTimer: null,
  gpuTotalGb: 0,    // populated from /api/gpu-stats on load; 0 = unknown
  // Output mode: '2d' (image gen via CheckpointLoaderSimple) or
  // '3d' (Hy3D / TRELLIS image-to-mesh). Default 2D preserves every existing
  // flow; toggling repopulates the model dropdown from info.models_3d and
  // tells /api/generate to take the 3D path. The 3D engine (hy3d | trellis)
  // is *derived* from the selected model's `engine` tag rather than a
  // separate UI control — keeps the picker simple.
  outputMode: '2d',
  pipeline3d: 'shape',     // 'shape' | 'pbr' (Hy3D) | 'textured' (TRELLIS)
  engine3d: 'hy3d',        // 'hy3d' | 'trellis' — derived from model selection
  trellisFormat: 'GGUF Q4_K_M',
  trellisPipelineType: '512',
};

// Show / clear the prompt-trigger hint under the LoRA selector.
// Style LoRAs need a trigger word in the prompt or they barely fire even at strength 1.
function _updateLoraTriggerHint() {
  const loraSelect = document.getElementById('lora-select');
  if (!loraSelect) return;
  let hint = document.getElementById('lora-trigger-hint');
  if (!hint) {
    hint = document.createElement('div');
    hint.id = 'lora-trigger-hint';
    hint.style.cssText = 'font-size:11px;color:var(--text-dim);margin-top:4px;font-style:italic;';
    loraSelect.parentElement.appendChild(hint);
  }
  const opt = loraSelect.options[loraSelect.selectedIndex];
  const trigger = opt && opt.dataset ? opt.dataset.trigger : '';
  hint.textContent = trigger ? `Tip: include "${trigger}" in your prompt for this LoRA to fire.` : '';
}

// LoRA compatibility — SDXL architecture only (not Flux, SD3, or SD 1.5)
function _isLoraCompatible(modelId) {
  if (!modelId) return false;
  const id = modelId.toLowerCase();
  // Explicitly NOT compatible
  if (id.includes('flux') || id.includes('sd3') || id.includes('v1-5') || id.includes('sd_1') || id.includes('1.5')) return false;
  // Compatible: anything SDXL-based
  if (id.includes('sdxl') || id.includes('xl') || id.includes('juggernaut') || id.includes('realvis') || id.includes('dreamshaper') || id.includes('lightning')) return true;
  // Cloud models — no LoRA
  if (!id.endsWith('.safetensors') && !id.endsWith('.gguf')) return false;
  return false;
}

// Per-model optimal defaults — trained resolutions + recommended settings
const MODEL_DEFAULTS = {
  // SD 1.5 — trained on 512x512
  'v1-5-pruned-emaonly.safetensors': {
    width: 512, height: 512, steps: 20, cfg: 7.0,
    tips: 'SD 1.5 works best at 512x512. Higher resolutions produce artifacts. Use 20-30 steps. Good for stylised art, illustrations, and quick drafts.',
  },
  // SDXL GGUF variants — trained on 1024x1024
  'sdxl_base_1.0-Q4_0.gguf': {
    width: 1024, height: 1024, steps: 25, cfg: 7.0,
    tips: 'SDXL works best at 1024x1024. Use 20-30 steps. Good all-rounder for both photo and art styles.',
  },
  'juggernautXL_juggXIByRundiffusion-Q4_0.gguf': {
    width: 1024, height: 1024, steps: 30, cfg: 6.0,
    tips: 'Juggernaut XL excels at photorealism. Use 1024x1024, 25-35 steps, CFG 5-7. Add "photorealistic, detailed" to prompts. Avoid "cartoon" or "anime" unless intended.',
  },
  'RealVisXL_V4.0-Q4_0.gguf': {
    width: 1024, height: 1024, steps: 28, cfg: 5.5,
    tips: 'RealVisXL is tuned for realistic portraits and scenes. Use 1024x1024, 25-35 steps, CFG 4.5-6.5. Lower CFG = more natural. Great for people, architecture, nature.',
  },
  // SDXL base safetensor — trained on 1024x1024
  'sd_xl_base_1.0.safetensors': {
    width: 1024, height: 1024, steps: 25, cfg: 7.0,
    tips: 'SDXL base model. Best at 1024x1024, 20-30 steps, CFG 6-8. Good all-rounder for both photo and art styles. Foundation model that all XL finetunes build on.',
  },
  // Juggernaut XL v9 — photorealistic SDXL finetune
  'juggernautXL_v9.safetensors': {
    width: 1024, height: 1024, steps: 30, cfg: 6.0,
    tips: 'Juggernaut XL v9 — top-tier photorealism. Use 1024x1024, 25-35 steps, CFG 5-7. Add "photorealistic, detailed, 8k" to prompts. Excels at people, landscapes, products.',
  },
  // RealVisXL V4 — realistic portraits and scenes
  'realvisxl-v4.safetensors': {
    width: 1024, height: 1024, steps: 28, cfg: 5.5,
    tips: 'RealVisXL V4 — tuned for realistic portraits and scenes. Use 1024x1024, 25-35 steps, CFG 4.5-6.5. Lower CFG = more natural. Great for people, architecture, nature.',
  },
  // DreamShaper XL Turbo — fast versatile generation
  'dreamshaper-xl-v21.safetensors': {
    width: 1024, height: 1024, steps: 8, cfg: 2.0,
    tips: 'DreamShaper XL Turbo — optimised for speed. Only needs 6-10 steps at CFG 1.5-2.5. Great for rapid iteration. Versatile style — handles illustration, photo, fantasy.',
  },
  // Flux.1 Dev GGUF — best open-source model, various quantizations
  'flux1-dev-Q4_0.gguf': {
    width: 1024, height: 1024, steps: 20, cfg: 3.5,
    tips: 'Flux.1 Dev Q4 — state-of-the-art quality in ~6GB VRAM. Use 20-30 steps, CFG 3-4. Excellent prompt following, photorealism, and text rendering. Euler sampler, simple scheduler.',
  },
  'flux1-dev-Q5_K_S.gguf': {
    width: 1024, height: 1024, steps: 20, cfg: 3.5,
    tips: 'Flux.1 Dev Q5 — higher fidelity quantization (~7GB). Same settings as Q4 but slightly sharper details. May be tight on 8GB VRAM.',
  },
  'flux1-dev-Q8_0.gguf': {
    width: 1024, height: 1024, steps: 20, cfg: 3.5,
    tips: 'Flux.1 Dev Q8 — near-lossless (~12GB). Will use CPU offloading on 8GB GPU — slower but maximum quality. Best for hero images where you can wait.',
  },
  // Flux.1 Schnell — ultra-fast 4-step generation
  'flux1-schnell-Q4_0.gguf': {
    width: 1024, height: 1024, steps: 4, cfg: 1.0,
    tips: 'Flux.1 Schnell — distilled for speed. Only 4 steps needed! CFG is ignored (set to 1). Great for rapid iteration and drafts. Same quality architecture as Dev but much faster.',
  },
  // SD3 Medium — Stability AI's transformer architecture
  'sd3-medium-Q4_0.gguf': {
    width: 1024, height: 1024, steps: 28, cfg: 7.0,
    tips: 'Stable Diffusion 3 Medium Q4 — transformer-based, good prompt adherence. Use 25-30 steps, CFG 5-8. Different aesthetic from SDXL. ~5GB VRAM.',
  },
  // RealVisXL V5 — upgraded realistic model
  'RealVisXL_V5.0-Q4_0.gguf': {
    width: 1024, height: 1024, steps: 28, cfg: 5.5,
    tips: 'RealVisXL V5 — upgraded version with better architecture, interiors, and skin tones. Use 25-35 steps, CFG 4.5-6.5.',
  },
  // ZavyChromaXL — vibrant fantasy and sci-fi
  'zavychromaxl_v100-Q4_0.gguf': {
    width: 1024, height: 1024, steps: 30, cfg: 7.0,
    tips: 'ZavyChromaXL — punchy, saturated colors. Excels at fantasy, sci-fi, concept art, and anything that benefits from vivid palettes. CFG 6-8.',
  },
  // SDXL Lightning — ByteDance distilled model
  'sdxl-lightning-4step.safetensors': {
    width: 1024, height: 1024, steps: 4, cfg: 1.0,
    tips: 'SDXL Lightning — distilled to 4 steps. CFG ~1. Extremely fast with decent quality. Uses SDXL architecture so compatible with SDXL LoRAs.',
  },
  // Gemini models — resolution flexible
  'gemini-2.5-flash-image': {
    width: 1024, height: 1024, steps: 30, cfg: 7.0,
    tips: 'Nano Banana handles any resolution up to 1024x1024. Steps/CFG are ignored (cloud model). Strong at photorealism and following complex prompts. Costs ~$0.04/image.',
  },
  'gemini-3-pro-image-preview': {
    width: 1024, height: 1024, steps: 30, cfg: 7.0,
    tips: 'Nano Banana Pro — highest quality Google model. ~$0.13/image. Best for final/hero images where quality matters most.',
  },
  'gemini-3.1-flash-image-preview': {
    width: 1024, height: 1024, steps: 30, cfg: 7.0,
    tips: 'Nano Banana 2 — latest Gemini image model. Good balance of quality and cost.',
  },
  'imagen-4.0-fast-generate-001': {
    width: 1024, height: 1024, steps: 30, cfg: 7.0,
    tips: 'Imagen 4 Fast — cheapest Google option at ~$0.02/image. Good for iteration and drafts.',
  },
  'imagen-4.0-generate-001': {
    width: 1024, height: 1024, steps: 30, cfg: 7.0,
    tips: 'Imagen 4 Standard — high quality at ~$0.04/image. Good default for cloud generation.',
  },
  // Pollinations
  'flux': {
    width: 1024, height: 1024, steps: 30, cfg: 7.0,
    tips: 'Flux via Pollinations. Requires API token from enter.pollinations.ai.',
  },
  // HuggingFace
  'stabilityai/stable-diffusion-xl-base-1.0': {
    width: 1024, height: 1024, steps: 30, cfg: 7.0,
    tips: 'SDXL via HuggingFace Inference API. Uses monthly free credits.',
  },
};

// --- Init ---

document.addEventListener('DOMContentLoaded', async () => {
  await loadBackends();
  await loadGallery();
  initWebSocket();
  bindEvents();
  // GPU stats — drives the VRAM ceiling badge in 3D mode. Fire-and-forget;
  // badge stays hidden if ComfyUI isn't reachable or the call fails.
  _loadGpuStats();
  // Check if OP prompt optimizer is available
  fetch('/api/op-prompt/status')
    .then(r => r.json())
    .then(data => {
      state.opStatus = data;
      const btn = document.getElementById('btn-op-prompt');
      btn.disabled = !data.available;
      if (!data.available) {
        btn.classList.add('unavailable');
        btn.title = data.reason || 'Prompt optimizer not available';
      } else {
        btn.classList.remove('unavailable');
        btn.title = 'Enhance prompt with local AI';
      }
    })
    .catch(() => {
      state.opStatus = { available: false, reason: 'Could not reach server' };
      const btn = document.getElementById('btn-op-prompt');
      btn.disabled = true;
      btn.classList.add('unavailable');
    });

  // Populate OP-model dropdown. Server config holds the global default; the
  // dropdown lets you override per-session without touching settings.
  // Precedence for initial selection: localStorage → server default.
  fetch('/api/op-prompt/config')
    .then(r => r.json())
    .then(cfg => {
      const sel = document.getElementById('op-model-select');
      if (!sel) return;
      const installed = cfg.installed_models || [];
      const serverDefault = cfg.model || '';
      const remembered = localStorage.getItem('opModel');
      const initial = (remembered && installed.includes(remembered))
        ? remembered
        : serverDefault;

      sel.replaceChildren();
      installed.forEach(m => {
        const opt = document.createElement('option');
        opt.value = m;
        opt.textContent = (m === serverDefault) ? `${m} (default)` : m;
        if (m === initial) opt.selected = true;
        sel.appendChild(opt);
      });
      // Accent the border when the user's choice differs from server default.
      const markOverride = () => {
        sel.classList.toggle('override', sel.value !== serverDefault);
      };
      markOverride();
      sel.addEventListener('change', () => {
        localStorage.setItem('opModel', sel.value);
        markOverride();
      });
      state.opModel = initial;
    })
    .catch(() => { /* dropdown stays empty; OP button will just use server default */ });

  // Check for images sent from Projects page
  const refData = sessionStorage.getItem('ws-ref-images');
  if (refData) {
    sessionStorage.removeItem('ws-ref-images');
    try {
      const refs = JSON.parse(refData);
      refs.forEach(async (ref, i) => {
        if (i >= 4) return;
        const resp = await fetch(ref.url);
        const blob = await resp.blob();
        const file = new File([blob], ref.filename, { type: blob.type });
        setRefImage(i, file);
      });
      toast(`Loaded ${Math.min(refs.length, 4)} reference image(s) from project`, 'success');
    } catch (e) {}
  }
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
  try {
    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    state.ws = new WebSocket(`${proto}//${location.host}/ws`);
    state.ws.onmessage = (e) => {
      const msg = JSON.parse(e.data);
      if (msg.type === 'job_update') handleJobUpdate(msg);
    };
    state.ws.onclose = () => setTimeout(initWebSocket, 3000);
    state.ws.onerror = () => {
      console.log('WebSocket unavailable, using polling fallback');
      state.ws = null;
    };
  } catch (e) {
    state.ws = null;
  }
}

function startPolling(jobId) {
  if (state.pollTimer) clearInterval(state.pollTimer);
  let notFoundCount = 0;
  state.pollTimer = setInterval(async () => {
    try {
      const resp = await fetch(`/api/job/${jobId}`);
      if (resp.status === 404) {
        notFoundCount++;
        if (notFoundCount > 5) {
          clearInterval(state.pollTimer);
          state.pollTimer = null;
          handleJobUpdate({ job_id: jobId, type: 'job_update', status: 'error', error: 'Job lost (server may have restarted)' });
        }
        return;
      }
      const data = await resp.json();
      handleJobUpdate({ ...data, job_id: jobId, type: 'job_update' });
      if (data.status === 'complete' || data.status === 'error') {
        clearInterval(state.pollTimer);
        state.pollTimer = null;
      }
    } catch (e) { /* retry next interval */ }
  }, 1000);
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

  // Update model dropdown.
  // In 3D mode, the dropdown is populated from `info.models_3d` (Hy3D DiTs
  // discovered in ComfyUI/models/diffusion_models). 2D mode uses `info.models`
  // (CheckpointLoaderSimple targets). Keeping the lists separate is the
  // whole point of the discovery split — picking a 3D model from the 2D
  // dropdown was the original "Value not in list" bug.
  const info = state.backends[name];
  const modelSelect = document.getElementById('model-select');
  modelSelect.innerHTML = '';

  const models = (state.outputMode === '3d' ? (info.models_3d || []) : (info.models || []));
  if (models.length === 0) {
    const placeholderOpt = document.createElement('option');
    placeholderOpt.value = '';
    placeholderOpt.textContent = state.outputMode === '3d'
      ? 'No 3D models found — check /models/diffusion_models'
      : 'Default';
    modelSelect.appendChild(placeholderOpt);
  } else {
    // Sort: available first, then unavailable
    const sorted = [...models].sort((a, b) => {
      const aAvail = typeof a === 'string' || a.available !== false;
      const bAvail = typeof b === 'string' || b.available !== false;
      if (aAvail && !bAvail) return -1;
      if (!aAvail && bAvail) return 1;
      return 0;
    });
    sorted.forEach(m => {
      const opt = document.createElement('option');
      const id = typeof m === 'string' ? m : m.id;
      const label = typeof m === 'string' ? m : m.label;
      const available = typeof m === 'string' || m.available !== false;
      const discovered = typeof m === 'object' && m.discovered;
      const loraOk = _isLoraCompatible(id);
      opt.value = id;
      const suffix = !available ? '  [not installed]' : discovered ? '  [auto-detected]' : '';
      opt.textContent = (loraOk ? '\u2605 ' : '') + label + suffix;
      opt.disabled = !available;
      if (!available) opt.style.color = '#555';
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
      const available = m.available !== false;
      opt.value = m.id;
      opt.textContent = available ? m.label : `${m.label}  [not installed]`;
      opt.disabled = !available;
      if (!available) opt.style.color = '#555';
      ipSelect.appendChild(opt);
    });
  }

  // Update LoRA options (ComfyUI only — SDXL compatible)
  const loraSelect = document.getElementById('lora-select');
  while (loraSelect.firstChild) loraSelect.removeChild(loraSelect.firstChild);
  const noneOpt = document.createElement('option');
  noneOpt.value = '';
  noneOpt.textContent = 'None';
  loraSelect.appendChild(noneOpt);
  if (name === 'comfyui' && info.model_categories?.loras) {
    info.model_categories.loras.forEach(m => {
      const opt = document.createElement('option');
      const available = m.available !== false;
      opt.value = m.id;
      opt.textContent = available ? m.label : `${m.label}  [not installed]`;
      opt.disabled = !available;
      if (!available) opt.style.color = '#555';
      // Trigger word: needed in prompt for the LoRA to fire visibly.
      if (m.trigger) opt.dataset.trigger = m.trigger;
      loraSelect.appendChild(opt);
    });
  }
  _updateLoraTriggerHint();

  // Update upscaler options
  const upSelect = document.getElementById('upscaler-select');
  upSelect.innerHTML = '<option value="">None</option>';
  if (name === 'comfyui' && info.model_categories?.upscalers) {
    info.model_categories.upscalers.forEach(m => {
      const opt = document.createElement('option');
      const available = m.available !== false;
      opt.value = m.id;
      opt.textContent = available ? m.label : `${m.label}  [not installed]`;
      opt.disabled = !available;
      if (!available) opt.style.color = '#555';
      upSelect.appendChild(opt);
    });
  }
}

// Derive the 3D engine from the currently selected model and adjust the
// pipeline-picker labels + show/hide TRELLIS-specific options. Called from
// updateModelInfo() so it runs on every model change, and from the 2D/3D
// mode toggle so it runs when the dropdown source list flips.
// Coarse VRAM cost model for TRELLIS combos. Numbers are based on observed
// peak usage on a 7900 XTX (24 GB) — accurate within ±2 GB across formats
// and voxel resolutions. Goal isn't to predict exactly, just to flag combos
// likely to OOM so the user picks something achievable.
const TRELLIS_FORMAT_VRAM_GB = {
  'GGUF Q4_K_M': 4,
  'GGUF Q5_K_M': 5,
  'GGUF Q6_K': 6,
  'GGUF Q8_0': 7,
  'Safetensors (FP8)': 6.5,
  'Safetensors (BF16)': 12,
};
const TRELLIS_VOXEL_MULT = {
  '512': 1.0,
  '1024': 1.3,
  '1024_cascade': 1.6,
  '1536_cascade': 2.2,
};
function estimateTrellisVram() {
  const fmt = document.getElementById('trellis-format')?.value || 'GGUF Q4_K_M';
  const vox = document.getElementById('trellis-pipeline-type')?.value || '512';
  const base = TRELLIS_FORMAT_VRAM_GB[fmt] || 4;
  const mult = TRELLIS_VOXEL_MULT[vox] || 1.0;
  let est = base * mult;
  // Multi-view encoding adds the extra image-encoder cost per additional view.
  const viewCount = state.refImages.filter(r => r).length;
  if (viewCount >= 2) est += 1.0 * (viewCount - 1);
  // Textured pipeline loads the paint diffusion model on top of shape weights.
  if (state.pipeline3d === 'textured' || state.pipeline3d === 'pbr') est += 3.0;
  // Activation / scratch overhead — empirically ~2 GB across all combos.
  est += 2.0;
  return est;
}
// FP8 + cascade is structurally incompatible on ROCm: the cascade sampler hits
// raw addmm_cuda which has no Float8_e4m3fn kernel in the ROCm PyTorch build.
// When the user picks an incompatible combo, auto-shift the OTHER field — which
// one to nudge depends on which one the user just changed (preserve their last
// choice). Surfaces a subtle inline note so it's clear what happened.
const TRELLIS_CASCADE_PIPELINES = ['1024_cascade', '1536_cascade'];
function enforceTrellisCompatGuard(changed) {
  const fmtEl = document.getElementById('trellis-format');
  const pipeEl = document.getElementById('trellis-pipeline-type');
  const noteEl = document.getElementById('trellis-compat-note');
  if (!fmtEl || !pipeEl) return;
  const isFp8 = fmtEl.value === 'Safetensors (FP8)';
  // Broadened — FP8 has no ROCm addmm kernel anywhere we've tested. Silently
  // shift to BF16 whenever the user picks FP8, and surface a note so they
  // know what happened. Server has the same guard for stale pages / direct API.
  if (isFp8) {
    fmtEl.value = 'Safetensors (BF16)';
    if (noteEl) {
      noteEl.textContent = 'FP8 has no ROCm matmul kernel — switched to BF16. Use GGUF Q8_0 for similar size with full ROCm support.';
      noteEl.style.display = '';
      clearTimeout(enforceTrellisCompatGuard._t);
      enforceTrellisCompatGuard._t = setTimeout(() => { noteEl.style.display = 'none'; }, 8000);
    }
  } else if (noteEl) {
    noteEl.style.display = 'none';
  }
}

function refreshVramBadge() {
  const badge = document.getElementById('vram-badge');
  if (!badge) return;
  // Only meaningful in 3D + TRELLIS mode (Hy3D has its own cost profile we
  // don't model, and 2D image gen never touches the ceiling on these cards).
  if (state.outputMode !== '3d' || state.engine3d !== 'trellis' || !state.gpuTotalGb) {
    badge.style.display = 'none';
    return;
  }
  const est = estimateTrellisVram();
  const total = state.gpuTotalGb;
  const pct = Math.min(100, (est / total) * 100);
  document.getElementById('vram-value').textContent = `${est.toFixed(1)} / ${total} GB`;
  document.getElementById('vram-bar-fill').style.width = pct + '%';
  badge.classList.toggle('tight', pct >= 70 && pct < 90);
  badge.classList.toggle('over',  pct >= 90);
  badge.style.display = '';
}

async function _loadGpuStats() {
  try {
    const res = await fetch('/api/gpu-stats');
    const d = await res.json();
    if (d.available) {
      state.gpuTotalGb = d.vram_total_gb;
      refreshVramBadge();
    }
  } catch (e) { /* surface nothing — badge just stays hidden */ }
}

function _refreshEngine3d() {
  if (state.outputMode !== '3d') return;
  const info = state.backends[state.activeBackend] || {};
  const modelId = document.getElementById('model-select').value;
  const m3 = (info.models_3d || []).find(m => m.id === modelId);
  const engine = (m3 && m3.engine) || 'hy3d';
  state.engine3d = engine;

  // Pipeline pill labels diverge by engine. Hy3D's "PBR" calls into the paint
  // diffusion model; TRELLIS's "textured" runs MeshTexturing_GGUF — the same
  // user intent ("with color") routes to different node graphs.
  const pills = document.querySelectorAll('.mode-pill[data-pipeline]');
  const slotLabels = document.querySelectorAll('.ref-slot-label');
  const multiviewHint = document.getElementById('multiview-hint');
  if (engine === 'trellis') {
    pills.forEach(p => {
      if (p.dataset.pipeline === 'shape') p.textContent = 'Shape only';
      if (p.dataset.pipeline === 'pbr' || p.dataset.pipeline === 'textured') {
        p.dataset.pipeline = 'textured';
        p.textContent = 'Textured';
        p.title = '~3-5min. Full-color textured mesh via MeshTexturing_GGUF.';
      }
    });
    // Sync state if the previous value isn't valid for trellis.
    if (state.pipeline3d === 'pbr') state.pipeline3d = 'textured';
    document.getElementById('trellis-options').style.display = '';
    const hy3dAdvT = document.getElementById('hy3d-advanced');
    if (hy3dAdvT) hy3dAdvT.style.display = 'none';
    if (multiviewHint) multiviewHint.style.display = '';
    // TRELLIS multi-view treats the 4 slots positionally: front/back/left/right.
    // Slot 0 (front) is required; the others constrain side/back geometry.
    const labels = ['Front', 'Back', 'Left', 'Right'];
    slotLabels.forEach((el, i) => { el.textContent = labels[i] || ''; });
  } else {
    pills.forEach(p => {
      if (p.dataset.pipeline === 'shape') p.textContent = 'Shape only';
      if (p.dataset.pipeline === 'pbr' || p.dataset.pipeline === 'textured') {
        p.dataset.pipeline = 'pbr';
        p.textContent = 'Full PBR';
        p.title = '~3-5min. Full-color baked PBR textures (auto-downloads ~12GB on first run).';
      }
    });
    if (state.pipeline3d === 'textured') state.pipeline3d = 'pbr';
    document.getElementById('trellis-options').style.display = 'none';
    const hy3dAdv = document.getElementById('hy3d-advanced');
    if (hy3dAdv) hy3dAdv.style.display = '';
    // Hy3D now supports multi-view in both shape AND pbr modes (shape via
    // Hy3DGenerateMeshMultiView, pbr via shape-multiview + paint pipeline).
    // Keep slot labels visible in both.
    if (multiviewHint) multiviewHint.style.display = '';
    const labels = ['Front', 'Back', 'Left', 'Right'];
    slotLabels.forEach((el, i) => { el.textContent = labels[i] || ''; });
  }
  refreshVramBadge();
}

function updateModelInfo() {
  const info = state.backends[state.activeBackend];
  const modelId = document.getElementById('model-select').value;
  const models = info.models || [];
  const model = models.find(m => (typeof m === 'string' ? m : m.id) === modelId);
  const el = document.getElementById('model-info');
  // Engine derivation for 3D mode runs first so subsequent UI hooks see fresh state.
  _refreshEngine3d();

  const parts = [];
  if (model && typeof model === 'object' && model.vram) {
    parts.push(`<span class="vram">VRAM: ${model.vram}</span>`);
  }

  // Show tips from defaults
  const defaults = MODEL_DEFAULTS[modelId];
  if (defaults && defaults.tips) {
    parts.push(`<span class="model-tip">${defaults.tips}</span>`);
  }
  el.innerHTML = parts.join('');

  // Auto-apply optimal settings
  if (defaults) {
    document.getElementById('width').value = defaults.width;
    document.getElementById('height').value = defaults.height;
    document.getElementById('steps').value = defaults.steps;
    document.getElementById('steps-val').textContent = defaults.steps;
    document.getElementById('cfg-scale').value = defaults.cfg;
    document.getElementById('cfg-val').textContent = defaults.cfg.toFixed(1);
  }

  // LoRA compatibility — disable selector + silently clear for non-SDXL models
  const loraSelect = document.getElementById('lora-select');
  const loraStrength = document.getElementById('lora-strength');
  const loraOk = _isLoraCompatible(modelId);
  if (loraSelect) {
    loraSelect.disabled = !loraOk;
    if (!loraOk) {
      loraSelect.value = '';
      loraSelect.style.opacity = '0.4';
    } else {
      loraSelect.style.opacity = '1';
    }
  }
  if (loraStrength) loraStrength.disabled = !loraOk;
  const loraClipStrength = document.getElementById('lora-clip-strength');
  if (loraClipStrength) loraClipStrength.disabled = !loraOk;
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
    const content = document.getElementById('advanced-content');
    content.classList.toggle('open');
    document.getElementById('advanced-toggle').classList.toggle('open');
  });

  // 2D/3D mode toggle. Top-level pills swap the output type; sub-pills
  // pick the 3D pipeline. Both repaint the model dropdown (3D models live
  // in info.models_3d, 2D models in info.models — kept separate to avoid
  // routing a Hy3D file through CheckpointLoaderSimple).

  // 2D-only controls: hidden in 3D mode, restored in 2D. Centralised so
  // every entry below is one place where "this is a 2D-only thing" is
  // declared. Each is the wrapping element/button that should disappear
  // wholesale, never a partial control.
  const TWO_D_ONLY_IDS = [
    'size-row',          // width × height inputs (3D engines pick their own res)
    'steps-group',       // sampling steps (3D pipelines use preset/internal schedules)
    'cfg-group',         // CFG scale (TRELLIS preset-driven; Hy3D fixed at 5.5)
    'seed-group',        // seed (3D pipelines use their own seed flow)
    'lora-section',      // LoRA style + model strength + CLIP strength
    'ipadapter-section', // IP-Adapter model + strength
    'upscaler-group',    // upscaler (post-processes 2D images, not GLBs)
    'btn-op-prompt',     // prompt enhancer (3D engines ignore prompt)
    'btn-compare',       // Compare modal is image-side-by-side, not GLB
    'btn-copy-url',      // less actionable for a .glb than a PNG
    'btn-use-as-ref',    // a mesh isn't usable as a 2D reference image
  ];
  const TWO_D_ONLY_SELECTORS = ['.batch-row']; // batch input lives next to btn-batch
  function applyOutputModeVisibility(mode) {
    const is3d = mode === '3d';
    document.getElementById('mode-3d-options').style.display = is3d ? '' : 'none';
    document.getElementById('model-section-title').textContent =
      is3d ? '3D Model (Hy3D DiT)' : 'Model';
    document.getElementById('prompt-section').style.display = is3d ? 'none' : '';
    TWO_D_ONLY_IDS.forEach(id => {
      const el = document.getElementById(id);
      if (el) el.style.display = is3d ? 'none' : '';
    });
    TWO_D_ONLY_SELECTORS.forEach(sel => {
      document.querySelectorAll(sel).forEach(el => {
        el.style.display = is3d ? 'none' : '';
      });
    });
  }

  document.querySelectorAll('.mode-pill[data-mode]').forEach(pill => {
    pill.addEventListener('click', () => {
      const mode = pill.dataset.mode;
      if (state.outputMode === mode) return;
      state.outputMode = mode;
      document.querySelectorAll('.mode-pill[data-mode]').forEach(p => {
        const isActive = p.dataset.mode === mode;
        p.classList.toggle('active', isActive);
        p.setAttribute('aria-checked', String(isActive));
      });
      applyOutputModeVisibility(mode);
      // Repaint the model dropdown from the right list.
      if (state.activeBackend) selectBackend(state.activeBackend);
    });
  });
  document.querySelectorAll('.mode-pill[data-pipeline]').forEach(pill => {
    pill.addEventListener('click', () => {
      const p = pill.dataset.pipeline;
      state.pipeline3d = p;
      document.querySelectorAll('.mode-pill[data-pipeline]').forEach(o => {
        const isActive = o.dataset.pipeline === p;
        o.classList.toggle('active', isActive);
        o.setAttribute('aria-checked', String(isActive));
      });
      refreshVramBadge();
    });
  });
  // Format + voxel-resolution selectors directly drive the VRAM estimate.
  document.getElementById('trellis-format')?.addEventListener('change', () => {
    enforceTrellisCompatGuard('format');
    refreshVramBadge();
  });
  document.getElementById('trellis-pipeline-type')?.addEventListener('change', () => {
    enforceTrellisCompatGuard('pipeline');
    refreshVramBadge();
  });

  // Mobile sidebar expand/collapse (click the ::after pseudo-element area)
  document.querySelector('.sidebar').addEventListener('click', (e) => {
    if (window.innerWidth > 768) return;
    const sidebar = e.currentTarget;
    const rect = sidebar.getBoundingClientRect();
    // Only toggle if click is in the bottom 40px (the ::after area)
    if (e.clientY > rect.bottom - 40 && e.clientY <= rect.bottom) {
      sidebar.classList.toggle('expanded');
    }
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

  document.getElementById('lora-strength').addEventListener('input', (e) => {
    document.getElementById('lora-val').textContent = parseFloat(e.target.value).toFixed(2);
  });
  document.getElementById('lora-clip-strength').addEventListener('input', (e) => {
    document.getElementById('lora-clip-val').textContent = parseFloat(e.target.value).toFixed(2);
  });
  document.getElementById('lora-select').addEventListener('change', _updateLoraTriggerHint);

  // Model change
  document.getElementById('model-select').addEventListener('change', updateModelInfo);

  // Generate
  document.getElementById('btn-generate').addEventListener('click', generate);

  // OP my prompt
  document.getElementById('btn-op-prompt').addEventListener('click', opMyPrompt);
  document.getElementById('prompt').addEventListener('input', (e) => {
    const opBtn = document.getElementById('btn-op-prompt');
    if (opBtn.style.display !== 'none') opBtn.disabled = !e.target.value.trim();
  });

  // Keyboard shortcut
  document.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') generate();
  });

  // Result actions
  document.getElementById('btn-save').addEventListener('click', saveImage);
  document.getElementById('btn-copy-url').addEventListener('click', copyImageUrl);
  document.getElementById('btn-use-as-ref').addEventListener('click', useAsRef);
  document.getElementById('btn-send-project').addEventListener('click', sendImageToProject);

  // Batch
  document.getElementById('btn-batch').addEventListener('click', startBatch);

  // Compare
  document.getElementById('btn-compare').addEventListener('click', openCompareModal);
  document.getElementById('compare-modal-close').addEventListener('click', closeCompareModal);
  document.getElementById('compare-cancel').addEventListener('click', closeCompareModal);
  document.getElementById('compare-start').addEventListener('click', startComparison);

  // Compare modal filter buttons
  document.querySelectorAll('.btn-filter').forEach(btn => {
    btn.addEventListener('click', () => {
      const filter = btn.dataset.filter;
      document.querySelectorAll('.compare-option').forEach(opt => {
        const cb = opt.querySelector('input');
        const type = opt.dataset.type;
        if (filter === 'all') {
          cb.checked = true;
        } else if (filter === 'none') {
          cb.checked = false;
        } else {
          cb.checked = (type === filter);
        }
        opt.classList.toggle('selected', cb.checked);
      });
    });
  });

  // Tips
  document.getElementById('btn-tips').addEventListener('click', () => {
    document.getElementById('tips-modal').classList.add('active');
  });
  document.getElementById('tips-modal-close').addEventListener('click', () => {
    document.getElementById('tips-modal').classList.remove('active');
  });
}

function setRefImage(index, file) {
  // Downscale client-side: 1024px max edge, JPEG 85% — reduces upload size + VRAM
  _downscaleImage(file, 1024, 0.85).then(scaled => {
    state.refImages[index] = scaled;
    refreshVramBadge();  // multi-view adds ~1 GB per extra view
    const slot = document.querySelector(`.ref-slot[data-index="${index}"]`);
    slot.classList.add('has-image');
    const url = URL.createObjectURL(scaled);
    let img = slot.querySelector('img');
    if (!img) {
      img = document.createElement('img');
      slot.insertBefore(img, slot.firstChild);
    }
    img.src = url;
    slot.querySelector('.plus').style.display = 'none';
  });
}

function _downscaleImage(file, maxEdge, quality) {
  return new Promise((resolve) => {
    // Skip if already small enough
    if (file.size < 500_000) { resolve(file); return; }
    const img = new Image();
    img.onload = () => {
      const { width, height } = img;
      if (width <= maxEdge && height <= maxEdge) { resolve(file); return; }
      const scale = maxEdge / Math.max(width, height);
      const canvas = document.createElement('canvas');
      canvas.width = Math.round(width * scale);
      canvas.height = Math.round(height * scale);
      canvas.getContext('2d').drawImage(img, 0, 0, canvas.width, canvas.height);
      canvas.toBlob(blob => {
        resolve(new File([blob], file.name.replace(/\.[^.]+$/, '.jpg'), { type: 'image/jpeg' }));
      }, 'image/jpeg', quality);
    };
    img.src = URL.createObjectURL(file);
  });
}

function removeRefImage(index) {
  state.refImages[index] = null;
  refreshVramBadge();
  const slot = document.querySelector(`.ref-slot[data-index="${index}"]`);
  slot.classList.remove('has-image');
  const img = slot.querySelector('img');
  if (img) img.remove();
  slot.querySelector('.plus').style.display = '';
}

// --- Generate ---

async function generate() {
  const prompt = document.getElementById('prompt').value.trim();
  const is3d = state.outputMode === '3d';

  // 3D is image-conditioned (Hy3D ignores the prompt entirely), so we
  // require a reference image instead. 2D still requires a prompt.
  if (is3d) {
    const hasRef = state.refImages.some(r => r);
    if (!hasRef) {
      toast('3D mode requires a reference image — upload one to convert to 3D', 'error');
      return;
    }
  } else if (!prompt) {
    toast('Please enter a prompt', 'error');
    return;
  }

  const btn = document.getElementById('btn-generate');
  btn.disabled = true;
  btn.textContent = is3d ? 'Generating 3D...' : 'Generating...';

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
  const selectedModel = document.getElementById('model-select').value;
  const loraModel = _isLoraCompatible(selectedModel) ? document.getElementById('lora-select').value : '';
  formData.append('lora_model', loraModel);
  formData.append('lora_strength', document.getElementById('lora-strength').value);
  formData.append('lora_strength_model', document.getElementById('lora-strength').value);
  formData.append('lora_strength_clip', document.getElementById('lora-clip-strength').value);

  // Output-mode fields: server defaults mode='2d' so omitting them is safe,
  // but we send explicitly to keep the contract clear. Pipeline only matters
  // in 3D mode but it's harmless to always send it.
  formData.append('mode', state.outputMode);
  formData.append('mode_3d', state.pipeline3d);
  if (is3d) {
    // Engine routes the request to generate_3d (Hy3D) or generate_trellis
    // server-side. Format + voxel-grid are TRELLIS-only knobs that the server
    // ignores when engine='hy3d', so we always send them.
    formData.append('engine', state.engine3d);
    // Hy3D-only knobs (paint variant + camera overrides). Server safely
    // ignores when engine='trellis'. Empty camera strings mean "use defaults".
    if (state.engine3d === 'hy3d') {
      const paintEl = document.getElementById('hy3d-paint-model');
      if (paintEl) formData.append('paint_model', paintEl.value);
      const azEl = document.getElementById('hy3d-cam-azimuths');
      const elEl = document.getElementById('hy3d-cam-elevations');
      if (azEl && azEl.value.trim()) formData.append('hy3d_cam_azimuths', azEl.value.trim());
      if (elEl && elEl.value.trim()) formData.append('hy3d_cam_elevations', elEl.value.trim());
    }
    formData.append('trellis_format', document.getElementById('trellis-format').value);
    formData.append('trellis_pipeline_type', document.getElementById('trellis-pipeline-type').value);
    // Quality preset + tweak modifiers — server resolves to per-stage hyperparams.
    formData.append('trellis_preset', document.getElementById('trellis-preset')?.value || 'balanced');
    formData.append('trellis_tweak_faithful', document.getElementById('trellis-tweak-faithful')?.checked ? '1' : '0');
    formData.append('trellis_tweak_fine_detail', document.getElementById('trellis-tweak-fine-detail')?.checked ? '1' : '0');
    formData.append('trellis_tweak_sharp_edges', document.getElementById('trellis-tweak-sharp-edges')?.checked ? '1' : '0');
    // Auto-bg removal — currently consulted only by the TRELLIS path
    // (Hy3D doesn't include a rembg node in our wrapper).
    formData.append('auto_bg_removal', document.getElementById('auto-bg-removal').checked ? '1' : '0');
  }

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
    // Always start polling as fallback (works even if WS is up)
    startPolling(data.job_id);
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
    if (msg.scores) {
      renderScores(msg.scores, document.getElementById('result-container'));
    }
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

// Defaults are object-orbit (TRELLIS / Hy3D) — restored when a non-worldgen
// mesh is shown after a worldgen one. Stash on the element so we don't drift.
const _MESH_VIEWER_DEFAULTS = {
  'auto-rotate': '',
  'shadow-intensity': '1',
  'exposure': '1',
  'field-of-view': '',
  'min-field-of-view': '',
  'max-field-of-view': '',
  'camera-target': '',
  'camera-orbit': '',
  'min-camera-orbit': '',
  'max-camera-orbit': '',
  'interaction-prompt': '',
};
const _MESH_VIEWER_WORLDGEN = {
  // Worldgen scenes are 360° depth-extruded panoramas — first-person, not orbit.
  'auto-rotate': null,             // remove (would be dizzy)
  'shadow-intensity': '0',         // texture has lighting baked in
  'exposure': '1',
  'field-of-view': '75deg',
  'min-field-of-view': '20deg',
  'max-field-of-view': '110deg',
  'camera-target': 'auto auto auto',
  'camera-orbit': '0deg 80deg 0.1m',
  'min-camera-orbit': 'auto auto 0m',
  'max-camera-orbit': 'auto auto auto',
  'interaction-prompt': 'none',
};

function applyMeshViewerMode(mv, mode) {
  const conf = mode === 'worldgen' ? _MESH_VIEWER_WORLDGEN : _MESH_VIEWER_DEFAULTS;
  Object.entries(conf).forEach(([attr, value]) => {
    if (value === null) {
      mv.removeAttribute(attr);
    } else if (value === '') {
      // Empty string for boolean attrs means "present, no value" (e.g. auto-rotate).
      mv.setAttribute(attr, '');
    } else {
      mv.setAttribute(attr, value);
    }
  });
}

async function detectMeshEngine(url) {
  // Sidecar lives next to the GLB with a .json suffix. Fail gracefully —
  // legacy meshes without sidecars just get the default object-orbit mode.
  const sidecarUrl = url.replace(/\.(glb|gltf)(\?|$)/i, '.json$2');
  try {
    const r = await fetch(sidecarUrl);
    if (!r.ok) return null;
    const meta = await r.json();
    return meta.engine || null;
  } catch {
    return null;
  }
}

function showResult(url) {
  document.getElementById('placeholder').style.display = 'none';
  const container = document.getElementById('result-container');
  container.classList.add('visible');
  const img = document.getElementById('result-image');
  const mv = document.getElementById('result-mesh');
  // Route to <model-viewer> when the asset is a 3D file; otherwise use <img>.
  // Cache-bust both with a timestamp so re-runs of the same job_id repaint.
  const is3d = /\.(glb|gltf)(\?|$)/i.test(url);
  const bust = url + (url.includes('?') ? '&' : '?') + 't=' + Date.now();
  if (is3d) {
    img.style.display = 'none';
    mv.style.display = '';
    // Apply object-orbit defaults synchronously so the viewer never flashes
    // with the wrong camera; then upgrade to worldgen mode if the sidecar
    // says so. Avoids a 200-300 ms wait on every 3D show.
    applyMeshViewerMode(mv, 'object');
    mv.src = bust;
    mv.dataset.url = url;
    img.removeAttribute('src');
    detectMeshEngine(url).then((engine) => {
      // Only switch if THIS url is still the active one — guards against
      // race when the user clicks another thumb mid-fetch.
      if (mv.dataset.url === url && engine === 'worldgen') {
        applyMeshViewerMode(mv, 'worldgen');
      }
    });
  } else {
    mv.style.display = 'none';
    mv.removeAttribute('src');
    img.style.display = '';
    img.src = bust;
    img.dataset.url = url;
  }
}

// --- Gallery ---

function renderGallery(items) {
  const strip = document.getElementById('gallery-strip');
  strip.innerHTML = '';
  items.forEach(item => {
    const thumb = document.createElement('div');
    thumb.className = 'gallery-thumb';
    const isMesh = (item.type === 'mesh') || /\.(glb|gltf)(\?|$)/i.test(item.url);
    if (isMesh) {
      // 3D placeholder — rendering live model-viewer instances per thumb
      // would tank the strip; SVG cube icon instead. Click → result panel
      // already routes .glb URLs through <model-viewer> via showResult().
      const tile = document.createElement('div');
      tile.className = 'mesh-thumb';
      tile.title = item.filename || '3D mesh';
      // Inline SVG so styling can match the theme. Rotated cube + "3D" label
      // makes the affordance unmistakable at thumbnail size.
      const svgNS = 'http://www.w3.org/2000/svg';
      const svg = document.createElementNS(svgNS, 'svg');
      svg.setAttribute('viewBox', '0 0 24 24');
      svg.setAttribute('width', '22');
      svg.setAttribute('height', '22');
      svg.setAttribute('fill', 'none');
      svg.setAttribute('stroke', 'currentColor');
      svg.setAttribute('stroke-width', '1.6');
      svg.setAttribute('stroke-linejoin', 'round');
      const path = document.createElementNS(svgNS, 'path');
      path.setAttribute('d', 'M12 2 L21 7 V17 L12 22 L3 17 V7 Z M12 2 L12 12 M12 12 L21 7 M12 12 L3 7');
      svg.appendChild(path);
      const label = document.createElement('span');
      label.textContent = '3D';
      tile.appendChild(svg);
      tile.appendChild(label);
      thumb.appendChild(tile);
      thumb.classList.add('is-mesh');
    } else {
      const img = document.createElement('img');
      img.src = item.url;
      img.alt = '';
      thumb.appendChild(img);
    }
    thumb.onclick = () => showResult(item.url);
    strip.appendChild(thumb);
  });
}

// --- Result actions ---

function saveImage() {
  // Pick whichever element is currently showing — img for 2D, model-viewer for 3D.
  // Keep extension faithful to the source so .glb downloads stay openable in
  // Blender / model viewers and don't get misinterpreted as PNG.
  const mv = document.getElementById('result-mesh');
  const img = document.getElementById('result-image');
  const showingMesh = mv && mv.style.display !== 'none' && mv.dataset.url;
  const url = showingMesh ? mv.dataset.url : img.dataset.url;
  if (!url) return;
  const ext = (url.match(/\.[a-z0-9]+(?:\?|$)/i) || ['.png'])[0].replace(/\?.*$/, '');
  const a = document.createElement('a');
  a.href = url;
  a.download = `wyltek-${Date.now()}${ext}`;
  a.click();
}

function copyImageUrl() {
  const mv = document.getElementById('result-mesh');
  const img = document.getElementById('result-image');
  const showingMesh = mv && mv.style.display !== 'none' && mv.dataset.url;
  const url = showingMesh ? mv.dataset.url : img.dataset.url;
  if (!url) return;
  const fullUrl = location.origin + url;
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

// --- Send to Project ---

function sendImageToProject() {
  const img = document.getElementById('result-image');
  if (!img.dataset.url) return;
  const filename = img.dataset.url.split('/').pop();
  ProjectPicker.init(toast);
  ProjectPicker.show(filename);
}

// --- Scores display ---

function renderScores(scores, container) {
  if (!scores) return;
  // Remove any existing scores panel in this container
  const existing = container.querySelector('.scores-panel');
  if (existing) existing.remove();

  const metrics = ['sharpness', 'saturation', 'brightness', 'color_diversity',
                   'contrast', 'noise', 'edge_density', 'dynamic_range'];
  const labels = {
    sharpness: 'Sharpness', saturation: 'Saturation', brightness: 'Brightness',
    color_diversity: 'Colors', contrast: 'Contrast', noise: 'Noise',
    edge_density: 'Edge Detail', dynamic_range: 'Dyn Range',
  };

  const panel = document.createElement('div');
  panel.className = 'scores-panel';
  const toggle = document.createElement('button');
  toggle.className = 'scores-toggle';
  toggle.textContent = 'Scores';
  const detail = document.createElement('div');
  detail.className = 'scores-detail';
  detail.style.display = 'none';

  metrics.forEach(m => {
    if (scores[m] == null) return;
    const row = document.createElement('div');
    row.className = 'score-row';
    const val = typeof scores[m] === 'number' ? scores[m].toFixed(2) : scores[m];
    row.innerHTML = `<span class="score-label">${labels[m] || m}</span><span class="score-value">${val}</span>`;
    detail.appendChild(row);
  });

  toggle.onclick = () => {
    detail.style.display = detail.style.display === 'none' ? 'block' : 'none';
  };
  panel.appendChild(toggle);
  panel.appendChild(detail);
  container.appendChild(panel);
}

// --- OP my prompt ---

async function opMyPrompt() {
  const promptEl = document.getElementById('prompt');
  const prompt = promptEl.value.trim();
  if (!prompt) return;

  // Check availability and show helpful setup guidance
  if (state.opStatus && !state.opStatus.available) {
    const reason = state.opStatus.reason || '';
    if (reason.includes('not reachable')) {
      toast('Ollama is not running. Install from ollama.com and run: ollama serve', 'error');
    } else if (reason.includes('not found')) {
      toast(`Model "${state.opStatus.model}" not installed. Run: ollama pull ${state.opStatus.model}`, 'error');
    } else if (reason.includes('disabled')) {
      toast('Prompt optimizer is disabled. Enable it in Settings > Prompt Optimizer', 'error');
    } else {
      toast('Prompt optimizer not available. Check Settings for setup instructions.', 'error');
    }
    return;
  }

  const btn = document.getElementById('btn-op-prompt');
  const originalText = btn.textContent;
  btn.disabled = true;
  btn.textContent = 'Enhancing...';

  try {
    const model = document.getElementById('model-select').value;
    const opSel = document.getElementById('op-model-select');
    const ollama_model = opSel && opSel.value ? opSel.value : undefined;
    const resp = await fetch('/api/op-prompt', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ prompt, model, ollama_model }),
    });
    const data = await resp.json();
    if (data.error) throw new Error(data.error);

    promptEl.value = data.enhanced_prompt;
    if (data.negative_prompt) {
      document.getElementById('negative-prompt').value = data.negative_prompt;
    }
    toast(`Prompt enhanced: ${data.changes_made || 'improved'}`, 'success');
  } catch (e) {
    if (e.message.includes('timed out')) {
      toast('Ollama is loading the model (first run is slow). Try again in 10 seconds.', 'error');
    } else {
      toast(`OP failed: ${e.message}`, 'error');
    }
  } finally {
    btn.disabled = !promptEl.value.trim();
    btn.textContent = originalText;
  }
}

// --- Batch mode (N images, same model, different seeds) ---

async function startBatch() {
  const prompt = document.getElementById('prompt').value.trim();
  if (!prompt) { toast('Enter a prompt first', 'error'); return; }

  const count = parseInt(document.getElementById('batch-count').value) || 4;
  const backend = state.activeBackend;
  const model = document.getElementById('model-select').value;

  // Build N options with same backend/model (compare API handles it)
  const options = [];
  for (let i = 0; i < count; i++) {
    options.push({ backend, model });
  }

  // Reuse compare grid UI
  document.getElementById('placeholder').style.display = 'none';
  document.getElementById('result-container').classList.remove('visible');
  const grid = document.getElementById('compare-grid');
  grid.classList.add('active');
  grid.innerHTML = '';

  options.forEach((opt, i) => {
    const card = document.createElement('div');
    card.className = 'compare-card';
    card.id = `batch-card-${i}`;
    const typeClass = (state.backends[opt.backend] || {}).type || 'local';
    card.innerHTML = `
      <div class="compare-card-header">
        <span><span class="dot ${typeClass}"></span><span class="backend-name">#${i + 1}</span></span>
        <span class="model-name">${model || 'default'}</span>
      </div>
      <div class="compare-card-body">
        <div class="compare-loading">
          <div class="compare-progress">
            <span class="progress-status">Queued...</span>
            <div class="progress-bar"><div class="progress-fill" style="width:0%"></div></div>
          </div>
        </div>
      </div>
      <div class="compare-card-footer" style="display:none">
        <button class="btn btn-save-compare">Save</button>
        <button class="btn btn-ref-compare">Use as Ref</button>
      </div>
    `;
    grid.appendChild(card);
  });

  // Submit as compare request (server handles parallel dispatch)
  const formData = new FormData();
  formData.append('prompt', prompt);
  formData.append('negative_prompt', document.getElementById('negative-prompt').value);
  formData.append('backends_json', JSON.stringify(options));
  formData.append('width', document.getElementById('width').value);
  formData.append('height', document.getElementById('height').value);
  formData.append('steps', document.getElementById('steps').value);
  formData.append('cfg_scale', document.getElementById('cfg-scale').value);
  formData.append('seed', '-1'); // Always random for batch — each gets unique seed
  // LoRA — same logic as single-generate path (architecture-gated by selected model)
  const _loraModel = _isLoraCompatible(model) ? document.getElementById('lora-select').value : '';
  formData.append('lora_model', _loraModel);
  formData.append('lora_strength', document.getElementById('lora-strength').value);
  formData.append('lora_strength_model', document.getElementById('lora-strength').value);
  formData.append('lora_strength_clip', document.getElementById('lora-clip-strength').value);
  state.refImages.forEach(file => { if (file) formData.append('reference_images', file); });

  try {
    const resp = await fetch('/api/compare', { method: 'POST', body: formData });
    const data = await resp.json();
    state.compareJobs = data.jobs.map((j, i) => ({
      ...j, status: 'queued', cardId: `batch-card-${i}`,
    }));
    startComparePoll();
    toast(`Generating ${count} variations...`, 'success');
  } catch (e) {
    toast(`Batch failed: ${e.message}`, 'error');
  }
}

// --- Compare mode ---

function openCompareModal() {
  const prompt = document.getElementById('prompt').value.trim();
  if (!prompt) {
    toast('Enter a prompt first', 'error');
    return;
  }

  const container = document.getElementById('compare-options');
  container.innerHTML = '';

  // Build list of all available backend+model combos
  for (const [name, info] of Object.entries(state.backends)) {
    if (!info.enabled) continue;
    const models = info.models || [];
    const availableModels = models.filter(m => typeof m === 'string' || m.available !== false);

    if (availableModels.length === 0) {
      // Backend with no specific models (e.g. pollinations default)
      container.appendChild(makeCompareOption(name, '', name, info.type));
    } else {
      availableModels.forEach(m => {
        const id = typeof m === 'string' ? m : m.id;
        const label = typeof m === 'string' ? m : m.label;
        container.appendChild(makeCompareOption(name, id, `${name} / ${label}`, info.type));
      });
    }
  }

  document.getElementById('compare-modal').classList.add('active');
}

function makeCompareOption(backend, model, label, type) {
  const div = document.createElement('div');
  div.className = 'compare-option';
  div.dataset.backend = backend;
  div.dataset.model = model;
  div.dataset.type = type;
  div.innerHTML = `
    <input type="checkbox">
    <span class="opt-label">${label}</span>
    <span class="opt-type ${type}">${type}</span>
  `;
  div.addEventListener('click', (e) => {
    if (e.target.type !== 'checkbox') {
      const cb = div.querySelector('input');
      cb.checked = !cb.checked;
    }
    div.classList.toggle('selected', div.querySelector('input').checked);
  });
  return div;
}

function closeCompareModal() {
  document.getElementById('compare-modal').classList.remove('active');
}

async function startComparison() {
  const prompt = document.getElementById('prompt').value.trim();
  if (!prompt) return;

  // Gather selected options
  const options = [];
  document.querySelectorAll('.compare-option').forEach(opt => {
    if (opt.querySelector('input').checked) {
      options.push({ backend: opt.dataset.backend, model: opt.dataset.model });
    }
  });

  if (options.length < 2) {
    toast('Select at least 2 backends to compare', 'error');
    return;
  }

  closeCompareModal();

  // Hide single result, show compare grid
  document.getElementById('placeholder').style.display = 'none';
  document.getElementById('result-container').classList.remove('visible');
  const grid = document.getElementById('compare-grid');
  grid.classList.add('active');
  grid.innerHTML = '';

  // Create cards
  options.forEach(opt => {
    const card = document.createElement('div');
    card.className = 'compare-card';
    card.id = `compare-card-${opt.backend}-${opt.model}`.replace(/[^a-z0-9-]/gi, '_');
    const typeClass = (state.backends[opt.backend] || {}).type || 'local';
    card.innerHTML = `
      <div class="compare-card-header">
        <span><span class="dot ${typeClass}"></span><span class="backend-name">${opt.backend}</span></span>
        <span class="model-name">${opt.model || 'default'}</span>
      </div>
      <div class="compare-card-body">
        <div class="compare-loading">
          <div class="compare-progress">
            <span class="progress-status">Queued...</span>
            <div class="progress-bar"><div class="progress-fill" style="width:0%"></div></div>
          </div>
        </div>
      </div>
      <div class="compare-card-footer" style="display:none">
        <button class="btn btn-save-compare">Save</button>
        <button class="btn btn-ref-compare">Use as Ref</button>
      </div>
    `;
    grid.appendChild(card);
  });

  // Submit compare request
  const formData = new FormData();
  formData.append('prompt', prompt);
  formData.append('negative_prompt', document.getElementById('negative-prompt').value);
  formData.append('backends_json', JSON.stringify(options));
  formData.append('width', document.getElementById('width').value);
  formData.append('height', document.getElementById('height').value);
  formData.append('steps', document.getElementById('steps').value);
  formData.append('cfg_scale', document.getElementById('cfg-scale').value);
  formData.append('seed', document.getElementById('seed').value);
  // LoRA — applied per-job in backend; only meaningful for SDXL-arch options.
  // For mixed-architecture compares, backend will inject for all and ComfyUI will
  // error visibly on incompatible combos rather than silently skipping.
  formData.append('lora_model', document.getElementById('lora-select').value);
  formData.append('lora_strength', document.getElementById('lora-strength').value);
  formData.append('lora_strength_model', document.getElementById('lora-strength').value);
  formData.append('lora_strength_clip', document.getElementById('lora-clip-strength').value);
  state.refImages.forEach(file => { if (file) formData.append('reference_images', file); });

  try {
    const resp = await fetch('/api/compare', { method: 'POST', body: formData });
    const data = await resp.json();
    state.compareJobs = data.jobs.map((j, i) => ({
      ...j, status: 'queued', cardId: `compare-card-${options[i].backend}-${options[i].model}`.replace(/[^a-z0-9-]/gi, '_'),
    }));
    startComparePoll();
    toast(`Comparing ${options.length} backends...`, 'success');
  } catch (e) {
    toast(`Compare failed: ${e.message}`, 'error');
  }
}

function startComparePoll() {
  if (state.comparePollTimer) clearInterval(state.comparePollTimer);
  state.comparePollTimer = setInterval(async () => {
    let allDone = true;
    for (const job of state.compareJobs) {
      if (job.status === 'complete' || job.status === 'error') continue;
      allDone = false;
      try {
        const resp = await fetch(`/api/job/${job.job_id}`);
        const data = await resp.json();
        job.status = data.status;
        job.progress = data.progress || 0;
        updateCompareCard(job, data);
      } catch (e) { /* retry */ }
    }
    if (allDone) {
      clearInterval(state.comparePollTimer);
      state.comparePollTimer = null;
      loadGallery();
    }
  }, 1000);
}

function updateCompareCard(job, data) {
  const card = document.getElementById(job.cardId);
  if (!card) return;
  const body = card.querySelector('.compare-card-body');
  const footer = card.querySelector('.compare-card-footer');

  if (data.status === 'running') {
    body.innerHTML = `
      <div class="compare-loading">
        <div class="compare-progress">
          <span class="progress-status">${data.message || 'Generating...'} ${data.progress || 0}%</span>
          <div class="progress-bar"><div class="progress-fill" style="width:${data.progress || 0}%"></div></div>
        </div>
      </div>`;
  } else if (data.status === 'complete') {
    body.innerHTML = `<img src="${data.output_url}?t=${Date.now()}" alt="Result">`;
    if (data.scores) renderScores(data.scores, body);
    footer.style.display = 'flex';
    // Wire up card buttons
    footer.querySelector('.btn-save-compare').onclick = () => {
      const a = document.createElement('a');
      a.href = data.output_url;
      a.download = `compare-${job.backend}-${Date.now()}.png`;
      a.click();
    };
    footer.querySelector('.btn-ref-compare').onclick = () => {
      const idx = state.refImages.findIndex(r => r === null);
      if (idx === -1) { toast('All ref slots full', 'error'); return; }
      fetch(data.output_url).then(r => r.blob()).then(blob => {
        setRefImage(idx, new File([blob], 'reference.png', { type: 'image/png' }));
        toast(`Added to ref slot ${idx + 1}`, 'success');
      });
    };
  } else if (data.status === 'error') {
    body.innerHTML = `<div class="compare-error">${data.error || 'Generation failed'}</div>`;
  }
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
