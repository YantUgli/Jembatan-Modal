"""`angka_rupiah` — parser angka gaya Indonesia (titik=ribuan, koma=desimal).

Jebakan klasik jalur impor CSV (§5 B3 rencana eksekusi): kalau ini salah,
seluruh angka yang diimpor salah baca tanpa ada yang tahu.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.services.angka import angka_rupiah


@pytest.mark.parametrize(
    "teks,diharapkan",
    [
        ("1.000", Decimal("1000")),
        ("1.250.000,50", Decimal("1250000.50")),
        ("2500", Decimal("2500")),
        ("0", Decimal("0")),
        ("Rp1.500", Decimal("1500")),
        ("Rp 75.000", Decimal("75000")),
        ("  1.000  ", Decimal("1000")),
        ("-1.500", Decimal("-1500")),
        ("1.234.567.890,12", Decimal("1234567890.12")),
        ("0,5", Decimal("0.5")),
    ],
)
def test_angka_rupiah_kasus_benar(teks: str, diharapkan: Decimal):
    assert angka_rupiah(teks) == diharapkan


@pytest.mark.parametrize(
    "teks",
    [
        "",
        "   ",
        None,
        "abc",
        "-",
        ".",
        ",",
        "1,2,3",  # dua koma — bukan angka Indonesia yang sah
        "Rp",
    ],
)
def test_angka_rupiah_invalid_mengembalikan_none_bukan_crash(teks):
    assert angka_rupiah(teks) is None
