"""USPTO ODP Bulk Data client."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from pathlib import Path
from typing import Any

from ..models import BulkDataProductResponse, BulkDataSearchResponse
from .base import UsptoOdpBaseClient, _format_bool, _format_csv, _format_date


class BulkDataClient(UsptoOdpBaseClient):
    """Client for USPTO ODP Bulk Data Storage System (BDSS) API.

    Provides methods to search and retrieve bulk data products.
    """

    async def search(
        self,
        *,
        query: str | None = None,
        sort: str | None = None,
        offset: int = 0,
        limit: int = 25,
        facets: str | Sequence[str] | None = None,
        fields: str | Sequence[str] | None = None,
        filters: str | Sequence[str] | None = None,
        range_filters: str | Sequence[str] | None = None,
    ) -> BulkDataSearchResponse:
        """Search bulk data products.

        Args:
            query: Lucene-style search query.
            sort: Sort expression.
            offset: Number of results to skip.
            limit: Maximum results to return.
            facets: Fields to aggregate.
            fields: Fields to return.
            filters: Filter expressions.
            range_filters: Range filter expressions.

        Returns:
            BulkDataSearchResponse with matching products.
        """
        params: dict[str, Any] = {}
        if offset is not None:
            params["offset"] = offset
        if limit is not None:
            params["limit"] = limit
        if query:
            params["q"] = query
        if sort:
            params["sort"] = sort
        if (facets_value := _format_csv(facets)) is not None:
            params["facets"] = facets_value
        if (fields_value := _format_csv(fields)) is not None:
            params["fields"] = fields_value
        if (filters_value := _format_csv(filters)) is not None:
            params["filters"] = filters_value
        if (range_value := _format_csv(range_filters)) is not None:
            params["rangeFilters"] = range_value

        data = await self._get_with_404_handling(
            "/api/v1/datasets/products/search",
            empty_bag_key="bulkDataProductBag",
            context="search bulk datasets",
            params=params,
        )
        data.setdefault("bulkDataProductBag", [])
        return BulkDataSearchResponse.model_validate(data)

    async def get_product(
        self,
        product_identifier: str,
        *,
        file_from_date: date | str | None = None,
        file_to_date: date | str | None = None,
        offset: int | None = None,
        limit: int | None = None,
        include_files: bool | None = None,
        latest_only: bool | None = None,
    ) -> BulkDataProductResponse:
        """Get a specific bulk data product.

        Args:
            product_identifier: The product identifier (e.g., "PTFWPRE").
            file_from_date: Filter files from this date.
            file_to_date: Filter files to this date.
            offset: Pagination offset for files.
            limit: Maximum files to return.
            include_files: Whether to include file list.
            latest_only: Return only the latest file.

        Returns:
            BulkDataProductResponse with product details.
        """
        from mcp_data_core.exceptions import ValidationError

        normalized_identifier = product_identifier.strip()
        if not normalized_identifier:
            raise ValidationError("product_identifier is required")

        params: dict[str, Any] = {}
        if (from_value := _format_date(file_from_date)) is not None:
            params["fileDataFromDate"] = from_value
        if (to_value := _format_date(file_to_date)) is not None:
            params["fileDataToDate"] = to_value
        if offset is not None:
            params["offset"] = offset
        if limit is not None:
            params["limit"] = limit
        if (include_value := _format_bool(include_files)) is not None:
            params["includeFiles"] = include_value
        if (latest_value := _format_bool(latest_only)) is not None:
            params["latest"] = latest_value

        data = await self._get_with_404_handling(
            f"/api/v1/datasets/products/{normalized_identifier}",
            empty_bag_key="bulkDataProductBag",
            context=f"get bulk product {normalized_identifier}",
            params=params or None,
        )
        data.setdefault("bulkDataProductBag", [])
        return BulkDataProductResponse.model_validate(data)

    async def download_file(
        self,
        product_identifier: str,
        file_name: str,
        output_path: str | Path,
    ) -> Path:
        """Download one bulk data product file to disk.

        The file is streamed, since product files run to tens of gigabytes.
        ODP limits each key to 20 downloads of the same file per year (XML
        files have a higher limit), so avoid re-downloading.

        Args:
            product_identifier: The product identifier (e.g., "PTFWPRE").
            file_name: A ``fileName`` from the product's ``fileDataBag``
                (see :meth:`get_product` with ``include_files=True``).
            output_path: Where to write the file. Parent directories are
                created if needed.

        Returns:
            The path written.
        """
        from mcp_data_core.exceptions import ValidationError

        product = product_identifier.strip()
        name = file_name.strip()
        if not product or not name:
            raise ValidationError("product_identifier and file_name are required")

        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        url = self._build_url(f"/api/v1/datasets/products/files/{product}/{name}")
        async with self._client.stream("GET", url, follow_redirects=True) as response:
            if not response.is_success:
                await response.aread()
                self._raise_for_status(response, f"download bulk file {product}/{name}")
            with output.open("wb") as handle:
                async for chunk in response.aiter_bytes():
                    handle.write(chunk)
        return output


__all__ = ["BulkDataClient"]
