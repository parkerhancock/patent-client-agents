"""Pydantic models for parsed JPO document-bundle contents.

These complement :mod:`patent_client_agents.inpi_pi.models` —
``DocumentBundleResult`` carries the raw ZIP bytes / oversize URL,
while the types in this module model the *contents* of the ZIP
after :func:`patent_client_agents.inpi_pi.documents.parse_document_bundle`
unpacks and parses each index XML.

Three document kinds map to three client methods per IP type:

* ``application`` — opinions and amendments (applicant-filed)
* ``mailed`` — JPO-mailed notices (rejections + decisions)
* ``refusal`` — strict subset of mailed: only refusal-reason notices

The XML schemas for ``mailed`` and ``refusal`` are functionally
identical (same DTD), so :class:`DocumentEntry` is shared.
``application`` documents differ enough (no examiner / no statute
list, but they do carry a body text) that a single, mostly-optional
:class:`DocumentEntry` shape covers all three with empty-string
defaults for the fields that don't apply.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

IpType = Literal["patent", "design", "trademark"]
DocumentKind = Literal["application", "mailed", "refusal"]


class DocumentEntry(BaseModel):
    """A single parsed document inside a JPO bundle ZIP.

    All fields default to empty / falsy values so the shape is uniform
    across the three doc kinds — fields that don't apply to a given
    kind simply stay empty.
    """

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    filename: str = Field(
        description="Path of the index XML inside the bundle ZIP",
    )
    ip_type: IpType = Field(description="patent / design / trademark")
    doc_kind: DocumentKind = Field(description="application / mailed / refusal")

    # JPO classification
    document_code: str = Field(
        default="",
        description="JPO 4-digit document code (e.g. A153 for opinion)",
    )
    document_name: str = Field(
        default="",
        description="Human-readable JPO document name (e.g. 拒絶理由通知書)",
    )
    document_variant: str = Field(
        default="",
        description="Inner XML element name (e.g. response-a53, amendment-a523)",
    )

    # Identifying / dating
    application_number: str = Field(
        default="",
        description="Application number this document attaches to",
    )
    legal_date: str = Field(
        default="",
        description=(
            "Drafting / filing date in YYYYMMDD form. For mailed docs this is "
            "the JPO drafting date; for applicant-filed docs it's the filing date."
        ),
    )

    # Mailed-doc specific
    drafter_name: str = Field(
        default="",
        description="Examiner / drafting person name (mailed docs only)",
    )
    articles: list[str] = Field(
        default_factory=list,
        description=(
            "Statutes cited — typically present on refusal-reason notices. "
            "Each entry is the raw text e.g. '第29条第1項第3号（新規性）'."
        ),
    )

    # Application-doc specific
    applicant_names: list[str] = Field(
        default_factory=list,
        description=(
            "Applicant + agent names from <jp:applicant>/<jp:agent>. "
            "Mailed docs typically don't carry these — the names appear "
            "on the corresponding addressed-to-person element instead."
        ),
    )
    dispatch_number: str = Field(
        default="",
        description=(
            "JPO dispatch number that the document references — typically "
            "the JPO-issued ID of the office action being responded to "
            "(applicant-filed docs only)."
        ),
    )

    # Body
    body_text: str = Field(
        default="",
        description=(
            "Concatenated text from the document body section "
            "(opinion-contents-article, conclusion-part-article, etc.). "
            "Empty when no body section is present."
        ),
    )

    parse_error: str = Field(
        default="",
        description=(
            "Set when the index XML failed to parse (the entry is still "
            "returned so callers see the filename, but other fields will "
            "be empty)."
        ),
    )


class DocumentBundle(BaseModel):
    """Parsed contents of a JPO ``app_doc_cont_*`` ZIP.

    Wraps a list of :class:`DocumentEntry` plus the IP-type / doc-kind
    context. Empty bundles (``entries=[]``) are valid — the JPO returns
    them when there are no documents on file (status 107 / 108).
    """

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    ip_type: IpType = Field(description="patent / design / trademark")
    doc_kind: DocumentKind = Field(description="application / mailed / refusal")
    application_number: str = Field(
        default="",
        description="Application number queried (echo)",
    )
    entries: list[DocumentEntry] = Field(
        default_factory=list,
        description="Parsed document entries (one per index XML)",
    )
    binary_attachments: list[str] = Field(
        default_factory=list,
        description=(
            "Filenames of non-XML files in the archive. Their bytes are not "
            "inlined here — fetch the raw ZIP via the bundle download_url to "
            "get them."
        ),
    )

    @property
    def is_empty(self) -> bool:
        """True if the bundle contained no parseable index XML."""
        return not self.entries


__all__ = [
    "DocumentBundle",
    "DocumentEntry",
    "DocumentKind",
    "IpType",
]
