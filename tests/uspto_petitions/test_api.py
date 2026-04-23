from __future__ import annotations

from typing import Any, cast

import pytest

from patent_client_agents.uspto_odp.models import (
    PetitionDecision,
    PetitionDecisionIdentifierResponse,
    PetitionDecisionResponse,
    PetitionDecisionWithDocuments,
)
from patent_client_agents.uspto_petitions import api as petitions_api


@pytest.mark.asyncio
async def test_search_petitions() -> None:
    class DummyClient:
        async def search_petitions(self, **kwargs: object) -> PetitionDecisionResponse:
            assert kwargs["q"] == "finalDecidingOfficeName:OFFICE"
            return PetitionDecisionResponse(
                count=1,
                petitionDecisionDataBag=[
                    PetitionDecision(petitionDecisionRecordIdentifier="abc"),
                ],
            )

    result = await petitions_api.search_petitions(
        q="finalDecidingOfficeName:OFFICE",
        client=cast(Any, DummyClient()),
    )
    assert isinstance(result, PetitionDecisionResponse)
    assert result.count == 1


@pytest.mark.asyncio
async def test_get_petition() -> None:
    class DummyClient:
        async def get_petition(
            self, petition_decision_record_identifier: str, include_documents: bool = False
        ) -> PetitionDecisionIdentifierResponse:
            assert petition_decision_record_identifier == "abc"
            assert include_documents is True
            return PetitionDecisionIdentifierResponse(
                count=1,
                petitionDecisionDataBag=[
                    PetitionDecisionWithDocuments(petitionDecisionRecordIdentifier="abc"),
                ],
            )

    result = await petitions_api.get_petition(
        "abc",
        include_documents=True,
        client=cast(Any, DummyClient()),
    )
    assert isinstance(result, PetitionDecisionIdentifierResponse)
    assert result.petitionDecisionDataBag[0].petitionDecisionRecordIdentifier == "abc"


@pytest.mark.asyncio
async def test_download_petitions() -> None:
    class DummyClient:
        async def download_petitions(self, **kwargs: object) -> PetitionDecisionResponse:
            assert kwargs["file_format"] == "csv"
            return PetitionDecisionResponse(count=0, petitionDecisionDataBag=[])

    result = await petitions_api.download_petitions(
        file_format="csv",
        client=cast(Any, DummyClient()),
    )
    assert isinstance(result, PetitionDecisionResponse)
