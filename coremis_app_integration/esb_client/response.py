"""Rich wrapper around a raw ESB response."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ESBResponse:
    """Normalized view of an ESB response.

    Attributes
    ----------
    ok:
        ``True`` when the HTTP status was 2xx *and* the response signature
        was verified (or verification was disabled).
    status_code:
        HTTP status code returned by the ESB engine.
    raw:
        The parsed JSON body (for JSON responses) or the raw string (XML /
        error responses).
    signature_verified:
        ``True`` if the ESB signature was cryptographically validated.
        ``None`` if verification was skipped.
    """

    ok: bool
    status_code: int
    raw: Any
    signature_verified: bool | None = None
    error: str | None = None

    # --- Accessors that mirror the ESB document shape ------------------
    @property
    def data(self) -> dict:
        if isinstance(self.raw, dict):
            return self.raw.get("data", {})
        return {}

    @property
    def esb_body(self) -> dict:
        return self.data.get("esbBody", {}) if isinstance(self.data, dict) else {}

    @property
    def request_id(self) -> str | None:
        return self.data.get("requestId") if isinstance(self.data, dict) else None

    @property
    def success(self) -> bool | None:
        return self.data.get("success") if isinstance(self.data, dict) else None

    def __bool__(self) -> bool:  # allows ``if response: ...``
        return self.ok
