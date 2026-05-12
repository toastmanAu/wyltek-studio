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

COMFYUI_HOST = "127.0.0.1"
COMFYUI_PORT = 8188
SENSENOVA_WORKER_URL = "http://127.0.0.1:9091"

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


async def all_statuses() -> dict:
    """Convenience: both workers concurrently for the UI status pill."""
    comfy, sense = await asyncio.gather(comfyui_status(), sensenova_status())
    return {"comfyui": comfy.to_dict(), "sensenova": sense.to_dict()}
