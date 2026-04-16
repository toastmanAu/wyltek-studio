/**
 * Shared "Send to Project" picker component.
 *
 * Usage:
 *   1. Include this script on any page.
 *   2. Call ProjectPicker.init() once on page load.
 *   3. Call ProjectPicker.show(filename) to open the picker for an asset.
 *
 * The picker is a floating dropdown that lists all projects. Clicking a
 * project copies the asset into it via POST /api/projects/{id}/move.
 */
const ProjectPicker = (() => {
  let _overlay = null;
  let _list = null;
  let _currentFilename = null;
  let _toastFn = null;

  function init(toastFn) {
    _toastFn = toastFn || _defaultToast;

    // Create overlay
    _overlay = document.createElement('div');
    _overlay.id = 'pp-overlay';
    _overlay.style.cssText =
      'display:none;position:fixed;inset:0;z-index:999;';
    _overlay.addEventListener('click', (e) => {
      if (e.target === _overlay) hide();
    });

    // Create popup
    const popup = document.createElement('div');
    popup.style.cssText =
      'position:fixed;top:50%;left:50%;transform:translate(-50%,-50%);' +
      'min-width:280px;max-width:400px;max-height:400px;overflow-y:auto;' +
      'background:var(--surface);border:1px solid var(--border);' +
      'border-radius:12px;box-shadow:0 8px 32px rgba(0,0,0,0.4);z-index:1000;';

    const header = document.createElement('div');
    header.style.cssText =
      'padding:12px 16px;font-size:13px;font-weight:600;' +
      'border-bottom:1px solid var(--border);display:flex;' +
      'justify-content:space-between;align-items:center;';
    header.textContent = 'Send to Project';

    const close = document.createElement('button');
    close.textContent = '\u00d7';
    close.style.cssText =
      'background:none;border:none;color:var(--text-dim);font-size:18px;cursor:pointer;';
    close.onclick = hide;
    header.appendChild(close);

    _list = document.createElement('div');
    _list.id = 'pp-list';

    popup.appendChild(header);
    popup.appendChild(_list);
    _overlay.appendChild(popup);
    document.body.appendChild(_overlay);
  }

  function _defaultToast(msg) {
    // Fallback if no toast function provided
    const el = document.getElementById('toast-msg');
    if (el) {
      el.textContent = msg;
      el.classList.add('show');
      setTimeout(() => el.classList.remove('show'), 3000);
    }
  }

  async function show(filename) {
    if (!_overlay) init();
    _currentFilename = filename;
    _overlay.style.display = 'block';
    _list.textContent = 'Loading...';
    _list.style.padding = '16px';

    try {
      const projects = await (await fetch('/api/projects')).json();
      _list.textContent = '';
      _list.style.padding = '';

      if (projects.length === 0) {
        const empty = document.createElement('div');
        empty.style.cssText = 'padding:20px;font-size:13px;color:var(--text-dim);text-align:center;';
        empty.textContent = 'No projects yet. Create one in Projects first.';
        _list.appendChild(empty);
        return;
      }

      projects.forEach(p => {
        const item = document.createElement('div');
        item.style.cssText =
          'padding:10px 16px;cursor:pointer;font-size:13px;' +
          'border-bottom:1px solid var(--border);';
        item.textContent = p.name;
        item.onmouseenter = () => item.style.background = 'var(--accent-dim)';
        item.onmouseleave = () => item.style.background = '';
        item.onclick = () => _send(p.id, p.name);
        _list.appendChild(item);
      });
    } catch (e) {
      _list.textContent = 'Failed to load projects';
      _list.style.cssText = 'padding:16px;color:var(--error);font-size:13px;';
    }
  }

  function hide() {
    if (_overlay) _overlay.style.display = 'none';
  }

  async function _send(projectId, projectName) {
    try {
      const resp = await fetch(`/api/projects/${projectId}/move`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ filename: _currentFilename, copy: true }),
      });
      const data = await resp.json();
      if (data.error) throw new Error(data.error);
      _toastFn(`Sent to ${projectName}`);
    } catch (e) {
      _toastFn('Failed: ' + e.message);
    }
    hide();
  }

  return { init, show, hide };
})();
