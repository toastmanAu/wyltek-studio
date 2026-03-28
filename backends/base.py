"""Base class for generation backends."""

from __future__ import annotations
from typing import Callable, Awaitable


class BaseBackend:
    def __init__(self, config: dict):
        self.config = config
        self.url = config.get("url", "")
        self.api_key = config.get("api_key") or ""

    async def generate(
        self,
        params: dict,
        output_path: str,
        on_progress: Callable[[int, str], Awaitable[None]],
    ) -> None:
        raise NotImplementedError
