"""Input models and one-shot helpers behind each outline package's ``api.py``.

A package's ``api.py`` keeps its typed public functions (``search``,
``get_section``, ``list_versions``) and delegates their bodies here. Each
helper uses the caller's client when one is passed (the deprecated
``client=`` form, which warns) and otherwise opens and closes a fresh one.
"""

from __future__ import annotations

import warnings
from typing import Any

from pydantic import BaseModel, Field

from .client import OutlineCorpusClient, ResponseT, SectionT, VersionT

# The deprecation warning names the caller of the package's public function:
# warn -> _warn_client_deprecated -> helper here -> package function -> caller.
_CALLER_STACKLEVEL = 4


class OutlineSearchInput(BaseModel):
    query: str
    version: str = "current"
    include_index: bool = False
    include_notes: bool = False
    include_form_paragraphs: bool = False
    syntax: str = Field(default="adj", description="adj, and, or, exact")
    snippet: str = Field(default="compact", description="compact or full")
    sort: str = Field(default="relevance", description="relevance or outline")
    per_page: int = Field(default=10, ge=1, le=100)
    page: int = Field(default=1, ge=1)


class OutlineSectionInput(BaseModel):
    section: str = Field(
        description="Section number (e.g., '2106') or href (e.g., 'd0e122292.html')"
    )
    version: str = "current"
    highlight_query: str | None = Field(
        default=None,
        description="Optional query for highlighted view",
    )

    # Backwards compatibility: allow 'href' as an alias for 'section'
    def __init__(self, **data: Any) -> None:
        if "href" in data and "section" not in data:
            data["section"] = data.pop("href")
        super().__init__(**data)


def _warn_client_deprecated(client_cls: type) -> None:
    warnings.warn(
        "Passing client= is deprecated and will be removed in v1.0. "
        f"Use 'async with {client_cls.__name__}() as client:' instead.",
        DeprecationWarning,
        stacklevel=_CALLER_STACKLEVEL,
    )


async def search(
    client_cls: type[OutlineCorpusClient[ResponseT, Any, Any]],
    params: BaseModel,
    *,
    client: OutlineCorpusClient[ResponseT, Any, Any] | None = None,
) -> ResponseT:
    """Run ``client.search`` with every field of ``params`` as a keyword."""
    kwargs: dict[str, Any] = {"include_content": True, **params.model_dump()}
    if client is not None:
        _warn_client_deprecated(client_cls)
        return await client.search(**kwargs)
    async with client_cls() as cl:
        return await cl.search(**kwargs)


async def get_section(
    client_cls: type[OutlineCorpusClient[Any, SectionT, Any]],
    params: OutlineSectionInput,
    *,
    client: OutlineCorpusClient[Any, SectionT, Any] | None = None,
) -> SectionT:
    kwargs: dict[str, Any] = {
        "section": params.section,
        "version": params.version,
        "highlight_query": params.highlight_query,
    }
    if client is not None:
        _warn_client_deprecated(client_cls)
        return await client.get_section(**kwargs)
    async with client_cls() as cl:
        return await cl.get_section(**kwargs)


async def list_versions(
    client_cls: type[OutlineCorpusClient[Any, Any, VersionT]],
    *,
    client: OutlineCorpusClient[Any, Any, VersionT] | None = None,
) -> list[VersionT]:
    if client is not None:
        _warn_client_deprecated(client_cls)
        return await client.list_versions()
    async with client_cls() as cl:
        return await cl.list_versions()


__all__ = [
    "OutlineSearchInput",
    "OutlineSectionInput",
    "get_section",
    "list_versions",
    "search",
]
