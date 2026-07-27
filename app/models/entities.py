"""Skema data inti JembatanModal — mengikuti 02-arsitektur.md §5.

Catatan penting yang tidak boleh hilang saat refactor:
- `cost_items.tipe` enum {material|labor_time|overhead} SEJAK migrasi pertama,
  walau hanya `material` diimplementasi. Ini titik di mana skema menolak
  menyandera dirinya sendiri (§3a).
- `recipe_items` & `transactions` menunjuk `cost_item_id`, BUKAN `ingredient_id`.
- `cost_item_prices` append-only, bertanggal.
- tautan HPP di `transactions` (`product_id`, `cost_item_id`, `qty`, `satuan`)
  ada sejak awal — menambahkannya belakangan = migrasi menyakitkan.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import (
    Base,
    HasilKur,
    JenisDokumen,
    JenisProduk,
    JenisTransaksi,
    StatusBarisImpor,
    StatusImpor,
    SumberHarga,
    SumberInput,
    TimestampMixin,
    TipeKomponen,
    now_utc,
)

# Presisi: uang 2 desimal, kuantitas 3 desimal (mis. 0,5 liter / 0,25 kg).
Uang = Numeric(14, 2)
Qty = Numeric(14, 3)


# ── Inti ────────────────────────────────────────────────────────────────────


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    nama: Mapped[str] = mapped_column(String(120), nullable=False)
    no_hp: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)

    # Auth no.HP + PIN. `pin_hash` = `scrypt$<salt_hex>$<hash_hex>` (stdlib, tanpa
    # dependensi). Nullable: user lama/seed tanpa PIN belum bisa login sampai
    # di-set. Lockout brute-force: PIN 6 digit lemah, jadi hitung kegagalan.
    pin_hash: Mapped[str | None] = mapped_column(String(255))
    percobaan_gagal: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    terkunci_sampai: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    businesses: Mapped[list[Business]] = relationship(back_populates="user")
    sesi: Mapped[list[Sesi]] = relationship(back_populates="user")


class Business(Base):
    __tablename__ = "businesses"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    nama_usaha: Mapped[str] = mapped_column(String(160), nullable=False)
    jenis_usaha: Mapped[str | None] = mapped_column(String(120))  # deskripsi bebas
    lokasi: Mapped[str | None] = mapped_column(String(160))
    mulai_usaha: Mapped[date | None] = mapped_column(Date)

    user: Mapped[User] = relationship(back_populates="businesses")


class Sesi(Base):
    """Sesi login server-side (token opaque, revocable).

    ⛔ Yang disimpan adalah **hash** token (SHA-256 hex), bukan token mentah:
    kalau DB bocor, tak ada sesi yang bisa dipakai ulang. Lookup selalu by hash.
    Kedaluwarsa & logout cukup lewati/hapus baris — tak ada JWT stateless yang
    tak bisa dicabut.
    """

    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    dibuat_pada: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, nullable=False
    )
    kedaluwarsa_pada: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    user: Mapped[User] = relationship(back_populates="sesi")


class Transaction(Base):
    """**Buku ini append-only.** Koreksi tidak pernah menimpa baris lama:
    yang lama ditandai `dibatalkan_pada`, yang benar masuk sebagai baris baru
    (keputusan.md 2026-07-20).

    ⛔ Konsekuensinya mengikat SEMUA pembaca: setiap query yang menjumlah uang
    wajib menyaring `dibatalkan_pada IS NULL`. Lupa satu tempat = angka yang
    sudah dikoreksi pengguna diam-diam ikut terhitung lagi.
    """

    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    business_id: Mapped[int] = mapped_column(
        ForeignKey("businesses.id"), nullable=False, index=True
    )
    jenis: Mapped[JenisTransaksi] = mapped_column(
        Enum(JenisTransaksi, name="jenis_transaksi"), nullable=False
    )
    nominal: Mapped[float] = mapped_column(Uang, nullable=False)
    deskripsi: Mapped[str | None] = mapped_column(String(255))
    kategori_detail: Mapped[str | None] = mapped_column(String(80))
    tanggal: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    sumber_input: Mapped[SumberInput] = mapped_column(
        Enum(SumberInput, name="sumber_input"), default=SumberInput.chat, nullable=False
    )
    raw_text: Mapped[str | None] = mapped_column(Text)

    # Terisi = baris ini sudah dikoreksi/dibatalkan pengguna dan TIDAK BOLEH
    # ikut dihitung. Baris penggantinya (kalau ada) menunjuk balik lewat
    # `koreksi_dari_id`, sehingga riwayat "dulu salah tulis, lalu dibetulkan"
    # tetap bisa ditelusuri.
    dibatalkan_pada: Mapped[datetime | None] = mapped_column(DateTime, index=True)
    koreksi_dari_id: Mapped[int | None] = mapped_column(
        ForeignKey("transactions.id"), index=True
    )

    # ── tautan HPP (P4), semuanya nullable ──
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id"), index=True)
    cost_item_id: Mapped[int | None] = mapped_column(ForeignKey("cost_items.id"), index=True)
    qty: Mapped[float | None] = mapped_column(Qty)
    satuan: Mapped[str | None] = mapped_column(String(32))

    product: Mapped[Product | None] = relationship()
    cost_item: Mapped[CostItem | None] = relationship()


class Message(TimestampMixin, Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    business_id: Mapped[int] = mapped_column(
        ForeignKey("businesses.id"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)  # user | assistant
    content: Mapped[str] = mapped_column(Text, nullable=False)


# ── Pilar 4: HPP (model komponen biaya) ─────────────────────────────────────


class Product(TimestampMixin, Base):
    """Kolom `satuan_beli`/`satuan_jual`/`isi_per_satuan_beli`/`faktor_kehilangan`
    adalah **jalur reseller** (keputusan.md 2026-07-19).

    Repacking bukan transformasi: beras 1 sak dijual literan tetap `reseller`,
    tidak pernah ditawari wawancara resep (aturan #8). Yang ditanyakan ke mereka
    adalah *isi per kemasan* dan *susut*, bukan resep.

    `faktor_kehilangan` di sini ≠ `recipes.faktor_kehilangan`: yang ini susut saat
    mengecer, yang itu kehilangan saat produksi. Dua peristiwa berbeda.

    **Invariant sadar: produk `produksi` dan `reseller` selalu baris berbeda.**
    Tidak perlu constraint — `jenis` satu kolom sudah menjaminnya. Satu baris
    tidak pernah mencoba jadi dua jenis sekaligus.

    Edge case penggilingan-yang-juga-mengecer bukan pengecualian atas invariant
    itu, melainkan **dua baris `products` yang terhubung lewat sub-produk**
    (`recipe_items.product_id`): baris pertama gabah → beras (`produksi`, resep),
    baris kedua produk ecerannya yang mengambil baris pertama sebagai sub-produk.
    """

    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint(
            "faktor_kehilangan IS NULL OR (faktor_kehilangan >= 0 AND faktor_kehilangan < 1)",
            name="ck_products_faktor_kehilangan_wajar",
        ),
        CheckConstraint(
            "isi_per_satuan_beli IS NULL OR isi_per_satuan_beli > 0",
            name="ck_products_isi_positif",
        ),
        CheckConstraint(
            "isi_per_satuan_beli IS NULL "
            "OR (satuan_beli IS NOT NULL AND satuan_jual IS NOT NULL)",
            name="ck_products_konversi_butuh_satuan",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    business_id: Mapped[int] = mapped_column(
        ForeignKey("businesses.id"), nullable=False, index=True
    )
    nama: Mapped[str] = mapped_column(String(120), nullable=False)
    jenis: Mapped[JenisProduk] = mapped_column(Enum(JenisProduk, name="jenis_produk"), nullable=False)
    # ⛔ `harga_jual` skalar sudah dipindah ke `product_prices` (bertanggal &
    # berkanal). Jangan dihidupkan lagi di sini — dua sumber kebenaran harga
    # adalah cara paling cepat membuat laporan bertengkar dengan dirinya sendiri.

    # ── jalur reseller (semua nullable; NULL = belum diketahui, bukan nol) ──
    satuan_beli: Mapped[str | None] = mapped_column(String(32))
    satuan_jual: Mapped[str | None] = mapped_column(String(32))
    # berapa `satuan_jual` didapat dari 1 `satuan_beli` (1 sak = 31,25 liter)
    isi_per_satuan_beli: Mapped[float | None] = mapped_column(Qty)
    faktor_kehilangan: Mapped[float | None] = mapped_column(Numeric(6, 4))

    recipe: Mapped[Recipe | None] = relationship(back_populates="product", uselist=False)


class ProductPrice(Base):
    """Harga jual bisa lebih dari satu untuk produk yang sama.

    Dari 9 kasus lapangan: frozen food (eceran Rp 30.000 vs tebus reseller
    Rp 23.000), hidroponik (resto Grade A vs ecer Grade B), konveksi (tier
    kuantitas 50/100/300/500 pcs), kelontong (utuh vs eceran).

    Append-only & bertanggal — bentuk yang sama dengan `cost_item_prices`, supaya
    "harga jual berlaku pada tanggal X" bisa ditelusuri, bukan ditimpa.

    Kolom penyaring semuanya nullable; NULL = **berlaku umum**, bukan "kosong".
    Pemilihannya: yang paling spesifik menang, seri diputus oleh tanggal terbaru
    (lihat `app/services/harga.py`).
    """

    __tablename__ = "product_prices"
    __table_args__ = (
        CheckConstraint("min_qty IS NULL OR min_qty > 0", name="ck_product_prices_min_qty"),
        CheckConstraint("harga >= 0", name="ck_product_prices_harga"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False, index=True)
    kanal: Mapped[str | None] = mapped_column(String(40))  # eceran|reseller|resto|…
    grade: Mapped[str | None] = mapped_column(String(20))  # A|B|…
    min_qty: Mapped[float | None] = mapped_column(Qty)     # tier: berlaku mulai qty ini
    harga: Mapped[float] = mapped_column(Uang, nullable=False)
    berlaku_dari: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    catatan: Mapped[str | None] = mapped_column(String(160))

    product: Mapped[Product] = relationship()


class CostItem(Base):
    """Generalisasi `ingredients`. SEKARANG hanya baris tipe='material' yang
    dibuat & dipakai; `labor_time`/`overhead` adalah SLOT.
    """

    __tablename__ = "cost_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    business_id: Mapped[int] = mapped_column(
        ForeignKey("businesses.id"), nullable=False, index=True
    )
    tipe: Mapped[TipeKomponen] = mapped_column(
        Enum(TipeKomponen, name="tipe_komponen"), default=TipeKomponen.material, nullable=False
    )
    nama: Mapped[str] = mapped_column(String(120), nullable=False)
    satuan_baku: Mapped[str | None] = mapped_column(String(32))

    prices: Mapped[list[CostItemPrice]] = relationship(back_populates="cost_item")


class CostItemPrice(Base):
    """Append-only, bertanggal. Untuk labor_time nanti, `harga_satuan` = tarif
    per jam — bentuknya sudah muat.
    """

    __tablename__ = "cost_item_prices"

    id: Mapped[int] = mapped_column(primary_key=True)
    cost_item_id: Mapped[int] = mapped_column(
        ForeignKey("cost_items.id"), nullable=False, index=True
    )
    harga_satuan: Mapped[float] = mapped_column(Uang, nullable=False)
    satuan: Mapped[str | None] = mapped_column(String(32))
    tanggal: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    sumber: Mapped[SumberHarga] = mapped_column(
        Enum(SumberHarga, name="sumber_harga"), nullable=False
    )
    transaction_id: Mapped[int | None] = mapped_column(ForeignKey("transactions.id"))

    cost_item: Mapped[CostItem] = relationship(back_populates="prices")


class Recipe(TimestampMixin, Base):
    """`yield_qty` = hasil **kotor**; `faktor_kehilangan` menguranginya jadi
    hasil yang benar-benar bisa dijual.

    Satu kolom, empat nama di lapangan: susut beras saat dieceran (2,5%), waste
    kain di konveksi (12–18%), reject jahitan (4%), gagal panen hidroponik (10%),
    pentol jatuh di gerobak. Matematikanya identik —
    `hasil_efektif = yield_qty × (1 − faktor_kehilangan)` — jadi jangan dipecah
    jadi empat fitur.

    Susut **pengeceran** bukan di sini: itu `products.faktor_kehilangan`, jalur
    reseller. Repacking bukan transformasi (keputusan.md 2026-07-19), dan
    **produk `produksi` & `reseller` selalu baris berbeda** — invariant sadar,
    dijamin oleh kolom `products.jenis`, tidak butuh construction tambahan.
    Penggilingan yang juga mengecer = dua baris `products` terhubung sub-produk,
    bukan satu baris dua jenis.
    """

    __tablename__ = "recipes"
    __table_args__ = (
        CheckConstraint(
            "faktor_kehilangan IS NULL OR (faktor_kehilangan >= 0 AND faktor_kehilangan < 1)",
            name="ck_recipes_faktor_kehilangan_wajar",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id"), nullable=False, unique=True, index=True
    )
    yield_qty: Mapped[float] = mapped_column(Qty, nullable=False)
    yield_satuan: Mapped[str | None] = mapped_column(String(32))
    # pecahan 0..<1 (0,025 = susut 2,5%). NULL = belum diukur, bukan "nol".
    faktor_kehilangan: Mapped[float | None] = mapped_column(Numeric(6, 4))
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    product: Mapped[Product] = relationship(back_populates="recipe")
    items: Mapped[list[RecipeItem]] = relationship(back_populates="recipe")


class RecipeItem(Base):
    """Satu baris resep. Menunjuk **salah satu** dari dua hal:

    - `cost_item_id` → bahan yang dibeli (harga dari `cost_item_prices`)
    - `product_id`   → **sub-produk**: barang setengah jadi yang punya resep
      sendiri (pentol di bakso, lauk batch di warteg, usus ungkep di
      angkringan). HPP-nya dihitung rekursif, bukan diketik pengguna.

    Tanpa sub-produk, pengguna harus menghitung sendiri "Rp 1.150/butir" lalu
    memasukkannya sebagai harga bahan — aritmatika berpindah ke kepala pengguna,
    yang semangatnya sama buruknya dengan menaruhnya di prompt LLM (aturan #1).
    """

    __tablename__ = "recipe_items"
    __table_args__ = (
        CheckConstraint(
            "(cost_item_id IS NOT NULL) <> (product_id IS NOT NULL)",
            name="ck_recipe_items_bahan_atau_subproduk",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    recipe_id: Mapped[int] = mapped_column(ForeignKey("recipes.id"), nullable=False, index=True)
    cost_item_id: Mapped[int | None] = mapped_column(ForeignKey("cost_items.id"), index=True)
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id"), index=True)
    qty: Mapped[float] = mapped_column(Qty, nullable=False)
    satuan: Mapped[str | None] = mapped_column(String(32))

    recipe: Mapped[Recipe] = relationship(back_populates="items")
    cost_item: Mapped[CostItem | None] = relationship()
    sub_product: Mapped[Product | None] = relationship(foreign_keys=[product_id])


class HppSnapshot(TimestampMixin, Base):
    __tablename__ = "hpp_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False, index=True)
    hpp_per_unit: Mapped[float | None] = mapped_column(Uang)
    # rincian: asal tiap angka + tanggal harga dipakai + tipe tiap komponen
    rincian: Mapped[dict | None] = mapped_column(JSON)


# ── Pilar 2: Impor ──────────────────────────────────────────────────────────


class Import(TimestampMixin, Base):
    __tablename__ = "imports"

    id: Mapped[int] = mapped_column(primary_key=True)
    business_id: Mapped[int] = mapped_column(
        ForeignKey("businesses.id"), nullable=False, index=True
    )
    sumber: Mapped[str] = mapped_column(String(40), nullable=False)  # foto|csv|export_*
    file_path: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[StatusImpor] = mapped_column(
        Enum(StatusImpor, name="status_impor"), default=StatusImpor.draft, nullable=False
    )
    ringkasan: Mapped[dict | None] = mapped_column(JSON)

    rows: Mapped[list[ImportRow]] = relationship(back_populates="import_")


class ImportRow(Base):
    __tablename__ = "import_rows"

    id: Mapped[int] = mapped_column(primary_key=True)
    import_id: Mapped[int] = mapped_column(ForeignKey("imports.id"), nullable=False, index=True)
    raw: Mapped[str | None] = mapped_column(Text)
    parsed: Mapped[dict | None] = mapped_column(JSON)
    keyakinan: Mapped[float | None] = mapped_column(Float)  # 0..1
    status: Mapped[StatusBarisImpor] = mapped_column(
        Enum(StatusBarisImpor, name="status_baris_impor"),
        default=StatusBarisImpor.draft,
        nullable=False,
    )
    transaction_id: Mapped[int | None] = mapped_column(ForeignKey("transactions.id"))

    import_: Mapped[Import] = relationship(back_populates="rows")


# ── Pilar 3: Dokumen & panduan ──────────────────────────────────────────────


class ScoreSnapshot(TimestampMixin, Base):
    __tablename__ = "score_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    business_id: Mapped[int] = mapped_column(
        ForeignKey("businesses.id"), nullable=False, index=True
    )
    # skor_total = keluaran PENGGUNA saja. Yang masuk dokumen penyalur adalah
    # fakta mentah, BUKAN kolom ini (§4).
    skor_total: Mapped[int | None] = mapped_column()
    komponen: Mapped[dict | None] = mapped_column(JSON)
    periode: Mapped[str | None] = mapped_column(String(32))


class Document(TimestampMixin, Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    business_id: Mapped[int] = mapped_column(
        ForeignKey("businesses.id"), nullable=False, index=True
    )
    jenis: Mapped[JenisDokumen] = mapped_column(Enum(JenisDokumen, name="jenis_dokumen"), nullable=False)
    periode: Mapped[str | None] = mapped_column(String(32))
    file_path: Mapped[str | None] = mapped_column(String(255))


class KurInterview(TimestampMixin, Base):
    __tablename__ = "kur_interviews"

    id: Mapped[int] = mapped_column(primary_key=True)
    business_id: Mapped[int] = mapped_column(
        ForeignKey("businesses.id"), nullable=False, index=True
    )
    jawaban: Mapped[dict | None] = mapped_column(JSON)
    status: Mapped[str | None] = mapped_column(String(32))


class KurOutcome(TimestampMixin, Base):
    """Bahan bakar flywheel kalibrasi (§4). Yang dibangun sekarang hanya
    PENCATATAN hasilnya; kalibrasinya menunggu data cukup.
    """

    __tablename__ = "kur_outcomes"

    id: Mapped[int] = mapped_column(primary_key=True)
    business_id: Mapped[int] = mapped_column(
        ForeignKey("businesses.id"), nullable=False, index=True
    )
    document_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id"))
    hasil: Mapped[HasilKur] = mapped_column(Enum(HasilKur, name="hasil_kur"), nullable=False)
    plafon_cair: Mapped[float | None] = mapped_column(Uang)
    alasan_penolakan: Mapped[str | None] = mapped_column(Text)
    tanggal: Mapped[date | None] = mapped_column(Date)


class PanduanEntry(Base):
    """Klaim regulasi WAJIB bersumber + bertanggal — bukan ingatan LLM."""

    __tablename__ = "panduan_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    topik: Mapped[str] = mapped_column(String(40), nullable=False, index=True)  # kur|nib|izin_usaha|...
    jenis_usaha: Mapped[str | None] = mapped_column(String(120))
    isi: Mapped[str] = mapped_column(Text, nullable=False)
    sumber_url: Mapped[str] = mapped_column(String(400), nullable=False)
    tanggal_akses: Mapped[date] = mapped_column(Date, nullable=False)
    berlaku_sampai: Mapped[date | None] = mapped_column(Date)
