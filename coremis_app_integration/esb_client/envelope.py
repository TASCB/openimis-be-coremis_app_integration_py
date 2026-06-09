"""ESB request envelope builders for JSON and XML.

The ESB expects a signed envelope of the form::

    {
      "data":      { "apiCode": ..., "esbBody": {...}, "userId": "..." },
      "signature": "<base64 ECDSA signature over the compact-serialized data>"
    }

For XML the equivalent structure is produced with ``<esbrequest>``,
``<data>``, ``<apiCode>``, ``<esbBody>``, ``<signature>`` elements.

Keep the JSON encoder deterministic (no spaces, stable key order) because
the signature is computed over its exact byte-for-byte output.
"""
from __future__ import annotations

import json
import logging
import xml.etree.ElementTree as ET
from typing import Any
from xml.dom import minidom

from .enums import ESBRequestType
from .exceptions import ESBError, ESBRequestError
from .signatures import SignatureService

logger = logging.getLogger(__name__)


def _compact_json(data: Any) -> str:
    """Deterministic JSON serialization matching what the ESB signs."""
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))


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
        if not isinstance(body_xml, str) or not self._is_valid_xml(body_xml):
            raise ESBRequestError("payload['requestdata'] must be a valid XML string.")

        doc = ET.Element("esbrequest")
        data = ET.SubElement(doc, "data")

        tag = "pushCode" if request_type is ESBRequestType.PUSH else "apiCode"
        ET.SubElement(data, tag).text = api_code
        if user_id:
            ET.SubElement(data, "userId").text = str(user_id)

        pretty_body = self._format_xml(body_xml)
        if user_id:
            pretty_body = f"<Payload>{pretty_body}</Payload>"
        pretty_body = pretty_body.replace('<?xml version="1.0" ?>', "")
        esb_body = ET.fromstring(f"<esbBody>{pretty_body}</esbBody>")
        data.append(esb_body)

        data_string = ET.tostring(data, encoding="unicode", method="xml", xml_declaration=True)
        signature = self._signer.sign(data_string)
        ET.SubElement(doc, "signature").text = signature
        return ET.tostring(doc, encoding="unicode", method="xml", xml_declaration=True)

    # --- helpers --------------------------------------------------------
    @staticmethod
    def _is_valid_xml(xml: str) -> bool:
        try:
            ET.fromstring(xml)
            return True
        except ET.ParseError:
            return False

    @staticmethod
    def _format_xml(xml: str) -> str:
        root = ET.fromstring(xml)
        return minidom.parseString(
            ET.tostring(root, encoding="utf-8")
        ).toprettyxml(indent="")
