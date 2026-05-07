/* Worldgen page controller — runs WorldGen (FLUX.1-dev + DA-2 + LoRA) to
 * produce an explorable 3D scene from a text prompt or reference image.
 * Backend is /api/worldgen; output is a GLB rendered with model-viewer. */

const $ = (id) => document.getElementById(id);

const state = {
  refImageFile: null,
  jobId: null,
  ws: null,
};

function clearChildren(el) {
  while (el.firstChild) el.removeChild(el.firstChild);
}

function setEmptyState(parent, text, errorColor = false) {
  clearChildren(parent);
  const div = document.createElement('div');
  div.className = 'empty-state';
  if (errorColor) div.style.color = '#e74c3c';
  div.textContent = text;
  parent.appendChild(div);
}

function updateModeVisibility() {
  const mode = $('mode').value;
  $('image-input-row').style.display = mode === 'i2s' ? 'block' : 'none';
}

function setReadiness(message, level = 'info') {
  const banner = $('readiness-banner');
  banner.textContent = message;
  banner.style.borderLeftColor = level === 'error' ? '#e74c3c'
    : level === 'warn' ? '#f39c12'
    : 'var(--accent)';
}

async function checkBackendReadiness() {
  try {
    const r = await fetch('/api/worldgen/status');
    if (!r.ok) {
      setReadiness('Backend unavailable. Check /api/worldgen/status.', 'error');
      $('generate-btn').disabled = true;
      return;
    }
    const info = await r.json();
    if (info.ready) {
      setReadiness(`Ready. ${info.notes || ''}`.trim(), 'info');
      $('generate-btn').disabled = false;
    } else {
      const reason = info.reason || 'Backend not ready';
      setReadiness(`Not ready — ${reason}`, 'warn');
      $('generate-btn').disabled = true;
    }
  } catch (e) {
    setReadiness('Cannot reach backend status endpoint.', 'error');
    $('generate-btn').disabled = true;
  }
}

function pickRefImage(file) {
  state.refImageFile = file;
  const thumb = $('ref-thumb');
  clearChildren(thumb);
  if (!file) {
    thumb.textContent = 'No image';
    return;
  }
  const img = document.createElement('img');
  img.src = URL.createObjectURL(file);
  thumb.appendChild(img);
}

async function generate() {
  const prompt = $('prompt').value.trim();
  if (!prompt && $('mode').value === 't2s') {
    alert('Enter a prompt for text-to-scene mode.');
    return;
  }
  const mode = $('mode').value;
  if (mode === 'i2s' && !state.refImageFile) {
    alert('Upload a reference image for image-to-scene mode.');
    return;
  }

  $('generate-btn').disabled = true;
  $('cancel-btn').style.display = 'inline-block';
  $('progress').textContent = 'Submitting…';
  setEmptyState($('output-body'), 'Generating — this can take 5-15 minutes on first run (FLUX + depth + scene assembly).');

  const fd = new FormData();
  fd.append('prompt', prompt);
  fd.append('mode', mode);
  fd.append('resolution', $('resolution').value);
  fd.append('seed', $('seed').value);
  fd.append('output_format', $('output-format').value);
  if (state.refImageFile) {
    fd.append('reference_image', state.refImageFile);
  }

  try {
    const r = await fetch('/api/worldgen', { method: 'POST', body: fd });
    if (!r.ok) {
      const errText = await r.text();
      throw new Error(`HTTP ${r.status}: ${errText}`);
    }
    const data = await r.json();
    state.jobId = data.job_id;
    $('progress').textContent = `Queued — job ${state.jobId.slice(0, 8)}…`;
    subscribeProgress(state.jobId);
  } catch (e) {
    $('progress').textContent = `Failed: ${e.message}`;
    setEmptyState($('output-body'), `Error: ${e.message}`, true);
    $('generate-btn').disabled = false;
    $('cancel-btn').style.display = 'none';
  }
}

function subscribeProgress(jobId) {
  if (state.ws) {
    state.ws.close();
    state.ws = null;
  }
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const ws = new WebSocket(`${proto}//${window.location.host}/ws/jobs/${jobId}`);
  state.ws = ws;

  ws.onmessage = (event) => {
    let msg;
    try { msg = JSON.parse(event.data); } catch { return; }
    if (msg.progress != null) {
      $('progress').textContent = `${msg.progress}% — ${msg.message || ''}`.trim();
    }
    if (msg.status === 'complete' || msg.status === 'failed') {
      ws.close();
      state.ws = null;
      $('generate-btn').disabled = false;
      $('cancel-btn').style.display = 'none';
      if (msg.status === 'complete') {
        renderOutput(msg);
      } else {
        $('progress').textContent = `Failed: ${msg.error || 'unknown'}`;
        setEmptyState($('output-body'), `Generation failed: ${msg.error || 'unknown'}`, true);
      }
    }
  };
  ws.onerror = () => {
    $('progress').textContent = 'Connection lost. Refresh to check final status.';
  };
}

function renderOutput(msg) {
  const url = msg.output_url || msg.url;
  if (!url) {
    $('output-meta').textContent = 'Generated, but no URL returned';
    return;
  }
  $('output-meta').textContent = `Job ${state.jobId.slice(0, 8)} — ${msg.message || 'complete'}`;
  $('progress').textContent = '';
  const dl = $('download-link');
  dl.href = url;
  dl.style.display = 'inline';

  const body = $('output-body');
  clearChildren(body);
  const viewer = document.createElement('model-viewer');
  viewer.setAttribute('src', url);
  viewer.setAttribute('camera-controls', '');
  // No auto-rotate — Worldgen meshes are 360° scenes meant to be navigated
  // from inside (look around like a panorama, not orbit like an object).
  // Wider FOV than the model-viewer default (~30°) gives a more natural
  // first-person feel; user can scroll-zoom for narrower if they want.
  viewer.setAttribute('field-of-view', '75deg');
  viewer.setAttribute('min-field-of-view', '20deg');
  viewer.setAttribute('max-field-of-view', '110deg');
  // Spawn camera near the centroid (which is at world-origin for new
  // generations after the run_worker.py recenter; the centroid for
  // legacy GLBs is wherever WorldGen put it — auto is fine because we
  // let model-viewer pick the bounding-box center as target).
  viewer.setAttribute('camera-target', 'auto auto auto');
  viewer.setAttribute('camera-orbit', '0deg 80deg 0.1m');
  viewer.setAttribute('min-camera-orbit', 'auto auto 0m');
  viewer.setAttribute('max-camera-orbit', 'auto auto auto');
  viewer.setAttribute('interaction-prompt', 'none');
  viewer.setAttribute('exposure', '1.0');
  viewer.setAttribute('shadow-intensity', '0');  // scene already has baked-in lighting
  viewer.style.width = '100%';
  viewer.style.height = '600px';
  body.appendChild(viewer);
}

function cancel() {
  if (!state.jobId) return;
  fetch(`/api/jobs/${state.jobId}/cancel`, { method: 'POST' }).catch(() => {});
  if (state.ws) { state.ws.close(); state.ws = null; }
  $('progress').textContent = 'Cancelled.';
  $('generate-btn').disabled = false;
  $('cancel-btn').style.display = 'none';
}

document.addEventListener('DOMContentLoaded', () => {
  $('mode').addEventListener('change', updateModeVisibility);
  $('ref-image').addEventListener('change', (e) => pickRefImage(e.target.files[0]));
  $('generate-btn').addEventListener('click', generate);
  $('cancel-btn').addEventListener('click', cancel);
  updateModeVisibility();
  checkBackendReadiness();
});
