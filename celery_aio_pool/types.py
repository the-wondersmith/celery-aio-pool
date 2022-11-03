"""Type definitions."""

# Future Imports
from __future__ import annotations

# Standard Library Imports
import typing

__all__ = (
    "AnyCallable",
    "AnyCoroutine",
    "AnyException",
)


AnyCallable = typing.Callable[..., typing.Any]
AnyException = typing.Union[Exception, typing.Type[Exception]]
AnyCoroutine = typing.Coroutine[typing.Any, typing.Any, typing.Any]
