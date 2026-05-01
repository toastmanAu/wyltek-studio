/* Wyltek Studio — health widget.
 *
 * Floating top-right pill with one coloured dot per component plus a
 * Reset button. Polls /api/health/components every 5s. First press of
 * Reset issues a soft reset (orphan rescue + re-probe). If 60s later
 * the queue still shows a job in flight, the button label switches to
 * "Hard reset" and the next press also restarts comfyui.service.
 *
 * Pure vanilla JS, no build step. Mounted by static/js/nav.js so it
 * appears on every studio page.
 */

(function () {
  'use strict';

  const POLL_MS = 5000;
  const ESCALATE_AFTER_MS = 60_000;

  const COMPONENTS = [
    { key: 'comfyui', label: 'ComfyUI' },
    { key: 'ollama',  label: 'Ollama' },
    { key: 'gpu',     label: 'GPU' },
    { key: 'disk',    label: 'Disk' },
    { key: 'queue',   label: 'Queue' },
  ];

  const state = {
    lastSoftAt: 0,
    busy: false,
    lastQueueComponent: null,
  };

  let dotEls = {};
  let buttonEl = null;
  let popoverEl = null;

  function buildWidget() {
    const root = document.createElement('div');
    root.className = 'health-widget';
    root.id = 'health-widget';

    const dotStrip = document.createElement('div');
    dotStrip.className = 'health-dots';
    COMPONENTS.forEach(({ key, label }) => {
      const dot = document.createElement('button');
      dot.type = 'button';
      dot.className = 'health-dot health-dot--unknown';
      dot.dataset.component = key;
      dot.setAttribute('aria-label', `${label} status`);
      dot.title = `${label}: probing…`;
      dot.addEventListener('click', (e) => {
        e.stopPropagation();
        showPopover(dot, dot.title);
      });
      dotStrip.appendChild(dot);
      dotEls[key] = dot;
    });

    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'health-reset-btn';
    btn.textContent = 'Reset';
    btn.title = 'Run a soft reset: rescue any orphan files and re-probe.';
    btn.addEventListener('click', onResetClick);
    buttonEl = btn;

    root.appendChild(dotStrip);
    root.appendChild(btn);

    popoverEl = document.createElement('div');
    popoverEl.className = 'health-popover';
    popoverEl.hidden = true;
    root.appendChild(popoverEl);

    document.body.appendChild(root);
    document.addEventListener('click', () => hidePopover());
  }

  function showPopover(anchor, text) {
    if (!popoverEl) return;
    popoverEl.textContent = text;
    popoverEl.hidden = false;
    const rect = anchor.getBoundingClientRect();
    const widget = document.getElementById('health-widget');
    const widgetRect = widget.getBoundingClientRect();
    popoverEl.style.top = (rect.bottom - widgetRect.top + 6) + 'px';
    popoverEl.style.left = (rect.left - widgetRect.left) + 'px';
  }

  function hidePopover() {
    if (popoverEl) popoverEl.hidden = true;
  }

  async function pollHealth() {
    try {
      const resp = await fetch('/api/health/components', { cache: 'no-store' });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();
      applyHealth(data.components || []);
    } catch (err) {
      applyHealth(COMPONENTS.map((c) => ({
        name: c.key, status: 'red', tooltip: 'API unreachable',
      })));
    }
  }

  function applyHealth(components) {
    components.forEach((c) => {
      const dot = dotEls[c.name];
      if (!dot) return;
      dot.className = `health-dot health-dot--${c.status}`;
      const label = (COMPONENTS.find((x) => x.key === c.name) || {}).label || c.name;
      dot.title = `${label}: ${c.tooltip}`;
      if (c.name === 'queue') state.lastQueueComponent = c;
    });
    refreshResetButtonLabel();
  }

  function queueIsActive() {
    const q = state.lastQueueComponent;
    if (!q) return false;
    const m = /^(\d+)\b/.exec(q.tooltip || '');
    return m ? parseInt(m[1], 10) > 0 : q.status !== 'green';
  }

  function refreshResetButtonLabel() {
    if (!buttonEl) return;
    const sinceSoft = Date.now() - state.lastSoftAt;
    const escalate =
      state.lastSoftAt > 0 && sinceSoft > ESCALATE_AFTER_MS && queueIsActive();
    buttonEl.textContent = escalate ? 'Hard reset' : 'Reset';
    buttonEl.classList.toggle('health-reset-btn--hard', escalate);
    buttonEl.title = escalate
      ? 'Soft reset did not clear the queue. Hard reset will also restart ComfyUI.'
      : 'Run a soft reset: rescue any orphan files and re-probe.';
  }

  async function onResetClick(e) {
    e.stopPropagation();
    if (state.busy || !buttonEl) return;
    state.busy = true;
    const originalText = buttonEl.textContent;
    buttonEl.disabled = true;
    buttonEl.textContent = '…';
    const level = buttonEl.classList.contains('health-reset-btn--hard') ? 'hard' : 'soft';

    try {
      const resp = await fetch('/api/health/reset', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ level }),
      });
      const data = await resp.json();

      if (level === 'soft') state.lastSoftAt = Date.now();
      else state.lastSoftAt = 0;

      applyHealth(data.components || []);
      const rescuedCount = (data.rescue && data.rescue.rescued) ? data.rescue.rescued.length : 0;
      const restartNote = data.service_restart
        ? (data.service_restart.ok ? ' · ComfyUI restarted' : ` · restart failed: ${data.service_restart.error}`)
        : '';
      flashToast(`${level === 'hard' ? 'Hard' : 'Soft'} reset · rescued ${rescuedCount} mesh(es)${restartNote}`);
    } catch (err) {
      flashToast('Reset failed — check open-palette logs', true);
    } finally {
      buttonEl.disabled = false;
      buttonEl.textContent = originalText;
      state.busy = false;
      refreshResetButtonLabel();
    }
  }

  function flashToast(msg, isError) {
    const t = document.createElement('div');
    t.className = 'health-toast' + (isError ? ' health-toast--error' : '');
    t.textContent = msg;
    document.body.appendChild(t);
    requestAnimationFrame(() => t.classList.add('health-toast--in'));
    setTimeout(() => {
      t.classList.remove('health-toast--in');
      setTimeout(() => t.remove(), 300);
    }, 4000);
  }

  function start() {
    buildWidget();
    pollHealth();
    setInterval(pollHealth, POLL_MS);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', start);
  } else {
    start();
  }
})();
