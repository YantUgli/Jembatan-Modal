"""Autentikasi no.HP + PIN — deterministik, teruji, tanpa dependensi baru.

Semua primitif kripto dari **stdlib** (konsisten ethos repo: nol SDK vendor):
- PIN di-hash `hashlib.scrypt` (memory-hard) + salt per-user acak.
- Token sesi acak `secrets.token_urlsafe`; yang disimpan **hash SHA-256**-nya.
- Banding rahasia pakai `hmac.compare_digest` (constant-time).

Tak ada angka LLM di sini; aturan #1 tak relevan. Yang relevan: aturan #6 —
isolasi tenant lahir dari sinilah (`resolusi_sesi` → user → business-nya).
"""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import Sesi, User
from app.models.base import now_utc

# Parameter scrypt (RFC 7914). n=2^14 → ~16 MB/hitung; cukup memberati brute-force
# PIN 6 digit tanpa membuat login terasa lambat. maxmem diberi headroom eksplisit
# agar tak menabrak batas bawaan.
_N, _R, _P = 2**14, 8, 1
_MAXMEM = 128 * _N * _R * 2

_PIN_RE = re.compile(r"^\d{6}$")

# Lockout: PIN 6 digit = sejuta kombinasi, lemah. Kunci sebentar setelah
# beberapa gagal beruntun — cukup mematikan tebak-otomatis, tak menyiksa pemilik
# yang cuma salah ketik.
_MAKS_GAGAL = 5
_DURASI_KUNCI = timedelta(minutes=15)


class KredensialSalah(Exception):
    """No.HP tak dikenal ATAU PIN salah — sengaja tak dibedakan (anti-enumerasi)."""


class TerkunciSementara(Exception):
    """Terlalu banyak percobaan gagal; login dikunci hingga `sampai`."""

    def __init__(self, sampai: datetime) -> None:
        self.sampai = sampai
        super().__init__("Terlalu banyak percobaan. Coba lagi nanti.")


# ── PIN ──────────────────────────────────────────────────────────────────────


def hash_pin(pin: str) -> str:
    """`scrypt$<salt_hex>$<hash_hex>`. Menolak PIN yang bukan 6 digit."""
    if not _PIN_RE.match(pin):
        raise ValueError("PIN harus tepat 6 digit angka.")
    salt = secrets.token_bytes(16)
    dk = hashlib.scrypt(pin.encode(), salt=salt, n=_N, r=_R, p=_P, maxmem=_MAXMEM)
    return f"scrypt${salt.hex()}${dk.hex()}"


def verifikasi_pin(pin: str, pin_hash: str | None) -> bool:
    """True bila `pin` cocok. Format hash rusak / kosong → False (bukan error)."""
    if not pin_hash:
        return False
    try:
        skema, salt_hex, hash_hex = pin_hash.split("$")
    except ValueError:
        return False
    if skema != "scrypt":
        return False
    dk = hashlib.scrypt(
        pin.encode(), salt=bytes.fromhex(salt_hex), n=_N, r=_R, p=_P, maxmem=_MAXMEM
    )
    return hmac.compare_digest(dk.hex(), hash_hex)


# Hash umpan: dipakai saat no.HP tak dikenal supaya waktu komputasi tetap sama
# (tanpa scrypt, respons "user tak ada" jauh lebih cepat → membocorkan siapa
# terdaftar). Dihitung sekali saat impor.
_DUMMY_HASH = hash_pin("000000")


# ── Sesi ─────────────────────────────────────────────────────────────────────


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _utc_naive(dt: datetime) -> datetime:
    """Samakan ke UTC naif untuk banding portabel (SQLite kembalikan naif,
    Postgres kembalikan aware)."""
    return dt.astimezone(UTC).replace(tzinfo=None) if dt.tzinfo is not None else dt


def buat_sesi(session: Session, user: User, ttl_hari: int = 30) -> str:
    """Buat sesi baru, kembalikan token **mentah** (hanya di sinilah ia ada —
    yang tersimpan cuma hash-nya)."""
    token = secrets.token_urlsafe(32)
    session.add(
        Sesi(
            user_id=user.id,
            token_hash=_hash_token(token),
            kedaluwarsa_pada=now_utc() + timedelta(days=ttl_hari),
        )
    )
    session.flush()
    return token


def resolusi_sesi(session: Session, token: str | None) -> User | None:
    """Token → User pemilik sesi, atau None bila tak ada/kedaluwarsa."""
    if not token:
        return None
    s = session.scalar(select(Sesi).where(Sesi.token_hash == _hash_token(token)))
    if s is None:
        return None
    if _utc_naive(s.kedaluwarsa_pada) <= _utc_naive(now_utc()):
        return None
    return s.user


def hapus_sesi(session: Session, token: str | None) -> None:
    """Cabut satu sesi (logout). Token asing/None → no-op."""
    if not token:
        return
    session.execute(delete(Sesi).where(Sesi.token_hash == _hash_token(token)))


# ── Login ────────────────────────────────────────────────────────────────────


def coba_masuk(session: Session, no_hp: str, pin: str) -> User:
    """Verifikasi kredensial → User, atau raise.

    ⛔ Anti-enumerasi: no.HP tak dikenal & PIN salah → `KredensialSalah` yang
    **sama**, dan scrypt tetap dijalankan (via hash umpan) agar waktu responsnya
    seragam. Lockout dicek sebelum verifikasi; sukses mereset hitungannya.
    """
    user = session.scalar(select(User).where(User.no_hp == no_hp.strip()))
    now = now_utc()

    if (
        user is not None
        and user.terkunci_sampai is not None
        and _utc_naive(user.terkunci_sampai) > _utc_naive(now)
    ):
        raise TerkunciSementara(user.terkunci_sampai)

    pin_hash = user.pin_hash if (user is not None and user.pin_hash) else _DUMMY_HASH
    cocok = verifikasi_pin(pin, pin_hash)
    ok = user is not None and user.pin_hash is not None and cocok

    if not ok:
        if user is not None:
            user.percobaan_gagal += 1
            if user.percobaan_gagal >= _MAKS_GAGAL:
                user.terkunci_sampai = now + _DURASI_KUNCI
                user.percobaan_gagal = 0
            session.flush()
        raise KredensialSalah

    user.percobaan_gagal = 0
    user.terkunci_sampai = None
    session.flush()
    return user
