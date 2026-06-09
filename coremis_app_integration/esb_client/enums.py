"""Enumerations used by the ESB client."""
from enum import Enum


class DataFormat(str, Enum):
    """Content-type for the ESB request body."""

    JSON = "json"
    XML = "xml"

    @property
    def content_type(self) -> str:
        return f"application/{self.value}"


class ESBRequestType(str, Enum):
    """ESB routing path. The value is appended to the engine URL."""

    NORMAL = "/request"
    NIDA = "/nida-request"
    PUSH = "/push-request"
