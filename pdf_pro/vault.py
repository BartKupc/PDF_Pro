"""Passphrase-protected signature vault: AES-256-GCM at rest, Argon2id KDF.

Passphrase is never stored. Unlock is per process/session.
"""

from __future__ import annotations

import json
import os
import secrets
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from pdf_pro.constants import (
    AES_NONCE_LEN,
    SALT_LEN,
    VAULT_MAGIC,
    VAULT_VERSION,
    VAULT_WRONG_PASSPHRASE,
)
from pdf_pro.kdf import derive_key
from pdf_pro.paths import vault_file


class VaultError(Exception):
    pass


class VaultLocked(VaultError):
    pass


class WrongPassphrase(VaultError):
    def __init__(self) -> None:
        super().__init__(VAULT_WRONG_PASSPHRASE)


def _aesgcm_encrypt(key: bytes, plaintext: bytes) -> bytes:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    nonce = os.urandom(AES_NONCE_LEN)
    ct = AESGCM(key).encrypt(nonce, plaintext, None)
    return nonce + ct


def _aesgcm_decrypt(key: bytes, blob: bytes) -> bytes:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    if len(blob) < AES_NONCE_LEN + 16:
        raise VaultError("Vault file is truncated or corrupt")
    nonce, ct = blob[:AES_NONCE_LEN], blob[AES_NONCE_LEN:]
    try:
        return AESGCM(key).decrypt(nonce, ct, None)
    except Exception as exc:
        raise WrongPassphrase() from exc


def pack_vault(salt: bytes, ciphertext: bytes) -> bytes:
    if len(salt) != SALT_LEN:
        raise VaultError("Invalid salt length")
    return VAULT_MAGIC + bytes([VAULT_VERSION]) + salt + ciphertext


def unpack_vault(raw: bytes) -> tuple[int, bytes, bytes]:
    hdr = len(VAULT_MAGIC) + 1 + SALT_LEN
    if len(raw) < hdr + AES_NONCE_LEN + 16:
        raise VaultError("Vault file is truncated or corrupt")
    if not raw.startswith(VAULT_MAGIC):
        raise VaultError("Not a PDF_Pro vault file")
    version = raw[len(VAULT_MAGIC)]
    salt = raw[len(VAULT_MAGIC) + 1 : hdr]
    return version, salt, raw[hdr:]


@dataclass
class SignatureAsset:
    id: str
    name: str
    kind: str  # draw | type | image
    png_b64: str = ""
    strokes: list = field(default_factory=list)
    text: str = ""
    font_family: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "kind": self.kind,
            "png_b64": self.png_b64,
            "strokes": self.strokes,
            "text": self.text,
            "font_family": self.font_family,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SignatureAsset":
        return cls(
            id=str(data["id"]),
            name=str(data.get("name") or "Signature"),
            kind=str(data.get("kind") or "image"),
            png_b64=str(data.get("png_b64") or ""),
            strokes=list(data.get("strokes") or []),
            text=str(data.get("text") or ""),
            font_family=str(data.get("font_family") or ""),
        )


class SignatureVault:
    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = Path(path) if path else vault_file()
        self._key: Optional[bytes] = None
        self._salt: Optional[bytes] = None
        self._assets: list[SignatureAsset] = []

    @property
    def exists(self) -> bool:
        return self.path.is_file() and self.path.stat().st_size > 0

    @property
    def unlocked(self) -> bool:
        return self._key is not None

    def is_first_use(self) -> bool:
        return not self.exists

    def _require_unlocked(self) -> None:
        if self._key is None:
            raise VaultLocked("Signature vault is locked")

    def set_passphrase(self, passphrase: str) -> None:
        """First-use: create an empty encrypted vault."""
        if self.exists:
            raise VaultError("Vault already exists; unlock it instead")
        if not passphrase:
            raise VaultError("Passphrase must not be empty")
        self._salt = secrets.token_bytes(SALT_LEN)
        self._key = derive_key(passphrase, self._salt)
        self._assets = []
        self._persist()

    def unlock(self, passphrase: str) -> None:
        if not self.exists:
            raise VaultError("No vault on disk; set a passphrase first")
        raw = self.path.read_bytes()
        _version, salt, blob = unpack_vault(raw)
        key = derive_key(passphrase, salt)
        plaintext = _aesgcm_decrypt(key, blob)
        try:
            payload = json.loads(plaintext.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise VaultError("Vault payload is corrupt") from exc
        self._key = key
        self._salt = salt
        self._assets = [SignatureAsset.from_dict(x) for x in payload.get("signatures", [])]

    def lock(self) -> None:
        self._key = None
        self._salt = None
        self._assets = []

    def list_assets(self) -> list[SignatureAsset]:
        self._require_unlocked()
        return list(self._assets)

    def add(self, asset: SignatureAsset) -> SignatureAsset:
        self._require_unlocked()
        if not asset.id:
            asset.id = str(uuid.uuid4())
        self._assets.append(asset)
        self._persist()
        return asset

    def remove(self, asset_id: str) -> None:
        self._require_unlocked()
        self._assets = [a for a in self._assets if a.id != asset_id]
        self._persist()

    def get(self, asset_id: str) -> Optional[SignatureAsset]:
        self._require_unlocked()
        for a in self._assets:
            if a.id == asset_id:
                return a
        return None

    def rename(self, asset_id: str, name: str) -> SignatureAsset:
        asset = self.get(asset_id)
        if asset is None:
            raise VaultError("Signature not found")
        asset.name = (name or "").strip() or asset.name
        self._persist()
        return asset

    def replace(self, asset_id: str, new_asset: SignatureAsset) -> SignatureAsset:
        self._require_unlocked()
        for i, a in enumerate(self._assets):
            if a.id == asset_id:
                new_asset.id = asset_id
                self._assets[i] = new_asset
                self._persist()
                return new_asset
        raise VaultError("Signature not found")

    def _persist(self) -> None:
        self._require_unlocked()
        assert self._key is not None and self._salt is not None
        payload = json.dumps(
            {"version": VAULT_VERSION, "signatures": [a.to_dict() for a in self._assets]},
            separators=(",", ":"),
        ).encode("utf-8")
        blob = _aesgcm_encrypt(self._key, payload)
        packed = pack_vault(self._salt, blob)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".bin.tmp")
        tmp.write_bytes(packed)
        tmp.replace(self.path)

    def disk_is_ciphertext(self) -> bool:
        """True if the on-disk file does not contain recoverable PNG/JSON plaintext."""
        if not self.exists:
            return True
        raw = self.path.read_bytes()
        if not raw.startswith(VAULT_MAGIC):
            return False
        # PNG magic or JSON should never appear after the header in a valid vault
        body = raw[len(VAULT_MAGIC) + 1 + SALT_LEN :]
        if b"\x89PNG" in body or b'"signatures"' in body or b"png_b64" in body:
            return False
        return True
