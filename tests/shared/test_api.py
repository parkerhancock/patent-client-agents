"""Module-level one-shot functions built with ``shared.api.one_shot``."""

from __future__ import annotations

import inspect
import warnings
from typing import Any

import pytest

from patent_client_agents.shared.api import one_shot


class FakeClient:
    """Records every client the factory builds and every call made on it."""

    built: list[FakeClient] = []

    def __init__(self, **factory_kwargs: Any) -> None:
        self.factory_kwargs = factory_kwargs
        self.enters = 0
        self.exits = 0
        self.calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
        FakeClient.built.append(self)

    async def __aenter__(self) -> FakeClient:
        self.enters += 1
        return self

    async def __aexit__(self, *exc: object) -> None:
        self.exits += 1

    async def get_record(self, record_number: str, *, limit: int = 99) -> dict[str, Any]:
        self.calls.append(((record_number,), {"limit": limit}))
        return {"number": record_number, "limit": limit}

    async def search(self, query: str, *, size: int = 10, **extra: Any) -> list[Any]:
        self.calls.append(((), {"query": query, "size": size, **extra}))
        return [query, size, extra]

    async def fail(self, number: str) -> str:
        raise RuntimeError(f"upstream failed for {number}")


@pytest.fixture(autouse=True)
def _reset_built() -> None:
    FakeClient.built = []


def _new_client(**kwargs: Any) -> FakeClient:
    return FakeClient(**kwargs)


def _warn_client_deprecated() -> None:
    warnings.warn("Passing client= is deprecated.", DeprecationWarning, stacklevel=3)


@one_shot(_new_client, FakeClient.get_record)
async def get_record(number: str, *, limit: int = 5) -> dict[str, Any]:
    """Fetch one record."""


@one_shot(_new_client, FakeClient.search)
async def search(query: str, *, size: int = 25, **extra: Any) -> list[Any]: ...


@one_shot(_new_client, FakeClient.get_record, factory_args=("username",))
async def get_record_as(number: str, *, username: str | None = None) -> dict[str, Any]: ...


@one_shot(_new_client, FakeClient.fail)
async def fail(number: str) -> str: ...


@one_shot(_new_client, FakeClient.get_record, deprecated_client=_warn_client_deprecated)
async def get_record_legacy(number: str, *, client: FakeClient | None = None) -> dict[str, Any]: ...


def test_keeps_the_declared_name_signature_and_docstring() -> None:
    async def reference(number: str, *, limit: int = 5) -> dict[str, Any]:
        """Fetch one record."""
        return {}

    assert get_record.__name__ == "get_record"
    assert get_record.__doc__ == "Fetch one record."
    assert str(inspect.signature(get_record)) == str(inspect.signature(reference))
    assert inspect.iscoroutinefunction(get_record)


async def test_opens_and_closes_one_client_per_call() -> None:
    assert await get_record("A1") == {"number": "A1", "limit": 5}
    assert await get_record("A2", limit=7) == {"number": "A2", "limit": 7}

    assert [(c.enters, c.exits) for c in FakeClient.built] == [(1, 1), (1, 1)]
    # The declared default (5) reaches the method, not the method's own (99).
    assert FakeClient.built[0].calls == [(("A1",), {"limit": 5})]


async def test_closes_the_client_when_the_method_raises() -> None:
    with pytest.raises(RuntimeError, match="upstream failed for X"):
        await fail("X")

    (client,) = FakeClient.built
    assert (client.enters, client.exits) == (1, 1)


async def test_passes_named_arguments_and_extra_kwargs_by_keyword() -> None:
    assert await search(query="q", size=3, sort="date") == ["q", 3, {"sort": "date"}]
    assert FakeClient.built[0].calls == [((), {"query": "q", "size": 3, "sort": "date"})]


async def test_renamed_leading_argument_goes_positionally_and_unknown_names_into_kwargs() -> None:
    @one_shot(_new_client, FakeClient.search)
    async def search_text(text: str, *, page: int = 1) -> list[Any]: ...

    assert await search_text("q") == ["q", 10, {"page": 1}]


async def test_factory_args_go_to_the_factory_not_the_method() -> None:
    await get_record_as("A1", username="alice")

    (client,) = FakeClient.built
    assert client.factory_kwargs == {"username": "alice"}
    assert client.calls == [(("A1",), {"limit": 99})]


async def test_rejects_arguments_the_declared_signature_does_not_take() -> None:
    with pytest.raises(TypeError):
        await get_record("A1", 5)  # ty: ignore[too-many-positional-arguments]
    assert FakeClient.built == []


async def test_legacy_client_is_used_and_left_open_with_a_warning() -> None:
    passed = FakeClient()

    with pytest.warns(DeprecationWarning, match="Passing client= is deprecated") as record:
        result = await get_record_legacy("A1", client=passed)

    assert result == {"number": "A1", "limit": 99}
    assert record[0].filename == __file__  # stacklevel points at the caller
    assert FakeClient.built == [passed]
    assert (passed.enters, passed.exits) == (0, 0)


async def test_legacy_client_none_opens_a_client_without_warning() -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        await get_record_legacy("A1", client=None)

    (client,) = FakeClient.built
    assert (client.enters, client.exits) == (1, 1)


def _decorate(method: Any, stub: Any, **options: Any) -> Any:
    return one_shot(_new_client, method, **options)(stub)


async def _positional(number: str) -> None: ...


async def _keyword_only(*, size: int) -> None: ...


async def _unknown_keyword(*, size: int = 1) -> None: ...


async def _with_client(number: str, *, client: Any = None) -> None: ...


async def _with_username(number: str, username: str | None = None) -> None: ...


async def _with_extra(number: str, **extra: Any) -> None: ...


async def _var_positional(*numbers: str) -> None: ...


def _not_async(number: str) -> None: ...


@pytest.mark.parametrize(
    ("method", "stub", "options", "message"),
    [
        (FakeClient.get_record, _not_async, {}, "must be 'async def'"),
        (FakeClient.get_record, _var_positional, {}, "unsupported parameter kind"),
        (FakeClient.search, _keyword_only, {}, "required method parameters not passed"),
        (FakeClient.get_record, _unknown_keyword, {}, "no parameter for 'size'"),
        (FakeClient.fail, _with_extra, {}, "needs a method that takes"),
        (FakeClient.get_record, _with_client, {}, "needs deprecated_client"),
        (
            FakeClient.get_record,
            _positional,
            {"deprecated_client": _warn_client_deprecated},
            "'client' must be a keyword-only parameter",
        ),
        (
            FakeClient.get_record,
            _with_username,
            {"factory_args": ("username",)},
            "'username' must be a keyword-only parameter",
        ),
    ],
)
def test_mismatched_declarations_fail_at_import_time(
    method: Any, stub: Any, options: dict[str, Any], message: str
) -> None:
    with pytest.raises(TypeError, match=message):
        _decorate(method, stub, **options)


class _Lookup:
    async def __aenter__(self) -> _Lookup:
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None

    async def lookup(self, kind: str, number: str) -> str:
        return f"{kind}:{number}"


async def test_same_named_parameters_are_matched_by_name_not_position() -> None:
    @one_shot(_Lookup, _Lookup.lookup)
    async def lookup(number: str, kind: str) -> str: ...

    assert await lookup("123", "patent") == "patent:123"


def test_rejects_a_renamed_positional_that_collides_with_a_keyword() -> None:
    async def lookup(code: str, *, kind: str) -> str: ...

    with pytest.raises(TypeError, match="fill the same parameter"):
        one_shot(_Lookup, _Lookup.lookup)(lookup)


def test_rejects_an_unnamed_method() -> None:
    class Callable:
        async def __call__(self, client: Any) -> None: ...

    with pytest.raises(TypeError, match="named client method"):
        one_shot(_new_client, Callable())
