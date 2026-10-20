"""ESB request envelope builders for JSON and XML.

The ESB expects a signed envelope of the form::

    {
      "data":      { "apiCode": ..., "esbBody": {...}, "userId": "..." },
      "signature": "<base64 ECDSA signature over the compact-serialized data>"
    }

For XML the equivalent structure is ``<esbrequest><data><apiCode/><esbBody/></data>
<signature/></esbrequest>``; the signature covers the ``<data>`` element serialized
the way e-GA's helper does it: no declaration, no layout whitespace, no ``<x/>``.

Keep the JSON encoder deterministic (no spaces, stable key order) because
the signature is computed over its exact byte-for-byte output.
"""
from __future__ import annotations

import copy
import json
import logging
import re
import xml.etree.ElementTree as ET
from typing import Any

from .enums import ESBRequestType
from .exceptions import ESBError, ESBRequestError
from .signatures import SignatureService

logger = logging.getLogger(__name__)


def _compact_json(data: Any) -> str:
    """Deterministic JSON serialization matching what the ESB signs."""
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))


def raw_json_member(text: str | bytes | None, key: str) -> str | None:
    """The exact source text of a top-level member of a JSON object, or None.
    Signatures cover the sender's bytes, which re-serializing may not reproduce."""
    if text is None:
        return None
    if isinstance(text, bytes):
        try:
            text = text.decode("utf-8")
        except UnicodeDecodeError:
            return None
    decoder = json.JSONDecoder()
    ws = " \t\n\r"
    try:
        i = len(text) - len(text.lstrip(ws))
        if text[i] != "{":
            return None
        i += 1
        while True:
            while text[i] in ws:
                i += 1
            if text[i] == "}":
                return None
            name, i = decoder.raw_decode(text, i)
            while text[i] in ws:
                i += 1
            if text[i] != ":":
                return None
            i += 1
            while text[i] in ws:
                i += 1
            start = i
            _, i = decoder.raw_decode(text, i)
            if name == key:
                return text[start:i]
            while text[i] in ws:
                i += 1
            if text[i] != ",":
                return None
            i += 1
    except (ValueError, IndexError):
        return None


def signed_content_candidates(raw: str | bytes | None, data: Any) -> list[str]:
    """What the ``data`` signature may cover: the raw text first, then our compact form."""
    candidates = []
    raw_data = raw_json_member(raw, "data")
    if raw_data is not None:
        candidates.append(raw_data)
    compact = _compact_json(data)
    if compact not in candidates:
        candidates.append(compact)
    return candidates


def _strip_layout(element: ET.Element) -> ET.Element:
    for node in element.iter():
        if len(node) and node.text is not None and not node.text.strip():
            node.text = None
        if node.tail is not None and not node.tail.strip():
            node.tail = None
    return element


def compact_xml(element: ET.Element | str | bytes) -> str:
    """One element as GovESB signs it: no declaration, no layout whitespace, ``<x></x>``."""
    if isinstance(element, (str, bytes)):
        element = ET.fromstring(element)
    else:
        element = copy.deepcopy(element)
    return ET.tostring(_strip_layout(element), encoding="unicode", short_empty_elements=False)


def raw_xml_element(text: str | bytes | None, tag: str) -> str | None:
    """The exact source text of the outermost ``<tag>…</tag>``, or None."""
    if text is None:
        return None
    if isinstance(text, bytes):
        try:
            text = text.decode("utf-8")
        except UnicodeDecodeError:
            return None
    match = re.search(rf"<{tag}(?:\s[^>]*)?>.*</{tag}\s*>", text, re.S)
    return match.group(0) if match else None


def xml_signed_content_candidates(raw: str | bytes | None, data: ET.Element) -> list[str]:
    """XML twin of ``signed_content_candidates``: the received ``<data>`` text, then ours."""
    candidates = []
    raw_data = raw_xml_element(raw, "data")
    if raw_data is not None:
        candidates.append(raw_data)
    compact = compact_xml(data)
    if compact not in candidates:
        candidates.append(compact)
    return candidates


def xml_envelope_fields(data: ET.Element | None) -> dict:
    """``success`` / ``requestId`` / ``message`` / ``esbBody`` of an XML ``<data>``; the
    body is returned as compact XML text (a ``<Payload>`` wrapper removed)."""
    if data is None:
        return {}
    fields: dict[str, Any] = {}
    success = data.findtext("success")
    if success is not None:
        fields["success"] = success.strip().lower() == "true"
    for name in ("requestId", "message"):
        value = data.findtext(name)
        if value is not None:
            fields[name] = value.strip()
    body = data.find("esbBody")
    if body is not None:
        children = list(body)
        if len(children) == 1 and children[0].tag == "Payload":
            children = list(children[0])
        fields["esbBody"] = "".join(compact_xml(c) for c in children) or (body.text or "").strip()
    return fields


class EnvelopeBuilder:
    """Produces signed JSON/XML envelopes ready to send to the ESB."""

    def __init__(self, signer: SignatureService):
        self._signer = signer

    # --- JSON -----------------------------------------------------------
    def build_json(
        self,
        *,
        api_code: str,
        payload: dict,
        request_type: ESBRequestType,
        user_id: str | None = None,
    ) -> str:
        if not isinstance(payload, dict) or "requestdata" not in payload:
            raise ESBRequestError(
                "Payload must be a dict wrapping a 'requestdata' key."
            )
        request_data = payload["requestdata"]
        if not isinstance(request_data, dict):
            raise ESBRequestError("payload['requestdata'] must be a dict.")

        data: dict[str, Any] = {}
        code_field = "pushCode" if request_type is ESBRequestType.PUSH else "apiCode"
        data[code_field] = api_code

        if user_id:
            data["userId"] = user_id
            data["esbBody"] = (
                request_data
                if "Payload" in request_data
                else {"Payload": request_data}
            )
        else:
            data["esbBody"] = request_data

        serialized = _compact_json(data)
        signature = self._signer.sign(serialized)
        envelope = {"data": data, "signature": signature}
        return _compact_json(envelope)

    # --- XML ------------------------------------------------------------
    def build_xml(
        self,
        *,
        api_code: str,
        payload: dict,
        request_type: ESBRequestType,
        user_id: str | None = None,
    ) -> str:
        if "requestdata" not in payload:
            raise ESBRequestError("XML payload requires a 'requestdata' key.")
        body_xml = payload["requestdata"]
        try:
            body = ET.fromstring(body_xml) if isinstance(body_xml, (str, bytes)) else None
        except ET.ParseError:
            body = None
        if body is None:
            raise ESBRequestError("payload['requestdata'] must be a valid XML string.")

        doc = ET.Element("esbrequest")
        data = ET.SubElement(doc, "data")
        tag = "pushCode" if request_type is ESBRequestType.PUSH else "apiCode"
        ET.SubElement(data, tag).text = api_code
        if user_id:
            ET.SubElement(data, "userId").text = str(user_id)
        esb_body = ET.SubElement(data, "esbBody")
        (ET.SubElement(esb_body, "Payload") if user_id else esb_body).append(_strip_layout(body))

        ET.SubElement(doc, "signature").text = self._signer.sign(compact_xml(data))
        return compact_xml(doc)
