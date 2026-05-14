/* Save a server-hosted file to the user's device.
 *
 * Root cause for iOS standalone PWA:
 *   - manifest "display: standalone" means the WebView never has Safari
 *     chrome — no back, no done, no nav of any kind.
 *   - iOS routes binary navigations to Quick Look (a system UI overlay)
 *     which replaces the WebView content. With no chrome on the WebView,
 *     there's no way back to the PWA except force-quit.
 *   - navigator.share would be the proper save mechanism but is gated on
 *     secure context (HTTPS). LAN HTTP and Tailscale 100.x.x.x IPs aren't
 *     secure → navigator.share is undefined.
 *
 * We can't add chrome to Quick Look or to the PWA WebView. What we CAN do
 * is keep the user inside the PWA's own DOM the whole time, so a Done
 * button we render is always reachable. This builds an in-page modal with
 * an iframe pointing at /save?path=..., loaded over a fixed-position
 * overlay. The user interacts with the file inside the iframe (whatever
 * iOS does for binary in iframes — Quick Look, share sheet, blank with
 * long-press fallback) and dismisses via our Done button.
 *
 * Desktop browsers route through /download for a clean Save As. */

const _isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent) ||
  (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);

function _openIOSSaveModal(url, name) {
  const overlay = document.createElement('div');
  overlay.style.cssText =
    'position:fixed;inset:0;background:#000;z-index:99999;' +
    'display:flex;flex-direction:column;-webkit-tap-highlight-color:transparent';

  const bar = document.createElement('div');
  bar.style.cssText =
    'display:flex;justify-content:space-between;align-items:center;gap:12px;' +
    'padding:12px 16px;background:#111;color:#fff;flex:0 0 auto;' +
    'padding-top:max(12px,env(safe-area-inset-top))';

  const title = document.createElement('span');
  title.textContent = name;
  title.style.cssText =
    'font-size:14px;font-weight:500;opacity:0.85;word-break:break-all;' +
    'overflow:hidden;text-overflow:ellipsis;white-space:nowrap;flex:1 1 auto';

  const done = document.createElement('button');
  done.textContent = 'Done';
  done.style.cssText =
    'background:#2563eb;color:#fff;border:0;padding:9px 20px;border-radius:10px;' +
    'font-size:15px;font-weight:600;flex:0 0 auto;cursor:pointer';
  done.addEventListener('click', () => overlay.remove());

  bar.appendChild(title);
  bar.appendChild(done);

  const frame = document.createElement('iframe');
  frame.src = `/save?path=${encodeURIComponent(url)}`;
  frame.setAttribute('allow', 'fullscreen');
  frame.style.cssText = 'flex:1 1 auto;border:0;background:#0f0f10;width:100%';

  overlay.appendChild(bar);
  overlay.appendChild(frame);
  document.body.appendChild(overlay);
}

window.saveFile = async function saveFile(url, filename) {
  const name = filename || url.split('/').pop().split('?')[0] || 'download';

  if (typeof navigator.canShare === 'function' && typeof navigator.share === 'function') {
    try {
      const res = await fetch(url);
      if (!res.ok) throw new Error(`fetch ${res.status}`);
      const blob = await res.blob();
      const file = new File([blob], name, {
        type: blob.type || 'application/octet-stream',
      });
      if (navigator.canShare({ files: [file] })) {
        await navigator.share({ files: [file], title: name });
        return;
      }
    } catch (err) {
      if (err && err.name === 'AbortError') return;
    }
  }

  if (_isIOS) {
    _openIOSSaveModal(url, name);
    return;
  }

  const a = document.createElement('a');
  a.href = `/download?path=${encodeURIComponent(url)}`;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  a.remove();
};
