"""Structured ownership for existing concurrent discovery operations."""

from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from typing import Any, TypeVar

T = TypeVar("T")


async def gather_workers(tasks: list[asyncio.Task[T]]) -> list[T]:
    """Cancel and join every owned sibling before returning an error to its parent."""
    try:
        return list(await asyncio.gather(*tasks))
    except BaseException:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        raise


async def gather_owned(*work: Coroutine[Any, Any, T]) -> list[T]:
    """Run platform/query coroutines with the same bounded lifetime as their parent."""
    return await gather_workers([asyncio.create_task(item) for item in work])
