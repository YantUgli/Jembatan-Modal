"""Evaluasi ekstraksi: `pipenv run python -m app.llm.evaluasi [--ulang N]`

Menjawab pertanyaan yang tidak bisa dijawab unit test: **apakah model ini cukup
untuk bahasa warung Indonesia?** Kasusnya di `evaluasi/ekstraksi.json`.

Dua skor dilaporkan terpisah, sengaja:

  inti   — jenis + nominal + tanggal. Salah di sini = angka di laporan salah.
  rinci  — produk + qty + satuan. Salah di sini = HPP kurang lengkap, tapi
           laba periode tetap benar.

Menggabungkannya jadi satu persentase akan menyembunyikan perbedaan yang
menentukan pilihan provider. Kasus `gagal` dihitung sebagai `inti`: mengaku
tidak tahu adalah jawaban yang benar (aturan #2), bukan kegagalan.

!!️ Ini memanggil API sungguhan (±40 permintaan sekali jalan).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation

from app import config
from app.llm.kontrak import Ekstraksi, Gagal
from app.llm.openai_kompatibel import AdapterOpenAIKompatibel, KesalahanProvider
from app.llm.skema import BarisTransaksi, HasilCatat, instruksi_catat

BERKAS = config.ROOT_DIR / "evaluasi" / "ekstraksi.json"

INTI = ("jenis", "nominal", "tanggal")
RINCI = ("produk", "qty", "satuan")


@dataclass
class Nilai:
    id: str
    teks: str
    inti_benar: bool
    rinci_benar: bool
    beda: list[str]
    dapat: str


def _angka(n) -> Decimal | None:
    if n is None:
        return None
    try:
        return Decimal(str(n))
    except InvalidOperation:
        return None


def _samakan_teks(a, b) -> bool:
    if a is None or b is None:
        return a is None and b is None
    return str(a).strip().casefold() == str(b).strip().casefold()


def _banding_baris(harap: dict, dapat: BarisTransaksi) -> tuple[list[str], list[str]]:
    """→ (beda inti, beda rinci)."""
    beda_inti, beda_rinci = [], []

    if dapat.jenis.value != harap["jenis"]:
        beda_inti.append(f"jenis={dapat.jenis.value}!={harap['jenis']}")
    if _angka(dapat.nominal) != _angka(harap["nominal"]):
        beda_inti.append(f"nominal={dapat.nominal}!={harap['nominal']}")
    if dapat.tanggal.isoformat() != harap["tanggal"]:
        beda_inti.append(f"tanggal={dapat.tanggal}!={harap['tanggal']}")

    # `produk` sengaja LONGGAR: harapan kosong berarti "bebas". Model yang
    # mengisi produk='listrik' untuk "bayar listrik" tidak merugikan siapa pun.
    if harap.get("produk") and not _samakan_teks(dapat.produk, harap["produk"]):
        beda_rinci.append(f"produk={dapat.produk!r}!={harap['produk']!r}")

    # `qty`/`satuan` sengaja KETAT sampai ke arah sebaliknya: mengisi takaran
    # yang tidak diucapkan pengguna ("1 ekor" untuk "beli ayam 200rb") adalah
    # mengarang data — pelanggaran aturan #2 yang akan masuk ke HPP diam-diam.
    if _angka(dapat.qty) != _angka(harap.get("qty")):
        asal = "mengarang" if harap.get("qty") is None else "salah"
        beda_rinci.append(f"qty {asal}={dapat.qty}!={harap.get('qty')}")
    if not _samakan_teks(dapat.satuan, harap.get("satuan")):
        asal = "mengarang" if harap.get("satuan") is None else "salah"
        beda_rinci.append(f"satuan {asal}={dapat.satuan!r}!={harap.get('satuan')!r}")

    return beda_inti, beda_rinci


def _ringkas_baris(b: BarisTransaksi) -> str:
    ekor = " ".join(
        str(x) for x in (b.qty, b.satuan, b.produk) if x is not None
    )
    return f"{b.jenis.value} {b.nominal} {b.tanggal}" + (f" [{ekor}]" if ekor else "")


def nilai_kasus(kasus: dict, hasil: Ekstraksi | Gagal) -> Nilai:
    teks, kid = kasus["teks"], kasus["id"]
    harus_gagal = kasus["harap"] == "gagal"

    if isinstance(hasil, Gagal):
        dapat = f"Gagal({hasil.alasan[:60]})"
        if harus_gagal:
            return Nilai(kid, teks, True, True, [], dapat)
        return Nilai(kid, teks, False, False, ["menyerah padahal bisa"], dapat)

    baris = hasil.data.baris
    dapat = " | ".join(_ringkas_baris(b) for b in baris) or "(kosong)"

    if harus_gagal:
        # Daftar kosong = "tidak ada transaksi di kalimat ini". Itu bentuk lain
        # dari mengaku tidak tahu, bukan karangan — jangan dihukum seperti
        # model yang menyulap angka dari ketiadaan.
        if not baris:
            return Nilai(kid, teks, True, True, [], "(tidak ada transaksi)")
        return Nilai(kid, teks, False, False, ["MENEBAK padahal harus gagal"], dapat)

    harap = kasus["harap"]
    if len(baris) != len(harap):
        return Nilai(kid, teks, False, False,
                     [f"jumlah baris {len(baris)}!={len(harap)}"], dapat)

    semua_inti, semua_rinci = [], []
    for h, d in zip(harap, baris):
        bi, br = _banding_baris(h, d)
        semua_inti += bi
        semua_rinci += br

    return Nilai(kid, teks, not semua_inti, not semua_rinci,
                 semua_inti + semua_rinci, dapat)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Evaluasi ekstraksi terhadap provider aktif.")
    p.add_argument("--ulang", type=int, default=1,
                   help="Jalankan tiap kasus N kali untuk melihat kestabilan.")
    p.add_argument("--saring", default="", help="Hanya kasus yang id-nya memuat teks ini.")
    # Tier gratis Groq dibatasi TOKEN per menit (12.000), bukan permintaan per
    # menit. Satu kasus ~1.100 token, jadi ~11 kasus/menit adalah atapnya.
    # Menabraknya lalu mengandalkan retry cuma memindahkan antrean ke belakang
    # dan membakar kuota dua kali; lebih jujur mengatur langkah sejak awal.
    p.add_argument("--jeda", type=float, default=5.5,
                   help="Detik jeda antar-permintaan agar tidak menabrak batas TPM.")
    arg = p.parse_args(argv)

    if not config.llm_api_key():
        print("!!  LLM_API_KEY kosong.")
        return 1

    data = json.loads(BERKAS.read_text(encoding="utf-8"))
    acuan = date.fromisoformat(data["acuan"])
    kasus = [k for k in data["kasus"] if arg.saring in k["id"]]
    instruksi = instruksi_catat(acuan)
    adapter = AdapterOpenAIKompatibel.dari_env(percobaan=5, jeda=8.0)

    n_panggil = len(kasus) * arg.ulang
    print(f"  model  : {config.llm_model()}")
    print(f"  kasus  : {len(kasus)} x {arg.ulang} jalan"
          f"  (~{n_panggil * arg.jeda / 60:.0f} menit, dijeda demi batas TPM)\n")

    nilai: list[Nilai] = []
    goyah: Counter = Counter()
    pertama = True
    for k in kasus:
        hasil_ulang = []
        for _ in range(arg.ulang):
            if not pertama:
                time.sleep(arg.jeda)
            pertama = False
            try:
                hasil_ulang.append(nilai_kasus(k, adapter.ekstrak(instruksi, k["teks"], HasilCatat)))
            except KesalahanProvider as e:
                print(f"!!  provider mati di {k['id']}: {e}")
                return 1
        # Kasus yang goyah dinilai dari jalan TERBURUK, bukan jalan pertama.
        # Suhu sudah 0.0 dan tetap goyah — jadi "pernah benar" bukan jaminan
        # apa pun bagi pengguna yang cuma mengetik sekali.
        hasil_ulang.sort(key=lambda h: (h.inti_benar, h.rinci_benar))
        n = hasil_ulang[0]
        if len({(h.inti_benar, h.rinci_benar) for h in hasil_ulang}) > 1:
            goyah[k["id"]] = sum(h.inti_benar for h in hasil_ulang)
        nilai.append(n)

        tanda = "OK " if n.inti_benar and n.rinci_benar else ("~  " if n.inti_benar else "!! ")
        print(f"{tanda} {n.id:<26} {n.teks}")
        if n.beda:
            print(f"        {n.dapat}")
            print(f"        beda: {', '.join(n.beda)}")

    inti = sum(n.inti_benar for n in nilai)
    rinci = sum(n.rinci_benar for n in nilai)
    total = len(nilai)
    gagal_seharusnya = [n for n in nilai if data_harap(data, n.id) == "gagal"]
    gagal_benar = sum(n.inti_benar for n in gagal_seharusnya)

    print(f"\n  inti  (jenis+nominal+tanggal) : {inti}/{total} = {inti / total:.0%}")
    print(f"  rinci (produk+qty+satuan)     : {rinci}/{total} = {rinci / total:.0%}")
    print(f"  tahu-diri (harus Gagal)       : {gagal_benar}/{len(gagal_seharusnya)}")
    if goyah:
        rinci_goyah = ", ".join(f"{kid} ({n}/{arg.ulang} benar)" for kid, n in goyah.items())
        print(f"  !! goyah antar-jalan           : {rinci_goyah}")
        print("     (skor di atas memakai jalan terburuk tiap kasus)")
    return 0


def data_harap(data: dict, kid: str):
    for k in data["kasus"]:
        if k["id"] == kid:
            return k["harap"]
    return None


if __name__ == "__main__":
    sys.exit(main())
