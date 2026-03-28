"""Backend registry — discovers and manages generation backends."""

from __future__ import annotations
from typing import Protocol, Callable, Awaitable

_backends: dict[str, "GenerationBackend"] = {}
_configs: dict[str, dict] = {}


class GenerationBackend(Protocol):
    async def generate(
        self,
        params: dict,
        output_path: str,
        on_progress: Callable[[int, str], Awaitable[None]],
    ) -> None: ...


def init_backends(backend_configs: dict):
    """Initialize all enabled backends from config."""
    global _configs
    _configs = backend_configs

    for name, cfg in backend_configs.items():
        if not cfg.get("enabled", False):
            continue
        try:
            backend = _create_backend(name, cfg)
            if backend:
                _backends[name] = backend
        except Exception as e:
            print(f"[open-palette] Failed to init backend '{name}': {e}")


def _create_backend(name: str, cfg: dict):
    if name == "comfyui":
        from backends.comfyui import ComfyUIBackend
        return ComfyUIBackend(cfg)
    elif name == "fooocus":
        from backends.fooocus import FooocusBackend
        return FooocusBackend(cfg)
    elif name == "a1111":
        from backends.a1111 import A1111Backend
        return A1111Backend(cfg)
    elif name == "pollinations":
        from backends.pollinations import PollinationsBackend
        return PollinationsBackend(cfg)
    elif name == "gemini":
        from backends.gemini import GeminiBackend
        return GeminiBackend(cfg)
    elif name == "stability":
        from backends.stability import StabilityBackend
        return StabilityBackend(cfg)
    elif name == "openai":
        from backends.openai_dalle import OpenAIBackend
        return OpenAIBackend(cfg)
    elif name == "replicate":
        from backends.replicate_backend import ReplicateBackend
        return ReplicateBackend(cfg)
    elif name == "huggingface":
        from backends.huggingface import HuggingFaceBackend
        return HuggingFaceBackend(cfg)
    return None


def get_backend(name: str) -> GenerationBackend | None:
    return _backends.get(name)


def list_backends() -> list[str]:
    return list(_backends.keys())
