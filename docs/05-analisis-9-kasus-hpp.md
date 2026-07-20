# Analisis 9 Kasus UMKM terhadap HPP Tracer

> Sumber: `C:\project\UMKM\rangkuman-*.md` (angkringan, bakso gerobak, frozen food,
> hidroponik selada, konveksi, laundry kiloan, toko fashion online, toko kelontong,
> warteg). Dibandingkan dengan implementasi HPP saat ini di `app/services/hpp.py`.
>
> Status: **bahan diskusi**, belum keputusan. Sesuai CLAUDE.md ("sebelum menambah
> tool/kolom baru: cek apakah brief & arsitektur sudah mencakupnya — kalau belum,
> bahas dulu").

---

## 1. Temuan utama: cakupan omzet ≠ cakupan biaya

`cakupan_hpp()` mengukur **berapa persen omzet yang produknya terkenali dan
HPP-nya berstatus `lengkap`**. Ia tidak mengukur **berapa persen biaya nyata yang
tertangkap** oleh HPP itu.

Akibatnya ada lubang jujur-tapi-menyesatkan: warteg yang semua penjualannya
tertaut produk akan melihat **`cakupan_hpp` = 100%** sementara HPP-nya hanya
memuat 60% biaya sebenarnya — laba dilaporkan terlalu besar ±36%, dengan label
"lengkap". Ini secara efektif melanggar semangat aturan #2 (jangan mengarang
angka saat data kurang): statusnya `lengkap` padahal yang lengkap cuma sisi bahan.

**Porsi biaya yang tertangkap model `material`-only:**

| Kasus | Basis | Material tertangkap | Total biaya riil | Cakupan biaya |
|---|---|---|---|---|
| Angkringan (es teh) | per gelas | Rp 1.195 | Rp 1.295 | **92%** |
| Toko kelontong (beras) | per liter | Rp 10.240 | Rp 10.492 | **98%** ⚠️ salah arah |
| Konveksi (kaos) | per pcs | ± Rp 35.600 | Rp 44.400 | **80%** |
| Bakso gerobak | per mangkok | ± Rp 9.000 | Rp 12.000 | **75%** |
| Frozen food (dimsum) | per pack | Rp 13.500 | Rp 17.800 | **76%** |
| Toko fashion online | per pcs | Rp 47.500 | Rp 74.490 | **64%** |
| Warteg | per porsi | Rp 6.550 | Rp 11.000 | **60%** |
| Hidroponik selada | per kg | ± Rp 4.830 | Rp 13.850 | **35%** |
| Laundry kiloan | per kg | Rp 640 | Rp 6.075 | **11%** |

Tiga kasus terbawah bukan kasus pinggiran — laundry & hidroponik justru contoh
usaha yang paling butuh HPP jujur, karena di sanalah "merasa untung padahal
tidak" paling sering terjadi. Dokumen laundry menyebutnya eksplisit: *"biaya
terbesar bukan deterjen."*

**Rekomendasi minimal (tidak melanggar batas keras):** pisahkan `cakupan_hpp`
menjadi dua angka — **cakupan omzet** (sudah ada) dan **cakupan biaya**
(indikatif: apakah usaha ini punya pos biaya berulang di `transactions` yang
tidak pernah muncul di resep mana pun). Yang kedua tidak menghitung overhead,
hanya **mengaku bahwa ada biaya di luar HPP** — persis semangat aturan #2.

---

## 2. Pola struktural yang berulang di 9 kasus

Diurutkan dari yang paling sering muncul. Kolom terakhir = apakah skema sekarang
sanggup menampungnya tanpa migrasi menyakitkan.

| # | Pola | Muncul di | Skema siap? |
|---|---|---|---|
| A | **Overhead pool per periode ÷ output** | warteg, laundry, hidroponik, bakso, angkringan, frozen food, konveksi (7/9) | Slot `overhead` ada, tapi **belum ada tempat menyimpan "pool per periode"** — `recipe_items` hanya bisa menampung takaran per-unit |
| B | **Sub-produk / resep bertingkat** | bakso (adonan→pentol→mangkok), warteg (lauk batch→porsi), angkringan (usus ungkep→tusuk), frozen food (adonan→pcs→pack) (4/9) | ❌ `recipe_items.cost_item_id` tidak bisa menunjuk produk lain |
| C | **Konversi satuan & susut** | kelontong (25 kg → 30,5 liter, susut 2,5%), konveksi (kg kain → pcs, waste 12–18%), hidroponik (1.200 semai → 900 krop), bakso (1 kg → 130 butir) (4/9) | ⚠️ sebagian: `yield_qty` menampung konversi, **susut/rendemen tidak ada** |
| D | **Reject / rework dibebankan ke unit yang laku** | konveksi (÷ 1−4%), laundry (rewash 2%), warteg (waste 10%), hidroponik (gagal panen 10%) (4/9) | ❌ tidak ada |
| E | **Harga jual majemuk** (kanal/grade/kuantitas) | frozen food (reseller vs eceran), hidroponik (resto vs ecer, Grade A/B), laundry (4 menu), konveksi (tier qty), kelontong (utuh vs eceran) (5/9) | ❌ `products.harga_jual` skalar tunggal |
| F | **Biaya persentase-dari-harga-jual & per-transaksi** | fashion online (platform 13%, iklan 8%, retur 6%, logistik Rp 3.000/order), laundry (cadangan 2%) (2/9) | ❌ bentuk biaya ketiga: bukan `qty × harga` |
| G | **Konsinyasi / titip jual** | angkringan (makanan), kelontong (roti & susu segar) (2/9) | ❌ HPP = harga titip, modal nol, hanya bayar yang laku — bukan "harga beli terakhir" |

---

## 3. Catatan per kasus (yang tidak tertangkap tabel)

**Angkringan.** Dua model biaya hidup berdampingan di satu warung: minuman
(produksi, resep jelas) dan makanan (konsinyasi, margin terkunci Rp 1.000/item).
Deteksi jenis usaha per-**produk** — bukan per-usaha — terbukti keputusan yang
benar (aturan #8). Pencatatannya bukan per-transaksi melainkan **rekonsiliasi
stok** ("bahan awal − sisa = terjual"); ini bentuk input yang tidak diantisipasi
tool `catat_transaksi`.

**Bakso gerobak.** Kasus paling menuntut. Pentol adalah *mata uang audit* — satu
entitas yang sekaligus output resep A dan bahan resep B. Tanpa resep bertingkat,
pengguna harus menghitung sendiri Rp 1.150/butir lalu memasukkannya sebagai harga
bahan — artinya **aritmatika pindah ke kepala pengguna**, yang secara semangat
sama buruknya dengan menaruhnya di prompt LLM.

**Frozen food.** Satu-satunya kasus di mana `labor_time` muncul dalam bentuk
paling bersih (jam-orang × tarif, Rp 3.750/pack = 21% HPP). Juga: alokasi subsidi
ongkir sebagai "biaya mendarat" — konsep landed cost yang berbeda dari HPP
produksi.

**Hidroponik.** HPP-nya sama sekali bukan resep: total biaya sebulan ÷ kg yang
laku. Penyusutan aset saja 23% HPP. Model `Σ bahan ÷ yield` tidak berlaku —
yang berlaku adalah *cost pool periodik*.

**Konveksi.** Job costing: biaya tetap per order (afdruk screen Rp 25.000) dibagi
kuantitas order, sehingga **HPP per pcs berubah mengikuti besar order** (Rp 47.500
@50 pcs vs Rp 42.800 @500 pcs). Skema sekarang mengasumsikan HPP per produk itu
tunggal.

**Laundry.** Secara jujur ini **kasus jasa** — non-goal yang disadari. Berguna
justru sebagai penanda batas: kalau produk ini menerima pengguna laundry hari
ini, angkanya akan salah 89%. Perlu ada perilaku **menolak dengan sopan**, bukan
menghitung setengah-setengah.

**Toko fashion online.** Reseller murni pada intinya (`harga modal` = harga beli
terakhir ✅), tapi 36% biayanya adalah potongan platform + iklan yang proporsional
terhadap harga jual. HPP-nya benar, "untung"-nya yang salah.

**Toko kelontong.** Kasus paling penting untuk pilar 4 versi sekarang, karena
100% material — **dan tetap salah**. Dokumennya menyebut perhitungan tanpa susut
sebagai *"yang paling sering salah dihitung pemilik kelontong"*: Rp 10.240 vs
Rp 10.492 riil. Menambahkan **rendemen/susut pada konversi satuan** adalah
perbaikan bernilai tinggi yang **tidak menyentuh `labor_time`/`overhead` sama
sekali** — masih di dalam batas keras.

**Warteg.** Overhead dapur bersama (gas, minyak, bumbu dasar) memang **tidak bisa**
dibebankan per resep secara akurat — dokumennya sendiri bilang begitu, dan
menyelesaikannya dengan `total per hari ÷ porsi per hari`. Ini konfirmasi
independen bahwa pola A adalah *cost pool*, bukan takaran per-unit.

---

## 4. Implikasi untuk urutan garap

Yang **bisa dikerjakan sekarang tanpa melanggar batas keras** (semuanya
`material`-only, tidak ada kalkulasi `labor_time`/`overhead`):

1. **Susut/rendemen pada konversi satuan** — menyelamatkan kasus kelontong &
   konveksi. Bentuk: faktor pada `recipes` (atau pada konversi satuan produk
   reseller), bukan tipe komponen baru.
2. **Cakupan biaya sebagai keluaran kedua di samping cakupan omzet** — jujur soal
   apa yang belum masuk, tanpa menghitung apa pun yang belum boleh dihitung.
3. **Resep bertingkat (sub-produk)** — murni relasional (`recipe_items` boleh
   menunjuk `product_id`), tetap `material`, tapi membuka bakso, warteg,
   angkringan, frozen food sekaligus. Ini kandidat terkuat: dampak besar, tidak
   menyentuh batas.
4. **Harga jual majemuk** — memindahkan `harga_jual` dari kolom skalar ke tabel
   bertanggal/berkanal. Kalau ditunda, migrasinya nanti menyakitkan (argumen yang
   sama persis dengan `cost_items.tipe`).

Yang **harus dibahas dulu** karena menyentuh atau melewati batas: pola A
(overhead pool), D (reject), F (biaya persentase), G (konsinyasi), dan sikap
terhadap kasus jasa (laundry).
