"""Exception hierarchy for the ESB client.

All exceptions inherit from :class:`ESBError` so consumers can handle every
ESB failure in a single ``except`` block when desired.
"""
from __future__ import annotations


class ESBError(Exception):
    """Base class for every error raised by ``esb_client``."""


class ESBConfigurationError(ESBError):
    """Raised when required settings/keys are missing or invalid."""


class ESBAuthenticationError(ESBError):
    """Raised when the OAuth2 token endpoint rejects the credentials."""


class ESBRequestError(ESBError):
    """Raised when the ESB returns a non-2xx response or malformed body."""

    def __init__(self, message: str, *, status_code: int | None = None, body: object = None):
        super().__init__(message)
        self.status_code = status_code
        self.body = body


class ESBSignatureError(ESBError):
    """Raised when outgoing signing or response verification fails."""
