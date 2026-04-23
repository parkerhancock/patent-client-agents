"""Tests for MPEP client."""

from __future__ import annotations

import httpx
import pytest

from patent_client_agents.mpep.client import MpepClient
from patent_client_agents.mpep.models import MpepSearchResponse, MpepSection, MpepVersion


class TestMpepClientInit:
    """Tests for client initialization."""

    def test_creates_client(self) -> None:
        client = MpepClient()
        assert client._client is not None
        assert client._owns_client is True

    def test_accepts_custom_client(self) -> None:
        custom = httpx.AsyncClient()
        client = MpepClient(client=custom)
        assert client._client is custom
        assert client._owns_client is False


class TestMpepClientMethods:
    """Tests for client methods with mocked HTTP."""

    @pytest.fixture
    def mock_client(self) -> httpx.AsyncClient:
        """Create a mock async client."""

        def handler(request: httpx.Request) -> httpx.Response:
            path = request.url.path

            if "/search" in path:
                # Match real site structure: chapter-level uses <span>, sections use <a>
                return httpx.Response(
                    200,
                    json={
                        "list": """<ul>
<li><span href="#/result/d0e55397.html?q=patent">0700 - Examination of Applications</span>
<ul><li><a href="#/result/d0e57969.html?q=patent">706 - Rejection of Claims</a></li></ul>
</li></ul>"""
                    },
                )
            elif "/result" in path or "/content" in path:
                return httpx.Response(
                    200,
                    text="""
                        <html>
                            <body>
                                <h1>§700 Examination of Applications</h1>
                                <p>This chapter discusses patent examination.</p>
                            </body>
                        </html>
                    """,
                )
            elif "/current" in path:
                return httpx.Response(
                    200,
                    text="""
                        <html>
                            <body>
                                <select id="edition-select">
                                    <option value="/current" selected>Current Edition</option>
                                    <option value="/R-09.2019">R-09.2019</option>
                                </select>
                            </body>
                        </html>
                    """,
                )

            return httpx.Response(404, text="Not found")

        return httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            headers={"User-Agent": "Test/1.0"},
        )

    @pytest.mark.asyncio
    async def test_search(self, mock_client: httpx.AsyncClient) -> None:
        client = MpepClient(client=mock_client)
        result = await client.search("patent")
        assert isinstance(result, MpepSearchResponse)
        # Only <a> tags are returned as hits, not <span> tags
        assert len(result.hits) == 1
        assert result.hits[0].title == "706 - Rejection of Claims"

    @pytest.mark.asyncio
    async def test_search_with_options(self, mock_client: httpx.AsyncClient) -> None:
        client = MpepClient(client=mock_client)
        result = await client.search(
            "patent",
            version="R-09.2019",
            include_content=True,
            include_index=True,
            per_page=20,
            page=2,
        )
        assert isinstance(result, MpepSearchResponse)

    @pytest.mark.asyncio
    async def test_get_section(self, mock_client: httpx.AsyncClient) -> None:
        client = MpepClient(client=mock_client)
        result = await client.get_section("0700")
        assert isinstance(result, MpepSection)
        assert result.title == "§700 Examination of Applications"
        assert "patent examination" in result.text

    @pytest.mark.asyncio
    async def test_get_section_with_highlight(self, mock_client: httpx.AsyncClient) -> None:
        client = MpepClient(client=mock_client)
        result = await client.get_section("0700", highlight_query="patent")
        assert isinstance(result, MpepSection)

    @pytest.mark.asyncio
    async def test_list_versions(self, mock_client: httpx.AsyncClient) -> None:
        client = MpepClient(client=mock_client)
        result = await client.list_versions()
        assert isinstance(result, list)
        assert len(result) == 2
        assert all(isinstance(v, MpepVersion) for v in result)
        assert result[0].current is True

    @pytest.mark.asyncio
    async def test_context_manager(self, mock_client: httpx.AsyncClient) -> None:
        async with MpepClient(client=mock_client) as client:
            result = await client.search("test")
            assert isinstance(result, MpepSearchResponse)


class TestSearchParams:
    """Tests for search parameter handling."""

    @pytest.mark.asyncio
    async def test_page_parameter_calculation(self) -> None:
        captured_params: dict[str, str] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured_params.update(dict(request.url.params))
            return httpx.Response(200, json={"list": "<div></div>"})

        mock = httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            headers={"User-Agent": "Test/1.0"},
        )
        client = MpepClient(client=mock)
        await client.search("test", page=3, per_page=10)
        # Page 3 with per_page 10 means start at item 20
        assert captured_params.get("startPage") == "20"

    @pytest.mark.asyncio
    async def test_first_page_no_start(self) -> None:
        captured_params: dict[str, str] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured_params.update(dict(request.url.params))
            return httpx.Response(200, json={"list": "<div></div>"})

        mock = httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            headers={"User-Agent": "Test/1.0"},
        )
        client = MpepClient(client=mock)
        await client.search("test", page=1)
        # Page 1 should have empty startPage
        assert captured_params.get("startPage") == ""
