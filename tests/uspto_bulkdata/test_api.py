from __future__ import annotations

from datetime import date
from typing import Any, cast

import pytest

from patent_client_agents.uspto_bulkdata import api as bulk_api
from patent_client_agents.uspto_odp.models import (
    BulkDataProduct,
    BulkDataProductResponse,
    BulkDataSearchResponse,
)


@pytest.mark.asyncio
async def test_search_products() -> None:
    class DummyClient:
        async def search_bulk_datasets(self, **kwargs: object) -> BulkDataSearchResponse:
            assert kwargs["query"] == "label:patent"
            assert kwargs["facets"] == ["productLabelArrayText"]
            return BulkDataSearchResponse(
                count=1, bulkDataProductBag=[BulkDataProduct(productIdentifier="PT")]
            )

    result = await bulk_api.search_products(
        q="label:patent",
        facets=["productLabelArrayText"],
        client=cast(Any, DummyClient()),
    )
    assert isinstance(result, BulkDataSearchResponse)
    assert result.count == 1
    assert result.bulkDataProductBag[0].productIdentifier == "PT"


@pytest.mark.asyncio
async def test_get_product() -> None:
    class DummyClient:
        async def get_bulk_dataset_product(
            self, product_identifier: str, **kwargs: object
        ) -> BulkDataProductResponse:
            assert product_identifier == "PTGRXML"
            assert kwargs["include_files"] is True
            assert kwargs["file_from_date"] == date(2024, 1, 1)
            return BulkDataProductResponse(
                count=1,
                bulkDataProductBag=[BulkDataProduct(productIdentifier=product_identifier)],
            )

    result = await bulk_api.get_product(
        "PTGRXML",
        file_data_from_date=date(2024, 1, 1),
        include_files=True,
        client=cast(Any, DummyClient()),
    )
    assert isinstance(result, BulkDataProductResponse)
    assert result.bulkDataProductBag[0].productIdentifier == "PTGRXML"
