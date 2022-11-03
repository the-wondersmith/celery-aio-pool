"""Test the asyncio pool w/ Celery's pytest contrib."""

# Future Imports
from __future__ import annotations

# Standard Library Imports
import asyncio as aio
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Coroutine,
    TypeVar,
)

# Third-Party Imports
import celery
import celery.apps.worker
import celery.canvas
import celery.contrib.testing.worker
import celery.result
import pytest

__all__ = tuple()


message: str = "Hello World!"
TaskWrappedFunction = Callable[..., Any]
TaskWrappedAsyncFunction = Callable[..., Coroutine[Any, Any, str]]


@pytest.mark.descriptor
def describe_sync_tasks() -> None:
    """Test that regular (synchronous) functions work as expected when
    decorated as Celery `Task`s and run with `AsyncIOPool`."""

    @pytest.mark.description
    def when_called_directly(sync_task: TaskWrappedFunction) -> None:
        """Test that Celery `Task`-wrapped regular (synchronous) functions
        behave as expected when called directly."""

        sync_task: TaskWrappedFunction

        reply: str = sync_task(data=message)

        assert reply == message.upper()

    @pytest.mark.description
    def when_called_with_delay(sync_task: celery.Task) -> None:
        """Test that Celery `Task`-wrapped regular (synchronous) functions
        behave as expected when run in a worker pool via `.delay()`."""

        sync_task: celery.Task

        result: celery.result.AsyncResult = sync_task.delay(
            data=message,
        )

        reply = result.get(timeout=60)

        assert reply == message.upper()

    @pytest.mark.description
    def when_called_with_apply_async(sync_task: celery.Task) -> None:
        """Test that Celery `Task`-wrapped regular (synchronous) functions
        behave as expected when run in a worker pool via `.apply_async()`."""

        sync_task: celery.Task

        result: celery.result.AsyncResult = sync_task.apply_async(
            kwargs=dict(data=message),
        )

        reply = result.get(timeout=60)

        assert reply == message.upper()


@pytest.mark.descriptor
def describe_async_tasks() -> None:
    """Test that coroutine (async) functions work as expected when decorated as
    Celery `Task`s and run with `AsyncIOPool`."""

    @pytest.mark.description
    def when_called_directly_from_synchronous_code(
        async_task: TaskWrappedAsyncFunction,
    ) -> None:
        """Test that `Task`-wrapped async functions behave as expected when
        called directly and then passed to an asyncio eventloop."""

        async_task: TaskWrappedAsyncFunction

        reply: str = aio.new_event_loop().run_until_complete(
            async_task(data=message),
        )

        assert reply == message.upper()

    @pytest.mark.anyio
    @pytest.mark.description
    async def when_called_directly_from_asynchronous_code(
        async_task: TaskWrappedAsyncFunction,
    ) -> None:
        """Test that `Task`-wrapped async functions behave as expected when
        called directly from inside a running asyncio eventloop."""

        async_task: TaskWrappedAsyncFunction

        reply: str = await async_task(data=message)

        assert reply == message.upper()

    @pytest.mark.description
    def when_called_with_delay(async_task: celery.Task) -> None:
        """Test that Celery `Task`-wrapped coroutine (async) functions behave
        as expected when run in a worker pool via `.delay()`."""

        async_task: celery.Task

        result: celery.result.AsyncResult = async_task.delay(
            data=message,
        )

        reply = result.get(timeout=60)

        assert reply == message.upper()

    @pytest.mark.description
    def when_called_with_apply_async(async_task: celery.Task) -> None:
        """Test that Celery `Task`-wrapped coroutine (async) functions behave
        as expected when run in a worker pool via `.apply_async()`."""

        async_task: celery.Task

        result: celery.result.AsyncResult = async_task.apply_async(
            kwargs=dict(data=message),
        )

        reply = result.get(timeout=60)

        assert reply == message.upper()
