"""USPTO ODP Applications client."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

from law_tools_core.cache import get_default_cache_dir

from ..models import (
    ApplicationResponse,
    AssignmentResponse,
    DocumentRecord,
    DocumentsResponse,
    FamilyEdge,
    FamilyGraphResponse,
    FamilyNode,
    OdpFilter,
    OdpRangeFilter,
    OdpSort,
    SearchResponse,
)
from .base import UsptoOdpBaseClient, _prune, _serialize_model_list

_OCR_CACHE_DIR = get_default_cache_dir() / "ifw_ocr"
_OCR_MIN_CHARS_PER_PAGE = 50


def _extract_pdf_text(pdf_bytes: bytes) -> tuple[str, int]:
    """Extract the text layer from a PDF. Returns (text, page_count)."""
    import io

    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(pdf_bytes))
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n\n".join(pages).strip(), len(pages)


def _pdf_needs_ocr(text: str, page_count: int) -> bool:
    if page_count == 0:
        return False
    return (len(text) / page_count) < _OCR_MIN_CHARS_PER_PAGE


def _ocr_pdf(pdf_bytes: bytes, cache_key: str) -> str:
    """OCR a PDF with Tesseract, caching the result under cache_key.

    Requires ``tesseract-ocr`` and ``poppler-utils`` installed on the host.
    """
    cache_path = _OCR_CACHE_DIR / f"{cache_key}.txt"
    if cache_path.exists():
        return cache_path.read_text()

    import pytesseract
    from pdf2image import convert_from_bytes

    images = convert_from_bytes(pdf_bytes)
    text = "\n\n".join(pytesseract.image_to_string(img) for img in images)
    _OCR_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(text)
    return text


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
    """Clean a patent identifier for lookup.

    Strips country prefix (US), kind codes (A1, B1, B2, etc.),
    and non-alphanumeric characters to produce a bare number
    suitable for ODP patentNumber search.
    """
    import re

    cleaned = "".join(ch for ch in identifier.upper() if ch.isalnum())
    if cleaned.startswith("US"):
        cleaned = cleaned[2:]
    # Strip trailing kind codes (e.g. B1, B2, A1, A2, S1, P2, E1, H1)
    cleaned = re.sub(r"[A-Z]\d$", "", cleaned)
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
        filters: Sequence[OdpFilter | dict[str, Any]] | None = None,
        range_filters: Sequence[OdpRangeFilter | dict[str, Any]] | None = None,
        sort: Sequence[OdpSort | dict[str, Any]] | None = None,
        limit: int = 25,
        offset: int = 0,
        raw_payload: dict[str, Any] | None = None,
    ) -> SearchResponse:
        """Search patent applications.

        Args:
            query: Lucene-style search query.
            fields: Fields to return in response.
            facets: Fields to aggregate.
            filters: Filter objects or dicts (e.g.,
                ``[{"name": "applicationMetaData.publicationCategoryBag",
                     "value": ["Granted/Issued"]}]``).
            range_filters: Range filter objects or dicts (e.g.,
                ``[{"field": "applicationMetaData.filingDate",
                     "valueFrom": "2022-01-01", "valueTo": "2023-12-31"}]``).
            sort: Sort objects or dicts (e.g.,
                ``[{"field": "applicationMetaData.filingDate", "order": "Desc"}]``).
            limit: Maximum results to return.
            offset: Number of results to skip.
            raw_payload: Override with a custom payload dict.

        Returns:
            SearchResponse with matching applications.
        """
        if raw_payload is not None:
            payload = _prune(raw_payload)
        else:
            payload: dict[str, Any] = {}
            if query:
                payload["q"] = query
            if fields:
                payload["fields"] = list(fields)
            if facets:
                payload["facets"] = list(facets)
            if (filters_value := _serialize_model_list(filters)) is not None:
                payload["filters"] = filters_value
            if (ranges_value := _serialize_model_list(range_filters)) is not None:
                payload["rangeFilters"] = ranges_value
            if (sort_value := _serialize_model_list(sort)) is not None:
                payload["sort"] = sort_value
            payload["pagination"] = {"offset": offset, "limit": limit}
            payload = _prune(payload)

        data = await self._search_with_payload(
            "/api/v1/patent/applications/search",
            payload,
            empty_bag_key="patentFileWrapperDataBag",
            context="search applications",
        )
        return SearchResponse(**_normalize_patent_response(data))

    async def get(self, application_number: str) -> ApplicationResponse:
        """Get a single application by number.

        Args:
            application_number: The application number (e.g., "16123456").

        Returns:
            ApplicationResponse with the application data.
        """
        appl = self._normalize_application_number(application_number)
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

    async def download_document(
        self,
        application_number: str,
        document_identifier: str,
        *,
        output_path: str | Path | None = None,
    ) -> bytes:
        """Download a file-wrapper document PDF.

        Args:
            application_number: The application number (e.g., "10827445").
            document_identifier: The document identifier from DocumentRecord
                (e.g., "F2P71DT9PPOPPY5").
            output_path: Optional path to save the PDF. If provided, the file
                is written to this path.

        Returns:
            The PDF content as bytes.

        Example:
            >>> async with ApplicationsClient() as client:
            ...     # First, list documents to find the one you want
            ...     docs = await client.get_documents("10827445")
            ...     for doc in docs.documents:
            ...         if doc.documentCode == "CTRS":  # Restriction requirement
            ...             pdf_bytes = await client.download_document(
            ...                 "10827445",
            ...                 doc.documentIdentifier,
            ...                 output_path="restriction.pdf",
            ...             )
            ...             break
        """
        appl = self._normalize_application_number(application_number)
        # The download URL format is: /api/v1/download/applications/{appNum}/{docId}.pdf
        path = f"/api/v1/download/applications/{appl}/{document_identifier}.pdf"

        response = await self._request(
            "GET",
            path,
            context=f"download document {document_identifier} for {application_number}",
            timeout=120.0,  # Longer timeout for large PDFs
        )

        content = response.content

        if output_path is not None:
            output = Path(output_path)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(content)

        return content

    async def download_document_xml(
        self,
        application_number: str,
        document_identifier: str,
    ) -> str:
        """Download the XML content of a file-wrapper document.

        Not all documents have XML — check the ``downloadOptionBag`` in the
        document listing for ``mimeTypeIdentifier: "XML"`` first.

        The ODP XML archive endpoint returns a tar containing one ST.96 XML
        file.  This method extracts and returns the XML text.

        Args:
            application_number: The application number (e.g., ``"17654321"``).
            document_identifier: The document identifier from DocumentRecord.

        Returns:
            The raw XML string.

        Raises:
            NotFoundError: If the document or XML archive is not available.
        """
        import io
        import tarfile

        appl = self._normalize_application_number(application_number)
        path = f"/api/v1/download/applications/{appl}/{document_identifier}/xmlarchive"

        response = await self._request(
            "GET",
            path,
            context=f"download XML for {document_identifier} of {application_number}",
            timeout=120.0,
        )

        tf = tarfile.open(fileobj=io.BytesIO(response.content))
        for member in tf.getmembers():
            if member.name.endswith(".xml"):
                extracted = tf.extractfile(member)
                if extracted is not None:
                    return extracted.read().decode("utf-8")

        raise ValueError(f"No XML file found in archive for {document_identifier}")

    async def get_document_content(
        self,
        application_number: str,
        document_identifier: str,
        *,
        format: str = "auto",
    ) -> dict[str, Any]:
        """Fetch a file-wrapper document in the best available format.

        Modes:

        - ``"auto"`` (default): readable structured text. Tries ST.96 XML
          first (parsed into claims/spec/abstract/office-action structure);
          falls back to PDF text-layer extraction; falls back to Tesseract
          OCR for image-only PDFs. OCR results are cached under
          ``~/.cache/ip_tools/ifw_ocr/{document_identifier}.txt``.
        - ``"pdf"``: base64-encoded PDF bytes (for display/download).
        - ``"xml"``: raw ST.96 XML string (raises if XML not filed).

        Returns a dict whose shape depends on the mode. All responses
        include ``application_number``, ``document_identifier``, and
        ``format``. ``auto`` additionally includes ``source_format``
        (``"xml"`` | ``"pdf_text"`` | ``"pdf_ocr"``) and ``content``.
        """
        if format not in ("auto", "pdf", "xml"):
            raise ValueError(f"format must be 'auto', 'pdf', or 'xml', got {format!r}")

        appl = self._normalize_application_number(application_number)
        result: dict[str, Any] = {
            "application_number": appl,
            "document_identifier": document_identifier,
        }

        if format in ("auto", "xml"):
            from ...core.exceptions import NotFoundError

            try:
                xml_text = await self.download_document_xml(appl, document_identifier)
            except (ValueError, NotFoundError):
                if format == "xml":
                    raise
                xml_text = None
            if xml_text is not None:
                if format == "xml":
                    result["format"] = "xml"
                    result["content"] = xml_text
                    return result
                from ..xml_parser import parse_document_xml

                result["format"] = "text"
                result["source_format"] = "xml"
                result["content"] = parse_document_xml(xml_text)
                return result

        import asyncio
        import base64

        pdf_bytes = await self.download_document(appl, document_identifier)

        if format == "pdf":
            result["format"] = "pdf"
            result["content_type"] = "application/pdf"
            result["content_base64"] = base64.b64encode(pdf_bytes).decode()
            result["size_bytes"] = len(pdf_bytes)
            return result

        text, page_count = await asyncio.to_thread(_extract_pdf_text, pdf_bytes)
        result["format"] = "text"
        result["page_count"] = page_count

        if _pdf_needs_ocr(text, page_count):
            ocr_text = await asyncio.to_thread(_ocr_pdf, pdf_bytes, document_identifier)
            result["source_format"] = "pdf_ocr"
            result["content"] = ocr_text
        else:
            result["source_format"] = "pdf_text"
            result["content"] = text
        return result

    async def download_documents(
        self,
        application_number: str,
        *,
        document_codes: Sequence[str] | None = None,
        output_dir: str | Path | None = None,
    ) -> list[tuple[DocumentRecord, bytes]]:
        """Download multiple file-wrapper documents for an application.

        Args:
            application_number: The application number.
            document_codes: Optional list of document codes to filter by
                (e.g., ["CTRS", "ELC.", "NOA"]). If None, downloads all documents.
            output_dir: Optional directory to save PDFs. Files are named as
                "{date}_{code}_{identifier}.pdf".

        Returns:
            List of (DocumentRecord, bytes) tuples for each downloaded document.

        Example:
            >>> async with ApplicationsClient() as client:
            ...     # Download restriction requirement and election response
            ...     results = await client.download_documents(
            ...         "10827445",
            ...         document_codes=["CTRS", "ELC."],
            ...         output_dir="./prosecution_history/",
            ...     )
            ...     for doc, pdf_bytes in results:
            ...         print(f"Downloaded {doc.documentCode}: {len(pdf_bytes)} bytes")
        """
        docs_response = await self.get_documents(application_number)
        results: list[tuple[DocumentRecord, bytes]] = []

        output_path = Path(output_dir) if output_dir else None
        if output_path:
            output_path.mkdir(parents=True, exist_ok=True)

        for doc in docs_response.documents:
            # Filter by document codes if specified
            if document_codes is not None:
                if doc.documentCode not in document_codes:
                    continue

            # Skip if no document identifier
            if not doc.documentIdentifier:
                continue

            # Build output filename if saving
            file_path: Path | None = None
            if output_path:
                # Extract date from officialDate if available
                date_str = ""
                if hasattr(doc, "model_extra") and doc.model_extra:
                    official_date = doc.model_extra.get("officialDate", "")
                    if official_date:
                        date_str = official_date[:10]  # YYYY-MM-DD

                safe_code = (doc.documentCode or "UNK").replace("/", "-").replace(".", "_")
                filename = f"{date_str}_{safe_code}_{doc.documentIdentifier}.pdf"
                file_path = output_path / filename

            content = await self.download_document(
                application_number,
                doc.documentIdentifier,
                output_path=file_path,
            )
            results.append((doc, content))

        return results

    async def get_assignment(self, application_number: str) -> AssignmentResponse:
        """Get assignment history for an application.

        Args:
            application_number: The application number (e.g., "16123456").

        Returns:
            AssignmentResponse with assignment records including assignors,
            assignees, conveyance text, and recorded dates.
        """
        appl = self._normalize_application_number(application_number)
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
        identifier_type: str = "patent",
        batch_size: int = 25,
    ) -> FamilyGraphResponse:
        """Build a patent family graph starting from an identifier.

        Args:
            identifier: The number to start from.
            identifier_type: One of 'application', 'patent', or 'publication'.
            batch_size: Number of applications to fetch per batch.

        Returns:
            FamilyGraphResponse with nodes and edges.
        """
        root_application = await self.resolve_identifier(identifier, identifier_type)
        normalized_root = self._normalize_application_number(root_application)
        if not normalized_root:
            from law_tools_core.exceptions import ValidationError

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
            batch = sorted(list(to_visit))[:batch_size]
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
        from law_tools_core.exceptions import NotFoundError

        try:
            response = await self.get(application_number)
        except NotFoundError:
            return None
        if not response.patentBag:
            return None
        return response.patentBag[0]

    async def get_granted_claims(self, patent_number: str) -> list[dict[str, Any]] | None:
        """Fetch granted patent claims from the USPTO patent grant XML.

        Resolves the patent number to an application number, looks up the
        grant XML URL from the associated-documents metadata, downloads it,
        and parses the claims with hierarchical formatting preserved.

        Returns None if the application has no grant XML URL available
        (e.g. very recent grants, pre-grant publications). Raises on
        unexpected errors — callers that want a soft fallback should
        catch ``NotFoundError`` / ``ValidationError`` explicitly.
        """
        from ..xml_parser import parse_grant_claims_xml

        app_num = await self.resolve_identifier(patent_number, "patent")
        docs_response = await self.get_documents(app_num, include_associated=True)

        grant_url: str | None = None
        for ad in docs_response.associatedDocuments or []:
            grant_meta = ad.get("grantDocumentMetaData")
            if isinstance(grant_meta, dict):
                uri = grant_meta.get("fileLocationURI")
                if uri:
                    grant_url = uri
                    break
        if not grant_url:
            return None

        response = await self._request(
            "GET", grant_url, context=f"download grant XML for {patent_number}"
        )
        claims = parse_grant_claims_xml(response.text)
        return claims or None

    async def resolve_identifier(self, identifier: str, identifier_type: str = "patent") -> str:
        """Resolve an identifier to an application number.

        Args:
            identifier: The number to resolve.
            identifier_type: One of 'application', 'patent', or 'publication'.
                Controls which lookup strategy is used, avoiding ambiguity
                between 8-digit application numbers and patent numbers.
        """
        from law_tools_core.exceptions import ValidationError

        id_type = identifier_type.lower().strip()

        if id_type == "application":
            normalized = self._normalize_application_number(identifier)
            record = await self._fetch_single_application_record(normalized)
            if record and record.get("applicationNumberText"):
                return str(record["applicationNumberText"])
            raise ValidationError(f"Application '{identifier}' not found")

        if id_type in ("patent", "publication"):
            cleaned = _clean_patent_identifier(identifier)
            field = (
                "applicationMetaData.patentNumber"
                if id_type == "patent"
                else "applicationMetaData.publicationNumber"
            )
            if cleaned:
                response = await self.search(
                    query=f'{field}:"{cleaned}"',
                    fields=["applicationNumberText"],
                    limit=1,
                )
                if response.patentBag:
                    resolved = response.patentBag[0].get("applicationNumberText")
                    if resolved:
                        return str(resolved)
            raise ValidationError(
                f"Could not resolve {id_type} number '{identifier}' to an application number"
            )

        raise ValidationError(
            f"Unknown identifier_type '{identifier_type}'. "
            "Use 'application', 'patent', or 'publication'."
        )


__all__ = ["ApplicationsClient"]
