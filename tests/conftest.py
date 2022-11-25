"""Test configuration and fixtures for `celery-aio-pool`."""

# Future Imports
from __future__ import annotations

# Standard Library Imports
import asyncio as aio
import copy
import subprocess
import sys
import time
from operator import methodcaller
from pathlib import Path
from typing import (
    Any,
    Generator,
)
from uuid import UUID

# Third-Party Imports
import celery  # noqaL F401
import celery.concurrency.prefork
import pytest

# Package-Level Imports
import celery_aio_pool as aio_pool

__all__ = tuple()

assert aio_pool.patch_celery_tracer()

conf_path = Path(__file__).resolve()
cap_dir = conf_path.parent.parent.resolve()

root = cap_dir / "test-output"
logs = root / "logs"
broker = root / "broker"
results = root / "results"
msg_dir = broker / "messages"
processed = broker / "processed"


test_dirs = (
    root,
    logs,
    broker,
    msg_dir,
    results,
    processed,
)

frozenset(
    map(
        methodcaller(
            "mkdir",
            mode=0o777,
            parents=True,
            exist_ok=True,
        ),
        test_dirs,
    )
)


session_app: celery.Celery = celery.Celery(
    without_mingle=False,
    without_gossip=False,
    result_persistent=True,
    task_always_eager=False,
    task_ignore_result=False,
    main="test-celery-aio-pool",
    task_store_eager_result=True,
    imports=("tests", "conftest"),
    result_backend=f"file://{results}",
    broker_url=f"filesystem://{broker}",
    worker_pool=aio_pool.pool.AsyncIOPool,
    broker_transport_options={
        "data_folder_in": str(msg_dir),
        "data_folder_out": str(msg_dir),
        "data_folder_processed": str(processed),
    },
)


def _request_attributes(request: Any) -> dict[str, bool]:
    """Extract the commonly used / referenced attributes of the supplied `Task`
    request and inspect them for validity."""

    host, info = request.hostname, request.delivery_info

    try:
        task_id, root_id, correlation_id = map(
            UUID,
            (
                request.id,
                request.root_id,
                request.correlation_id,
            ),
        )
    except (ValueError, TypeError, AttributeError):
        task_id, root_id, correlation_id = (
            None,
            None,
            None,
        )

    return {
        "id": bool(task_id),
        "root_id": bool(root_id),
        "correlation_id": bool(correlation_id),
        "hostname": host and isinstance(host, str),
        "delivery_info": info and isinstance(info, dict),
    }


@session_app.task
def _sync_task(data: str) -> str:
    """A simple dummy function."""
    time.sleep(1)

    data = data.upper()

    return data


@session_app.task
async def _async_task(data: str) -> str:
    """A simple dummy async function."""
    await aio.sleep(1)

    data = data.upper()

    return data


@session_app.task(bind=True)
def _bound_sync_task(self: celery.Task) -> dict[str, bool]:
    """Guard against malformed / improperly populated request objects."""
    return _request_attributes(request=self.request)


@session_app.task(bind=True)
async def _bound_async_task(self: celery.Task) -> dict[str, bool]:
    """Guard against malformed / improperly populated request objects."""
    return _request_attributes(request=self.request)


def _run_celery_worker() -> None:
    """Replace the current `sys.argv` contents with the supplied arguments and
    call Celery's `main` method."""

    # Third-Party Imports
    import celery.__main__

    original_argv = copy.deepcopy(sys.argv)

    sys.argv.clear()
    sys.argv.extend(
        (
            "celery",
            "--app=tests.conftest:session_app",
            "worker",
            "--task-events",
            "--loglevel=debug",
        )
    )

    celery.__main__.main()

    sys.argv.clear()
    sys.argv.extend(original_argv)


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    """Specify the backend for `AnyIO`'s eventloop."""
    return "asyncio"


@pytest.fixture(scope="session", autouse=True)
def sync_task() -> Generator[celery.Task, None, None]:
    """A session-scoped Celery `Task`."""
    yield _sync_task


@pytest.fixture(scope="session", autouse=True)
def async_task() -> Generator[celery.Task, None, None]:
    """A session-scoped async Celery `Task`."""
    yield _async_task


@pytest.fixture(scope="session", autouse=True)
def bound_sync_task() -> Generator[celery.Task, None, None]:
    """A session-scoped Celery `Task` with `bind=True` enabled."""
    yield _bound_sync_task


@pytest.fixture(scope="session", autouse=True)
def bound_async_task() -> Generator[celery.Task, None, None]:
    """A session-scoped async Celery `Task` with `bind=True` enabled."""
    yield _bound_async_task


@pytest.fixture(scope="session", autouse=True)
def session_worker() -> Generator[Any, None, None]:
    """A session-scoped Celery worker running in a separate process from the
    test suite."""

    worker_process = subprocess.Popen(
        (sys.executable, str(conf_path)),
        cwd=str(cap_dir),
        stderr=(logs / "stderr.log").open("wb+"),
        stdout=(logs / "stdout.log").open("wb+"),
    )

    time.sleep(2.0)

    yield worker_process

    worker_process.kill()


if __name__ == "__main__":
    _run_celery_worker()
