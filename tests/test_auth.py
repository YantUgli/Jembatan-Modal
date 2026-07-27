"""Auth no.HP + PIN — service (hash/sesi/lockout) + jalur API (Bearer, isolasi).

Rule #6 lahir dari sini: sesi → user → business-nya. Uji bahwa token sesi
memetakan ke tenant yang benar dan **tak pernah** tenant lain.
"""

from __future__ import annotations

from datetime import date

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.main import Kredensial, PesanMasuk
from app.api.main import business_saat_ini as _business_saat_ini
from app.api.main import chat as _chat
from app.api.main import masuk as _masuk_endpoint
from app.api.main import pengguna_saat_ini as _pengguna_saat_ini
from app.models import Business, JenisTransaksi, Sesi, Transaction, User
from app.services.auth import (
    KredensialSalah,
    TerkunciSementara,
    buat_sesi,
    coba_masuk,
    hapus_sesi,
    hash_pin,
    resolusi_sesi,
    verifikasi_pin,
)


def _buat_user(session: Session, no_hp: str, pin: str = "123456", nama: str = "Bu A") -> Business:
    user = User(nama=nama, no_hp=no_hp, pin_hash=hash_pin(pin))
    session.add(user)
    session.flush()
    biz = Business(user_id=user.id, nama_usaha=f"Warung {nama}")
    session.add(biz)
    session.flush()
    return biz


# ── PIN ──────────────────────────────────────────────────────────────────────


def test_hash_pin_roundtrip():
    h = hash_pin("135790")
    assert verifikasi_pin("135790", h)
    assert not verifikasi_pin("000000", h)


def test_salt_beda_tiap_hash():
    assert hash_pin("123456") != hash_pin("123456")


def test_pin_wajib_6_digit():
    for buruk in ("12345", "1234567", "12ab56", "", "abcdef"):
        with pytest.raises(ValueError):
            hash_pin(buruk)


def test_verifikasi_hash_rusak_atau_kosong():
    assert not verifikasi_pin("123456", None)
    assert not verifikasi_pin("123456", "bukan-format")
    assert not verifikasi_pin("123456", "md5$aa$bb")


# ── Sesi ─────────────────────────────────────────────────────────────────────


def test_sesi_resolusi(session: Session):
    biz = _buat_user(session, "0811")
    user = session.get(User, biz.user_id)
    token = buat_sesi(session, user)
    assert resolusi_sesi(session, token).id == user.id


def test_sesi_menyimpan_hash_bukan_token_mentah(session: Session):
    biz = _buat_user(session, "0811")
    user = session.get(User, biz.user_id)
    token = buat_sesi(session, user)
    baris = session.scalar(select(Sesi))
    assert baris.token_hash != token  # yang tersimpan adalah hash, bukan token


def test_sesi_kedaluwarsa_ditolak(session: Session):
    biz = _buat_user(session, "0811")
    user = session.get(User, biz.user_id)
    token = buat_sesi(session, user, ttl_hari=-1)
    assert resolusi_sesi(session, token) is None


def test_sesi_asing_dan_kosong(session: Session):
    _buat_user(session, "0811")
    assert resolusi_sesi(session, "token-ngawur") is None
    assert resolusi_sesi(session, None) is None
    assert resolusi_sesi(session, "") is None


def test_hapus_sesi_mencabut(session: Session):
    biz = _buat_user(session, "0811")
    user = session.get(User, biz.user_id)
    token = buat_sesi(session, user)
    hapus_sesi(session, token)
    assert resolusi_sesi(session, token) is None


# ── Login & lockout ──────────────────────────────────────────────────────────


def test_login_benar(session: Session):
    biz = _buat_user(session, "0811", pin="246810")
    user = coba_masuk(session, "0811", "246810")
    assert user.id == biz.user_id


def test_no_hp_tak_dikenal_dan_pin_salah_pesan_sama(session: Session):
    _buat_user(session, "0811", pin="246810")
    # Anti-enumerasi: dua-duanya KredensialSalah yang sama.
    with pytest.raises(KredensialSalah):
        coba_masuk(session, "0899", "246810")  # no.HP tak ada
    with pytest.raises(KredensialSalah):
        coba_masuk(session, "0811", "000000")  # PIN salah


def test_lockout_setelah_gagal_beruntun(session: Session):
    _buat_user(session, "0811", pin="246810")
    for _ in range(5):
        with pytest.raises(KredensialSalah):
            coba_masuk(session, "0811", "000000")
    # Terkunci sekarang — PIN benar pun ditolak sementara.
    with pytest.raises(TerkunciSementara):
        coba_masuk(session, "0811", "246810")


def test_sukses_mereset_hitungan_gagal(session: Session):
    biz = _buat_user(session, "0811", pin="246810")
    for _ in range(3):
        with pytest.raises(KredensialSalah):
            coba_masuk(session, "0811", "000000")
    coba_masuk(session, "0811", "246810")  # berhasil
    assert session.get(User, biz.user_id).percobaan_gagal == 0


# ── Jalur API (dependency dipanggil langsung — konsisten gaya repo, tanpa HTTP)


def _login_token(session: Session, no_hp: str, pin: str) -> str:
    return _masuk_endpoint(Kredensial(no_hp=no_hp, pin=pin), session)["token"]


def _riwayat(session: Session, token: str) -> dict:
    """Tiru satu request /chat lihat_transaksi ter-auth: resolve tenant dari
    Bearer lalu jalankan endpoint (adapter tak dipakai di jalur aksi)."""
    user = _pengguna_saat_ini(session, authorization=f"Bearer {token}")
    business = _business_saat_ini(session, user)
    return _chat(PesanMasuk(aksi="lihat_transaksi"), session, business, adapter=None)


def test_api_masuk_lalu_chat(session: Session):
    _buat_user(session, "0811", pin="246810")
    token = _login_token(session, "0811", "246810")

    # Tanpa Bearer → 401 sebelum menyentuh bisnis/adapter.
    with pytest.raises(HTTPException) as ex:
        _pengguna_saat_ini(session, authorization=None)
    assert ex.value.status_code == 401

    hasil = _riwayat(session, token)
    assert hasil["kartu"][0]["tipe"] == "riwayat"


def test_api_masuk_pin_salah_401(session: Session):
    _buat_user(session, "0811", pin="246810")
    for kred in (("0811", "000000"), ("0899", "246810")):  # PIN salah / no.HP tak ada
        with pytest.raises(HTTPException) as ex:
            _masuk_endpoint(Kredensial(no_hp=kred[0], pin=kred[1]), session)
        assert ex.value.status_code == 401


def test_api_isolasi_tenant_lewat_sesi(session: Session):
    biz_a = _buat_user(session, "0811", pin="111111", nama="A")
    biz_b = _buat_user(session, "0822", pin="222222", nama="B")
    # Satu transaksi HANYA milik B.
    session.add(
        Transaction(
            business_id=biz_b.id,
            jenis=JenisTransaksi.pemasukan,
            nominal=50000,
            tanggal=date(2026, 7, 20),
        )
    )
    session.flush()

    tok_a = _login_token(session, "0811", "111111")
    tok_b = _login_token(session, "0822", "222222")

    assert _riwayat(session, tok_a)["kartu"][0]["baris"] == []  # A tak lihat transaksi B
    assert len(_riwayat(session, tok_b)["kartu"][0]["baris"]) == 1  # B lihat miliknya
    assert biz_a.id != biz_b.id
