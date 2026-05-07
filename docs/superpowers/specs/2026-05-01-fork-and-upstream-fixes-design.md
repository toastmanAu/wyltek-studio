# Fork & Upstream Strategy for ROCm 3D Wrapper Fixes

**Author:** Claude Code (paired w/ Phill)
**Date:** 2026-05-01
**Status:** Phase 1 (Trellis2-GGUF fork) executed 2026-05-02; Hy3D fork + Phase 2 structural fix still pending.

## 2026-05-02 update — Phase 1 Trellis2-GGUF executed

Forked `Aero-Ex/ComfyUI-Trellis2-GGUF` → `toastmanAu/ComfyUI-Trellis2-GGUF-rocm`. Five branches pushed; `main` is the merged sum.

| Branch | File(s) | Upstream-able? | Status |
|---|---|---|---|
| `upstream-prs/dinov3-device` | `image_feature_extractor.py` | Yes | Pushed, PR not yet filed |
| `upstream-prs/transformers5-layer-path` | `image_feature_extractor.py` | Yes | Pushed, PR not yet filed |
| `upstream-prs/bf16-filename` | `model_manager.py` | Yes | Pushed, PR not yet filed |
| `upstream-prs/preprocess-rgb` | `nodes.py` | Yes | Pushed, PR not yet filed. **NEW** — added bug #5 to inventory below. |
| `rocm-only/rasterize-glcontext` | `nodes.py`, `trellis2_image_to_3d.py` | No (ROCm-only) | Stays on fork. |

Local install: `/home/phill/ComfyUI/custom_nodes/ComfyUI-Trellis2-GGUF/` is now a clone of the fork (HEAD = 684a1ac). Old hand-edited copy archived at `/home/phill/repos/archive/ComfyUI-Trellis2-GGUF.bak-2026-05-02/`.

---

## TL;DR

Stop frankensteining around third-party wrapper bugs with monkey-patches we maintain in our public guide. Instead:

1. **Fork** `Aero-Ex/ComfyUI-Trellis2-GGUF` and `kijai/ComfyUI-Hunyuan3DWrapper` under `toastmanAu/`
2. **Apply** the patches we've already drafted directly into the forks (no patch files needed in the public guide anymore)
3. **PR** the small clean fixes to upstream while maintaining our forks for ROCm-specific behaviour
4. **Implement** a structural fix for the `low_vram` overload that's currently the largest source of "needs fix" reports
5. **Pivot** `trellis-2-rocm-comfyui` (our public guide repo) to point at the forks; remove the patches/ directory in favour of "clone these forks instead of upstream"

End state: AMD ROCm users get a clean install — `git clone toastmanAu/X` instead of `git clone upstream/X && apply 5 patches`. We become a credible fork maintainer rather than a downstream patcher. PR acceptance turns our forks back into pure ROCm-flavour overlays.

---

## Why now

We've now characterised the wrapper bug surface across two full days of work. The bugs cluster into three categories:

1. **Trivial single-line fixes** that are clearly correct, no design judgement needed (DINOv3 device move, BF16 filename suffix). These should just be PR'd upstream. Worst case: they're declined and we maintain in our fork forever — same place we are today, just with proper attribution and a public history.

2. **Structural fixes** that need maintainer involvement (the `low_vram` overload). Best handled by filing a detailed issue with repro evidence first; if maintainer is interested, follow up with a PR. If they're not, we keep it in our fork and the public guide says "use our fork for ROCm, here's why."

3. **Wrapper-version drift** (the `Hy3DApplyTexture` API changing inputs from `trimesh/image/mask` to `texture/renderer`). Not a bug per se — just upstream evolution. Our workflow JSON was stale. **Solved by us locking to a known-good fork commit** so users don't get surprised by future API breaks.

The "fork instead of patch" framing also helps the public-guide narrative: instead of "here's a 6-patch ROCm frankenstein," it becomes "here's a properly maintained ROCm fork track that follows upstream when patches land."

---

## Bug inventory

| # | Repo | File / Area | Severity | Fix size | Action |
|---|---|---|---|---|---|
| 1 | Aero-Ex/Trellis2-GGUF | `trellis2_gguf/modules/image_feature_extractor.py:117` | High (multi-view crash) | 2 lines | **PR upstream** |
| 2 | Aero-Ex/Trellis2-GGUF | `model_manager.py:~302` (BF16 filename) | High (404 on download) | 6 lines | **PR upstream** |
| 3 | kijai/ComfyUI-Hunyuan3DWrapper | `hy3dgen/shapegen/models/conditioner.py:~117` (4D Resize no-op) | High (multi-view crash) | ~10 lines (switch to v2 transforms or pre-resize) | **PR upstream** |
| 4 | Aero-Ex/Trellis2-GGUF | `trellis2_gguf/pipelines/trellis2_image_to_3d.py` (low_vram overload) | High (intermittent stale state, "load different model to unstick") | ~30 lines (extract `_ensure_on_device` helper) | **Issue + PR proposal** |
| 5 | Aero-Ex/Trellis2-GGUF | `model_manager.py` (FP8 won't work on ROCm) | Doc-only | ~10 lines doc | **Doc PR** |
| 6 | kijai/ComfyUI-Hunyuan3DWrapper | `nodes.py:Hy3DSampleMultiView` (single ref_image) | Medium (feature gap) | ~40 lines (accept image list, propagate to pipeline) | **Issue first, PR if welcomed** |
| 7 | egore/comfyui-trellis2-gguf-rocm | install script | Already patched in our public repo | n/a | **Keep our patches; PR if egore is responsive** |
| 8 | Aero-Ex/Trellis2-GGUF | `nodes.py:preprocess_image` (~line 2566) — unconditionally indexes `output_np[:, :, 3]` while the in-method rembg fallback is commented out, crashing on any RGB-without-alpha input | High (every RGB input crashes when `remove_background=False`) | 6 lines (`if mode != 'RGBA': output = output.convert('RGBA')` guard) | **PR upstream** — added 2026-05-02 after live failure with `IndexError: index 3 is out of bounds for axis 2 with size 3` |

### Out of scope for this pass

- Hunyuan3D-2.1 support (different DiT checkpoint, separate fork target if user wants 2.1)
- TRELLIS resolution=512 path optimisations
- ComfyUI prompt-abort RPC (orthogonal)

---

## Fork plan

### Repo: `toastmanAu/ComfyUI-Trellis2-GGUF` (fork of `Aero-Ex/ComfyUI-Trellis2-GGUF`)

**Branches:**
- `main` — tracks `Aero-Ex:main`, with our patches rebased on top. This is what users clone.
- `upstream-prs/dinov3-device` — patch 1 isolated for clean PR.
- `upstream-prs/bf16-filename` — patch 2 isolated for clean PR.
- `rocm-only/low-vram-refactor` — patch 4 (structural). Lives here until either upstream accepts or we decide to keep it in `main` permanently.

**Initial commit on `main`:**
```
fix(rocm): force GPU placement for DINOv2/v3 feature extractors

The DINOv2/v3 image conditioning models in
trellis2_gguf/modules/image_feature_extractor.py have separately-managed
lifecycle from the main pipeline. When low_vram is disabled at the pipeline
level, these extractors can still load with their weights resident on CPU
because nothing in the multi-view path explicitly calls .cuda() on them.

Result: torch.cuda._wrapper_CUDA___slow_conv2d_forward fails with
"weight is on cpu, different from other tensors on cuda:0" during the
multi-view conditioning pass.

Fix: idempotent self.model.cuda() before invoking the model. <1ms overhead
per call when weights already on GPU.

Also fixes single-view low_vram=False users on machines where the loader
doesn't pre-place weights on GPU.

Refs: https://github.com/Aero-Ex/ComfyUI-Trellis2-GGUF/issues/<TBD>
```

**Subsequent commits:** patch 2 (BF16 filename), then patch 4 (low_vram refactor) on a separate branch.

### Repo: `toastmanAu/ComfyUI-Hunyuan3DWrapper` (fork of `kijai/ComfyUI-Hunyuan3DWrapper`)

**Branches:**
- `main` — tracks `kijai:main` plus our 4D-Resize fix.
- `upstream-prs/4d-nchw-resize` — patch 3 isolated for clean PR.
- `feature/multi-image-paint-conditioning` — patch 6 (multi-image paint) for issue + PR.

**Note on `Hy3DApplyTexture`:** kijai already changed the API. No fix needed on the wrapper side — we update our workflow JSON. Our fork tracks upstream.

### Repo: `toastmanAu/comfyui-trellis2-gguf-rocm` (fork of `egore/comfyui-trellis2-gguf-rocm`)

**Branches:**
- `main` — egore's install script with our 4 patches applied (gfx target, COMFY_ROOT, --user pip, SITE_PACKAGES).

**Note:** lower priority — egore's repo is itself already a wrapper-of-wrappers for ROCm. PRs welcome but not essential.

---

## Implementation order

### Phase 1 — Fork + integrate into our pipeline (~1 hour)

1. **Fork all three repos** under `toastmanAu/`.
2. **Apply patches** locally:
   - In our `~/ComfyUI/custom_nodes/`, replace the upstream clones with `toastmanAu/` clones.
   - Verify: TRELLIS multi-view + Hy3D textured runs work end-to-end.
3. **Push patched `main` branches** to GitHub.
4. **Update `trellis-2-rocm-comfyui/README.md`** to point at the forks. Remove `patches/` from the install flow (keep the directory as an archive of "what's in the fork" with each patch as a `.patch` file — useful for code-review).

### Phase 2 — Structural fix for `low_vram` overload (~2 hours)

This is the actual fix for "load different model to unstick" — the bug we've been routing around with conditional `low_vram=True/False` based on pipeline_type.

**Approach:**

1. Extract a helper in `trellis2_image_to_3d.py`:
   ```python
   def _ensure_on_device(self, *model_names):
       """Idempotently move named pipeline sub-models to self.device.
       Always call before any sampling step. Replaces the
       `if self.low_vram: model.to(self.device)` pattern, which conflates
       memory policy with correctness."""
       for name in model_names:
           m = self.models.get(name)
           if m is not None and next(m.parameters()).device != self.device:
               m.to(self.device)
   ```

2. Extract a paired helper for the offload side:
   ```python
   def _maybe_offload(self, *model_names):
       """Offload named sub-models to CPU IF low_vram is enabled.
       Caller's responsibility to call after sampling."""
       if not self.low_vram:
           return
       for name in model_names:
           m = self.models.get(name)
           if m is not None:
               m.cpu()
       self._cleanup_cuda()
   ```

3. Replace every `if self.low_vram: <model>.to(self.device)` site (20 instances across the file) with `self._ensure_on_device('<name>')`.

4. Replace every `if self.low_vram: <model>.cpu()` site with `self._maybe_offload('<name>')`.

5. **Test matrix:** all combinations of (BF16, GGUF Q4/Q6/Q8) × (512, 1024, 1024_cascade, 1536_cascade) × (single-view, multi-view) × (shape, textured). Confirm:
   - No "load different model to unstick" needed
   - Memory stays bounded on subsequent runs
   - Cascade and non-cascade both work with single global setting

6. Once green, revert our `low_vram = not is_cascade` workflow-side hack — the wrapper now handles it correctly regardless.

### Phase 3 — Open upstream issues + draft PRs (~1 hour)

For each of the 4 PR-able fixes (1, 2, 3, plus optionally 4 if we're confident):

1. Open issue with repro steps, traceback, environment.
2. Link to our fork's commit demonstrating the fix.
3. Offer to PR.
4. Wait 3–7 days for maintainer response.
5. If receptive: PR. If silent: leave fork as the canonical ROCm path.

For #4 (low_vram refactor) and #6 (multi-image paint): file detailed issues first. These are larger and warrant maintainer buy-in before a 200-line PR drops.

### Phase 4 — Public-guide pivot (~30 min)

Update `trellis-2-rocm-comfyui` README:

- Step 2: "Clone `toastmanAu/comfyui-trellis2-gguf-rocm`" instead of egore's
- Step 4: install script auto-clones `toastmanAu/ComfyUI-Trellis2-GGUF` (our patched fork) instead of `Aero-Ex/`
- Step 5: skip — patches are already in the fork
- Step 6: same as before (custom_rasterizer build)
- Add: optional "Want to track upstream instead? Here's what to do" section for advanced users
- Add: "Status of our patches" table — links to upstream issues/PRs and their states

This becomes the front-of-house signal: ROCm users get a clean clone, we're transparent about what's in our fork vs. upstream, and the upgrade path back to vanilla upstream once PRs merge is documented.

---

## Public-repo (`trellis-2-rocm-comfyui`) reorganisation

**Current structure:**
```
README.md
LICENSE
patches/
  01-gfx-arch.patch
  02-comfy-root-home.patch
  03-pip-user-flag.patch
  04-site-packages-user.patch
  05-model-manager-bf16.patch
  06-image-feature-extractor-device.patch
docs/
  index.html  (GitHub Pages site, awaiting examples)
```

**Proposed structure:**
```
README.md         (rewritten — "clone our forks, done")
LICENSE
upstream-status.md  (table tracking which patches are PR'd / merged / pending)
patches-archive/  (renamed; for transparency, kept as historical record)
  01..06.patch
docs/
  index.html
  examples/
    nervape.glb
    fortnite-llama.glb
    ...other showcase samples
```

The `patches-archive/` directory persists so anyone can audit *what* is in our forks without forking themselves. Reviewable diffs.

---

## Risk assessment

| Risk | Likelihood | Mitigation |
|---|---|---|
| Upstream maintainers reject our PRs | Medium | Forks are self-contained; we keep them maintained. Worst case: status quo with cleaner attribution. |
| Upstream lands a conflicting refactor | Medium | We rebase periodically. Branch hygiene (separate `upstream-prs/*` branches per fix) keeps merge conflicts isolated. |
| Wrapper API changes again (like `Hy3DApplyTexture` did) | High | Lock our public guide to specific fork commit hashes. Pin in README. Test before pinning. |
| Forks fall behind upstream | Medium | Set up GitHub Actions to nightly-rebase forks; alert on conflict. Or just manually rebase weekly. |
| `low_vram` refactor breaks edge cases we haven't tested | Medium | Phase 2 has explicit test matrix. Don't ship until all green. Keep old code path behind a `LEGACY_LOW_VRAM=1` env var for one release. |

---

## Success criteria

1. **`trellis-2-rocm-comfyui` public guide installs cleanly** with no `git apply` step. Just `git clone` of our forks.
2. **TRELLIS multi-view runs reliably** without the "load a different model to unstick" workaround. 10 consecutive runs across mixed model formats / pipeline_types succeed without a service restart.
3. **At least 2 of the 4 PR-able fixes are accepted upstream** within 30 days, or have explicit "won't fix" responses we can document.
4. **Issue threads exist** for the structural fixes (#4 low_vram, #6 multi-image paint) with clear repro steps that maintainers can act on independently.
5. **Hy3D textured + multi-view** confirmed working through the new fork path.

---

## Estimated total effort

- Phase 1 (fork + integrate): ~1 hr
- Phase 2 (low_vram refactor): ~2 hrs implementation + ~1 hr testing
- Phase 3 (issues + PRs): ~1 hr drafting (per repo)
- Phase 4 (public guide pivot): ~30 min

**Total: ~5–6 hours** spread across one or two sessions.

---

## Open questions for Phill

1. **Fork naming convention** — `toastmanAu/ComfyUI-Trellis2-GGUF` vs `toastmanAu/ComfyUI-Trellis2-GGUF-rocm` (more descriptive but longer)? Either works; mild preference for non-suffixed since it's a true fork that may upstream eventually.

2. **Public guide repo name** — keep `trellis-2-rocm-comfyui`, or rename to something more general now that it'll cover Hy3D too (e.g., `comfyui-3d-rocm-toolkit`)? Either is fine. Renaming costs link-rot but the current name is TRELLIS-specific.

3. **Phase 2 timing** — do you want the low_vram structural fix in this session's continuation, or should we ship Phases 1, 3, 4 first (which gets you a clean install path immediately) and tackle Phase 2 as a focused follow-up? My instinct: Phase 1 first to lock down a clean baseline, then Phase 2 as its own focused work.

4. **Rebase cadence for forks** — willing to set up GitHub Actions for nightly upstream pulls + auto-rebase, or prefer manual weekly?

---

## Next concrete action when ready

Phill confirms direction → we execute Phase 1 (~1 hour), then check in. The current "stale-state" issue continues to bite until Phase 2 lands but is liveable in the interim if you keep `low_vram=False` on cascade and avoid switching pipeline_types frequently within a session.
