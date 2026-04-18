#!/usr/bin/env python3
"""Render an HTML gallery for a LoRA matrix test run.

Reads results.json from a test-runs directory and writes index.html alongside
it. Layout is a grid: rows = OP models (including "raw"), cols = LoRAs
(including "no-lora"). Hover any thumbnail to see the prompt + metadata that
produced it. Click to open full-size.

Usage:
    # render the most recent run
    python scripts/matrix_gallery.py

    # or a specific run dir
    python scripts/matrix_gallery.py storage/test-runs/2026-04-17-lora-matrix-a-digital-blockchain-background-image
"""

from __future__ import annotations

import html
import json
import os
import sys
from pathlib import Path


def find_latest_run() -> Path:
    runs = sorted(Path("storage/test-runs").glob("*-lora-matrix-*"),
                  key=lambda p: p.stat().st_mtime, reverse=True)
    if not runs:
        sys.exit("No runs found in storage/test-runs/")
    return runs[0]


def relpath_for_browser(img_abs_or_rel: str, gallery_dir: Path) -> str:
    """Image paths in results.json are relative to the server CWD
    (open-palette root). Convert to a path relative to the gallery HTML."""
    if not img_abs_or_rel:
        return ""
    img = Path(img_abs_or_rel)
    if not img.is_absolute():
        img = Path.cwd() / img
    return os.path.relpath(img, gallery_dir)


def render(run_dir: Path) -> Path:
    data = json.loads((run_dir / "results.json").read_text())
    seed = data["seed_prompt"]
    cfg = data["config"]
    enhancements = {e["model"]: e for e in data["enhancements"]}
    results = data["results"]

    op_order: list[str] = ["*(raw)*"] + [m for m in cfg["op_models"]
                                         if any(r["op_model"] == m for r in results)]
    lora_order: list[str] = [""] + cfg["style_loras"]

    by_cell: dict[tuple[str, str], dict] = {}
    for r in results:
        key = (r["op_model"] or "*(raw)*", r["lora"])
        by_cell[key] = r

    out = [
        "<!doctype html><meta charset=utf-8>",
        f"<title>LoRA matrix — {html.escape(seed)}</title>",
        "<style>",
        "body{font:13px/1.4 system-ui,sans-serif;margin:20px;background:#111;color:#ddd}",
        "h1{font-size:18px;margin:0 0 4px}",
        "header small{color:#888}",
        ".meta{margin:12px 0;padding:10px 14px;background:#1c1c1c;border-left:3px solid #4a9;border-radius:3px;font-size:12px}",
        ".meta code{background:#000;padding:1px 5px;border-radius:3px;color:#9cc}",
        "table{border-collapse:collapse;margin-top:14px}",
        "th,td{border:1px solid #333;padding:4px;vertical-align:top;text-align:center}",
        "th{background:#1a1a1a;font-weight:600;position:sticky;top:0;z-index:2}",
        "th.op{text-align:left;padding:6px 10px;min-width:130px;max-width:180px;position:sticky;left:0;z-index:3;background:#1a1a1a}",
        "th.op.corner{z-index:4}",
        "th.op .latency{display:block;font-weight:400;color:#888;font-size:11px;margin-top:2px}",
        "th.op .prompt{display:block;font-weight:400;color:#9bb;font-size:11px;margin-top:4px;max-height:60px;overflow:hidden;text-overflow:ellipsis}",
        ".cell{position:relative;width:220px;height:220px;background:#000}",
        ".cell img{width:100%;height:100%;object-fit:cover;display:block;cursor:pointer}",
        ".cell .jobid{position:absolute;bottom:0;left:0;right:0;padding:3px 6px;background:rgba(0,0,0,0.7);font-size:10px;color:#bbb}",
        ".cell.miss{color:#666;font-size:11px;padding:20px}",
        ".tooltip{position:fixed;background:#222;border:1px solid #4a9;border-radius:4px;padding:10px 14px;max-width:560px;font-size:12px;line-height:1.4;pointer-events:none;z-index:100;display:none;box-shadow:0 4px 14px rgba(0,0,0,0.6)}",
        ".tooltip h4{margin:0 0 4px;color:#4a9}",
        ".tooltip .r{margin:3px 0}",
        ".tooltip .l{color:#888;display:inline-block;min-width:64px}",
        "</style>",
        f"<header><h1>LoRA matrix — <code>{html.escape(seed)}</code></h1>",
        f"<small>base: <code>{html.escape(cfg['base_model'])}</code> · seed {cfg['seed']} · "
        f"{cfg['steps']} steps @ cfg {cfg['cfg']} · "
        f"lora strengths m={cfg['lora_strength_model']}/c={cfg['lora_strength_clip']}</small></header>",
        "<div class=meta>Hover a tile for prompt+timing. Click to open full-size. "
        "Columns are LoRAs, rows are prompt-optimizer models (top row = raw untouched prompt).</div>",
        "<table><thead><tr>",
        "<th class='op corner'>OP model ↓ / LoRA →</th>",
    ]
    for lora in lora_order:
        label = "no-lora" if not lora else lora.replace(".safetensors", "")
        out.append(f"<th>{html.escape(label)}</th>")
    out.append("</tr></thead><tbody>")

    for op in op_order:
        enh = enhancements.get(op) if op != "*(raw)*" else None
        latency = (f"{enh['latency_s']:.1f}s · {len(enh['enhanced_prompt'].split())} words"
                   if enh else "—")
        prompt_preview = html.escape((enh["enhanced_prompt"] if enh else seed)[:200])
        out.append("<tr>")
        op_label = html.escape(op.replace("*(raw)*", "(raw)"))
        out.append(
            f"<th class=op><b>{op_label}</b>"
            f"<span class=latency>{latency}</span>"
            f"<span class=prompt>{prompt_preview}</span>"
            "</th>"
        )
        for lora in lora_order:
            r = by_cell.get((op, lora))
            if not r or r.get("status") != "complete" or not r.get("image_path"):
                out.append("<td class='cell miss'>—</td>")
                continue
            rel = html.escape(relpath_for_browser(r["image_path"], run_dir))
            job = html.escape(r["job_id"])
            prompt = html.escape(r["prompt"][:400])
            negative = html.escape(r.get("negative", "")[:200])
            lora_lbl = html.escape(lora or "none")
            out.append(
                f"<td class=cell data-job='{job}' data-prompt='{prompt}' "
                f"data-negative='{negative}' data-lora='{lora_lbl}' "
                f"data-op='{op_label}' data-time='{r['duration_s']:.1f}s'>"
                f"<a href='{rel}' target=_blank><img src='{rel}' loading=lazy></a>"
                f"<div class=jobid>{job}</div>"
                "</td>"
            )
        out.append("</tr>")
    out.append("</tbody></table>")

    # Tooltip built with safe DOM methods — no innerHTML, no string→HTML injection.
    out.extend([
        "<div id=tip class=tooltip></div>",
        "<script>",
        "const tip=document.getElementById('tip');",
        "function row(label, value){",
        "  const d=document.createElement('div'); d.className='r';",
        "  const l=document.createElement('span'); l.className='l'; l.textContent=label;",
        "  d.appendChild(l);",
        "  d.appendChild(document.createTextNode(' '+value));",
        "  return d;",
        "}",
        "document.querySelectorAll('td.cell[data-job]').forEach(td=>{",
        "  td.addEventListener('mousemove',e=>{",
        "    tip.replaceChildren();",
        "    const h=document.createElement('h4');",
        "    h.textContent=td.dataset.op+' + '+td.dataset.lora;",
        "    tip.appendChild(h);",
        "    tip.appendChild(row('Job:', td.dataset.job+' ('+td.dataset.time+')'));",
        "    tip.appendChild(row('Prompt:', td.dataset.prompt));",
        "    if(td.dataset.negative) tip.appendChild(row('Negative:', td.dataset.negative));",
        "    tip.style.display='block';",
        "    const maxX=window.innerWidth-tip.offsetWidth-10;",
        "    tip.style.left=Math.min(e.clientX+15,maxX)+'px';",
        "    tip.style.top=(e.clientY+15)+'px';",
        "  });",
        "  td.addEventListener('mouseleave',()=>{tip.style.display='none'});",
        "});",
        "</script>",
    ])

    html_path = run_dir / "index.html"
    html_path.write_text("\n".join(out))
    return html_path


def main() -> int:
    if len(sys.argv) > 1:
        run_dir = Path(sys.argv[1])
    else:
        run_dir = find_latest_run()
    if not (run_dir / "results.json").exists():
        sys.exit(f"No results.json at {run_dir}")
    out = render(run_dir)
    print(f"Gallery: {out}")
    print(f"Open with: xdg-open {out}   (or paste file://{out.resolve()} into a browser)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
