"""Plain local signature vault, with one-time migration from encrypted v0.2.1 files.

New vaults are unencrypted JSON. Existing AES-256-GCM vault.bin files are left
untouched until the user migrates (or chooses an empty vault).
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
from pdf_pro.paths import vault_file, vault_plain_file


class VaultError(Exception):
    pass


class VaultLocked(VaultError):
    pass


class WrongPassphrase(VaultError):
    def __init__(self) -> None:
        super().__init__(VAULT_WRONG_PASSPHRASE)


def is_encrypted_vault_bytes(raw: bytes) -> bool:
    return bool(raw) and raw.startswith(VAULT_MAGIC)


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


def decrypt_legacy_assets(raw: bytes, passphrase: str) -> list[SignatureAsset]:
    from pdf_pro.kdf import derive_key

    _version, salt, blob = unpack_vault(raw)
    key = derive_key(passphrase, salt)
    plaintext = _aesgcm_decrypt(key, blob)
    try:
        payload = json.loads(plaintext.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise VaultError("Vault payload is corrupt") from exc
    return [SignatureAsset.from_dict(x) for x in payload.get("signatures", [])]


def write_legacy_encrypted_vault(path: Path, passphrase: str, assets: list[SignatureAsset]) -> None:
    """Test/migration helper: write a v0.2.1 encrypted vault.bin."""
    from pdf_pro.kdf import derive_key

    if not passphrase:
        raise VaultError("Passphrase must not be empty")
    salt = secrets.token_bytes(SALT_LEN)
    key = derive_key(passphrase, salt)
    payload = json.dumps(
        {"version": VAULT_VERSION, "signatures": [a.to_dict() for a in assets]},
        separators=(",", ":"),
    ).encode("utf-8")
    packed = pack_vault(salt, _aesgcm_encrypt(key, payload))
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(packed)


class SignatureVault:
    def __init__(self, path: Optional[Path] = None) -> None:
        given = Path(path) if path else vault_plain_file()
        if given.suffix == ".bin":
            self.legacy_path = given
            self.path = given.with_suffix(".json")
        else:
            self.path = given
            self.legacy_path = given.with_name("vault.bin") if given.name else vault_file()
        self._assets: list[SignatureAsset] = []
        if self._plain_exists():
            self._load_plain()

    def _plain_exists(self) -> bool:
        return self.path.is_file() and self.path.stat().st_size > 0

    def _legacy_is_encrypted(self) -> bool:
        if not self.legacy_path.is_file() or self.legacy_path.stat().st_size == 0:
            return False
        try:
            return is_encrypted_vault_bytes(self.legacy_path.read_bytes())
        except OSError:
            return False

    @property
    def exists(self) -> bool:
        return self._plain_exists() or self._legacy_is_encrypted()

    @property
    def needs_migration(self) -> bool:
        if self._plain_exists():
            return False
        return self._legacy_is_encrypted()

    @property
    def unlocked(self) -> bool:
        return not self.needs_migration

    def is_first_use(self) -> bool:
        return not self.exists

    def _require_unlocked(self) -> None:
        if not self.unlocked:
            raise VaultLocked("Signature vault needs migration before use")

    def _load_plain(self) -> None:
        raw = self.path.read_text(encoding="utf-8")
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise VaultError("Vault payload is corrupt") from exc
        self._assets = [SignatureAsset.from_dict(x) for x in payload.get("signatures", [])]

    def migrate(self, passphrase: str) -> None:
        if not self.needs_migration:
            raise VaultError("No encrypted vault to migrate")
        if not (passphrase or "").strip():
            raise VaultError("Passphrase must not be empty")
        raw = self.legacy_path.read_bytes()
        assets = decrypt_legacy_assets(raw, passphrase)
        self._assets = assets
        self._persist()

    def start_empty_leaving_encrypted(self) -> None:
        """Use an empty plain vault; do not delete the encrypted original."""
        self._assets = []
        self._persist()

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
        payload = json.dumps(
            {"version": VAULT_VERSION, "signatures": [a.to_dict() for a in self._assets]},
            indent=2,
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".json.tmp")
        tmp.write_text(payload, encoding="utf-8")
        tmp.replace(self.path)

    def disk_is_ciphertext(self) -> bool:
        """True only for an unmigrated encrypted legacy file with no plain vault."""
        if self._plain_exists():
            return False
        return self._legacy_is_encrypted()
