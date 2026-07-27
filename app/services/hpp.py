"""Service HPP (Pilar 4) — jantung "untung jujur".

Deterministik, ber-unit-test. LLM tidak pernah masuk ke sini (prinsip #1).

Formula yang berlaku sekarang (material-only, 02-arsitektur.md §3a):

    HPP_per_unit(reseller)  = harga_beli_terakhir
    HPP_per_unit(produksi)  = Σ(qty_bahanᵢ × harga_satuanᵢ) ÷ yield_qty
    laba_kotor_per_unit     = harga_jual − HPP_per_unit
    HPP_total(periode)      = Σ(qty_terjual_produk × HPP_per_unit_produk)

Degradasi wajib (jangan mengarang angka saat data kurang):
    - produk belum punya resep        → HPP belum diketahui
    - bahan belum ada harganya         → HPP belum lengkap + daftar bahan kurang
    - penjualan tak terkenali produk   → tidak dipaksa masuk HPP
    - komponen bukan `material`         → belum didukung (labor_time/overhead = slot)
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    CostItemPrice,
    HppSnapshot,
    JenisProduk,
    JenisTransaksi,
    Product,
    Recipe,
    TipeKomponen,
    Transaction,
)
from app.services.angka import _dec, _rapikan, _uang
from app.services.harga import HargaTerpilih, harga_jual_berlaku


@dataclass(frozen=True)
class KonteksHarga:
    """Konteks penjualan yang menentukan harga jual mana yang berlaku.

    Semua opsional: tanpa konteks, yang terpilih adalah harga umum produk.
    Dipakai untuk menjawab "untung berapa kalau dijual eceran vs ke reseller"
    tanpa menyimpan angka laba yang berbeda-beda di skema.
    """

    tanggal: date | None = None
    kanal: str | None = None
    grade: str | None = None
    qty: Decimal | None = None


def _harga_jual(
    session: Session, product: Product, konteks: KonteksHarga | None
) -> HargaTerpilih | None:
    k = konteks or KonteksHarga()
    return harga_jual_berlaku(
        session, product.id, product.business_id,
        tanggal=k.tanggal, kanal=k.kanal, grade=k.grade, qty=k.qty,
    )


class StatusHpp(str, enum.Enum):
    lengkap = "lengkap"
    belum_ada_resep = "belum_ada_resep"          # produksi tanpa resep
    harga_tidak_lengkap = "harga_tidak_lengkap"  # ada bahan tanpa harga
    belum_ada_harga_beli = "belum_ada_harga_beli"  # reseller tanpa transaksi beli
    tipe_belum_didukung = "tipe_belum_didukung"  # ada komponen non-material
    subproduk_tidak_lengkap = "subproduk_tidak_lengkap"  # sub-produk belum bisa dihitung
    resep_melingkar = "resep_melingkar"          # A memakai B, B memakai A
    satuan_tidak_cocok = "satuan_tidak_cocok"    # takaran resep ≠ satuan harga


def _samakan_satuan(s: str | None) -> str | None:
    """Normalisasi satuan seminimal mungkin: hanya spasi & huruf besar-kecil.

    ⛔ Sengaja TIDAK mengenali sinonim ("kilogram" = "kg") dan TIDAK mengonversi
    ("gram" = 1/1000 kg). Menebak maksud pengguna dari string satuan adalah
    mengarang angka lewat pintu belakang (aturan #2) — dan tabel konversi diam-diam
    adalah bug berikutnya yang menunggu. Kalau konversi dibutuhkan nanti, ia harus
    eksplisit, bersumber, dan diuji tersendiri.
    """
    if s is None:
        return None
    bersih = s.strip().casefold()
    return bersih or None


def _satuan_bentrok(satuan_pemakaian: str | None, satuan_harga: str | None) -> bool:
    """True hanya bila keduanya diketahui DAN berbeda.

    Kalau salah satu tidak tercatat, kita memang tidak bisa memverifikasi apa pun —
    jangan berpura-pura menemukan masalah, dan jangan pula berpura-pura aman.
    """
    a, b = _samakan_satuan(satuan_pemakaian), _samakan_satuan(satuan_harga)
    return a is not None and b is not None and a != b


@dataclass
class KomponenHpp:
    nama: str
    tipe: str  # material | sub_produk (labor_time/overhead = slot, belum dihitung)
    qty: Decimal
    satuan: str | None
    harga_satuan: Decimal | None
    tanggal_harga: date | None
    subtotal: Decimal | None
    cost_item_id: int | None = None
    product_id: int | None = None


@dataclass
class HasilHpp:
    product_id: int
    nama: str
    jenis: str
    status: StatusHpp
    hpp_per_unit: Decimal | None
    harga_jual: Decimal | None
    laba_kotor_per_unit: Decimal | None
    # keterangan harga jual mana yang terpilih (kanal/grade/tier + sejak kapan)
    harga_jual_konteks: str | None = None
    yield_qty: Decimal | None = None          # hasil kotor
    faktor_kehilangan: Decimal | None = None  # pecahan 0..<1
    yield_efektif: Decimal | None = None      # yang benar-benar bisa dijual
    satuan_hpp: str | None = None  # satuan yang berlaku untuk `hpp_per_unit`
    komponen: list[KomponenHpp] = field(default_factory=list)
    bahan_kurang_harga: list[str] = field(default_factory=list)
    satuan_bertabrakan: list[str] = field(default_factory=list)
    catatan: list[str] = field(default_factory=list)

    @property
    def diketahui(self) -> bool:
        return self.hpp_per_unit is not None

    def rincian_json(self) -> dict:
        """Untuk disimpan di `hpp_snapshots.rincian` — asal tiap angka."""
        return {
            "status": self.status.value,
            "jenis": self.jenis,
            "hpp_per_unit": str(self.hpp_per_unit) if self.hpp_per_unit is not None else None,
            "harga_jual": str(self.harga_jual) if self.harga_jual is not None else None,
            "harga_jual_konteks": self.harga_jual_konteks,
            "satuan_hpp": self.satuan_hpp,
            "yield_qty": str(self.yield_qty) if self.yield_qty is not None else None,
            "faktor_kehilangan": (
                str(self.faktor_kehilangan) if self.faktor_kehilangan is not None else None
            ),
            "yield_efektif": str(self.yield_efektif) if self.yield_efektif is not None else None,
            "komponen": [
                {
                    "cost_item_id": k.cost_item_id,
                    "product_id": k.product_id,
                    "nama": k.nama,
                    "tipe": k.tipe,
                    "qty": str(k.qty),
                    "satuan": k.satuan,
                    "harga_satuan": str(k.harga_satuan) if k.harga_satuan is not None else None,
                    "tanggal_harga": k.tanggal_harga.isoformat() if k.tanggal_harga else None,
                    "subtotal": str(k.subtotal) if k.subtotal is not None else None,
                }
                for k in self.komponen
            ],
            "bahan_kurang_harga": self.bahan_kurang_harga,
            "satuan_bertabrakan": self.satuan_bertabrakan,
            "catatan": self.catatan,
        }


def _harga_terakhir(session: Session, cost_item_id: int) -> CostItemPrice | None:
    """Harga beli terakhir sebuah komponen biaya (append-only, bertanggal)."""
    stmt = (
        select(CostItemPrice)
        .where(CostItemPrice.cost_item_id == cost_item_id)
        .order_by(CostItemPrice.tanggal.desc(), CostItemPrice.id.desc())
        .limit(1)
    )
    return session.scalars(stmt).first()


def _hpp_reseller(
    session: Session, product: Product, konteks: KonteksHarga | None = None
) -> HasilHpp:
    """Reseller: HPP = harga beli terakhir (dari transaksi pembelian barang)."""
    pilihan_harga = _harga_jual(session, product, konteks)
    harga_jual = pilihan_harga.harga if pilihan_harga is not None else None
    stmt = (
        select(Transaction)
        .where(
            Transaction.business_id == product.business_id,  # isolasi tenant
            Transaction.product_id == product.id,
            Transaction.jenis == JenisTransaksi.pengeluaran,
            Transaction.qty.is_not(None),
            Transaction.qty > 0,
            Transaction.dibatalkan_pada.is_(None),  # buku append-only
        )
        .order_by(Transaction.tanggal.desc(), Transaction.id.desc())
        .limit(1)
    )
    beli = session.scalars(stmt).first()
    if beli is None:
        return HasilHpp(
            product_id=product.id,
            nama=product.nama,
            jenis=product.jenis.value,
            status=StatusHpp.belum_ada_harga_beli,
            hpp_per_unit=None,
            harga_jual=harga_jual,
            laba_kotor_per_unit=None,
            catatan=["Belum ada transaksi pembelian barang ini — harga beli belum diketahui."],
        )

    # Satuan pembelian harus sesuai `satuan_beli` yang dipakai untuk konversi —
    # kalau kadang beli per sak kadang per kg, konversinya salah diam-diam.
    if _satuan_bentrok(beli.satuan, product.satuan_beli):
        bentrok = (
            f"{product.nama} (dibeli per '{beli.satuan}', "
            f"tapi satuan beli produk ini '{product.satuan_beli}')"
        )
        return HasilHpp(
            product_id=product.id, nama=product.nama, jenis=product.jenis.value,
            status=StatusHpp.satuan_tidak_cocok, hpp_per_unit=None,
            harga_jual=harga_jual, laba_kotor_per_unit=None,
            satuan_hpp=product.satuan_jual, satuan_bertabrakan=[bentrok],
            catatan=[
                "Satuan pembelian berbeda dengan satuan beli yang tercatat untuk "
                f"produk ini: {bentrok}. Samakan dulu satuannya."
            ],
        )

    harga_per_satuan_beli = _dec(beli.nominal) / _dec(beli.qty)

    # Pengeceran: 1 satuan beli → `isi` satuan jual, dikurangi susut.
    isi = (
        _dec(product.isi_per_satuan_beli)
        if product.isi_per_satuan_beli is not None
        else Decimal("1")
    )
    faktor = (
        _dec(product.faktor_kehilangan) if product.faktor_kehilangan is not None else None
    )
    isi_efektif = isi * (Decimal("1") - faktor) if faktor is not None else isi

    if isi <= 0 or (faktor is not None and not (0 <= faktor < 1)) or isi_efektif <= 0:
        return HasilHpp(
            product_id=product.id, nama=product.nama, jenis=product.jenis.value,
            status=StatusHpp.belum_ada_harga_beli, hpp_per_unit=None,
            harga_jual=harga_jual, laba_kotor_per_unit=None,
            faktor_kehilangan=faktor, satuan_hpp=product.satuan_jual,
            catatan=["Isi per satuan beli tidak valid (≤ 0) — HPP belum bisa dihitung."],
        )

    hpp = _uang(harga_per_satuan_beli / isi_efektif)
    laba = _uang(harga_jual - hpp) if harga_jual is not None else None
    satuan_hpp = product.satuan_jual or beli.satuan

    komponen = [
        KomponenHpp(
            nama=product.nama,
            tipe="material",
            qty=_dec(beli.qty),
            satuan=beli.satuan,
            harga_satuan=_uang(harga_per_satuan_beli),
            tanggal_harga=beli.tanggal,
            subtotal=_uang(_dec(beli.nominal)),
        )
    ]
    catatan = [f"Harga beli terakhir per {beli.tanggal.isoformat()}."]
    if product.isi_per_satuan_beli is not None:
        catatan.append(
            f"1 {product.satuan_beli} = {_rapikan(isi)} {product.satuan_jual}."
        )
    if faktor is not None and faktor > 0:
        persen = (faktor * Decimal("100")).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
        catatan.append(
            f"Sudah memperhitungkan susut {_rapikan(persen)}%: dari {_rapikan(isi)} "
            f"{satuan_hpp}, terhitung {_rapikan(isi_efektif)} {satuan_hpp} yang bisa dijual."
        )

    return HasilHpp(
        product_id=product.id,
        nama=product.nama,
        jenis=product.jenis.value,
        status=StatusHpp.lengkap,
        hpp_per_unit=hpp,
        harga_jual=harga_jual,
        laba_kotor_per_unit=laba,
        harga_jual_konteks=pilihan_harga.sebagai_teks() if pilihan_harga else None,
        yield_qty=isi if product.isi_per_satuan_beli is not None else None,
        faktor_kehilangan=faktor,
        yield_efektif=isi_efektif if product.isi_per_satuan_beli is not None else None,
        satuan_hpp=satuan_hpp,
        komponen=komponen,
        catatan=catatan,
    )


def _hpp_produksi(
    session: Session,
    product: Product,
    jejak: tuple[int, ...] = (),
    memo: dict[tuple, HasilHpp] | None = None,
    konteks: KonteksHarga | None = None,
) -> HasilHpp:
    """Produksi: HPP = Σ(qty komponen × harga satuan) ÷ yield.

    Komponen bisa berupa bahan (`cost_item`) atau **sub-produk** (`product`)
    yang HPP-nya dihitung rekursif. `jejak` = rantai produk yang sedang dihitung,
    dipakai mendeteksi resep melingkar.
    """
    pilihan_harga = _harga_jual(session, product, konteks)
    harga_jual = pilihan_harga.harga if pilihan_harga is not None else None
    # Sengaja query, BUKAN `product.recipe`: relasi itu bisa sudah ter-cache
    # sebagai None dari perhitungan sebelumnya di sesi yang sama, sehingga resep
    # yang baru dibuat tidak terlihat. Itu persis alur `atur_resep` → tanya HPP.
    recipe: Recipe | None = session.scalars(
        select(Recipe).where(Recipe.product_id == product.id)
    ).first()
    if recipe is None:
        return HasilHpp(
            product_id=product.id,
            nama=product.nama,
            jenis=product.jenis.value,
            status=StatusHpp.belum_ada_resep,
            hpp_per_unit=None,
            harga_jual=harga_jual,
            laba_kotor_per_unit=None,
            catatan=["Produk belum punya resep — HPP belum diketahui."],
        )

    komponen: list[KomponenHpp] = []
    bahan_kurang_harga: list[str] = []
    komponen_non_material: list[str] = []
    subproduk_bermasalah: list[str] = []
    satuan_bertabrakan: list[str] = []
    melingkar = False
    total = Decimal("0")
    lengkap = True

    for item in recipe.items:
        # ── Sub-produk: barang setengah jadi dengan resepnya sendiri ──
        if item.product_id is not None:
            sub = item.sub_product
            if sub is None or sub.business_id != product.business_id:
                # Isolasi tenant (prinsip #6): resep tidak boleh menyeberang usaha.
                subproduk_bermasalah.append(f"sub-produk #{item.product_id}")
                lengkap = False
                continue

            if sub.id in jejak:
                melingkar = True
                lengkap = False
                komponen.append(
                    KomponenHpp(
                        nama=sub.nama, tipe="sub_produk", qty=_dec(item.qty),
                        satuan=item.satuan, harga_satuan=None, tanggal_harga=None,
                        subtotal=None, product_id=sub.id,
                    )
                )
                continue

            # konteks sengaja tidak diwariskan: yang dipakai induk hanya HPP sub-produk,
            # bukan harga jualnya.
            hasil_sub = _hpp_produk(session, sub, jejak + (product.id,), memo)
            if hasil_sub.status is not StatusHpp.lengkap:
                subproduk_bermasalah.append(sub.nama)
                lengkap = False
                if hasil_sub.status is StatusHpp.resep_melingkar:
                    melingkar = True
                bahan_kurang_harga.extend(hasil_sub.bahan_kurang_harga)
                satuan_bertabrakan.extend(hasil_sub.satuan_bertabrakan)
                komponen.append(
                    KomponenHpp(
                        nama=sub.nama, tipe="sub_produk", qty=_dec(item.qty),
                        satuan=item.satuan, harga_satuan=None, tanggal_harga=None,
                        subtotal=None, product_id=sub.id,
                    )
                )
                continue

            # Satuan pemakaian di resep induk harus sama dengan satuan HPP
            # sub-produk (yield-nya), kalau tidak angkanya meleset diam-diam.
            if _satuan_bentrok(item.satuan, hasil_sub.satuan_hpp):
                satuan_bertabrakan.append(
                    f"{sub.nama} (resep pakai '{item.satuan}', "
                    f"tapi HPP-nya per '{hasil_sub.satuan_hpp}')"
                )
                lengkap = False
                komponen.append(
                    KomponenHpp(
                        nama=sub.nama, tipe="sub_produk", qty=_dec(item.qty),
                        satuan=item.satuan, harga_satuan=hasil_sub.hpp_per_unit,
                        tanggal_harga=None, subtotal=None, product_id=sub.id,
                    )
                )
                continue

            subtotal = _dec(item.qty) * hasil_sub.hpp_per_unit  # type: ignore[operator]
            total += subtotal
            tanggal_sub = min(
                (k.tanggal_harga for k in hasil_sub.komponen if k.tanggal_harga), default=None
            )
            komponen.append(
                KomponenHpp(
                    nama=sub.nama, tipe="sub_produk", qty=_dec(item.qty),
                    satuan=item.satuan, harga_satuan=hasil_sub.hpp_per_unit,
                    tanggal_harga=tanggal_sub, subtotal=_uang(subtotal), product_id=sub.id,
                )
            )
            continue

        ci = item.cost_item
        if ci is None:
            bahan_kurang_harga.append("(baris resep tanpa bahan)")
            lengkap = False
            continue
        if ci.tipe != TipeKomponen.material:
            # ⛔ labor_time / overhead = slot; kalkulasinya belum diimplementasi.
            komponen_non_material.append(ci.nama)
            lengkap = False
            komponen.append(
                KomponenHpp(
                    cost_item_id=ci.id, nama=ci.nama, tipe=ci.tipe.value,
                    qty=_dec(item.qty), satuan=item.satuan,
                    harga_satuan=None, tanggal_harga=None, subtotal=None,
                )
            )
            continue

        harga = _harga_terakhir(session, ci.id)
        if harga is None:
            bahan_kurang_harga.append(ci.nama)
            lengkap = False
            komponen.append(
                KomponenHpp(
                    cost_item_id=ci.id, nama=ci.nama, tipe=ci.tipe.value,
                    qty=_dec(item.qty), satuan=item.satuan,
                    harga_satuan=None, tanggal_harga=None, subtotal=None,
                )
            )
            continue

        # ⚠️ Titik paling rawan mengarang angka: harga tersimpan per "kg" tapi
        # resep menakar "gram" akan meleset 1000× sambil berstatus `lengkap`.
        # Bandingkan, jangan konversi (lihat `_samakan_satuan`).
        if _satuan_bentrok(item.satuan, harga.satuan):
            satuan_bertabrakan.append(
                f"{ci.nama} (resep pakai '{item.satuan}', tapi harga per '{harga.satuan}')"
            )
            lengkap = False
            komponen.append(
                KomponenHpp(
                    cost_item_id=ci.id, nama=ci.nama, tipe=ci.tipe.value,
                    qty=_dec(item.qty), satuan=item.satuan,
                    harga_satuan=_uang(_dec(harga.harga_satuan)),
                    tanggal_harga=harga.tanggal, subtotal=None,
                )
            )
            continue

        subtotal = _dec(item.qty) * _dec(harga.harga_satuan)
        total += subtotal
        komponen.append(
            KomponenHpp(
                cost_item_id=ci.id, nama=ci.nama, tipe=ci.tipe.value,
                qty=_dec(item.qty), satuan=item.satuan,
                harga_satuan=_uang(_dec(harga.harga_satuan)),
                tanggal_harga=harga.tanggal,
                subtotal=_uang(subtotal),
            )
        )

    if not lengkap:
        # Urutan sengaja: siklus paling mendesak (resepnya salah, bukan datanya
        # kurang), lalu tipe belum didukung, lalu sub-produk, lalu harga bahan.
        if melingkar:
            status = StatusHpp.resep_melingkar
        elif satuan_bertabrakan:
            # Didahulukan: ini konflik data yang bisa langsung dibetulkan
            # pengguna, dan dampaknya paling besar kalau dibiarkan.
            status = StatusHpp.satuan_tidak_cocok
        elif komponen_non_material:
            status = StatusHpp.tipe_belum_didukung
        elif subproduk_bermasalah:
            status = StatusHpp.subproduk_tidak_lengkap
        else:
            status = StatusHpp.harga_tidak_lengkap
        catatan = []
        if satuan_bertabrakan:
            catatan.append(
                "Satuan takaran resep berbeda dengan satuan harganya: "
                + "; ".join(satuan_bertabrakan)
                + ". Samakan dulu satuannya — kalau dipaksa hitung, angkanya bisa "
                "meleset jauh."
            )
        if melingkar:
            catatan.append(
                f"Resep '{product.nama}' melingkar — produk ini memakai dirinya sendiri "
                "lewat rantai sub-produk. HPP tidak bisa dihitung sampai resepnya dibetulkan."
            )
        if bahan_kurang_harga:
            catatan.append("Bahan belum ada harganya: " + ", ".join(bahan_kurang_harga) + ".")
        if subproduk_bermasalah and not melingkar:
            catatan.append(
                "Sub-produk yang HPP-nya belum lengkap: "
                + ", ".join(subproduk_bermasalah)
                + "."
            )
        if komponen_non_material:
            catatan.append(
                "Komponen non-material belum didukung: " + ", ".join(komponen_non_material) + "."
            )
        return HasilHpp(
            product_id=product.id, nama=product.nama, jenis=product.jenis.value,
            status=status, hpp_per_unit=None, harga_jual=harga_jual,
            laba_kotor_per_unit=None, yield_qty=_dec(recipe.yield_qty),
            faktor_kehilangan=(
                _dec(recipe.faktor_kehilangan)
                if recipe.faktor_kehilangan is not None
                else None
            ),
            satuan_hpp=recipe.yield_satuan, komponen=komponen,
            bahan_kurang_harga=bahan_kurang_harga,
            satuan_bertabrakan=satuan_bertabrakan, catatan=catatan,
        )

    yield_qty = _dec(recipe.yield_qty)
    faktor = _dec(recipe.faktor_kehilangan) if recipe.faktor_kehilangan is not None else None
    # Biaya dibagi ke unit yang BENAR-BENAR laku, bukan ke hasil kotor. Ini yang
    # membuat susut/reject/gagal panen terlihat di HPP alih-alih menguap.
    yield_efektif = yield_qty * (Decimal("1") - faktor) if faktor is not None else yield_qty

    if yield_qty <= 0 or (faktor is not None and not (0 <= faktor < 1)) or yield_efektif <= 0:
        return HasilHpp(
            product_id=product.id, nama=product.nama, jenis=product.jenis.value,
            status=StatusHpp.belum_ada_resep, hpp_per_unit=None, harga_jual=harga_jual,
            laba_kotor_per_unit=None, yield_qty=yield_qty, faktor_kehilangan=faktor,
            satuan_hpp=recipe.yield_satuan, komponen=komponen,
            catatan=["Hasil resep tidak valid (≤ 0) — HPP belum bisa dihitung."],
        )

    hpp = _uang(total / yield_efektif)
    laba = _uang(harga_jual - hpp) if harga_jual is not None else None
    tanggal_termuda = min((k.tanggal_harga for k in komponen if k.tanggal_harga), default=None)
    catatan = []
    if tanggal_termuda:
        catatan.append(f"Harga bahan terlama yang dipakai per {tanggal_termuda.isoformat()}.")
    if faktor is not None and faktor > 0:
        persen = (faktor * Decimal("100")).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
        satuan_teks = f" {recipe.yield_satuan}" if recipe.yield_satuan else ""
        catatan.append(
            f"Sudah memperhitungkan kehilangan {_rapikan(persen)}%: dari "
            f"{_rapikan(yield_qty)}{satuan_teks} yang jadi, terhitung "
            f"{_rapikan(yield_efektif)}{satuan_teks} yang bisa dijual."
        )
    return HasilHpp(
        product_id=product.id, nama=product.nama, jenis=product.jenis.value,
        status=StatusHpp.lengkap, hpp_per_unit=hpp, harga_jual=harga_jual,
        laba_kotor_per_unit=laba,
        harga_jual_konteks=pilihan_harga.sebagai_teks() if pilihan_harga else None,
        yield_qty=yield_qty, faktor_kehilangan=faktor,
        yield_efektif=yield_efektif,
        satuan_hpp=recipe.yield_satuan, komponen=komponen, catatan=catatan,
    )


def _hpp_produk(
    session: Session,
    product: Product,
    jejak: tuple[int, ...] = (),
    memo: dict[tuple, HasilHpp] | None = None,
    konteks: KonteksHarga | None = None,
) -> HasilHpp:
    """Dispatcher internal — dipakai juga oleh rekursi sub-produk.

    Sub-produk boleh bertipe `reseller` (mis. pentol dibeli jadi dari pemasok):
    HPP-nya = harga beli terakhir, dan itu tetap sah sebagai komponen resep.

    `memo` mencegah sub-produk yang dipakai berkali-kali dihitung ulang (pola
    diamond: `jadi` → `isi1` → `adonan` dan `jadi` → `isi2` → `adonan`).
    """
    # Memo dikunci (product_id, konteks): harga jual — dan karenanya laba —
    # bergantung konteks, jadi hasil untuk kanal berbeda tidak boleh saling pakai.
    kunci = (product.id, konteks)
    if memo is not None and kunci in memo:
        return memo[kunci]

    if product.jenis == JenisProduk.reseller:
        hasil = _hpp_reseller(session, product, konteks)
    else:
        hasil = _hpp_produksi(session, product, jejak, memo, konteks)

    # ⚠️ Hasil `resep_melingkar` TIDAK di-memo: statusnya bergantung pada jalur
    # rekursi yang sedang ditempuh (`jejak`), bukan pada produknya semata.
    # Menyimpannya berisiko menular ke perhitungan lain yang sebenarnya sehat.
    if memo is not None and hasil.status is not StatusHpp.resep_melingkar:
        memo[kunci] = hasil
    return hasil


def hitung_hpp_produk(
    session: Session,
    product_id: int,
    business_id: int,
    konteks: KonteksHarga | None = None,
) -> HasilHpp:
    """Hitung HPP satu produk. `business_id` wajib (isolasi tenant, prinsip #6).

    `konteks` memilih harga jual mana yang dipakai untuk laba kotor (kanal/grade/
    tier kuantitas). HPP sendiri tidak terpengaruh konteks.
    """
    product = session.scalars(
        select(Product).where(Product.id == product_id, Product.business_id == business_id)
    ).first()
    if product is None:
        raise ValueError(f"Produk {product_id} tidak ditemukan untuk usaha {business_id}.")

    return _hpp_produk(session, product, memo={}, konteks=konteks)


def hitung_hpp_semua(
    session: Session, business_id: int, konteks: KonteksHarga | None = None
) -> list[HasilHpp]:
    """Satu memo dipakai bersama seluruh produk — sub-produk yang dipakai banyak
    produk induk hanya dihitung sekali."""
    products = session.scalars(
        select(Product).where(Product.business_id == business_id).order_by(Product.id)
    ).all()
    memo: dict[tuple, HasilHpp] = {}
    return [_hpp_produk(session, p, memo=memo, konteks=konteks) for p in products]


# ── Snapshot HPP (jejak historis — bahan margin-watch) ──────────────────────


@dataclass
class HasilSimpanSnapshot:
    snapshot: HppSnapshot
    baru: bool  # False = HPP tidak berubah, snapshot lama dipakai ulang


def snapshot_terakhir(session: Session, product_id: int) -> HppSnapshot | None:
    stmt = (
        select(HppSnapshot)
        .where(HppSnapshot.product_id == product_id)
        .order_by(HppSnapshot.created_at.desc(), HppSnapshot.id.desc())
        .limit(1)
    )
    return session.scalars(stmt).first()


def _sama_dengan(snapshot: HppSnapshot, hasil: HasilHpp) -> bool:
    """Sebuah snapshot dianggap tidak berubah bila nilai DAN statusnya sama.

    Status ikut dibandingkan supaya perpindahan `lengkap` → `harga_tidak_lengkap`
    tetap tercatat, walau keduanya sama-sama berujung `hpp_per_unit = None`.
    """
    lama = snapshot.hpp_per_unit
    baru = hasil.hpp_per_unit
    if (lama is None) != (baru is None):
        return False
    if lama is not None and baru is not None and _dec(lama) != _dec(baru):
        return False
    status_lama = (snapshot.rincian or {}).get("status")
    return status_lama == hasil.status.value


def simpan_snapshot_hpp(
    session: Session,
    product_id: int,
    business_id: int,
    hasil: HasilHpp | None = None,
) -> HasilSimpanSnapshot:
    """Catat HPP produk apa adanya ke `hpp_snapshots`.

    **Snapshot ditulis juga saat HPP belum diketahui** — "belum diketahui pada
    tanggal sekian, karena X" adalah informasi historis yang sah, dan justru itu
    yang menunjukkan perbaikan saat pengguna melengkapi datanya.

    **Dedup disengaja:** kalau nilai & status tidak berubah, snapshot lama
    dipakai ulang. Margin-watch mencari *perubahan*; menulis baris identik tiap
    hari hanya mengubur sinyalnya. Karena itu fungsi ini aman dipanggil berulang.

    `hasil` = HPP yang sudah terlanjur dihitung pemanggil (mis. `atur_resep`
    baru saja menghitungnya). Dipakai ulang supaya menyimpan jejak tidak berarti
    menghitung dua kali. ⚠️ Menyodorkannya **melewati** pemeriksaan tenant di
    `hitung_hpp_produk`, jadi pemanggil wajib sudah memastikan produk ini milik
    `business_id` (aturan #6). Tanpa `hasil`, pemeriksaan itu jalan di sini.
    """
    if hasil is None:
        hasil = hitung_hpp_produk(session, product_id, business_id)
    terakhir = snapshot_terakhir(session, product_id)
    if terakhir is not None and _sama_dengan(terakhir, hasil):
        return HasilSimpanSnapshot(snapshot=terakhir, baru=False)

    snapshot = HppSnapshot(
        product_id=product_id,
        hpp_per_unit=hasil.hpp_per_unit,
        rincian=hasil.rincian_json(),
    )
    session.add(snapshot)
    session.flush()
    return HasilSimpanSnapshot(snapshot=snapshot, baru=True)


def simpan_snapshot_semua(session: Session, business_id: int) -> list[HasilSimpanSnapshot]:
    """Snapshot seluruh produk satu usaha dalam **satu kali** hitung.

    Dipakai saat yang berubah adalah *harga bahan*: bahan dipakai bersama banyak
    produk dan menjalar lewat sub-produk, jadi tak ada cara murah menebak siapa
    saja yang tergeser — hitung semua, biarkan dedup yang menyaring.

    `hitung_hpp_semua` berbagi satu memo lintas produk, jadi sub-produk yang
    dipakai berkali-kali hanya dihitung sekali.
    """
    hasil = hitung_hpp_semua(session, business_id)
    return [
        simpan_snapshot_hpp(session, h.product_id, business_id, hasil=h) for h in hasil
    ]


def riwayat_hpp(
    session: Session, product_id: int, business_id: int, batas: int = 20
) -> list[HppSnapshot]:
    """Riwayat perubahan HPP, terbaru dulu. `business_id` wajib (prinsip #6)."""
    produk = session.scalars(
        select(Product).where(Product.id == product_id, Product.business_id == business_id)
    ).first()
    if produk is None:
        raise ValueError(f"Produk {product_id} tidak ditemukan untuk usaha {business_id}.")
    stmt = (
        select(HppSnapshot)
        .where(HppSnapshot.product_id == product_id)
        .order_by(HppSnapshot.created_at.desc(), HppSnapshot.id.desc())
        .limit(batas)
    )
    return list(session.scalars(stmt))


# ── Cakupan HPP (dipakai laporan & skor) ────────────────────────────────────


@dataclass
class CakupanHpp:
    omzet_total: Decimal
    omzet_tercakup: Decimal
    persen: Decimal            # 0..100, 1 desimal
    hpp_total: Decimal
    laba_kotor: Decimal        # hanya dari penjualan tercakup
    penjualan_tanpa_produk: Decimal
    produk_tak_terhitung: list[str] = field(default_factory=list)
    catatan: list[str] = field(default_factory=list)


def cakupan_hpp(
    session: Session, business_id: int, mulai: date, selesai: date
) -> CakupanHpp:
    """Berapa persen omzet periode yang HPP-nya benar-benar bisa dihitung.

    Selalu ditampilkan di laporan & skor — pengguna tahu seberapa bisa
    dipercaya angkanya (§3a). Sebuah baris penjualan "tercakup" hanya bila:
    ada product_id, HPP produk berstatus `lengkap`, dan qty terisi > 0.
    """
    penjualan = session.scalars(
        select(Transaction).where(
            Transaction.business_id == business_id,
            Transaction.jenis == JenisTransaksi.pemasukan,
            Transaction.tanggal >= mulai,
            Transaction.tanggal <= selesai,
            Transaction.dibatalkan_pada.is_(None),  # buku append-only
        )
    ).all()

    omzet_total = Decimal("0")
    omzet_tercakup = Decimal("0")
    hpp_total = Decimal("0")
    penjualan_tanpa_produk = Decimal("0")
    tak_terhitung: set[str] = set()

    # Satu memo untuk seluruh periode: produk yang terjual berkali-kali maupun
    # sub-produk yang dipakai banyak produk hanya dihitung sekali.
    memo: dict[tuple, HasilHpp] = {}

    for t in penjualan:
        omzet_total += _dec(t.nominal)

        if t.product_id is None:
            penjualan_tanpa_produk += _dec(t.nominal)
            continue

        hasil = memo.get((t.product_id, None))
        if hasil is None:
            produk = session.scalars(
                select(Product).where(
                    Product.id == t.product_id,
                    Product.business_id == business_id,  # isolasi tenant
                )
            ).first()
            if produk is None:
                penjualan_tanpa_produk += _dec(t.nominal)
                continue
            hasil = _hpp_produk(session, produk, memo=memo)

        if hasil.status != StatusHpp.lengkap:
            tak_terhitung.add(hasil.nama)
            continue
        if t.qty is None or _dec(t.qty) <= 0:
            tak_terhitung.add(hasil.nama)
            continue

        omzet_tercakup += _dec(t.nominal)
        hpp_total += _dec(t.qty) * hasil.hpp_per_unit  # type: ignore[operator]

    persen = (
        (omzet_tercakup / omzet_total * Decimal("100")).quantize(
            Decimal("0.1"), rounding=ROUND_HALF_UP
        )
        if omzet_total > 0
        else Decimal("0.0")
    )
    catatan: list[str] = []
    if omzet_total == 0:
        catatan.append("Belum ada penjualan pada periode ini.")
    if penjualan_tanpa_produk > 0:
        catatan.append("Ada penjualan tanpa produk terkenali — tidak dipaksa masuk HPP.")

    return CakupanHpp(
        omzet_total=_uang(omzet_total),
        omzet_tercakup=_uang(omzet_tercakup),
        persen=persen,
        hpp_total=_uang(hpp_total),
        laba_kotor=_uang(omzet_tercakup - hpp_total),
        penjualan_tanpa_produk=_uang(penjualan_tanpa_produk),
        produk_tak_terhitung=sorted(tak_terhitung),
        catatan=catatan,
    )
