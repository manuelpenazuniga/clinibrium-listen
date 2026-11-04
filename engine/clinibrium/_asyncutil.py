"""Small asyncio helpers shared by the orchestrator and the API.

`await_to_completion` was born in the pipeline (INV-4: an audit emission must
never be cut in half); plan T5 reuses it so a demo evaluation slot is released
only after its pipeline has finished.
"""
from __future__ import annotations

import asyncio
from typing import Any


async def await_to_completion(task: asyncio.Future[Any]) -> Any:
    """Awaits `task` until it finishes even if the caller is cancelled — once
    or repeatedly — while waiting (INV-4: an audit emission must never be cut
    in half). If a cancellation arrived, it is re-raised AFTER the task is done
    — also when the task then fails (the failure becomes the cancellation's
    __cause__; cancellation is never downgraded to an ordinary error). Without
    a cancellation, an exception raised by the task propagates as usual."""
    cancelled = False
    while True:
        try:
            result = await asyncio.shield(task)
            break
        except asyncio.CancelledError:
            if task.cancelled():  # the task itself was cancelled: nothing to wait for
                raise
            # Our caller was cancelled. The task may still be running OR may have
            # just finished (successfully or with an exception) in the same tick:
            # loop once more to collect its outcome and chain any failure.
            cancelled = True
        except Exception as exc:
            if cancelled:
                raise asyncio.CancelledError from exc
            raise
    if cancelled:
        raise asyncio.CancelledError
    return result
