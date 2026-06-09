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
  ...}`` envelope whose base64 ECDSA signature validates over the deterministic
  ``compact-json(data)`` against ``settings.ESB["GOV_ESB_PUBLIC_KEY_B64"]``.
  Anything else — missing envelope, missing key, crypto lib absent, bad
  signature, or any error — is **rejected** (the caller should return HTTP 401).

The business payload handed back is the envelope's ``esbBody`` (unwrapping a
``Payload`` wrapper if present), or the bare body when no envelope is used.
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


def verify_inbound(body):
    """
    Verify an inbound GovESB push.

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
    signature = body["signature"]
    pub = _esb_settings().get("GOV_ESB_PUBLIC_KEY_B64", "")

    if not pub:
        if required:
            return None, False, "GOV_ESB_PUBLIC_KEY_B64 not configured"
        return _unwrap_esb_body(data), False, None

    try:
        from pathlib import Path

        from .esb_client.envelope import _compact_json
        from .esb_client.signatures import SignatureService

        signer = SignatureService(private_key_path=Path("unused"), gov_public_key_b64=pub)
        ok = signer.verify(_compact_json(data), signature)
    except ImportError:
        logger.warning("GovESB inbound: esb_client/ecdsa unavailable; cannot verify")
        if required:
            return None, False, "GovESB verification unavailable (esb_client/ecdsa missing)"
        return _unwrap_esb_body(data), False, None
    except Exception as exc:  # noqa: BLE001 — fail closed on any signing error
        logger.warning("GovESB inbound: signature check raised: %s", exc)
        if required:
            return None, False, f"Signature verification error: {exc}"
        return _unwrap_esb_body(data), False, None

    if not ok:
        if required:
            return None, False, "Invalid GovESB signature"
        logger.warning("GovESB inbound: signature invalid but verification not required")
        return _unwrap_esb_body(data), False, None

    return _unwrap_esb_body(data), True, None


__all__ = ["verify_inbound", "inbound_verification_required"]
