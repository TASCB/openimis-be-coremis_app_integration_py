"""ECDSA (secp256k1) signing and verification for ESB payloads.

The ESB contract requires every outgoing envelope to carry a base64-encoded
ECDSA signature of the serialized ``data`` element, and every incoming
response to be verified against the ESB's public key.

This module wraps ``starkbank-ecdsa`` and isolates all key/IO concerns so
that higher layers never touch PEM files directly.
"""
from __future__ import annotations

import base64
import logging
from pathlib import Path

from ellipticcurve import Ecdsa, PrivateKey, PublicKey
from ellipticcurve import Signature as EcSignature

from .exceptions import ESBConfigurationError, ESBSignatureError

logger = logging.getLogger(__name__)


class SignatureService:
    """Signs outgoing payloads and verifies ESB responses.

    An instance caches the parsed private key in memory so repeated calls
    avoid re-reading the PEM file from disk.
    """

    def __init__(self, private_key_path: Path, gov_public_key_b64: str):
        self._private_key_path = Path(private_key_path)
        self._gov_public_key_b64 = gov_public_key_b64
        self._private_key: PrivateKey | None = None

    # --- signing --------------------------------------------------------
    def sign(self, content: str) -> str:
        """Return a base64-encoded ECDSA signature over ``content``."""
        try:
            key = self._load_private_key()
            signature = Ecdsa.sign(content, key)
            return signature.toBase64()
        except ESBConfigurationError:
            raise
        except Exception as exc:  # pragma: no cover - library-level failures
            raise ESBSignatureError(f"Failed to sign payload: {exc}") from exc

    # --- verification ---------------------------------------------------
    def verify(self, content: str, signature_b64: str) -> bool:
        """Verify ``content`` against ``signature_b64`` using the ESB key."""
        if not self._gov_public_key_b64:
            raise ESBConfigurationError(
                "GOV_ESB_PUBLIC_KEY is not configured — cannot verify responses."
            )
        try:
            public_key = PublicKey.fromDer(base64.b64decode(self._gov_public_key_b64))
            signature = EcSignature.fromBase64(signature_b64)
            return Ecdsa.verify(content, signature, public_key)
        except Exception as exc:
            logger.warning("ESB signature verification failed: %s", exc)
            return False

    # --- internal -------------------------------------------------------
    def _load_private_key(self) -> PrivateKey:
        if self._private_key is not None:
            return self._private_key
        if not self._private_key_path.exists():
            raise ESBConfigurationError(
                f"Client private key not found at {self._private_key_path}. "
                "Run `python scripts/generate_keys.py` to create one."
            )
        pem = self._private_key_path.read_text()
        self._private_key = PrivateKey.fromPem(pem)
        return self._private_key

    # --- convenience ----------------------------------------------------
    @staticmethod
    def generate_keypair(private_key_path: Path, public_key_path: Path) -> None:
        """Generate a fresh secp256k1 keypair and write both PEM files."""
        private_key = PrivateKey()
        public_key = private_key.publicKey()

        Path(private_key_path).parent.mkdir(parents=True, exist_ok=True)
        Path(public_key_path).parent.mkdir(parents=True, exist_ok=True)
        Path(private_key_path).write_text(private_key.toPem())
        Path(public_key_path).write_text(public_key.toPem())
