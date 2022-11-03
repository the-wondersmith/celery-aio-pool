"""A custom implementation of Celery's built-in `celery.app.trace.build_tracer`
utility."""

# pylint: unused-argument

# Future Imports
from __future__ import annotations

# Standard Library Imports
import logging
import os
import time
from typing import (
    Any,
    Callable,
    Optional,
    Sequence,
    Type,
)

# Third-Party Imports
import celery
import celery.app
import celery.app.task
import celery.app.trace
import celery.canvas
import celery.exceptions
import celery.loaders
import celery.loaders.app

# Package-Level Imports
from celery_aio_pool.types import AnyException

__all__ = ("build_async_tracer",)


# noinspection PyUnusedLocal
def build_async_tracer(
    name: str,
    task: celery.Task | celery.local.PromiseProxy,
    loader: Optional[celery.loaders.app.AppLoader] = None,
    hostname: Optional[str] = None,
    store_errors: bool = True,
    Info: Type[celery.app.trace.TraceInfo] = celery.app.trace.TraceInfo,
    eager: bool = False,
    propagate: bool = False,
    app: Optional[celery.Celery] = None,
    monotonic: Callable[[], int] = time.monotonic,
    trace_ok_t: Type[celery.app.trace.trace_ok_t] = celery.app.trace.trace_ok_t,
    IGNORE_STATES: frozenset[str] = celery.app.trace.IGNORE_STATES,
) -> Callable[[str, tuple[Any, ...], dict[str, Any], Any], celery.app.trace.trace_ok_t]:
    """Return a function that traces task execution.

    Catches all exceptions and updates result backend with the
    state and result.

    If the call was successful, it saves the result to the task result
    backend, and sets the task status to `"SUCCESS"`.

    If the call raises :exc:`~@Retry`, it extracts
    the original exception, uses that as the result and sets the task state
    to `"RETRY"`.

    If the call results in an exception, it saves the exception as the task
    result, and sets the task state to `"FAILURE"`.

    Return a function that takes the following arguments:

        uuid: The id of the task.
        args: List of positional args to pass on to the function.
        kwargs: Keyword arguments mapping to pass on to the function.
        request: Request dict.
    """

    # pylint: disable=too-many-statements

    # If the task doesn't define a custom __call__ method
    # we optimize it away by simply calling the run method directly,
    # saving the extra method call and a line less in the stack trace.
    fun = task if celery.app.trace.task_has_custom(task, "__call__") else task.run

    loader = loader or app.loader
    ignore_result = task.ignore_result
    track_started = task.track_started
    track_started = not eager and (task.track_started and not ignore_result)

    publish_result = (
        True
        if (eager and not ignore_result and task.store_eager_result)
        else bool(not eager and not ignore_result)
    )

    deduplicate_successful_tasks = (
        (app.conf.task_acks_late or task.acks_late)
        and app.conf.worker_deduplicate_successful_tasks
        and app.backend.persistent
    )

    hostname = hostname or celery.app.trace.gethostname()
    inherit_parent_priority = app.conf.task_inherit_parent_priority

    loader_task_init = loader.on_task_init
    loader_cleanup = loader.on_process_cleanup

    task_before_start = None
    task_on_success = None
    task_after_return = None

    if celery.app.trace.task_has_custom(task, "before_start"):
        task_before_start = task.before_start

    if celery.app.trace.task_has_custom(task, "on_success"):
        task_on_success = task.on_success

    if celery.app.trace.task_has_custom(task, "after_return"):
        task_after_return = task.after_return

    pid = os.getpid()

    request_stack = task.request_stack
    push_request = request_stack.push
    pop_request = request_stack.pop
    push_task = celery.app.trace._task_stack.push
    pop_task = celery.app.trace._task_stack.pop
    _does_info = celery.app.trace.logger.isEnabledFor(logging.INFO)
    result_repr_maxsize = task.resultrepr_maxsize

    pre_run_receivers = celery.app.trace.signals.task_prerun.receivers
    post_run_receivers = celery.app.trace.signals.task_postrun.receivers
    success_receivers = celery.app.trace.signals.task_success.receivers

    # Third-Party Imports
    from celery import canvas

    # Package-Level Imports
    from celery_aio_pool.pool import AsyncIOPool

    signature = canvas.maybe_signature  # maybe_ does not clone if already

    # noinspection PyUnusedLocal
    def on_error(
        request: celery.app.task.Context,
        exc: AnyException,
        uuid: str,
        state: str = celery.app.trace.FAILURE,
        call_errbacks: bool = True,
    ) -> tuple[Info, Any, Any, Any]:
        """Handle any errors raised by a `Task`'s execution."""

        if propagate:
            raise

        I = Info(state, exc)
        R = I.handle_error_state(
            task,
            request,
            eager=eager,
            call_errbacks=call_errbacks,
        )

        return I, R, I.state, I.retval

    def trace_task(
        uuid: str,
        args: Sequence[Any],
        kwargs: dict[str, Any],
        request: Optional[dict[str, Any]] = None,
    ) -> trace_ok_t:
        """Execute and trace a `Task`."""

        # R      - is the possibly prepared return value.
        # I      - is the Info object.
        # T      - runtime
        # Rstr   - textual representation of return value
        # retval - is the always unmodified return value.
        # state  - is the resulting task state.

        # This function is very long because we've unrolled all the calls
        # for performance reasons, and because the function is so long
        # we want the main variables (I, and R) to stand out visually from the
        # the rest of the variables, so breaking PEP8 is worth it ;)
        R = I = T = Rstr = retval = state = None
        task_request = None
        time_start = monotonic()

        try:
            try:
                callable(kwargs.items)
            except AttributeError:
                raise celery.app.trace.InvalidTaskError("Task keyword arguments is not a mapping")

            task_request = celery.app.trace.Context(
                request or {},
                args=args,
                called_directly=False,
                kwargs=kwargs,
            )

            redelivered = task_request.delivery_info and task_request.delivery_info.get(
                "redelivered",
                False,
            )

            if deduplicate_successful_tasks and redelivered:
                if task_request.id in celery.app.trace.successful_requests:
                    return trace_ok_t(R, I, T, Rstr)

                r = celery.app.trace.AsyncResult(
                    task_request.id,
                    app=app,
                )

                try:
                    state = r.state
                except celery.app.trace.BackendGetMetaError:
                    pass
                else:
                    if state == celery.app.trace.SUCCESS:
                        celery.app.trace.info(
                            celery.app.trace.LOG_IGNORED,
                            {
                                "id": task_request.id,
                                "name": celery.app.trace.get_task_name(
                                    task_request,
                                    name,
                                ),
                                "description": "Task already completed successfully.",
                            },
                        )
                        return trace_ok_t(R, I, T, Rstr)

            push_task(task)

            root_id = task_request.root_id or uuid
            task_priority = (
                task_request.delivery_info.get(
                    "priority",
                )
                if inherit_parent_priority
                else None
            )

            push_request(task_request)

            try:
                # -*- PRE -*-
                if pre_run_receivers:
                    celery.app.trace.send_prerun(
                        sender=task,
                        task_id=uuid,
                        task=task,
                        args=args,
                        kwargs=kwargs,
                    )

                AsyncIOPool.run_in_pool(loader_task_init, uuid, task)

                if track_started:
                    task.backend.store_result(
                        uuid,
                        {
                            "pid": pid,
                            "hostname": hostname,
                        },
                        celery.app.trace.STARTED,
                        request=task_request,
                    )

                # -*- TRACE -*-
                try:
                    if task_before_start:
                        AsyncIOPool.run_in_pool(
                            task_before_start,
                            uuid,
                            args,
                            kwargs,
                        )

                    R = retval = AsyncIOPool.run_in_pool(fun, *args, **kwargs)
                    state = celery.app.trace.SUCCESS

                except celery.app.trace.Reject as exc:
                    I, R = Info(celery.app.trace.REJECTED, exc,), celery.app.trace.ExceptionInfo(
                        internal=True,
                    )
                    state, retval = I.state, I.retval
                    I.handle_reject(
                        task,
                        task_request,
                    )
                    celery.app.trace.traceback_clear(exc)
                except celery.app.trace.Ignore as exc:
                    I, R = Info(celery.app.trace.IGNORED, exc,), celery.app.trace.ExceptionInfo(
                        internal=True,
                    )
                    state, retval = I.state, I.retval
                    I.handle_ignore(task, task_request)
                    celery.app.trace.traceback_clear(exc)

                except celery.app.trace.Retry as exc:
                    I, R, state, retval = on_error(
                        task_request,
                        exc,
                        uuid,
                        celery.app.trace.RETRY,
                        call_errbacks=False,
                    )
                    celery.app.trace.traceback_clear(exc)

                except Exception as exc:
                    I, R, state, retval = on_error(
                        task_request,
                        exc,
                        uuid,
                    )
                    celery.app.trace.traceback_clear(exc)

                except BaseException:
                    raise
                else:
                    try:
                        # callback tasks must be applied before the result is
                        # stored, so that result.children is populated.

                        # groups are called inline and will store trail
                        # separately, so need to call them separately
                        # so that the trail's not added multiple times :(
                        # (Issue #1936)
                        callbacks = task.request.callbacks

                        if callbacks:
                            if len(task.request.callbacks) > 1:

                                sigs, groups = [], []

                                for sig in callbacks:
                                    sig = signature(sig, app=app)

                                    if isinstance(sig, celery.app.trace.group):
                                        groups.append(sig)
                                    else:
                                        sigs.append(sig)

                                for group_ in groups:
                                    group_.apply_async(
                                        (retval,),
                                        parent_id=uuid,
                                        root_id=root_id,
                                        priority=task_priority,
                                    )

                                if sigs:
                                    celery.app.trace.group(sigs, app=app,).apply_async(
                                        (retval,),
                                        parent_id=uuid,
                                        root_id=root_id,
                                        priority=task_priority,
                                    )
                            else:
                                signature(callbacks[0], app=app,).apply_async(
                                    (retval,),
                                    parent_id=uuid,
                                    root_id=root_id,
                                    priority=task_priority,
                                )

                        # execute first task in chain
                        chain = task_request.chain

                        if chain:
                            _chain_signature = signature(chain.pop(), app=app)
                            _chain_signature.apply_async(
                                (retval,),
                                chain=chain,
                                parent_id=uuid,
                                root_id=root_id,
                                priority=task_priority,
                            )

                        task.backend.mark_as_done(
                            uuid,
                            retval,
                            task_request,
                            publish_result,
                        )

                    except celery.app.trace.EncodeError as exc:
                        I, R, state, retval = on_error(
                            task_request,
                            exc,
                            uuid,
                        )

                    else:
                        Rstr = celery.app.trace.saferepr(R, result_repr_maxsize)
                        T = monotonic() - time_start

                        if task_on_success:
                            AsyncIOPool.run_in_pool(
                                task_on_success,
                                retval,
                                uuid,
                                args,
                                kwargs,
                            )

                        if success_receivers:
                            celery.app.trace.send_success(
                                sender=task,
                                result=retval,
                            )

                        if _does_info:
                            celery.app.trace.info(
                                celery.app.trace.LOG_SUCCESS,
                                {
                                    "id": uuid,
                                    "name": celery.app.trace.get_task_name(
                                        task_request,
                                        name,
                                    ),
                                    "return_value": Rstr,
                                    "runtime": T,
                                    "args": celery.app.trace.safe_repr(args),
                                    "kwargs": celery.app.trace.safe_repr(kwargs),
                                },
                            )

                # -* POST *-
                if state not in IGNORE_STATES:
                    if task_after_return:
                        AsyncIOPool.run_in_pool(
                            task_after_return,
                            state,
                            retval,
                            uuid,
                            args,
                            kwargs,
                            None,
                        )
            finally:
                try:
                    if post_run_receivers:
                        celery.app.trace.send_postrun(
                            sender=task,
                            task_id=uuid,
                            task=task,
                            args=args,
                            kwargs=kwargs,
                            retval=retval,
                            state=state,
                        )

                finally:
                    pop_task()
                    pop_request()

                    if not eager:
                        try:
                            task.backend.process_cleanup()
                            AsyncIOPool.run_in_pool(loader_cleanup)
                        except (KeyboardInterrupt, SystemExit, MemoryError):
                            raise
                        except Exception as exc:
                            celery.app.trace.logger.error(
                                "Process cleanup failed: %r",
                                exc,
                                exc_info=True,
                            )

        except MemoryError:
            raise

        except Exception as exc:
            celery.app.trace._signal_internal_error(
                task,
                uuid,
                args,
                kwargs,
                request,
                exc,
            )

            if eager:
                raise

            R = celery.app.trace.report_internal_error(
                task,
                exc,
            )

            if task_request is not None:
                I, _, _, _ = AsyncIOPool.run_in_pool(
                    on_error,
                    task_request,
                    exc,
                    uuid,
                )

        return trace_ok_t(
            R,
            I,
            T,
            Rstr,
        )

    return trace_task
