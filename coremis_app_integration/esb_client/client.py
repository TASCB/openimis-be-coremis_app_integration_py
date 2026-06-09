"""High-level ESB client.

The :class:`ESBClient` encapsulates the full ESB request lifecycle:

1. Obtain an OAuth2 access token (client_credentials grant, HTTP Basic).
2. Build a signed JSON or XML envelope around the caller's payload.
3. POST the envelope to the ESB engine.
4. Verify the response signature against the ESB's public key.
5. Return a structured :class:`~esb_client.response.ESBResponse`.

The client is stateless beyond a short-lived in-memory token cache, so a
single instance can be safely shared across threads.
"""
from __future__ import annotations

import base64
import logging
import threading
import time
from typing import Any

import requests

from .config import ESBSettings
from .enums import DataFormat, ESBRequestType
from .envelope import EnvelopeBuilder, _compact_json
from .exceptions import (
    ESBAuthenticationError,
    ESBRequestError,
    ESBSignatureError,
)
from .response import ESBResponse
from .signatures import SignatureService

logger = logging.getLogger(__name__)

_TOKEN_REFRESH_SKEW_SECONDS = 30


class _TokenCache:
    """Thread-safe cache for OAuth2 access tokens."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._token: str | None = None
        self._expires_at: float = 0.0

    def get(self) -> str | None:
        with self._lock:
            if self._token and time.time() < self._expires_at:
                return self._token
            return None

    def set(self, token: str, ttl_seconds: int) -> None:
        with self._lock:
            self._token = token
            self._expires_at = time.time() + max(ttl_seconds - _TOKEN_REFRESH_SKEW_SECONDS, 0)

    def clear(self) -> None:
        with self._lock:
            self._token = None
            self._expires_at = 0.0


class ESBClient:
    """Client for the Government ESB.

    Normally instantiated via :meth:`from_django_settings`; the explicit
    constructor is provided for non-Django callers and tests.
    """

    def __init__(
        self,
        settings: ESBSettings,
        *,
        signer: SignatureService | None = None,
        session: requests.Session | None = None,
    ):
        settings.validate()
        self._settings = settings
        self._signer = signer or SignatureService(
            private_key_path=settings.client_private_key_path,
            gov_public_key_b64=settings.gov_esb_public_key_b64,
        )
        self._envelope = EnvelopeBuilder(self._signer)
        self._session = session or requests.Session()
        self._tokens = _TokenCache()

    # --- construction --------------------------------------------------
    @classmethod
    def from_django_settings(cls) -> "ESBClient":
        return cls(ESBSettings.from_django())

    # --- public API ----------------------------------------------------
    def request(
        self,
        *,
        api_code: str,
        payload: dict,
        data_format: DataFormat = DataFormat.JSON,
        request_type: ESBRequestType = ESBRequestType.NORMAL,
        user_id: str | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> ESBResponse:
        """Send a signed request to the ESB and return a parsed response."""
        if not api_code:
            raise ESBRequestError("api_code is required.")
        if not isinstance(payload, dict):
            raise ESBRequestError("payload must be a dict.")

        body = self._build_envelope(
            api_code=api_code,
            payload=payload,
            data_format=data_format,
            request_type=request_type,
            user_id=user_id,
        )
        token = self._get_access_token()
        url = self._settings.engine_url.rstrip("/") + request_type.value
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": data_format.content_type,
        }
        if extra_headers:
            headers.update(extra_headers)

        logger.info("POST %s api_code=%s format=%s", url, api_code, data_format.value)
        logger.debug("ESB request body: %s", body)

        try:
            http_response = self._session.post(
                url,
                headers=headers,
                data=body.encode("utf-8"),
                timeout=self._settings.request_timeout,
            )
        except requests.RequestException as exc:
            raise ESBRequestError(f"ESB transport error: {exc}") from exc

        return self._parse_response(http_response, data_format)

    # --- token handling ------------------------------------------------
    def _get_access_token(self) -> str:
        cached = self._tokens.get()
        if cached:
            return cached

        basic = base64.b64encode(
            f"{self._settings.client_id}:{self._settings.client_secret}".encode("ascii")
        ).decode("ascii")
        headers = {"Authorization": f"Basic {basic}"}
        body = {
            "client_id": self._settings.client_id,
            "client_secret": self._settings.client_secret,
            "grant_type": self._settings.grant_type,
        }

        try:
            response = self._session.post(
                self._settings.auth_url,
                headers=headers,
                data=body,
                timeout=self._settings.request_timeout,
            )
        except requests.RequestException as exc:
            raise ESBAuthenticationError(f"Token endpoint unreachable: {exc}") from exc

        if response.status_code != 200:
            raise ESBAuthenticationError(
                f"Token endpoint returned {response.status_code}: {response.text}"
            )
        try:
            data = response.json()
            token = data["access_token"]
            ttl = int(data.get("expires_in", 300))
        except (ValueError, KeyError) as exc:
            raise ESBAuthenticationError(
                f"Malformed token response: {response.text}"
            ) from exc

        self._tokens.set(token, ttl)
        logger.info("Acquired new ESB access token (ttl=%ss)", ttl)
        return token

    def invalidate_token(self) -> None:
        """Force a refresh on the next request — useful after 401s."""
        self._tokens.clear()

    # --- internal helpers ---------------------------------------------
    def _build_envelope(
        self,
        *,
        api_code: str,
        payload: dict,
        data_format: DataFormat,
        request_type: ESBRequestType,
        user_id: str | None,
    ) -> str:
        if data_format is DataFormat.JSON:
            return self._envelope.build_json(
                api_code=api_code,
                payload=payload,
                request_type=request_type,
                user_id=user_id,
            )
        return self._envelope.build_xml(
            api_code=api_code,
            payload=payload,
            request_type=request_type,
            user_id=user_id,
        )

    def _parse_response(
        self, http_response: requests.Response, data_format: DataFormat
    ) -> ESBResponse:
        if http_response.status_code != 200:
            logger.warning(
                "ESB returned non-200: %s — %s",
                http_response.status_code,
                http_response.text[:500],
            )
            return ESBResponse(
                ok=False,
                status_code=http_response.status_code,
                raw=http_response.text,
                error=f"HTTP {http_response.status_code}",
            )

        if data_format is DataFormat.XML:
            # XML verification is out of scope for this demo; return as-is.
            return ESBResponse(
                ok=True, status_code=200, raw=http_response.text, signature_verified=None
            )

        try:
            body: dict[str, Any] = http_response.json()
        except ValueError as exc:
            raise ESBRequestError("ESB returned non-JSON body.", body=http_response.text) from exc

        verified: bool | None = None
        if self._settings.verify_response_signature:
            if "signature" not in body or "data" not in body:
                raise ESBSignatureError("ESB response missing 'data' or 'signature'.")
            serialized = _compact_json(body["data"])
            verified = self._signer.verify(serialized, body["signature"])
            if not verified:
                logger.error("ESB signature verification failed for requestId=%s",
                             body.get("data", {}).get("requestId"))
                return ESBResponse(
                    ok=False,
                    status_code=200,
                    raw=body,
                    signature_verified=False,
                    error="Invalid ESB response signature",
                )

        return ESBResponse(
            ok=True, status_code=200, raw=body, signature_verified=verified
        )
