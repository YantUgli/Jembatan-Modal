"""Evaluasi router intent: `pipenv run python -m app.llm.evaluasi_router [--ulang N]`

Menjawab pertanyaan yang tak bisa dijawab unit test (di sana adapter-nya
terskrip): **apakah model benar-benar memisahkan enam label ini?** Kasusnya di
`evaluasi/router.json`.

Terpisah dari `app.llm.evaluasi` karena yang dinilai berbeda bentuk: di sana
baris transaksi (skor inti/rinci), di sini satu label. Yang ditiru dari sana —
karena mahal dipelajari — adalah tata caranya: jeda demi batas TPM, `--ulang`,
dan **penilaian dari jalan terburuk**.

Dua angka dilaporkan terpisah:

  benar      — label yang cocok dengan `harap`.
  tahu-diri  — kasus ber-`harap: "gagal"` yang benar-benar dijawab `_gagal`.

Salah label ≠ sama beratnya: menebak "koreksi_transaksi" untuk kalimat yang
sebenarnya penjualan baru akan **membatalkan catatan yang benar**. Pasangan
salah-arah itu karena itu dicetak terpisah di akhir.

!!️ Ini memanggil API sungguhan (±31 permintaan sekali jalan).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from dataclasses import dataclass

from app import config
from app.llm.kontrak import Gagal
from app.llm.openai_kompatibel import AdapterOpenAIKompatibel, KesalahanProvider
from app.llm.skema import PilihanAksi, instruksi_router

BERKAS = config.ROOT_DIR / "evaluasi" / "router.json"

# Salah arah yang paling merusak: kalimat pencatatan dibaca sebagai koreksi
# (membatalkan baris yang benar) atau sebaliknya (koreksi jadi catatan hantu).
BERBAHAYA = {("catat_transaksi", "koreksi_transaksi"), ("koreksi_transaksi", "catat_transaksi")}


@dataclass
class Nilai:
    id: str
    teks: str
    harap: str
    dapat: str  # label, atau "gagal"
    benar: bool


def nilai_kasus(kasus: dict, hasil) -> Nilai:
    dapat = "gagal" if isinstance(hasil, Gagal) else hasil.data.aksi.value
    return Nilai(kasus["id"], kasus["teks"], kasus["harap"], dapat, dapat == kasus["harap"])


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Evaluasi router intent terhadap provider aktif.")
    p.add_argument("--ulang", type=int, default=1,
                   help="Jalankan tiap kasus N kali untuk melihat kestabilan.")
    p.add_argument("--saring", default="", help="Hanya kasus yang id-nya memuat teks ini.")
    # Sama seperti evaluasi ekstraksi: batas tier gratis dihitung per TOKEN per
    # menit. Kasus router jauh lebih pendek, tapi jedanya dibiarkan sama supaya
    # dua evaluasi bisa dijalankan berurutan tanpa memikirkan sisa kuota menit.
    p.add_argument("--jeda", type=float, default=5.5,
                   help="Detik jeda antar-permintaan agar tidak menabrak batas TPM.")
    arg = p.parse_args(argv)

    if not config.llm_api_key():
        print("!!  LLM_API_KEY kosong.")
        return 1

    data = json.loads(BERKAS.read_text(encoding="utf-8"))
    kasus = [k for k in data["kasus"] if arg.saring in k["id"]]
    instruksi = instruksi_router()
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
                hasil_ulang.append(
                    nilai_kasus(k, adapter.ekstrak(instruksi, k["teks"], PilihanAksi))
                )
            except KesalahanProvider as e:
                print(f"!!  provider mati di {k['id']}: {e}")
                return 1
        # Dinilai dari jalan TERBURUK, bukan jalan pertama: pengguna cuma
        # mengetik sekali, jadi "pernah benar" bukan jaminan apa pun.
        hasil_ulang.sort(key=lambda h: h.benar)
        n = hasil_ulang[0]
        if len({h.dapat for h in hasil_ulang}) > 1:
            goyah[k["id"]] = sum(h.benar for h in hasil_ulang)
        nilai.append(n)

        tanda = "OK " if n.benar else "!! "
        print(f"{tanda} {n.id:<26} {n.teks}")
        if not n.benar:
            print(f"        harap {n.harap} -> dapat {n.dapat}")

    benar = sum(n.benar for n in nilai)
    total = len(nilai)
    harus_gagal = [n for n in nilai if n.harap == "gagal"]
    gagal_benar = sum(n.benar for n in harus_gagal)
    berbahaya = [n for n in nilai if (n.harap, n.dapat) in BERBAHAYA]

    print(f"\n  benar                          : {benar}/{total} = {benar / total:.0%}")
    print(f"  tahu-diri (harus gagal)        : {gagal_benar}/{len(harus_gagal)}")
    if berbahaya:
        print(f"  !! salah arah catat<->koreksi  : {', '.join(n.id for n in berbahaya)}")
        print("     (paling merusak: membatalkan catatan benar / catatan hantu)")
    if goyah:
        rinci = ", ".join(f"{kid} ({n}/{arg.ulang} benar)" for kid, n in goyah.items())
        print(f"  !! goyah antar-jalan           : {rinci}")
        print("     (skor di atas memakai jalan terburuk tiap kasus)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
