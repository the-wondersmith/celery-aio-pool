"""Celery AIO Pool - Celery worker pool with support for asyncio coroutines as tasks."""

# Future Imports
from __future__ import annotations

# Standard Library Imports
import os

# Package-Level Imports
from celery_aio_pool.pool import AsyncIOPool
from celery_aio_pool.tracer import build_async_tracer

__pkg_name__ = "celery-aio-pool"
__version__ = "0.1.0-rc.8"  # x-release-please-version

__all__ = (
    "AsyncIOPool",
    "build_async_tracer",
    "patch_celery_tracer",
)


def patch_celery_tracer() -> bool:
    """Patch Celery's `celery.app.trace.build_tracer` utility to use the
    thread-bound worker event loop."""
    # Third-Party Imports
    import celery.app.trace

    if celery.app.trace.build_tracer is not build_async_tracer:
        celery.app.trace.warn(
            "Replacing Celery's default `build_tracer` utility "
            "w/ `build_async_tracer` from celery-aio-pool"
        )

        celery.app.trace.build_tracer = build_async_tracer

    #
    # The "stack protections" installed by :func:`celery.app.trace.setup_worker_optimizations`
    # cause the :class:`celery.Task` provided to bound task functions (i.e.
    # decorated with "@celery_app.task(bind=True)" to be malformed.
    # TODO: find out if this is the correct fix for that problem.
    #
    celery.app.trace.reset_worker_optimizations()
    return celery.app.trace.build_tracer is build_async_tracer


if os.getenv("CPA_AUTO_PATCH", False):
    patch_celery_tracer()
