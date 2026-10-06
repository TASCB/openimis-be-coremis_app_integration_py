"""
coremis_app_integration.govesb
==============================
Single GovESB transport for the whole openIMIS deployment.

Every module that needs to talk to the Government ESB (TASAF payment
verification / paylist dispatch, the MUSE payment connector, ...) goes through
``GovESBProducer`` so there is exactly one signed-envelope transport, one set of
credentials/keys, and one place to verify ESB response signatures. It wraps the
vendored ``esb_client`` SDK (ECDSA-signed envelopes over OAuth2).

Configuration (Django ``settings.ESB`` — see ``esb_client.config.ESBSettings``)::

    ESB = {
        "ENABLED":            True,                  # master on/off (default: True when ESB dict present)
        "AUTH_URL":           "https://gw.esb.go.tz/auth/.../token",
        "ENGINE_URL":         "https://gw.esb.go.tz/esb",
        "GRANT_TYPE":         "client_credentials",
        "CLIENT_ID":          "...",
        "CLIENT_SECRET":      "...",
        "CLIENT_PRIVATE_KEY": "/path/client_private.pem",   # secp256k1 PEM
        "CLIENT_PUBLIC_KEY":  "/path/client_public.pem",
        "GOV_ESB_PUBLIC_KEY_B64": "<base64-DER ESB public key>",
        "REQUEST_TIMEOUT":    30,
        "VERIFY_RESPONSE_SIGNATURE": True,
        # Optional: map logical topics to ESB-issued api/push codes.
        "API_CODES": {"tasaf.verification.request": "ABCD1234", ...},
    }

When ``settings.ESB`` is absent or ``ENABLED`` is false the producer becomes a
safe no-op that logs the intended message and returns ``{"published": False,
"disabled": True}`` — so deployments without ESB credentials keep working
exactly as the previous ``[GovESB STUB]`` did, while a configured deployment
sends for real with no code change.
"""
from __future__ import annotations

import logging
import threading
from typing import Optional

from django.conf import settings

from .esb_client import DataFormat, ESBClient, ESBRequestType
from .esb_client.exceptions import ESBConfigurationError, ESBError

logger = logging.getLogger(__name__)


def govesb_enabled() -> bool:
    """True when a usable ``settings.ESB`` block is present and not disabled."""
    raw = getattr(settings, "ESB", None)
    if not raw:
        return False
    return bool(raw.get("ENABLED", True))


class GovESBProducer:
    """
    Thin, shared facade over :class:`esb_client.ESBClient`.

    A single underlying ``ESBClient`` (which keeps its own thread-safe token
    cache) is reused across instances, so callers may freely do
    ``GovESBProducer().publish(...)`` without rebuilding the client/keys.
    """

    _client: Optional[ESBClient] = None
    _client_lock = threading.Lock()

    # ----------------------------------------------------------------- client
    @classmethod
    def _get_client(cls) -> ESBClient:
        if cls._client is None:
            with cls._client_lock:
                if cls._client is None:
                    cls._client = ESBClient.from_django_settings()
        return cls._client

    @classmethod
    def reset(cls) -> None:
        """Drop the cached client (e.g. after a settings/key rotation)."""
        with cls._client_lock:
            cls._client = None

    # ----------------------------------------------------------------- helpers
    @staticmethod
    def _resolve_api_code(topic: str) -> str:
        """Map a logical topic to the ESB-issued api/push code, if configured."""
        raw = getattr(settings, "ESB", None) or {}
        return (raw.get("API_CODES") or {}).get(topic, topic)

    # ----------------------------------------------------------------- publish
    def publish(
        self,
        topic: str,
        payload: dict,
        *,
        request_type: ESBRequestType = ESBRequestType.PUSH,
        data_format: DataFormat = DataFormat.JSON,
        user_id: Optional[str] = None,
    ) -> dict:
        """
        Send ``payload`` to the ESB under the api/push code resolved from
        ``topic``.

        Returns a result dict:
          - ``{"published": False, "disabled": True, ...}`` when ESB is off,
          - ``{"published": True, "ok": ..., "request_id": ..., ...}`` on send.

        Raises :class:`esb_client.ESBError` (auth / transport / signature /
        configuration) when ESB is enabled but the call fails, so the caller can
        decide whether to fail the operation or degrade.
        """
        api_code = self._resolve_api_code(topic)

        if not govesb_enabled():
            logger.info("[GovESB DISABLED] topic=%s api_code=%s payload=%s",
                        topic, api_code, payload)
            return {"published": False, "disabled": True, "topic": topic, "api_code": api_code}

        try:
            client = self._get_client()
        except ESBConfigurationError:
            logger.exception("[GovESB] enabled but misconfigured; topic=%s", topic)
            raise

        response = client.request(
            api_code=api_code,
            payload={"requestdata": payload},
            data_format=data_format,
            request_type=request_type,
            user_id=user_id,
        )

        if response.ok and response.success is False:
            response.ok = False
            response.error = "GovESB refused: {} (errors {})".format(
                response.data.get("message"), response.data.get("errors"))

        result = {
            "published": True,
            "ok": response.ok,
            "topic": topic,
            "api_code": api_code,
            "request_id": response.request_id,
            "signature_verified": response.signature_verified,
            "status_code": response.status_code,
            "esb_body": response.esb_body,
        }
        if not response.ok:
            logger.error("[GovESB] send not ok topic=%s status=%s error=%s",
                         topic, response.status_code, response.error)
            result["error"] = response.error
        else:
            logger.info("[GovESB] sent topic=%s api_code=%s request_id=%s",
                        topic, api_code, response.request_id)
        return result


__all__ = ["GovESBProducer", "govesb_enabled", "ESBError"]
