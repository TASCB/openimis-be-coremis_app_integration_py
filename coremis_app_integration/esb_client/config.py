"""Immutable configuration object for the ESB client.

The client is kept framework-agnostic: a dataclass is used instead of reading
Django settings inside library code. A convenience factory
``ESBSettings.from_django()`` bridges the two.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .exceptions import ESBConfigurationError


@dataclass(frozen=True)
class ESBSettings:
    auth_url: str
    engine_url: str
    grant_type: str
    client_id: str
    client_secret: str
    client_private_key_path: Path
    client_public_key_path: Path
    gov_esb_public_key_b64: str
    request_timeout: int = 30
    verify_response_signature: bool = True

    def validate(self) -> None:
        missing = [
            name
            for name, value in {
                "auth_url": self.auth_url,
                "engine_url": self.engine_url,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            }.items()
            if not value
        ]
        if missing:
            raise ESBConfigurationError(
                f"Missing required ESB settings: {', '.join(missing)}"
            )

    @classmethod
    def from_django(cls) -> "ESBSettings":
        from django.conf import settings

        raw = getattr(settings, "ESB", None)
        if not raw:
            raise ESBConfigurationError(
                "Django settings.ESB is not configured. See config/settings.py."
            )
        instance = cls(
            auth_url=raw["AUTH_URL"],
            engine_url=raw["ENGINE_URL"],
            grant_type=raw.get("GRANT_TYPE", "client_credentials"),
            client_id=raw["CLIENT_ID"],
            client_secret=raw["CLIENT_SECRET"],
            client_private_key_path=Path(raw["CLIENT_PRIVATE_KEY"]),
            client_public_key_path=Path(raw["CLIENT_PUBLIC_KEY"]),
            gov_esb_public_key_b64=raw.get("GOV_ESB_PUBLIC_KEY_B64", ""),
            request_timeout=int(raw.get("REQUEST_TIMEOUT", 30)),
            verify_response_signature=bool(raw.get("VERIFY_RESPONSE_SIGNATURE", True)),
        )
        instance.validate()
        return instance
