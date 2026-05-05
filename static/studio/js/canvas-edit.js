// Inline post-edit canvas. Renders the base PNG plus a stack of PNG
// overlay layers. Layers can be moved, resized, deleted, and the whole
// composite can be flattened back to a PNG via toBlob().
//
// Tasks 32-35 add: drag-drop layer creation, click-to-select, mouse
// drag for move/resize with corner handles, paste-from-clipboard, and
// save-composite endpoint. Task 31 (this file) lays down the rendering
// loop and the layer model only.

export class PreviewCanvas {
  constructor(canvas) {
    this.canvas = canvas;
    this.ctx = canvas.getContext('2d');
    this.base = null;          // {img}
    this.layers = [];          // [{img, x, y, w, h}]
    this.selected = -1;
    this.drag = null;          // populated by Task 33

    // Task 32: drag-drop PNG → addLayer at drop position.
    canvas.addEventListener('dragover', (e) => { e.preventDefault(); });
    canvas.addEventListener('drop', async (e) => {
      e.preventDefault();
      const f = e.dataTransfer?.files?.[0];
      if (!f || !f.type.startsWith('image/')) return;
      const rect = canvas.getBoundingClientRect();
      const x = (e.clientX - rect.left) * (canvas.width / rect.width);
      const y = (e.clientY - rect.top) * (canvas.height / rect.height);
      await this.addLayerFromBlob(f, x, y);
    });

    // Task 33: click to select, drag body to move, drag corner to resize.
    canvas.addEventListener('mousedown', (e) => this._mousedown(e));
    canvas.addEventListener('mousemove', (e) => this._mousemove(e));
    canvas.addEventListener('mouseup', () => this._mouseup());
    canvas.addEventListener('mouseleave', () => this._mouseup());
  }

  async setBase(url) {
    const img = await loadImage(url);
    this.canvas.width = img.naturalWidth;
    this.canvas.height = img.naturalHeight;
    this.base = {img};
    this.layers = [];
    this.selected = -1;
    this.canvas.hidden = false;
    this.render();
  }

  async addLayerFromBlob(blob, x = 50, y = 50) {
    const img = await loadImage(URL.createObjectURL(blob));
    this.layers.push({img, x, y, w: img.naturalWidth, h: img.naturalHeight});
    this.selected = this.layers.length - 1;
    this.render();
  }

  deleteSelected() {
    if (this.selected < 0) return;
    this.layers.splice(this.selected, 1);
    this.selected = -1;
    this.render();
  }

  render() {
    const {ctx, canvas} = this;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    if (this.base) ctx.drawImage(this.base.img, 0, 0);
    for (const [i, L] of this.layers.entries()) {
      ctx.drawImage(L.img, L.x, L.y, L.w, L.h);
      if (i === this.selected) {
        ctx.strokeStyle = '#0af';
        ctx.lineWidth = 2;
        ctx.strokeRect(L.x, L.y, L.w, L.h);
        for (const [hx, hy] of [
          [L.x, L.y], [L.x + L.w, L.y],
          [L.x, L.y + L.h], [L.x + L.w, L.y + L.h],
        ]) {
          ctx.fillStyle = '#0af';
          ctx.fillRect(hx - 6, hy - 6, 12, 12);
        }
      }
    }
  }

  toBlob() {
    return new Promise((res) => this.canvas.toBlob(res, 'image/png'));
  }

  _eventXY(e) {
    const r = this.canvas.getBoundingClientRect();
    return [
      (e.clientX - r.left) * (this.canvas.width / r.width),
      (e.clientY - r.top)  * (this.canvas.height / r.height),
    ];
  }

  _hitCorner(L, x, y) {
    const corners = [
      [L.x,         L.y,         'tl'],
      [L.x + L.w,   L.y,         'tr'],
      [L.x,         L.y + L.h,   'bl'],
      [L.x + L.w,   L.y + L.h,   'br'],
    ];
    for (const [cx, cy, name] of corners) {
      if (Math.abs(x - cx) <= 8 && Math.abs(y - cy) <= 8) return name;
    }
    return null;
  }

  _mousedown(e) {
    const [x, y] = this._eventXY(e);
    // Topmost layer first.
    for (let i = this.layers.length - 1; i >= 0; i--) {
      const L = this.layers[i];
      const corner = (i === this.selected) ? this._hitCorner(L, x, y) : null;
      if (corner) {
        this.drag = {
          mode: 'resize', corner,
          startX: x, startY: y, layer0: {...L},
          shift: e.shiftKey,
        };
        return;
      }
      if (x >= L.x && x <= L.x + L.w && y >= L.y && y <= L.y + L.h) {
        this.selected = i;
        this.drag = {mode: 'move', startX: x, startY: y, layer0: {...L}};
        this.render();
        return;
      }
    }
    // Click on empty: deselect.
    this.selected = -1;
    this.render();
  }

  _mousemove(e) {
    if (!this.drag) return;
    const [x, y] = this._eventXY(e);
    const L = this.layers[this.selected];
    if (!L) return;
    const dx = x - this.drag.startX;
    const dy = y - this.drag.startY;
    const L0 = this.drag.layer0;

    if (this.drag.mode === 'move') {
      L.x = L0.x + dx;
      L.y = L0.y + dy;
    } else if (this.drag.mode === 'resize') {
      let nx = L0.x, ny = L0.y, nw = L0.w, nh = L0.h;
      if (this.drag.corner.includes('r')) nw = Math.max(8, L0.w + dx);
      if (this.drag.corner.includes('l')) { nw = Math.max(8, L0.w - dx); nx = L0.x + dx; }
      if (this.drag.corner.includes('b')) nh = Math.max(8, L0.h + dy);
      if (this.drag.corner.includes('t')) { nh = Math.max(8, L0.h - dy); ny = L0.y + dy; }
      // Shift constrains aspect to original.
      if (this.drag.shift || e.shiftKey) {
        const asp = L0.w / L0.h;
        if (nw / nh > asp) nw = nh * asp; else nh = nw / asp;
      }
      L.x = nx; L.y = ny; L.w = nw; L.h = nh;
    }
    this.render();
  }

  _mouseup() { this.drag = null; }
}

function loadImage(src) {
  return new Promise((res, rej) => {
    const img = new Image();
    img.onload = () => res(img);
    img.onerror = rej;
    img.src = src;
  });
}
