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
}

function loadImage(src) {
  return new Promise((res, rej) => {
    const img = new Image();
    img.onload = () => res(img);
    img.onerror = rej;
    img.src = src;
  });
}
