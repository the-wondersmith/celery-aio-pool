"""Celery AIO Pool - Celery worker pool with support for asyncio coroutines as tasks."""

# Future Imports
from __future__ import annotations

# Standard Library Imports
import os

# Package-Level Imports
from celery_aio_pool.pool import AsyncIOPool
from celery_aio_pool.tracer import build_async_tracer

__pkg_name__ = "celery-aio-pool"
__version__ = "0.1.0-rc.0"  # x-release-please-version

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

    celery.app.trace.warn(
        "Replacing Celery's default `build_tracer` utility w/ `build_async_tracer` from celery-aio-pool"
    )

    celery.app.trace.build_tracer = build_async_tracer

    return celery.app.trace.build_tracer is build_async_tracer


if os.getenv("CPA_AUTO_PATCH", False):
    patch_celery_tracer()
