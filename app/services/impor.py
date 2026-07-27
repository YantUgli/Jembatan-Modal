"""Alur draft impor (Pilar 2) — pagar aturan #3 berdiri di sini.

    parse → import_rows (DRAFT) → ditinjau pengguna → konfirmasi → transactions

⛔ **Impor tidak pernah auto-commit.** Modul ini adalah tempat aturan itu
ditegakkan, jadi ada tiga hal yang sengaja tidak bisa dilakukan lewat modul ini:

1. `buat_draft` tidak pernah menulis satu pun `Transaction`. Ia hanya menyimpan
   calon.
2. `konfirmasi_impor` hanya memindahkan baris yang **statusnya `diterima`** —
   bukan yang keyakinannya tinggi, bukan yang "sepertinya benar". Status
   `diterima` hanya bisa lahir dari `putuskan_baris`/`terima_yakin`, yaitu dari
   ketukan pengguna.
3. `terima_yakin` **melewati baris ragu**. Aksi borongan yang ikut menyapu baris
   yang parser-nya sendiri tidak yakin akan mengubah peninjauan jadi formalitas —
   dan formalitas adalah auto-commit dengan satu ketukan tambahan.

## Isolasi tenant di tabel tanpa `business_id`

`import_rows` tidak punya kolom `business_id`; pemiliknya hanya diketahui lewat
`imports`. Karena itu **setiap** query baris di sini ikut men-join `Import` dan
menyaring `Import.business_id` (aturan #6) — bukan mengambil baris lalu memeriksa
pemiliknya sesudahnya. Id yang datang dari klien selalu dianggap tak tepercaya.

## Commit memakai ulang jalur chat

Baris yang disetujui masuk lewat `simpan_transaksi(..., sumber=SumberInput.impor)`,
service yang sama dengan pencatatan lewat obrolan. Jadi transaksi hasil impor
ikut tertaut ke produk & menyuapi HPP dengan cara yang persis sama — tak ada
jalur tulis kedua yang bisa menyimpang perlahan dari yang pertama. Yang berbeda
hanya `sumber_input`, supaya asalnya tetap bisa ditelusuri.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.impor.kontrak import AMBANG_YAKIN, BarisDraft
from app.llm.skema import BarisTransaksi
from app.models import (
    Import,
    ImportRow,
    JenisTransaksi,
    StatusBarisImpor,
    StatusImpor,
    SumberInput,
    Transaction,
)
from app.services.catat import simpan_transaksi

__all__ = [
    "BarisTinjau",
    "RingkasanTinjau",
    "TidakBisaDiterima",
    "buat_draft",
    "impor_terakhir",
    "konfirmasi_impor",
    "putuskan_baris",
    "terima_yakin",
    "tinjau_impor",
    "transaksi_dari_impor",
]


class TidakBisaDiterima(ValueError):
    """Baris yang tak terbaca tidak bisa disetujui — tak ada yang bisa disimpan."""


@dataclass
class BarisTinjau:
    """Satu baris draft, apa adanya dari DB. **Tanpa format tampilan.**

    Pemformatan (rupiah, label jenis, tanggal pendek) adalah urusan kanal — sama
    seperti `hitung_laba_periode` yang mengembalikan angka, bukan string.
    """

    row_id: int
    raw: str
    status: str
    keyakinan: float
    catatan: str = ""
    yang_kurang: list[str] = field(default_factory=list)
    jenis: JenisTransaksi | None = None
    nominal: Decimal | None = None
    tanggal: date | None = None
    produk: str | None = None
    qty: Decimal | None = None
    satuan: str | None = None
    transaksi_id: int | None = None

    @property
    def terbaca(self) -> bool:
        return self.nominal is not None

    @property
    def ragu(self) -> bool:
        return self.keyakinan < AMBANG_YAKIN


@dataclass
class RingkasanTinjau:
    """Keadaan satu impor + seluruh barisnya. Semua penghitungan di sini."""

    import_id: int
    sumber: str
    status: str
    baris: list[BarisTinjau] = field(default_factory=list)

    @property
    def jumlah(self) -> int:
        return len(self.baris)

    @property
    def jumlah_terbaca(self) -> int:
        return sum(1 for b in self.baris if b.terbaca)

    @property
    def jumlah_ragu(self) -> int:
        """Baris terbaca yang tetap perlu dilihat sendiri."""
        return sum(1 for b in self.baris if b.terbaca and b.ragu)

    @property
    def jumlah_gagal(self) -> int:
        return sum(1 for b in self.baris if not b.terbaca)

    @property
    def jumlah_diterima(self) -> int:
        """Sudah dicentang pengguna tapi **belum** masuk buku."""
        return sum(
            1
            for b in self.baris
            if b.status == StatusBarisImpor.diterima.value and b.transaksi_id is None
        )

    @property
    def jumlah_tersimpan(self) -> int:
        return sum(1 for b in self.baris if b.transaksi_id is not None)

    @property
    def jumlah_menunggu(self) -> int:
        """Masih draft — belum diputuskan pengguna sama sekali."""
        return sum(1 for b in self.baris if b.status == StatusBarisImpor.draft.value)

    @property
    def selesai(self) -> bool:
        return self.status in (StatusImpor.selesai.value, StatusImpor.batal.value)


# ── Serialisasi `import_rows.parsed` ────────────────────────────────────────
# JSON tak mengenal Decimal/date/Enum, jadi semuanya jadi string. `catatan` &
# `yang_kurang` ikut menumpang di sini — keduanya memang **hasil parse** (kenapa
# parser ragu), dan menumpangkannya menghindari migrasi kolom baru untuk data
# yang bentuknya masih akan berubah saat adaptor lain menyusul.


def _ke_json(d: BarisDraft) -> dict:
    baris = None
    if d.baris is not None:
        baris = {
            "jenis": d.baris.jenis.value,
            "nominal": str(d.baris.nominal),
            "tanggal": d.baris.tanggal.isoformat(),
            "produk": d.baris.produk,
            "qty": str(d.baris.qty) if d.baris.qty is not None else None,
            "satuan": d.baris.satuan,
        }
    return {"baris": baris, "catatan": d.catatan, "yang_kurang": list(d.yang_kurang)}


def _dari_json(parsed: dict | None) -> BarisTransaksi | None:
    """Bangun ulang baris terstruktur. Data rusak → `None`, bukan tebakan.

    Baris yang gagal dibangun ulang jatuh ke perlakuan "tak terbaca": ia tak bisa
    disetujui, jadi tak bisa masuk buku. Lebih baik satu baris hilang dari
    peninjauan daripada satu baris masuk dengan angka yang tak jelas asalnya.
    """
    if not parsed or not parsed.get("baris"):
        return None
    b = parsed["baris"]
    try:
        return BarisTransaksi(
            jenis=JenisTransaksi(b["jenis"]),
            nominal=Decimal(b["nominal"]),
            tanggal=date.fromisoformat(b["tanggal"]),
            produk=b.get("produk"),
            qty=Decimal(b["qty"]) if b.get("qty") is not None else None,
            satuan=b.get("satuan"),
        )
    except (KeyError, ValueError, TypeError, ArithmeticError):
        return None


# ── Query ber-tenant ────────────────────────────────────────────────────────


def _ambil_impor(session: Session, business_id: int, import_id: int) -> Import | None:
    """Aturan #6: `business_id` di dalam query, bukan diperiksa setelahnya."""
    return session.scalars(
        select(Import).where(Import.id == import_id, Import.business_id == business_id)
    ).first()


def _baris_impor(session: Session, business_id: int, import_id: int) -> list[ImportRow]:
    """Baris satu impor, disaring lewat join ke `imports` (aturan #6).

    `import_rows` tak punya `business_id` sendiri — tanpa join ini, `import_id`
    dari klien cukup untuk membaca draft usaha lain.
    """
    return list(
        session.scalars(
            select(ImportRow)
            .join(Import, ImportRow.import_id == Import.id)
            .where(Import.id == import_id, Import.business_id == business_id)
            .order_by(ImportRow.id)
        ).all()
    )


def _satu_baris(
    session: Session, business_id: int, import_id: int, row_id: int
) -> ImportRow | None:
    return session.scalars(
        select(ImportRow)
        .join(Import, ImportRow.import_id == Import.id)
        .where(
            ImportRow.id == row_id,
            Import.id == import_id,
            Import.business_id == business_id,
        )
    ).first()


def impor_terakhir(session: Session, business_id: int) -> Import | None:
    """Impor terakhir usaha ini yang masih perlu ditinjau.

    Dipakai agar pengguna yang mengirim pesan lain lalu kembali tetap menemukan
    draft-nya, tanpa klien harus menyimpan `import_id`.
    """
    return session.scalars(
        select(Import)
        .where(
            Import.business_id == business_id,
            Import.status.in_((StatusImpor.draft, StatusImpor.sebagian)),
        )
        .order_by(Import.id.desc())
        .limit(1)
    ).first()


# ── Alur ────────────────────────────────────────────────────────────────────


def buat_draft(
    session: Session, business_id: int, sumber: str, draft: list[BarisDraft]
) -> Import:
    """Simpan hasil parse sebagai draft. ⛔ Nol `Transaction` ditulis di sini."""
    impor = Import(business_id=business_id, sumber=sumber, status=StatusImpor.draft)
    session.add(impor)
    session.flush()

    for d in draft:
        session.add(
            ImportRow(
                import_id=impor.id,
                raw=d.raw,
                parsed=_ke_json(d),
                keyakinan=d.keyakinan,
                status=StatusBarisImpor.draft,
            )
        )
    session.flush()
    impor.ringkasan = {"jumlah_baris": len(draft)}
    return impor


def _tinjau(impor: Import, rows: list[ImportRow]) -> RingkasanTinjau:
    baris = []
    for r in rows:
        parsed = r.parsed or {}
        b = _dari_json(parsed)
        baris.append(
            BarisTinjau(
                row_id=r.id,
                raw=r.raw or "",
                status=r.status.value,
                keyakinan=r.keyakinan if r.keyakinan is not None else 0.0,
                catatan=parsed.get("catatan", "") or "",
                yang_kurang=list(parsed.get("yang_kurang") or []),
                jenis=b.jenis if b else None,
                nominal=b.nominal if b else None,
                tanggal=b.tanggal if b else None,
                produk=b.produk if b else None,
                qty=b.qty if b else None,
                satuan=b.satuan if b else None,
                transaksi_id=r.transaction_id,
            )
        )
    return RingkasanTinjau(
        import_id=impor.id, sumber=impor.sumber, status=impor.status.value, baris=baris
    )


def tinjau_impor(session: Session, business_id: int, import_id: int) -> RingkasanTinjau | None:
    """Baca keadaan satu impor. Bukan milik usaha ini → `None` (bukan error)."""
    impor = _ambil_impor(session, business_id, import_id)
    if impor is None:
        return None
    return _tinjau(impor, _baris_impor(session, business_id, import_id))


def putuskan_baris(
    session: Session, business_id: int, import_id: int, row_id: int, terima: bool
) -> RingkasanTinjau | None:
    """Centang/hapus centang satu baris. ⛔ Tidak menyentuh `transactions`.

    Baris yang sudah tersimpan tidak bisa dicabut dari sini: begitu ia masuk buku,
    yang berlaku adalah jalur koreksi transaksi yang append-only
    (keputusan.md 2026-07-20), bukan status draft-nya.
    """
    row = _satu_baris(session, business_id, import_id, row_id)
    if row is None:
        return None

    if row.transaction_id is None:
        if terima and _dari_json(row.parsed) is None:
            raise TidakBisaDiterima(
                "Baris ini tidak terbaca sebagai catatan uang, jadi belum ada yang bisa disimpan."
            )
        row.status = StatusBarisImpor.diterima if terima else StatusBarisImpor.ditolak
        session.flush()

    return tinjau_impor(session, business_id, import_id)


def terima_yakin(
    session: Session, business_id: int, import_id: int
) -> RingkasanTinjau | None:
    """Centang borongan — **hanya baris yang tidak ragu**. Nol commit.

    ⛔ Baris ragu sengaja dilewati (lihat docstring modul): baris yang parser-nya
    sendiri tidak yakin harus melewati mata pengguna satu per satu, kalau tidak
    peninjauan berubah jadi formalitas.
    """
    rows = _baris_impor(session, business_id, import_id)
    if not rows:
        return tinjau_impor(session, business_id, import_id)

    for r in rows:
        if r.transaction_id is not None or r.status is not StatusBarisImpor.draft:
            continue
        keyakinan = r.keyakinan if r.keyakinan is not None else 0.0
        if keyakinan >= AMBANG_YAKIN and _dari_json(r.parsed) is not None:
            r.status = StatusBarisImpor.diterima
    session.flush()
    return tinjau_impor(session, business_id, import_id)


def konfirmasi_impor(
    session: Session, business_id: int, import_id: int
) -> RingkasanTinjau | None:
    """Pindahkan baris **yang dicentang pengguna** ke buku transaksi.

    Idempoten: baris yang sudah punya `transaction_id` dilewati, jadi menekan
    tombol dua kali tidak menggandakan catatan. Sisa baris yang belum diputuskan
    tetap draft dan impornya berstatus `sebagian` — pengguna bisa kembali,
    dan tak ada yang tersapu masuk hanya karena ia berhenti di tengah.
    """
    impor = _ambil_impor(session, business_id, import_id)
    if impor is None:
        return None

    rows = _baris_impor(session, business_id, import_id)
    for r in rows:
        if r.status is not StatusBarisImpor.diterima or r.transaction_id is not None:
            continue
        baris = _dari_json(r.parsed)
        if baris is None:  # sabuk pengaman: tak terbaca → tak pernah masuk
            r.status = StatusBarisImpor.draft
            continue
        hasil = simpan_transaksi(
            session,
            business_id,
            [baris],
            raw_text=r.raw or "",
            sumber=SumberInput.impor,
        )
        r.transaction_id = hasil.tersimpan[0].id

    masih_draft = any(r.status is StatusBarisImpor.draft for r in rows)
    impor.status = StatusImpor.sebagian if masih_draft else StatusImpor.selesai
    session.flush()

    ringkas = _tinjau(impor, rows)
    impor.ringkasan = {
        "jumlah_baris": ringkas.jumlah,
        "tersimpan": ringkas.jumlah_tersimpan,
        "ditolak": sum(
            1 for b in ringkas.baris if b.status == StatusBarisImpor.ditolak.value
        ),
        "menunggu": ringkas.jumlah_menunggu,
    }
    session.flush()
    return ringkas


def transaksi_dari_impor(session: Session, business_id: int, import_id: int) -> list[Transaction]:
    """Transaksi yang benar-benar lahir dari impor ini — untuk test & audit."""
    return list(
        session.scalars(
            select(Transaction)
            .join(ImportRow, ImportRow.transaction_id == Transaction.id)
            .join(Import, ImportRow.import_id == Import.id)
            .where(
                Import.id == import_id,
                Import.business_id == business_id,
                Transaction.business_id == business_id,
            )
            .order_by(Transaction.id)
        ).all()
    )
