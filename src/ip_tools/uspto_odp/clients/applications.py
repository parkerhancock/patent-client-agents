"""USPTO ODP Applications client."""

from __future__ import annotations

import logging
from typing import Any

from ..models import (
    ApplicationResponse,
    AssignmentResponse,
    DocumentRecord,
    DocumentsResponse,
    FamilyEdge,
    FamilyGraphResponse,
    FamilyNode,
    SearchResponse,
)
from .base import PaginationModel, SearchPayload, UsptoOdpBaseClient, _prune

logger = logging.getLogger(__name__)


def _merge_application_metadata(entry: dict[str, Any]) -> dict[str, Any]:
    """Merge nested applicationMetaData into the top-level record."""
    combined = dict(entry)
    metadata_raw = combined.pop("applicationMetaData", {}) or {}
    metadata = dict(metadata_raw) if isinstance(metadata_raw, dict) else {}
    status_raw = metadata.pop("entityStatusData", {}) or {}
    entity_status = dict(status_raw) if isinstance(status_raw, dict) else {}
    if entity_status.get("businessEntityStatusCategory"):
        combined.setdefault(
            "businessEntityStatusCategory", entity_status.get("businessEntityStatusCategory")
        )
    if entity_status.get("smallEntityStatusIndicator") is not None:
        combined.setdefault(
            "smallEntityStatusIndicator", entity_status.get("smallEntityStatusIndicator")
        )

    parent = combined.pop("parentContinuityBag", None)
    child = combined.pop("childContinuityBag", None)
    if parent is not None or child is not None:
        combined["continuityBag"] = {
            "parentContinuityBag": parent or [],
            "childContinuityBag": child or [],
        }

    for key, value in metadata.items():
        combined.setdefault(str(key), value)

    return combined


def _normalize_patent_response(data: dict[str, Any]) -> dict[str, Any]:
    """Normalize the ODP response structure."""
    bag = [_merge_application_metadata(item) for item in data.get("patentFileWrapperDataBag", [])]
    return {
        "count": data.get("count", len(bag)),
        "patentBag": bag,
        "requestIdentifier": data.get("requestIdentifier"),
    }


def _clean_patent_identifier(identifier: str) -> str:
    """Clean a patent identifier for lookup."""
    cleaned = "".join(ch for ch in identifier.upper() if ch.isalnum())
    if cleaned.startswith("US"):
        cleaned = cleaned[2:]
    return cleaned


def _extract_parents(record: dict[str, Any]) -> list[dict[str, Any]]:
    continuity = record.get("continuityBag") or {}
    return list(continuity.get("parentContinuityBag") or record.get("parentContinuityBag") or [])


def _extract_children(record: dict[str, Any]) -> list[dict[str, Any]]:
    continuity = record.get("continuityBag") or {}
    return list(continuity.get("childContinuityBag") or record.get("childContinuityBag") or [])


def _build_family_node(record: dict[str, Any], *, data_source: str) -> FamilyNode:
    application_number = str(record.get("applicationNumberText") or "").strip()
    meta = record
    return FamilyNode(
        applicationNumber=application_number,
        dataSource=data_source,
        patentNumber=meta.get("patentNumber"),
        filingDate=meta.get("filingDate"),
        grantDate=meta.get("grantDate"),
        statusCode=meta.get("applicationStatusCode"),
        statusText=meta.get("applicationStatusDescriptionText"),
        title=meta.get("inventionTitle"),
    )


def _placeholder_node(application_number: str, *, source: str = "unknown") -> FamilyNode:
    return FamilyNode(applicationNumber=application_number, dataSource=source)


class ApplicationsClient(UsptoOdpBaseClient):
    """Client for USPTO ODP patent applications API.

    Provides methods to search applications, retrieve application details,
    list file wrapper documents, and build patent family graphs.
    """

    async def search(
        self,
        *,
        query: str | None = None,
        fields: list[str] | None = None,
        facets: list[str] | None = None,
        filters: list[str] | None = None,
        range_filters: list[str] | None = None,
        sort: str | None = None,
        limit: int = 25,
        offset: int = 0,
        raw_payload: dict[str, Any] | None = None,
    ) -> SearchResponse:
        """Search patent applications.

        Args:
            query: Lucene-style search query.
            fields: Fields to return in response.
            facets: Fields to aggregate.
            filters: Filter expressions (e.g., "applicationStatusCode:150").
            range_filters: Range filter expressions.
            sort: Sort expression (e.g., "filingDate desc").
            limit: Maximum results to return.
            offset: Number of results to skip.
            raw_payload: Override with a custom payload dict.

        Returns:
            SearchResponse with matching applications.
        """
        if raw_payload is not None:
            payload = _prune(raw_payload)
        else:
            payload = SearchPayload(
                q=query,
                fields=fields,
                facets=facets,
                filters=filters,
                range_filters=range_filters,
                sort=sort,
                pagination=PaginationModel(offset=offset, limit=limit),
            ).model_dump_pruned()

        logger.debug("Searching applications: query=%s limit=%d offset=%d", query, limit, offset)
        data = await self._search_with_payload(
            "/api/v1/patent/applications/search",
            payload,
            empty_bag_key="patentFileWrapperDataBag",
            context="search applications",
        )
        response = SearchResponse(**_normalize_patent_response(data))
        logger.debug("Application search returned %d results", response.count)
        return response

    async def get(self, application_number: str) -> ApplicationResponse:
        """Get a single application by number.

        Args:
            application_number: The application number (e.g., "16123456").

        Returns:
            ApplicationResponse with the application data.
        """
        appl = self._normalize_application_number(application_number)
        logger.debug("Getting application %s", appl)
        data = await self._request_json(
            "GET",
            f"/api/v1/patent/applications/{appl}",
            context=f"get application {application_number}",
        )
        return ApplicationResponse(**_normalize_patent_response(data))

    async def get_documents(
        self,
        application_number: str,
        *,
        include_associated: bool = True,
    ) -> DocumentsResponse:
        """List file-wrapper documents for an application.

        Args:
            application_number: The application number.
            include_associated: Whether to include associated PGPub/grant metadata.

        Returns:
            DocumentsResponse with document list.
        """
        appl = self._normalize_application_number(application_number)
        logger.debug("Getting documents for application %s", appl)
        data = await self._request_json(
            "GET",
            f"/api/v1/patent/applications/{appl}/documents",
            context=f"get documents for {application_number}",
        )
        documents_raw = data.get("documentBag", [])
        documents = [DocumentRecord(**item) for item in documents_raw if isinstance(item, dict)]

        associated_docs: list[dict[str, Any]] | None = None
        if include_associated:
            assoc_data = await self._get_with_404_handling(
                f"/api/v1/patent/applications/{appl}/associated-documents",
                empty_bag_key="patentFileWrapperDataBag",
                context=f"get associated documents for {application_number}",
            )
            raw_associated = assoc_data.get("patentFileWrapperDataBag", [])
            associated_docs = [item for item in raw_associated if isinstance(item, dict)]

        return DocumentsResponse(
            documents=documents,
            associatedDocuments=associated_docs if include_associated else None,
        )

    async def get_assignment(self, application_number: str) -> AssignmentResponse:
        """Get assignment history for an application.

        Args:
            application_number: The application number (e.g., "16123456").

        Returns:
            AssignmentResponse with assignment records including assignors,
            assignees, conveyance text, and recorded dates.
        """
        appl = self._normalize_application_number(application_number)
        logger.debug("Getting assignment for application %s", appl)
        data = await self._get_with_404_handling(
            f"/api/v1/patent/applications/{appl}/assignment",
            empty_bag_key="assignmentBag",
            context=f"get assignment for {application_number}",
        )
        return AssignmentResponse(
            applicationNumberText=appl,
            assignmentBag=data.get("assignmentBag", []),
            requestIdentifier=data.get("requestIdentifier"),
        )

    async def get_family(
        self,
        identifier: str,
        *,
        batch_size: int = 25,
    ) -> FamilyGraphResponse:
        """Build a patent family graph starting from an identifier.

        Args:
            identifier: Application number or patent number to start from.
            batch_size: Number of applications to fetch per batch.

        Returns:
            FamilyGraphResponse with nodes and edges.
        """
        logger.debug("Building patent family graph for identifier %s", identifier)
        root_application = await self._resolve_identifier(identifier)
        normalized_root = self._normalize_application_number(root_application)
        if not normalized_root:
            from ip_tools.core.exceptions import ValidationError

            raise ValidationError(
                f"Could not resolve identifier '{identifier}' to an application number"
            )

        visited: set[str] = set()
        to_visit: set[str] = {normalized_root}
        nodes: dict[str, FamilyNode] = {}
        edges: list[FamilyEdge] = []
        edge_keys: set[tuple[str, str, str | None]] = set()
        missing: set[str] = set()

        while to_visit:
            batch = sorted(to_visit)[:batch_size]
            to_visit.difference_update(batch)

            batch_results = await self._fetch_family_batch(batch)

            unresolved = [app for app in batch if app not in batch_results]
            for app in unresolved:
                record = await self._fetch_single_application_record(app)
                if record:
                    batch_results[app] = record
                else:
                    missing.add(app)
                    visited.add(app)
                    nodes.setdefault(app, _placeholder_node(app))

            for app_num, record in batch_results.items():
                normalized_app = self._normalize_application_number(app_num)
                visited.add(normalized_app)
                nodes[normalized_app] = _build_family_node(record, data_source="uspto_odp")

                for parent in _extract_parents(record):
                    parent_raw = parent.get("parentApplicationNumberText")
                    if not parent_raw:
                        continue
                    parent_num = self._normalize_application_number(str(parent_raw))
                    if parent_num not in nodes:
                        nodes[parent_num] = _placeholder_node(parent_num)
                    if parent_num not in visited and parent_num not in missing:
                        to_visit.add(parent_num)
                    key = (parent_num, normalized_app, parent.get("claimParentageTypeCode"))
                    if key not in edge_keys:
                        edges.append(
                            FamilyEdge(
                                fromApplication=parent_num,
                                toApplication=normalized_app,
                                relationshipCode=parent.get("claimParentageTypeCode"),
                                relationshipDescription=parent.get(
                                    "claimParentageTypeCodeDescriptionText"
                                ),
                                parentFilingDate=parent.get("parentApplicationFilingDate"),
                                parentPatentNumber=parent.get("parentPatentNumber"),
                            )
                        )
                        edge_keys.add(key)

                for child in _extract_children(record):
                    child_raw = child.get("childApplicationNumberText")
                    if not child_raw:
                        continue
                    child_num = self._normalize_application_number(str(child_raw))
                    if child_num not in nodes:
                        nodes[child_num] = _placeholder_node(child_num)
                    if child_num not in visited and child_num not in missing:
                        to_visit.add(child_num)
                    key = (normalized_app, child_num, child.get("claimParentageTypeCode"))
                    if key not in edge_keys:
                        edges.append(
                            FamilyEdge(
                                fromApplication=normalized_app,
                                toApplication=child_num,
                                relationshipCode=child.get("claimParentageTypeCode"),
                                relationshipDescription=child.get(
                                    "claimParentageTypeCodeDescriptionText"
                                ),
                                childFilingDate=child.get("childApplicationFilingDate"),
                                childPatentNumber=child.get("childPatentNumber"),
                            )
                        )
                        edge_keys.add(key)

        logger.debug(
            "Family graph complete: %d nodes, %d edges, %d missing",
            len(nodes),
            len(edges),
            len(missing),
        )
        metadata = {
            "nodeCount": len(nodes),
            "edgeCount": len(edges),
            "missingCount": len(missing),
        }
        return FamilyGraphResponse(
            rootApplication=normalized_root,
            nodes=sorted(nodes.values(), key=lambda node: node.applicationNumber),
            edges=edges,
            missingApplications=sorted(missing),
            metadata=metadata,
        )

    async def _fetch_family_batch(
        self, application_numbers: list[str]
    ) -> dict[str, dict[str, Any]]:
        """Fetch a batch of applications for family graph building."""
        if not application_numbers:
            return {}
        normalized_numbers = [
            self._normalize_application_number(num) for num in application_numbers
        ]
        query_terms = " OR ".join(normalized_numbers)
        query = f"applicationNumberText:({query_terms})"
        response = await self.search(
            query=query,
            fields=[
                "applicationNumberText",
                "applicationMetaData",
                "parentContinuityBag",
                "childContinuityBag",
            ],
            limit=len(normalized_numbers),
        )
        results: dict[str, dict[str, Any]] = {}
        for entry in response.patentBag:
            app_number = entry.get("applicationNumberText")
            if not app_number:
                continue
            normalized = self._normalize_application_number(str(app_number))
            results[normalized] = entry
        return results

    async def _fetch_single_application_record(
        self, application_number: str
    ) -> dict[str, Any] | None:
        """Fetch a single application record, returning None if not found."""
        from ip_tools.core.exceptions import NotFoundError

        try:
            response = await self.get(application_number)
        except NotFoundError:
            logger.debug("Application %s not found", application_number)
            return None
        if not response.patentBag:
            return None
        return response.patentBag[0]

    async def _resolve_identifier(self, identifier: str) -> str:
        """Resolve an application or patent number to an application number."""
        from ip_tools.core.exceptions import ValidationError

        normalized_identifier = self._normalize_application_number(identifier)
        record = await self._fetch_single_application_record(normalized_identifier)
        if record and record.get("applicationNumberText"):
            return str(record["applicationNumberText"])

        cleaned_patent = _clean_patent_identifier(identifier)
        if cleaned_patent:
            response = await self.search(
                query=f'applicationMetaData.patentNumber:"{cleaned_patent}"',
                fields=["applicationNumberText"],
                limit=1,
            )
            if response.patentBag:
                resolved = response.patentBag[0].get("applicationNumberText")
                if resolved:
                    return str(resolved)

        raise ValidationError(
            f"Could not resolve identifier '{identifier}' to an application number"
        )


__all__ = ["ApplicationsClient"]
