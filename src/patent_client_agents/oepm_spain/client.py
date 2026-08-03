"""Async client for Spain's OEPM CEO SOAP service.

The request and response contract follows OEPM's public CEO WSDL. Compatibility
is tested with synthetic WSDL-derived fixtures because no maintainer account is
configured.
"""

from __future__ import annotations

import os
import re
import xml.etree.ElementTree as ET
from typing import Any, Literal

import httpx

from mcp_data_core.base_client import BaseAsyncClient
from mcp_data_core.exceptions import (
    ApiError,
    AuthenticationError,
    ConfigurationError,
    NotFoundError,
    RateLimitError,
    ValidationError,
)

from .models import (
    OepmDesignRecord,
    OepmPatentRecord,
    OepmProceedingAct,
    OepmTrademarkRecord,
    parse_oepm_date,
)

BASE_URL = "https://consultas2.oepm.es/ceo/WSDetalleExpedienteOEPM"
WSDL_URL = f"{BASE_URL}?wsdl"
SOAP_NS = "http://schemas.xmlsoap.org/soap/envelope/"
SERVICE_NS = "http://detalleExpOEPM.ws.ceo.oepm.es/"
LIST_ACCEPT_CAP = 50
_SIGNUP_URL = (
    "https://www.oepm.es/es/sobre-OEPM/servicios-al-ciudadano/"
    "servicios-gratuitos/Servicios-web-de-la-OEPM/"
)

ET.register_namespace("soap", SOAP_NS)
ET.register_namespace("oepm", SERVICE_NS)

_MODALITIES: dict[str, set[str]] = {
    "patent": {"P", "U", "E", "W", "C", "T", "F", "L"},
    "trademark": {"M", "N", "R", "H"},
    "design": {"D", "I", "G", "DT", "DI", "DS"},
}


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].rsplit(":", 1)[-1]


def _element_to_value(element: ET.Element) -> Any:
    children = list(element)
    if not children:
        return (element.text or "").strip()
    value: dict[str, Any] = {}
    for child in children:
        name = _local(child.tag)
        child_value = _element_to_value(child)
        if name in value:
            current = value[name]
            value[name] = (
                current + [child_value] if isinstance(current, list) else [current, child_value]
            )
        else:
            value[name] = child_value
    return value


def _node(element: ET.Element, name: str) -> ET.Element | None:
    return next((item for item in element.iter() if _local(item.tag) == name), None)


def _text(element: ET.Element | None, name: str) -> str | None:
    if element is None:
        return None
    item = _node(element, name)
    text = (item.text or "").strip() if item is not None else ""
    return text or None


def _texts(element: ET.Element | None, name: str) -> list[str]:
    if element is None:
        return []
    return list(
        dict.fromkeys(
            text
            for item in element.iter()
            if _local(item.tag) == name and (text := (item.text or "").strip())
        )
    )


def _person(persons: ET.Element | None, role: str) -> str | None:
    if persons is None:
        return None
    person = _node(persons, role)
    if person is None:
        return None
    name = _text(person, "nombre")
    surname = _text(person, "apellidos")
    return " ".join(part for part in (name, surname) if part) or (person.text or "").strip() or None


def _proceedings(response: ET.Element) -> list[OepmProceedingAct]:
    result: list[OepmProceedingAct] = []
    for item in response.iter():
        if _local(item.tag) != "actoTramitacion":
            continue
        result.append(
            OepmProceedingAct(
                act_date=parse_oepm_date(_text(item, "fecha")),
                description=_text(item, "descripcion"),
            )
        )
    return result


def _modality(
    identifier: str, expected: Literal["patent", "trademark", "design"] | None = None
) -> str:
    compact = re.sub(r"\s+", "", identifier).upper()
    match = re.match(r"^[A-Z]+", compact)
    if not compact or match is None:
        raise ValidationError("OEPM file number must start with a documented modality code")
    modality = match.group(0)
    supported = set().union(*_MODALITIES.values())
    if modality not in supported:
        raise ValidationError(f"Unsupported OEPM modality code: {modality}")
    if expected and modality not in _MODALITIES[expected]:
        raise ValidationError(f"OEPM {expected} tool does not accept modality {modality}")
    return modality


def _soap_request(identifier: str, username: str, password: str) -> bytes:
    envelope = ET.Element(f"{{{SOAP_NS}}}Envelope")
    body = ET.SubElement(envelope, f"{{{SOAP_NS}}}Body")
    operation = ET.SubElement(body, f"{{{SERVICE_NS}}}detalleExpedienteOEPM")
    request = ET.SubElement(operation, "request")
    ET.SubElement(request, "numExpediente").text = identifier
    ET.SubElement(request, "usuario").text = username
    ET.SubElement(request, "pass").text = password
    return ET.tostring(envelope, encoding="utf-8", xml_declaration=True)


def _parse_response(xml_bytes: bytes) -> ET.Element:
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        raise ApiError(
            "OEPM CEO returned malformed XML", -1, xml_bytes[:500].decode(errors="replace")
        ) from exc
    fault = _node(root, "Fault")
    if fault is not None:
        message = _text(fault, "faultstring") or "unknown SOAP fault"
        raise ApiError(f"OEPM CEO SOAP fault: {message}", -1, "")
    response = _node(root, "response")
    if response is None:
        raise ApiError("OEPM CEO response lacks the documented response element", -1, "")
    result = _node(response, "resultado")
    state_text = _text(result, "estado")
    message = _text(result, "mensaje") or "request failed"
    try:
        state = int(state_text) if state_text is not None else None
    except ValueError as exc:
        raise ApiError("OEPM CEO returned an invalid result state", -1, "") from exc
    if state == -4:
        raise AuthenticationError("OEPM CEO rejected the configured credentials", 401, None)
    if state == -3:
        raise NotFoundError(f"OEPM file was not found: {message}", 404, "")
    if state != 0:
        raise ApiError(f"OEPM CEO error {state}: {message}", state, "")
    return response


def _common(response: ET.Element, identifier: str, modality: str) -> dict[str, Any]:
    bibliography = _node(response, "datosBibliograficos")
    identification = _node(bibliography, "identificacion") if bibliography is not None else None
    persons = _node(bibliography, "personas") if bibliography is not None else None
    return {
        "identifier": _text(identification, "numeroSolicitud") or identifier,
        "modality": modality,
        "status": _text(identification, "estado"),
        "status_code": _text(identification, "codigoEstado"),
        "owner": _person(persons, "titular"),
        "applicant": _person(persons, "solicitante"),
        "representative": _person(persons, "representante"),
        "proceedings": _proceedings(response),
        "raw": {_local(response.tag): _element_to_value(response)},
    }


def _patent(response: ET.Element, identifier: str, modality: str) -> OepmPatentRecord:
    bibliography = _node(response, "datosBibliograficos")
    details = _node(bibliography, "detallesInvencion") if bibliography is not None else None
    if details is None:
        raise ApiError("OEPM CEO response lacks invention details", -1, "")
    persons = _node(bibliography, "personas") if bibliography is not None else None
    common = _common(response, identifier, modality)
    common["status"] = _text(details, "estado") or common["status"]
    return OepmPatentRecord(
        **common,
        application_number=_text(details, "numeroSolicitud"),
        publication_number=_text(details, "numeroPublicacion"),
        epo_publication_number=_text(details, "numeroPublicacionOEP"),
        pct_publication_number=_text(details, "numeroPublicacionPCT"),
        title=_text(details, "titulo"),
        filing_date=parse_oepm_date(_text(details, "fechaPresentacion")),
        priority_number=_text(details, "numeroPrioridad"),
        priority_date=parse_oepm_date(_text(details, "fechaPrioridad")),
        publication_date=parse_oepm_date(_text(details, "fechaPublicacion")),
        grant_date=parse_oepm_date(_text(details, "fechaConcesion")),
        inventors=_texts(persons, "inventor"),
    )


def _trademark(response: ET.Element, identifier: str, modality: str) -> OepmTrademarkRecord:
    bibliography = _node(response, "datosBibliograficos")
    identification = _node(bibliography, "identificacion") if bibliography is not None else None
    details = _node(bibliography, "detallesMarca") if bibliography is not None else None
    classes = _node(bibliography, "clases") if bibliography is not None else None
    if identification is None or details is None:
        raise ApiError("OEPM CEO response lacks trademark details", -1, "")
    nice_classes = []
    for item in classes.iter() if classes is not None else ():
        if _local(item.tag) == "claseNiza" and (code := _text(item, "codigoClase")):
            nice_classes.append(code)
    vienna_classes = []
    for item in classes.iter() if classes is not None else ():
        if _local(item.tag) != "claseViena":
            continue
        parts = (_text(item, "categoria"), _text(item, "division"), _text(item, "seccion"))
        if value := ".".join(part for part in parts if part):
            vienna_classes.append(value)
    return OepmTrademarkRecord(
        **_common(response, identifier, modality),
        application_number=_text(identification, "numeroSolicitud"),
        denomination=_text(identification, "denominacion"),
        mark_type=_text(identification, "tipoMarca"),
        image_url=_text(identification, "imagen"),
        filing_date=parse_oepm_date(_text(details, "fechaSolicitud")),
        publication_date=parse_oepm_date(_text(details, "fechaPublicacion")),
        next_renewal_date=parse_oepm_date(_text(details, "fechaProxRenova")),
        nice_classes=list(dict.fromkeys(nice_classes)),
        vienna_classes=list(dict.fromkeys(vienna_classes)),
    )


def _design(response: ET.Element, identifier: str, modality: str) -> OepmDesignRecord:
    bibliography = _node(response, "datosBibliograficos")
    details = _node(bibliography, "detallesDiseno") if bibliography is not None else None
    persons = _node(bibliography, "personas") if bibliography is not None else None
    if details is None:
        raise ApiError("OEPM CEO response lacks design details", -1, "")
    common = _common(response, identifier, modality)
    common["status_code"] = _text(details, "codigoEstado") or common["status_code"]
    return OepmDesignRecord(
        **common,
        application_number=_text(details, "numeroSolicitud"),
        filing_date=parse_oepm_date(_text(details, "fechaSolicitud")),
        publication_date=parse_oepm_date(_text(details, "fechaPublicacion")),
        resolution_date=parse_oepm_date(_text(details, "fechaResolucion")),
        filing_place=_text(details, "lugarPresentacion"),
        creators=_texts(persons, "creador"),
    )


class OepmSpainClient(BaseAsyncClient):
    """Client for exact-number lookups in Spain's OEPM CEO register."""

    DEFAULT_BASE_URL = BASE_URL
    CACHE_NAME = "oepm_spain"

    def __init__(
        self,
        username: str | None = None,
        password: str | None = None,
        *,
        base_url: str | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.username = username or os.getenv("OEPM_CEO_USERNAME")
        self.password = password or os.getenv("OEPM_CEO_PASSWORD")
        if not self.username or not self.password:
            raise ConfigurationError(
                "OEPM CEO credentials required. Set OEPM_CEO_USERNAME and "
                f"OEPM_CEO_PASSWORD. Apply at {_SIGNUP_URL}."
            )
        resolved_base = (base_url or BASE_URL).rstrip("/")
        if client is None and not resolved_base.startswith("https://"):
            raise ConfigurationError("OEPM CEO requires an HTTPS endpoint")
        super().__init__(
            base_url=resolved_base,
            client=client,
            headers={"Accept": "text/xml", "Content-Type": "text/xml; charset=utf-8"},
            timeout=30.0,
            use_cache=False,
        )

    async def _get_response(self, identifier: str) -> tuple[ET.Element, str]:
        identifier = re.sub(r"\s+", "", identifier).upper()
        modality = _modality(identifier)
        response = await self._client.post(
            self.base_url,
            content=_soap_request(identifier, self.username or "", self.password or ""),
            headers={"SOAPAction": ""},
        )
        if response.status_code == 429:
            retry = response.headers.get("Retry-After")
            raise RateLimitError(
                "OEPM CEO rate limit exceeded",
                429,
                response.text[:500],
                retry_after=float(retry) if retry and retry.isdigit() else None,
            )
        if response.status_code in {401, 403}:
            raise AuthenticationError("OEPM CEO rejected the configured credentials", 401, None)
        if not response.is_success:
            raise ApiError(
                f"OEPM CEO HTTP {response.status_code}", response.status_code, response.text[:500]
            )
        return _parse_response(response.content), modality

    async def get_patent(self, identifier: str) -> OepmPatentRecord:
        modality = _modality(identifier, "patent")
        response, _ = await self._get_response(identifier)
        return _patent(response, identifier, modality)

    async def get_trademark(self, identifier: str) -> OepmTrademarkRecord:
        modality = _modality(identifier, "trademark")
        response, _ = await self._get_response(identifier)
        return _trademark(response, identifier, modality)

    async def get_design(self, identifier: str) -> OepmDesignRecord:
        modality = _modality(identifier, "design")
        response, _ = await self._get_response(identifier)
        return _design(response, identifier, modality)
