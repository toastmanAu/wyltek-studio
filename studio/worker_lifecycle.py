"""Worker lifecycle controls for SenseNova worker + ComfyUI.

UI-facing replacement for "open a terminal and `systemctl --user stop comfyui`"
that the infographic precheck used to demand. All actions are routed through
``systemctl --user`` via ``asyncio.create_subprocess_exec`` (argv list, no
shell) and ``aiohttp`` probes; no sudo, no shell interpolation.

Two workers are managed here:

* **comfyui.service**  - image-edit / mesh-edit / worldgen backend on :8188.
  SenseNova-U1 wants the whole 24 GB GPU, so the infographic page needs to
  be able to stop this while it's working and start it again after.
* **sensenova-worker.service** - the long-lived inference daemon on :9091
  (port owned by ``studio.sensenova_worker``). Holds a 32 GB BF16 model
  GPU-resident; we never auto-start it at boot, only on demand from the
  infographic page.

Status model (``WorkerStatus``):

* ``stopped``  - unit is inactive AND nothing listening
* ``starting`` - unit is active but port not yet accepting (model loading)
* ``running``  - unit is active AND port is responsive
* ``crashed``  - unit is failed
* ``unknown``  - systemctl unavailable / probe error

The "loading model" gap matters: SenseNova takes ~25 s to load 32 GB of
weights before its HTTP port opens. The UI uses ``starting`` to show a
spinner and avoid double-clicks that would spawn a second start request.
"""
from __future__ import annotations

import asyncio
import logging
import socket
from dataclasses import dataclass
from typing import Literal

import aiohttp


log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Policy
# ---------------------------------------------------------------------------

COMFYUI_SERVICE = "comfyui.service"
SENSENOVA_SERVICE = "sensenova-worker.service"
HIDREAM_SERVICE = "hidream-worker.service"
MINICPM_SERVICE = "minicpm-worker.service"

COMFYUI_HOST = "127.0.0.1"
COMFYUI_PORT = 8188
SENSENOVA_WORKER_URL = "http://127.0.0.1:9091"
HIDREAM_WORKER_URL = "http://127.0.0.1:9092"
MINICPM_WORKER_URL = "http://127.0.0.1:9093"

# systemctl actions should return in well under a second on healthy hosts;
# allow a generous ceiling so a slow unit start doesn't surface as a UI error.
_SYSTEMCTL_TIMEOUT_S = 15.0

# Probe budgets - both workers are localhost, so anything over 1.5 s is a sign
# the process is wedged or starting; treat the difference as a status signal,
# not a failure.
_TCP_PROBE_TIMEOUT_S = 0.5
_HTTP_PROBE_TIMEOUT_S = 1.5


WorkerState = Literal["stopped", "starting", "running", "crashed", "unknown"]


@dataclass(frozen=True)
class WorkerStatus:
    name: str
    state: WorkerState
    unit_active: bool
    unit_substate: str
    listening: bool
    detail: dict

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "state": self.state,
            "unit_active": self.unit_active,
            "unit_substate": self.unit_substate,
            "listening": self.listening,
            "detail": self.detail,
        }


# ---------------------------------------------------------------------------
# systemctl wrappers (--user; no sudo, no shell)
# ---------------------------------------------------------------------------

class SystemctlError(RuntimeError):
    """systemctl wasn't on PATH or its subprocess timed out."""


async def _run_systemctl(*args: str) -> tuple[int, str, str]:
    """Run ``systemctl --user <args>`` and return ``(rc, stdout, stderr)``.

    Uses ``asyncio.create_subprocess_exec`` with an argv list - no shell
    interpolation possible. All callers in this module pass static literal
    strings (action verbs + service-name constants), so there's no untrusted
    input on this path either way.

    Returns non-zero return codes rather than raising, because some commands
    (``is-active`` returns 3 for inactive units) carry their answer in the
    return code itself.
    """
    try:
        proc = await asyncio.create_subprocess_exec(  # noqa: S603 - argv list, no shell
            "systemctl", "--user", *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError as exc:
        raise SystemctlError("systemctl not on PATH") from exc

    try:
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(), timeout=_SYSTEMCTL_TIMEOUT_S)
    except asyncio.TimeoutError as exc:
        proc.kill()
        raise SystemctlError(
            f"systemctl --user {' '.join(args)} timed out") from exc

    return proc.returncode or 0, stdout.decode().strip(), stderr.decode().strip()


async def _unit_active(service: str) -> tuple[bool, str]:
    """Return ``(is_active, substate)``.

    ``is-active`` prints one of: active, inactive, failed, activating,
    deactivating, reloading. We treat ``active`` and ``activating`` as
    "active" for status purposes and surface the raw word as substate.
    """
    try:
        _, out, _ = await _run_systemctl("is-active", service)
    except SystemctlError:
        return False, "unknown"
    out = out.strip() or "unknown"
    return out in ("active", "activating", "reloading"), out


# ---------------------------------------------------------------------------
# Liveness probes
# ---------------------------------------------------------------------------

def _tcp_alive(host: str, port: int, timeout_s: float) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout_s):
            return True
    except OSError:
        return False


async def _http_get_json(url: str, timeout_s: float) -> dict | None:
    """GET ``url`` and parse JSON; return ``None`` on any failure."""
    try:
        timeout = aiohttp.ClientTimeout(total=timeout_s)
        async with aiohttp.ClientSession(timeout=timeout) as s:
            async with s.get(url) as resp:
                if resp.status >= 400:
                    return None
                return await resp.json(content_type=None)
    except Exception:
        return None


def _classify(unit_active: bool, substate: str, listening: bool) -> WorkerState:
    """Project (unit state, port state) onto the simpler UI ladder."""
    if substate == "failed":
        return "crashed"
    if substate == "unknown":
        return "unknown"
    if unit_active and listening:
        return "running"
    if unit_active and not listening:
        return "starting"
    return "stopped"


# ---------------------------------------------------------------------------
# Public: ComfyUI
# ---------------------------------------------------------------------------

async def comfyui_status() -> WorkerStatus:
    unit_active, sub = await _unit_active(COMFYUI_SERVICE)
    listening = await asyncio.get_running_loop().run_in_executor(
        None, _tcp_alive, COMFYUI_HOST, COMFYUI_PORT, _TCP_PROBE_TIMEOUT_S)
    state = _classify(unit_active, sub, listening)
    return WorkerStatus(
        name="comfyui",
        state=state,
        unit_active=unit_active,
        unit_substate=sub,
        listening=listening,
        detail={"service": COMFYUI_SERVICE,
                "host": COMFYUI_HOST, "port": COMFYUI_PORT},
    )


async def comfyui_start() -> dict:
    rc, _, err = await _run_systemctl("start", COMFYUI_SERVICE)
    return {"ok": rc == 0, "rc": rc, "error": err or None}


async def comfyui_stop() -> dict:
    rc, _, err = await _run_systemctl("stop", COMFYUI_SERVICE)
    return {"ok": rc == 0, "rc": rc, "error": err or None}


async def comfyui_restart() -> dict:
    rc, _, err = await _run_systemctl("restart", COMFYUI_SERVICE)
    return {"ok": rc == 0, "rc": rc, "error": err or None}


# ---------------------------------------------------------------------------
# Public: SenseNova worker
# ---------------------------------------------------------------------------

async def sensenova_status() -> WorkerStatus:
    """Status for sensenova-worker.service + :9091 HTTP probe.

    Distinguishes ``starting`` (unit active, port silent - loading 32 GB
    of BF16 weights) from ``running`` (unit active, /status responds with
    ``loaded: true``).
    """
    unit_active, sub = await _unit_active(SENSENOVA_SERVICE)
    status_json = await _http_get_json(
        f"{SENSENOVA_WORKER_URL}/status", _HTTP_PROBE_TIMEOUT_S)
    listening = status_json is not None

    state = _classify(unit_active, sub, listening)
    detail: dict = {"service": SENSENOVA_SERVICE, "url": SENSENOVA_WORKER_URL}
    if status_json:
        detail.update({
            "loaded": status_json.get("loaded"),
            "vram_gb": status_json.get("vram_gb"),
            "vram_max_gb": status_json.get("vram_max_gb"),
        })
        # The worker advertises a model load only once weights are fully on
        # GPU. Between unit start and "loaded:true" we still report
        # "starting" so the UI keeps the spinner.
        if state == "running" and status_json.get("loaded") is False:
            state = "starting"
    return WorkerStatus(
        name="sensenova-worker",
        state=state,
        unit_active=unit_active,
        unit_substate=sub,
        listening=listening,
        detail=detail,
    )


async def sensenova_start() -> dict:
    rc, _, err = await _run_systemctl("start", SENSENOVA_SERVICE)
    return {"ok": rc == 0, "rc": rc, "error": err or None}


async def sensenova_stop() -> dict:
    """Stop the sensenova worker.

    Hits ``/shutdown`` first so the worker can release GPU caches cleanly,
    then issues ``systemctl stop`` to guarantee the unit is inactive even if
    the HTTP path is wedged. The unit is set to ``Restart=on-failure``, so a
    clean exit via ``/shutdown`` doesn't bounce it.
    """
    try:
        timeout = aiohttp.ClientTimeout(total=_HTTP_PROBE_TIMEOUT_S)
        async with aiohttp.ClientSession(timeout=timeout) as s:
            await s.post(f"{SENSENOVA_WORKER_URL}/shutdown")
    except Exception:
        pass

    rc, _, err = await _run_systemctl("stop", SENSENOVA_SERVICE)
    return {"ok": rc == 0, "rc": rc, "error": err or None}


async def sensenova_restart() -> dict:
    """Restart for cancel-in-flight: SIGTERM the worker so any blocked CUDA
    call dies, then let systemd bring it back up. Faster than stop+start
    because systemd handles sequencing, and gives the same GPU-flush
    behaviour as a fresh boot.
    """
    rc, _, err = await _run_systemctl("restart", SENSENOVA_SERVICE)
    return {"ok": rc == 0, "rc": rc, "error": err or None}


# ---------------------------------------------------------------------------
# Public: HiDream-O1-Image worker
# ---------------------------------------------------------------------------

async def hidream_status() -> WorkerStatus:
    """Status for hidream-worker.service + :9092 HTTP probe.

    Distinguishes ``starting`` (unit active, port silent - 8 BF16 shards still
    loading) from ``running`` (unit active, /status responds with
    ``loaded: true``). Cold load is ~25 s, warm cache ~4 s.
    """
    unit_active, sub = await _unit_active(HIDREAM_SERVICE)
    status_json = await _http_get_json(
        f"{HIDREAM_WORKER_URL}/status", _HTTP_PROBE_TIMEOUT_S)
    listening = status_json is not None

    state = _classify(unit_active, sub, listening)
    detail: dict = {"service": HIDREAM_SERVICE, "url": HIDREAM_WORKER_URL}
    if status_json:
        detail.update({
            "loaded": status_json.get("loaded"),
            "vram_gb": status_json.get("vram_gb"),
            "vram_max_gb": status_json.get("vram_max_gb"),
        })
        if state == "running" and status_json.get("loaded") is False:
            state = "starting"
    return WorkerStatus(
        name="hidream-worker",
        state=state,
        unit_active=unit_active,
        unit_substate=sub,
        listening=listening,
        detail=detail,
    )


async def hidream_start() -> dict:
    rc, _, err = await _run_systemctl("start", HIDREAM_SERVICE)
    return {"ok": rc == 0, "rc": rc, "error": err or None}


async def hidream_stop() -> dict:
    """Stop the HiDream worker.

    Hits ``/shutdown`` first so the worker can release GPU caches cleanly,
    then issues ``systemctl stop`` to guarantee the unit is inactive even if
    the HTTP path is wedged. Unit is set ``Restart=on-failure`` so a clean
    exit via ``/shutdown`` doesn't bounce it.
    """
    try:
        timeout = aiohttp.ClientTimeout(total=_HTTP_PROBE_TIMEOUT_S)
        async with aiohttp.ClientSession(timeout=timeout) as s:
            await s.post(f"{HIDREAM_WORKER_URL}/shutdown")
    except Exception:
        pass

    rc, _, err = await _run_systemctl("stop", HIDREAM_SERVICE)
    return {"ok": rc == 0, "rc": rc, "error": err or None}


async def hidream_restart() -> dict:
    rc, _, err = await _run_systemctl("restart", HIDREAM_SERVICE)
    return {"ok": rc == 0, "rc": rc, "error": err or None}


# ---------------------------------------------------------------------------
# Public: MiniCPM-V-4.6 worker (idle CPU-offload)
# ---------------------------------------------------------------------------

async def minicpm_status() -> WorkerStatus:
    """Status for minicpm-worker.service + :9093 HTTP probe.

    The MiniCPM worker is unusual: it can be ``running`` even when no VRAM
    is allocated (idle offloaded to CPU). The ``device`` field in the JSON
    payload — "cuda" or "cpu" — is the real residency signal, surfaced
    here in ``detail.device`` so the UI can show "loaded (idle on CPU)"
    distinctly from "loaded (active on GPU)".
    """
    unit_active, sub = await _unit_active(MINICPM_SERVICE)
    status_json = await _http_get_json(
        f"{MINICPM_WORKER_URL}/status", _HTTP_PROBE_TIMEOUT_S)
    listening = status_json is not None

    state = _classify(unit_active, sub, listening)
    detail: dict = {"service": MINICPM_SERVICE, "url": MINICPM_WORKER_URL}
    if status_json:
        detail.update({
            "loaded": status_json.get("loaded"),
            "device": status_json.get("device"),
            "idle_s": status_json.get("idle_s"),
            "vram_gb": status_json.get("vram_gb"),
            "vram_max_gb": status_json.get("vram_max_gb"),
        })
        # Unlike sensenova/hidream, MiniCPM reports loaded:true the moment
        # weights are read from disk (still on CPU). We treat that as
        # "running" — the worker is ready to serve; first request will
        # incur a CPU->GPU move cost, surfaced in elapsed_s on /describe.
        if state == "running" and status_json.get("loaded") is False:
            state = "starting"
    return WorkerStatus(
        name="minicpm-worker",
        state=state,
        unit_active=unit_active,
        unit_substate=sub,
        listening=listening,
        detail=detail,
    )


async def minicpm_start() -> dict:
    rc, _, err = await _run_systemctl("start", MINICPM_SERVICE)
    return {"ok": rc == 0, "rc": rc, "error": err or None}


async def minicpm_stop() -> dict:
    """Stop the MiniCPM worker. Hits /shutdown first for a clean GPU
    flush; the unit is ``Restart=on-failure`` so a clean /shutdown exit
    doesn't bounce it."""
    try:
        timeout = aiohttp.ClientTimeout(total=_HTTP_PROBE_TIMEOUT_S)
        async with aiohttp.ClientSession(timeout=timeout) as s:
            await s.post(f"{MINICPM_WORKER_URL}/shutdown")
    except Exception:
        pass

    rc, _, err = await _run_systemctl("stop", MINICPM_SERVICE)
    return {"ok": rc == 0, "rc": rc, "error": err or None}


async def minicpm_restart() -> dict:
    rc, _, err = await _run_systemctl("restart", MINICPM_SERVICE)
    return {"ok": rc == 0, "rc": rc, "error": err or None}


async def all_statuses() -> dict:
    """Convenience: all workers concurrently for the UI status pill."""
    comfy, sense, hidream, minicpm = await asyncio.gather(
        comfyui_status(), sensenova_status(),
        hidream_status(), minicpm_status(),
    )
    return {
        "comfyui": comfy.to_dict(),
        "sensenova": sense.to_dict(),
        "hidream": hidream.to_dict(),
        "minicpm": minicpm.to_dict(),
    }


# ---------------------------------------------------------------------------
# Orchestration: auto-switch between conflicting workers
# ---------------------------------------------------------------------------

# Time to let the kernel + ROCm driver release VRAM after a worker shutdown
# before we start the next one. PyTorch's allocator releases on process exit,
# but the actual cudaMemGetInfo-visible free can lag a few seconds. Without
# this settle, the new worker can OOM at load while the dying worker's
# arenas are still resident.
_VRAM_SETTLE_S = 6.0

# Polling cadence for waiting on a worker to finish loading. Status probes
# are cheap localhost HTTPs but we don't want to hammer.
_LOAD_POLL_INTERVAL_S = 2.0

# Default ceiling for ``ensure_loaded`` — covers cold load (~25 s) + a stop/
# start cycle (~10 s) + headroom for slow CDNs / disk. Caller can override.
_ENSURE_TIMEOUT_S = 120.0


# Worker name → (status_fn, start_fn, stop_fn). Add new workers here when
# they join the arbitration.
_WORKER_TABLE: dict[str, tuple] = {
    "sensenova": (sensenova_status, sensenova_start, sensenova_stop),
    "hidream":   (hidream_status,   hidream_start,   hidream_stop),
    "comfyui":   (comfyui_status,   comfyui_start,   comfyui_stop),
    "minicpm":   (minicpm_status,   minicpm_start,   minicpm_stop),
}

# Default conflict graph: which workers contend for the same VRAM. ComfyUI
# is intentionally omitted from sensenova/hidream conflicts because it
# usually idles with no model resident — only an active ComfyUI render
# truly conflicts, and that's surfaced by the render attempt OOMing rather
# than worth auto-stopping (ComfyUI loses state when killed).
#
# MiniCPM is intentionally NOT a conflict with anyone: it can idle on CPU
# (releasing its 2.5 GB of VRAM voluntarily), and even when active it only
# needs ~3-4 GB peak — comfortably co-resident with HiDream's ~16 GB
# without an OOM. The lifecycle in studio.minicpm_worker handles the
# residency dance internally.
_DEFAULT_CONFLICTS: dict[str, list[str]] = {
    "sensenova": ["hidream"],
    "hidream":   ["sensenova"],
    "comfyui":   [],
    "minicpm":   [],
}


class WorkerArbitrationError(RuntimeError):
    """ensure_loaded couldn't reach a ready state for the target worker."""


async def ensure_loaded(
    target: str,
    *,
    conflicts: list[str] | None = None,
    timeout_s: float = _ENSURE_TIMEOUT_S,
    on_status: callable | None = None,
) -> None:
    """Make sure ``target`` worker is running and ``loaded: true``.

    If the target is already loaded, returns immediately. Otherwise stops
    any conflicting workers first (default conflict graph from
    ``_DEFAULT_CONFLICTS``), waits for VRAM to settle, starts the target,
    and polls until either ``loaded: true`` or the timeout elapses.

    ``on_status(msg)`` is an optional async callback for surfacing progress
    to the UI — the orchestrator emits "stopping sensenova", "starting
    hidream", "waiting for model load" etc.

    Raises ``WorkerArbitrationError`` on timeout, crash, or unknown target.
    """
    if target not in _WORKER_TABLE:
        raise WorkerArbitrationError(
            f"unknown worker {target!r}; known: {sorted(_WORKER_TABLE)}")

    if conflicts is None:
        conflicts = _DEFAULT_CONFLICTS.get(target, [])

    async def _notify(msg: str) -> None:
        if on_status is not None:
            try:
                await on_status(msg)
            except Exception:  # noqa: BLE001
                pass  # progress is best-effort

    target_status_fn, target_start_fn, _ = _WORKER_TABLE[target]

    # Fast path: target already loaded.
    s = await target_status_fn()
    if s.state == "running" and s.detail.get("loaded") is True:
        await _notify(f"{target} already loaded")
        return

    # Stop conflicts (in parallel; they're independent).
    stop_tasks = []
    stopped_any = False
    for c in conflicts:
        if c not in _WORKER_TABLE:
            continue
        c_status_fn, _, c_stop_fn = _WORKER_TABLE[c]
        cs = await c_status_fn()
        if cs.unit_active or cs.listening:
            log.info(f"ensure_loaded({target}): stopping conflict {c}")
            await _notify(f"stopping {c} (it's holding the GPU)")
            stop_tasks.append(c_stop_fn())
            stopped_any = True
    if stop_tasks:
        await asyncio.gather(*stop_tasks)
        await _notify(f"{target}: waiting {_VRAM_SETTLE_S:.0f}s for VRAM to settle")
        await asyncio.sleep(_VRAM_SETTLE_S)

    # Start the target (idempotent if already starting — systemd handles it).
    log.info(f"ensure_loaded({target}): starting worker")
    await _notify(f"starting {target} worker")
    await target_start_fn()

    # Poll until loaded or timeout.
    await _notify(f"{target}: loading model (cold ~25s, warm ~5s)")
    loop = asyncio.get_event_loop()
    deadline = loop.time() + timeout_s
    while loop.time() < deadline:
        s = await target_status_fn()
        if s.state == "running" and s.detail.get("loaded") is True:
            elapsed = timeout_s - (deadline - loop.time())
            log.info(
                f"ensure_loaded({target}): ready in {elapsed:.1f}s "
                f"(vram_gb={s.detail.get('vram_gb')})"
            )
            await _notify(f"{target} loaded ({s.detail.get('vram_gb','?')} GB VRAM)")
            return
        if s.state == "crashed":
            raise WorkerArbitrationError(
                f"{target}-worker crashed during startup. "
                f"Check `journalctl --user -u {target}-worker.service`.")
        await asyncio.sleep(_LOAD_POLL_INTERVAL_S)

    raise WorkerArbitrationError(
        f"{target}-worker didn't become ready within {timeout_s:.0f}s. "
        f"Last state: {s.state}, loaded={s.detail.get('loaded')}.")
