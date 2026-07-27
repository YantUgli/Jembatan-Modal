"""Pratinjau laporan sebagai HTML — alat dev, bukan permukaan produk.

    pipenv run python -m app.laporan.pratinjau --usaha 1 -o laporan.html

Ada karena verifikasi visual laporan tidak boleh menyandera pada WeasyPrint:
di mesin Windows tanpa GTK, PDF-nya tak bisa dirender tapi isinya tetap harus
bisa diperiksa mata. Sengaja **tanpa endpoint** — tak ada HTML laporan yang
tersaji lewat HTTP, jadi tak ada permukaan baru yang perlu dijaga izinnya.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from sqlalchemy import select

from app.db import session_scope
from app.laporan.html import render_html
from app.models import Business
from app.services.laporan import JUMLAH_BULAN_DEFAULT, ringkas_laporan


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Render laporan jadi HTML untuk diperiksa mata.")
    p.add_argument("--usaha", type=int, default=None, help="business_id; default = yang pertama.")
    p.add_argument("--bulan", type=int, default=JUMLAH_BULAN_DEFAULT, help="Jumlah bulan.")
    p.add_argument("--hari-ini", default=None, help="Tanggal acuan ISO (untuk data seed lama).")
    p.add_argument("-o", "--keluaran", default="laporan.html")
    arg = p.parse_args(argv)

    hari_ini = date.fromisoformat(arg.hari_ini) if arg.hari_ini else date.today()

    with session_scope() as session:
        if arg.usaha is None:
            business = session.scalars(select(Business).order_by(Business.id).limit(1)).first()
        else:
            business = session.get(Business, arg.usaha)
        if business is None:
            print("!!  Tidak ada usaha di database. Jalankan seed dulu.")
            return 1

        ringkasan = ringkas_laporan(session, business, hari_ini, jumlah_bulan=arg.bulan)
        html = render_html(ringkasan, dibuat_pada=hari_ini)

    tujuan = Path(arg.keluaran)
    tujuan.write_text(html, encoding="utf-8")
    print(f"  usaha   : {ringkasan.identitas.nama_usaha}")
    print(f"  periode : {ringkasan.periode_tampil}")
    print(f"  tertulis: {tujuan.resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
