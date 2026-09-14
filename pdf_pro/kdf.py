"""Argon2id key derivation. Prefer argon2-cffi; OpenSSL 3 libcrypto via ctypes as fallback."""

from __future__ import annotations

import ctypes
import ctypes.util
from typing import Optional

from pdf_pro.constants import (
    ARGON2_HASH_LEN,
    ARGON2_MEMORY_KIB,
    ARGON2_PARALLELISM,
    ARGON2_TIME_COST,
)


class KdfError(RuntimeError):
    pass


def _argon2_cffi(passphrase: str, salt: bytes) -> Optional[bytes]:
    try:
        from argon2.low_level import Type, hash_secret_raw
    except ImportError:
        return None
    return hash_secret_raw(
        secret=passphrase.encode("utf-8"),
        salt=salt,
        time_cost=ARGON2_TIME_COST,
        memory_cost=ARGON2_MEMORY_KIB,
        parallelism=ARGON2_PARALLELISM,
        hash_len=ARGON2_HASH_LEN,
        type=Type.ID,
    )


class _OsslParam(ctypes.Structure):
    _fields_ = [
        ("key", ctypes.c_char_p),
        ("data_type", ctypes.c_uint),
        ("data", ctypes.c_void_p),
        ("data_size", ctypes.c_size_t),
        ("return_size", ctypes.c_size_t),
    ]


OSSL_PARAM_OCTET_STRING = 5
OSSL_PARAM_UNSIGNED_INT = 2


def _openssl_argon2id(passphrase: str, salt: bytes) -> bytes:
    libname = ctypes.util.find_library("crypto") or "libcrypto.so.3"
    try:
        lib = ctypes.CDLL(libname)
    except OSError as exc:
        raise KdfError("Argon2id is unavailable (install argon2-cffi)") from exc

    lib.EVP_KDF_fetch.restype = ctypes.c_void_p
    lib.EVP_KDF_fetch.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_void_p]
    lib.EVP_KDF_CTX_new.restype = ctypes.c_void_p
    lib.EVP_KDF_CTX_new.argtypes = [ctypes.c_void_p]
    lib.EVP_KDF_derive.restype = ctypes.c_int
    lib.EVP_KDF_free.argtypes = [ctypes.c_void_p]
    lib.EVP_KDF_CTX_free.argtypes = [ctypes.c_void_p]

    kdf = lib.EVP_KDF_fetch(None, b"ARGON2ID", None)
    if not kdf:
        raise KdfError("OpenSSL has no ARGON2ID KDF; install argon2-cffi")
    ctx = lib.EVP_KDF_CTX_new(kdf)
    if not ctx:
        lib.EVP_KDF_free(kdf)
        raise KdfError("Could not create ARGON2ID context")

    pw = passphrase.encode("utf-8")
    pw_buf = ctypes.create_string_buffer(pw)
    salt_buf = ctypes.create_string_buffer(salt)
    iter_v = ctypes.c_uint(ARGON2_TIME_COST)
    mem_v = ctypes.c_uint(ARGON2_MEMORY_KIB)
    lanes_v = ctypes.c_uint(ARGON2_PARALLELISM)

    params = (_OsslParam * 6)()

    def octet(i, key, buf, size):
        params[i].key = key
        params[i].data_type = OSSL_PARAM_OCTET_STRING
        params[i].data = ctypes.cast(buf, ctypes.c_void_p)
        params[i].data_size = size
        params[i].return_size = ctypes.c_size_t(-1).value

    def uint(i, key, ptr):
        params[i].key = key
        params[i].data_type = OSSL_PARAM_UNSIGNED_INT
        params[i].data = ctypes.cast(ptr, ctypes.c_void_p)
        params[i].data_size = ctypes.sizeof(ctypes.c_uint)
        params[i].return_size = ctypes.c_size_t(-1).value

    octet(0, b"pass", pw_buf, len(pw))
    octet(1, b"salt", salt_buf, len(salt))
    uint(2, b"iter", ctypes.byref(iter_v))
    uint(3, b"memcost", ctypes.byref(mem_v))
    uint(4, b"lanes", ctypes.byref(lanes_v))
    params[5].key = None

    out = ctypes.create_string_buffer(ARGON2_HASH_LEN)
    # derive signature: int EVP_KDF_derive(ctx, key, keylen, params)
    lib.EVP_KDF_derive.argtypes = [
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_size_t,
        ctypes.POINTER(_OsslParam),
    ]
    rc = lib.EVP_KDF_derive(ctx, out, ARGON2_HASH_LEN, params)
    lib.EVP_KDF_CTX_free(ctx)
    lib.EVP_KDF_free(kdf)
    if rc <= 0:
        raise KdfError("Argon2id derivation failed")
    return out.raw


def derive_key(passphrase: str, salt: bytes) -> bytes:
    if not passphrase:
        raise KdfError("Passphrase must not be empty")
    if len(salt) < 8:
        raise KdfError("Salt too short")
    key = _argon2_cffi(passphrase, salt)
    if key is not None:
        return key
    return _openssl_argon2id(passphrase, salt)
