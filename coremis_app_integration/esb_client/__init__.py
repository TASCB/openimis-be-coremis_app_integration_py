"""Reusable client library for the Government ESB.

Typical usage::

    from esb_client import ESBClient, DataFormat, ESBRequestType

    client = ESBClient.from_django_settings()
    response = client.request(
        api_code="ABCDEF",
        payload={"requestdata": {"key": "value"}},
        data_format=DataFormat.JSON,
    )
    if response.ok:
        print(response.esb_body)
"""
from .client import ESBClient
from .config import ESBSettings
from .enums import DataFormat, ESBRequestType
from .exceptions import (
    ESBAuthenticationError,
    ESBError,
    ESBRequestError,
    ESBSignatureError,
)
from .response import ESBResponse

__all__ = [
    "ESBClient",
    "ESBSettings",
    "DataFormat",
    "ESBRequestType",
    "ESBResponse",
    "ESBError",
    "ESBAuthenticationError",
    "ESBRequestError",
    "ESBSignatureError",
]
