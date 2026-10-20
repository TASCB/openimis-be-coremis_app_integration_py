"""
coremis_app_integration.govesb_inbound
=======================================
Verification of inbound GovESB push messages (MUSE → openIMIS).

Outbound sending lives in :mod:`coremis_app_integration.govesb`; this module is
the receiving counterpart. It is deliberately importable **without** the ECDSA
crypto library (``starkbank-ecdsa``) so request handlers can always call it —
the heavy import happens lazily, only when an actual signature must be checked.

Policy (fail-closed in production, open in dev)
-----------------------------------------------
* **Verification not required** — no ``settings.ESB`` block, or
  ``ESB["VERIFY_INBOUND_SIGNATURE"]`` (defaulting to ``ESB["ENABLED"]``) is
  false: the body is accepted as-is. This preserves the dev/testing and
  admin-override use of the inbound REST endpoints with bare JSON payloads.
* **Verification required**: the body MUST be a ``{"data": ..., "signature":
  ...}`` envelope whose base64 ECDSA signature validates against
  ``settings.ESB["GOV_ESB_PUBLIC_KEY_B64"]`` over the ``data`` text exactly as it
  arrived (falling back to ``compact-json(data)`` when no raw body is given).
  Anything else — missing envelope, missing key, crypto lib absent, bad
  signature, or any error — is **rejected** (the caller should return HTTP 401).

The business payload handed back is the envelope's ``esbBody`` (unwrapping a
``Payload`` wrapper if present), or the bare body when no envelope is used.

Replies: :func:`signed_reply` builds the signed ``{"data": {"success", "esbBody" |
"message"}, "signature"}`` a provider sends back, always with HTTP 200.

XML (``<esbrequest>`` / ``<esbresponse>`` with ``<data>`` and ``<signature>``, as in e-GA's
helper): :func:`verify_inbound_xml` and :func:`signed_reply_xml`, same policy.
"""
from __future__ import annotations

import logging

from django.conf import settings

logger = logging.getLogger(__name__)


def _esb_settings() -> dict:
    return getattr(settings, "ESB", None) or {}


def inbound_verification_required() -> bool:
    """True when inbound GovESB signatures must be verified (production)."""
    raw = getattr(settings, "ESB", None)
    if not raw:
        return False
    return bool(raw.get("VERIFY_INBOUND_SIGNATURE", raw.get("ENABLED", True)))


def _unwrap_esb_body(data):
    """Extract the business payload from a verified envelope's ``data``."""
    if not isinstance(data, dict):
        return data
    body = data.get("esbBody", data)
    if isinstance(body, dict) and isinstance(body.get("Payload"), dict):
        return body["Payload"]
    return body


def verify_inbound(body, raw=None):
    """
    Verify an inbound GovESB push. ``raw`` is the request body as received; pass
    it whenever available so the signature is checked over the sender's bytes.

    Returns ``(payload, verified, error)``:
      * ``payload``  — business dict to hand to the service, or ``None`` on reject
      * ``verified`` — ``True`` when the ESB signature cryptographically validated
      * ``error``    — non-``None`` ⇒ reject (HTTP 401); ``None`` ⇒ accept ``payload``
    """
    required = inbound_verification_required()

    is_envelope = isinstance(body, dict) and "data" in body and "signature" in body
    if not is_envelope:
        if required:
            return None, False, "Missing GovESB signed envelope (data/signature)"
        return body, False, None

    data = body["data"]

    def candidates():
        from .esb_client.envelope import signed_content_candidates
        return signed_content_candidates(raw, data)

    verified, problem = _check_signature(candidates, body["signature"])
    if problem:
        if required:
            return None, False, problem
        logger.warning("GovESB inbound: %s; accepted because verification is not required", problem)
    return _unwrap_esb_body(data), verified, None


def verify_inbound_xml(raw):
    """XML twin of :func:`verify_inbound`: ``(esbBody as XML text, verified, error)``."""
    import xml.etree.ElementTree as ET

    from .esb_client.envelope import compact_xml, xml_envelope_fields, xml_signed_content_candidates

    required = inbound_verification_required()
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        return None, False, f"Invalid XML: {exc}"
    data = root.find("data")
    signature = (root.findtext("signature") or "").strip()
    if data is None or not signature:
        if required:
            return None, False, "Missing GovESB signed envelope (data/signature)"
        body = xml_envelope_fields(data).get("esbBody") if data is not None else compact_xml(root)
        return body, False, None

    verified, problem = _check_signature(lambda: xml_signed_content_candidates(raw, data), signature)
    if problem:
        if required:
            return None, False, problem
        logger.warning("GovESB inbound: %s; accepted because verification is not required", problem)
    return xml_envelope_fields(data).get("esbBody"), verified, None


def _check_signature(candidates, signature):
    """``(verified, problem)``; ``problem`` is why the signature could not be accepted."""
    pub = _esb_settings().get("GOV_ESB_PUBLIC_KEY_B64", "")
    if not pub:
        return False, "GOV_ESB_PUBLIC_KEY_B64 not configured"
    try:
        from pathlib import Path

        from .esb_client.signatures import SignatureService

        signer = SignatureService(private_key_path=Path("unused"), gov_public_key_b64=pub)
        ok = any(signer.verify(content, signature) for content in candidates())
    except ImportError:
        logger.warning("GovESB inbound: esb_client/ecdsa unavailable; cannot verify")
        return False, "GovESB verification unavailable (esb_client/ecdsa missing)"
    except Exception as exc:  # noqa: BLE001 — fail closed on any signing error
        logger.warning("GovESB inbound: signature check raised: %s", exc)
        return False, f"Signature verification error: {exc}"
    return (True, None) if ok else (False, "Invalid GovESB signature")


def _sign(serialized):
    """Our signature over ``serialized``, or None when ESB is off or the key can't be used."""
    esb = _esb_settings()
    if not esb or not esb.get("ENABLED", True):
        return None
    try:
        from pathlib import Path

        from .esb_client.signatures import SignatureService

        signer = SignatureService(private_key_path=Path(esb["CLIENT_PRIVATE_KEY"]),
                                  gov_public_key_b64=esb.get("GOV_ESB_PUBLIC_KEY_B64", ""))
        return signer.sign(serialized)
    except Exception as exc:  # noqa: BLE001 — still answer; GovESB decides
        logger.error("GovESB reply could not be signed: %s", exc)
        return None


def signed_reply(success, esb_body=None, message=None) -> str:
    """JSON text of a provider reply; send it unchanged, the signature covers these bytes.
    Unsigned when ESB is off or the key can't be used (logged)."""
    import json

    from .esb_client.envelope import _compact_json

    data = {"success": bool(success)}
    if esb_body is not None:
        data["esbBody"] = esb_body
    if message is not None:
        data["message"] = message
    serialized = _compact_json(data)
    signature = _sign(serialized)
    if signature is None:
        return '{"data":' + serialized + "}"
    return '{"data":' + serialized + ',"signature":' + json.dumps(signature) + "}"


def signed_reply_xml(success, esb_body=None, message=None) -> str:
    """XML text of a provider reply (``<esbresponse>``); ``esb_body`` is an XML string."""
    import xml.etree.ElementTree as ET

    from .esb_client.envelope import compact_xml

    doc = ET.Element("esbresponse")
    data = ET.SubElement(doc, "data")
    ET.SubElement(data, "success").text = "true" if success else "false"
    if esb_body is not None:
        ET.SubElement(data, "esbBody").append(ET.fromstring(compact_xml(esb_body)))
    if message is not None:
        ET.SubElement(data, "message").text = message
    signature = _sign(compact_xml(data))
    if signature is not None:
        ET.SubElement(doc, "signature").text = signature
    return compact_xml(doc)


__all__ = ["verify_inbound", "verify_inbound_xml", "inbound_verification_required", "signed_reply",
           "signed_reply_xml"]
