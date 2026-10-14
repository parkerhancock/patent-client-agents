"""Module-level one-shot functions built from client methods.

Every connector's ``api.py`` exposes coroutines that open a client, call one
method, and close the client. :func:`one_shot` writes that body once. The
public function is still declared in the module, so its name, parameters,
defaults, return annotation and docstring stay where readers (and ``inspect``)
expect them; only the body is generated::

    def _new_client() -> DpmaRegisterClient:
        return DpmaRegisterClient()


    @one_shot(_new_client, DpmaRegisterClient.get_patent)
    async def get_dpma_patent(number: str) -> PatentUtilityRecord: ...

Rules the generated body follows:

- Arguments are bound against the declared signature with defaults applied,
  so the method receives the declared defaults (as the hand-written
  ``limit=limit`` bodies did). A parameter the method also has is passed by
  keyword; a leading parameter the method names differently is passed
  positionally; ``**kwargs`` is spread. The fit against the method's
  signature is checked when the module is imported, and the stub's return
  type is checked against the method's by the type checker.
- The stub body is ``...`` (or just the docstring). ty's ``empty-body`` rule
  is switched off for ``*/api.py`` in ``pyproject.toml`` for this reason.
- ``factory`` is called on every invocation. Pass a small module-level
  function (not the class itself) so tests and callers that patch the client
  class on the ``api`` module keep working.
- The method is looked up by name on the opened client, so a stand-in client
  only needs a method with that name.
- ``factory_args`` names declared parameters (e.g. ``username``/``password``)
  that go to ``factory`` instead of the method.
- ``deprecated_client`` supports the legacy ``client=`` parameter: when the
  caller passes a client, the callback is called (it emits the module's
  ``DeprecationWarning``; it runs directly inside the public function, so a
  ``stacklevel=3`` warning still points at the caller) and the method runs on
  that client, which is left open.

Functions that do more than open, call, and close (renamed keyword arguments,
input models, error translation, several calls) stay hand-written.
"""

from __future__ import annotations

import functools
import inspect
from collections.abc import Awaitable, Callable, Coroutine
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from typing import Any, Concatenate, ParamSpec, TypeVar

__all__ = ["one_shot"]

P = ParamSpec("P")
T = TypeVar("T")
C = TypeVar("C")

_LEGACY_CLIENT = "client"


def one_shot(
    factory: Callable[..., AbstractAsyncContextManager[C]],
    method: Callable[Concatenate[C, ...], Awaitable[T]],
    *,
    factory_args: tuple[str, ...] = (),
    deprecated_client: Callable[[], None] | None = None,
) -> Callable[[Callable[P, Coroutine[Any, Any, T]]], Callable[P, Coroutine[Any, Any, T]]]:
    """Give a declared ``async def`` stub the body "open client, call ``method``, close".

    Args:
        factory: Called with the ``factory_args`` values to build the client,
            which is used as an async context manager.
        method: The client method to call (e.g. ``Client.get_patent``). Its
            return type must match the stub's.
        factory_args: Stub parameters passed to ``factory`` rather than the method.
        deprecated_client: When set, the stub must declare ``client``; a
            non-``None`` value calls this callback and is used instead of
            opening a new client.
    """
    method_name = getattr(method, "__name__", None)
    if not isinstance(method_name, str):
        raise TypeError(f"one_shot needs a named client method, got {method!r}.")

    def decorate(stub: Callable[P, Coroutine[Any, Any, T]]) -> Callable[P, Coroutine[Any, Any, T]]:
        signature = inspect.signature(stub)
        plan = _plan_call(stub, signature, method, factory_args, deprecated_client is not None)

        @functools.wraps(stub)
        async def run(*args: P.args, **kwargs: P.kwargs) -> T:
            bound = signature.bind(*args, **kwargs)
            bound.apply_defaults()
            values = bound.arguments
            call_args = [values[name] for name in plan.positional]
            call_kwargs = {name: values[name] for name in plan.keyword}
            if plan.var_keyword is not None:
                call_kwargs.update(values[plan.var_keyword])
            if deprecated_client is not None:
                client = values[_LEGACY_CLIENT]
                if client is not None:
                    deprecated_client()
                    return await getattr(client, method_name)(*call_args, **call_kwargs)
            factory_kwargs = {name: values[name] for name in factory_args}
            async with factory(**factory_kwargs) as opened:
                return await getattr(opened, method_name)(*call_args, **call_kwargs)

        return run

    return decorate


@dataclass(frozen=True)
class _CallPlan:
    positional: tuple[str, ...]
    keyword: tuple[str, ...]
    var_keyword: str | None


def _plan_call(
    stub: Callable[..., Any],
    signature: inspect.Signature,
    method: Callable[..., Any],
    factory_args: tuple[str, ...],
    legacy_client: bool,
) -> _CallPlan:
    """Work out how the stub's arguments reach ``method``; fail at import if they can't.

    A parameter the method also has (same name) is passed by keyword. A leading
    positional parameter the method names differently (``number`` vs
    ``patent_number``) is passed positionally into the same slot, as the
    hand-written bodies did. Anything else must land in the method's ``**kwargs``.
    """
    where = f"one_shot({_qualname(method)}) on {_qualname(stub)}"
    if not inspect.iscoroutinefunction(stub):
        raise TypeError(f"{where}: the decorated function must be 'async def'.")

    stub_params = signature.parameters
    routed_elsewhere = set(factory_args) | ({_LEGACY_CLIENT} if legacy_client else set())
    for name in routed_elsewhere:
        if name not in stub_params or stub_params[name].kind is not inspect.Parameter.KEYWORD_ONLY:
            raise TypeError(f"{where}: {name!r} must be a keyword-only parameter.")
    if not legacy_client and _LEGACY_CLIENT in stub_params:
        raise TypeError(f"{where}: a 'client' parameter needs deprecated_client=.")

    method_params = list(inspect.signature(method).parameters.values())[1:]  # drop self
    method_slots = [
        p for p in method_params if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)
    ]
    by_name = {
        p.name: p for p in method_params if p.kind in (p.POSITIONAL_OR_KEYWORD, p.KEYWORD_ONLY)
    }
    method_takes_kwargs = any(p.kind is p.VAR_KEYWORD for p in method_params)

    positional: list[str] = []
    keyword: list[str] = []
    var_keyword: str | None = None
    filled: set[str] = set()
    for index, param in enumerate(stub_params.values()):
        name = param.name
        if name in routed_elsewhere:
            continue
        if param.kind is param.VAR_KEYWORD:
            if not method_takes_kwargs:
                raise TypeError(f"{where}: **{name} needs a method that takes **kwargs.")
            var_keyword = name
        elif param.kind not in (param.POSITIONAL_OR_KEYWORD, param.KEYWORD_ONLY):
            raise TypeError(f"{where}: unsupported parameter kind for {name!r}.")
        elif name in by_name:
            keyword.append(name)
            filled.add(name)
        elif (
            param.kind is param.POSITIONAL_OR_KEYWORD
            and index == len(positional)
            and index < len(method_slots)
        ):
            positional.append(name)
            filled.add(method_slots[index].name)
        elif method_takes_kwargs:
            keyword.append(name)
        else:
            raise TypeError(f"{where}: the method has no parameter for {name!r}.")

    if any(slot.name in keyword for slot in method_slots[: len(positional)]):
        raise TypeError(f"{where}: a positional argument and a keyword fill the same parameter.")
    missing = [
        p.name
        for p in method_params
        if p.default is p.empty
        and p.kind not in (p.VAR_POSITIONAL, p.VAR_KEYWORD)
        and p.name not in filled
    ]
    if missing:
        raise TypeError(f"{where}: required method parameters not passed: {missing}.")
    return _CallPlan(tuple(positional), tuple(keyword), var_keyword)


def _qualname(obj: object) -> str:
    return getattr(obj, "__qualname__", repr(obj))
