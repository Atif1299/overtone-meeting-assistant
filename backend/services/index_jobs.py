from __future__ import annotations

import asyncio
import logging
from threading import Lock
from typing import Any

from indexer.pipeline import run_index_job
from services import storage as storage_mod

logger = logging.getLogger(__name__)

_index_tasks: dict[str, asyncio.Task[Any]] = {}
_index_tasks_lock = Lock()


def _remove_task_if_same(presentation_id: str, task: asyncio.Task[Any] | None) -> None:
    with _index_tasks_lock:
        if task is None or _index_tasks.get(presentation_id) is task:
            _index_tasks.pop(presentation_id, None)


def is_index_job_running(presentation_id: str) -> bool:
    with _index_tasks_lock:
        task = _index_tasks.get(presentation_id)
    if not task:
        return False
    if task.done():
        _remove_task_if_same(presentation_id, task)
        return False
    return True


def dispatch_index_job(presentation_id: str) -> bool:
    if is_index_job_running(presentation_id):
        return False

    # Surface immediate progress to polling clients.
    storage_mod.update_presentation_meta(
        presentation_id,
        status="indexing",
        index_error=None,
    )

    loop = asyncio.get_running_loop()
    task = loop.create_task(_run_index_job_guarded(presentation_id))
    with _index_tasks_lock:
        _index_tasks[presentation_id] = task
    task.add_done_callback(lambda done_task: _on_task_done(presentation_id, done_task))
    return True


async def _run_index_job_guarded(presentation_id: str) -> None:
    try:
        await run_index_job(presentation_id)
    except Exception as exc:
        logger.exception("Unhandled index job failure for %s", presentation_id)
        storage_mod.update_presentation_meta(
            presentation_id,
            status="failed",
            index_error=f"Unexpected indexing failure: {exc}",
        )


def _on_task_done(presentation_id: str, task: asyncio.Task[Any]) -> None:
    _remove_task_if_same(presentation_id, task)
    if task.cancelled():
        logger.warning("Index job was cancelled for %s", presentation_id)
        return
    exc = task.exception()
    if exc:
        logger.error("Index job task crashed for %s: %s", presentation_id, exc)


def reset_index_jobs_for_tests() -> None:
    with _index_tasks_lock:
        tasks = list(_index_tasks.values())
        _index_tasks.clear()
    for task in tasks:
        task.cancel()
