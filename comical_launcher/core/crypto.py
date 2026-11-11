"""AES-256-GCM payload encryption with keys derived from the hardware id
alone, so ciphertext produced on one machine is unreadable on any other
machine — no account, session, or license key involved.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import stat
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

NONCE_LEN = 12

# Fixed, non-secret domain-separation string mixed into every key
# derivation. It adds no real secrecy (it ships in the source) — its only
# job is to stop this launcher's derived keys from colliding with any
# other SHA-256(hwid) use elsewhere in the app.
_KEY_DOMAIN = b"comical-launcher/v1/payload-key"


def _derive_key(hwid: str) -> bytes:
    h = hashlib.sha256()
    h.update(_KEY_DOMAIN)
    h.update(b"::")
    h.update(hwid.encode("utf-8"))
    return h.digest()  # 32 bytes, exactly what AES-256 needs


def encrypt_bytes(plaintext: bytes, hwid: str) -> bytes:
    key = _derive_key(hwid)
    aesgcm = AESGCM(key)
    nonce = os.urandom(NONCE_LEN)
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)
    return nonce + ciphertext  # layout: [12-byte nonce][ciphertext+tag]


def decrypt_bytes(payload: bytes, hwid: str) -> bytes:
    if len(payload) < NONCE_LEN:
        raise ValueError("payload too short")
    nonce, ciphertext = payload[:NONCE_LEN], payload[NONCE_LEN:]
    key = _derive_key(hwid)
    aesgcm = AESGCM(key)
    try:
        return aesgcm.decrypt(nonce, ciphertext, None)
    except Exception as exc:  # cryptography raises InvalidTag
        raise ValueError("decryption failed (wrong key or tampered data)") from exc


def encrypt_file(src: Path, dst: Path, hwid: str) -> None:
    data = src.read_bytes()
    dst.write_bytes(encrypt_bytes(data, hwid))
    _set_owner_only_permissions(dst)


def decrypt_file(src: Path, dst: Path, hwid: str) -> None:
    data = src.read_bytes()
    dst.write_bytes(decrypt_bytes(data, hwid))


def _set_owner_only_permissions(path: Path) -> None:
    if os.name == "posix":
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)  # 0600


def secure_delete(path: Path) -> None:
    """Overwrites a file with random data then zeroes before deleting, so
    the plaintext doesn't linger trivially recoverable on disk."""
    if not path.exists():
        return
    length = path.stat().st_size
    with open(path, "r+b") as f:
        f.write(os.urandom(length))
        f.flush()
        os.fsync(f.fileno())
        f.seek(0)
        f.write(b"\x00" * length)
        f.flush()
        os.fsync(f.fileno())
    path.unlink()


def secure_delete_dir(directory: Path) -> None:
    """Recursively secure-deletes every file in a directory, then removes
    the directory itself."""
    if not directory.exists():
        return
    for child in directory.iterdir():
        if child.is_dir():
            secure_delete_dir(child)
        else:
            secure_delete(child)
    shutil.rmtree(directory, ignore_errors=True)
