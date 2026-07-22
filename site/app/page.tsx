import type { Metadata } from "next";
import Link from "next/link";
import Logo from "../components/Logo";
import HeroChat from "../components/HeroChat";
import s from "./page.module.css";

const DESC =
  "JembatanModal mengubah percakapan sehari-hari UMKM menjadi pembukuan yang jujur — untung bersih yang sebenarnya, siap saat mengajukan modal formal. Proyek portofolio dalam pengembangan.";

export const metadata: Metadata = {
  description: DESC,
  openGraph: {
    title: "JembatanModal — Asisten pembukuan AI untuk UMKM",
    description: DESC,
    locale: "id_ID",
    type: "website",
  },
  other: {
    "dicoding:email": "bryantnanur@gmail.com",
  },
};

export default function Landing() {
  return (
    <main className={s.page}>
      {/* ═══ NAV ═══ */}
      <header className={s.header}>
        <div className={s.navInner}>
          <div className={s.brand}>
            <Logo size={30} />
            <span className={s.brandName}>JembatanModal</span>
          </div>
          <nav className={s.nav}>
            <a href="#masalah" className={s.navLink}>
              Masalah
            </a>
            <a href="#siapa" className={s.navLink}>
              Untuk siapa
            </a>
            <a href="#pilar" className={s.navLink}>
              Cara kerja
            </a>
            <a href="#banding" className={s.navLink}>
              Perbandingan
            </a>
            <a href="#status" className={s.navLink}>
              Status
            </a>
            <Link href="/demo/" className={s.navCta}>
              Coba demo
            </Link>
          </nav>
        </div>
      </header>

      {/* ═══ HERO ═══ */}
      <section className={s.hero}>
        <div>
          <div className={s.heroTagRow}>
            <p className={s.heroEyebrow}>Asisten AI untuk UMKM</p>
            <span className={s.heroBadge}>
              <i />
              Dalam pengembangan
            </span>
          </div>
          <h1 className={s.h1}>
            Berjualan tiap hari, tapi untungnya tidak pernah kelihatan.
          </h1>
          <p className={s.heroLead}>
            Catatan di buku tulis, nota yang hilang, uang usaha bercampur uang
            pribadi. JembatanModal mengubah percakapan sehari-hari menjadi
            pembukuan yang jujur, sampai Anda tahu{" "}
            <strong>untung bersih yang sesungguhnya</strong> dan siap saat
            mengajukan modal ke bank. Tugasnya bukan sekadar membantu mencatat,
            melainkan <strong>membuat usaha layak mendapat modal</strong>.
          </p>
          <div className={s.heroCtas}>
            <Link href="/demo/" className={s.ctaPrimary}>
              Coba demonya
            </Link>
            <a href="#pilar" className={s.ctaSecondary}>
              Pelajari cara kerjanya
            </a>
          </div>
          <p className={s.heroHint}>
            Cukup bercakap seperti biasa. Tanpa form, tanpa istilah akuntansi.
          </p>
        </div>
        <HeroChat />
      </section>

      {/* ═══ MASALAH ═══ */}
      <section id="masalah" className={`${s.section} ${s.sectionTight} ${s.scrollAnchor}`}>
        <p className={s.kicker}>Masalah yang diserang</p>
        <h2 className={s.h2} style={{ maxWidth: "26ch" }}>
          Tiga masalah berlapis, dari yang paling umum ke yang paling dalam.
        </h2>
        <div className={s.grid3}>
          <div className={s.card}>
            <div className={s.cardNum}>01</div>
            <h3 className={s.cardTitle}>Tidak jelas soal uang sendiri</h3>
            <p className={s.cardBody}>
              Berjualan setiap hari tanpa tahu untung bersihnya. Uang usaha
              bercampur uang pribadi, dan omzet sering dikira untung. Setelah
              modal per produk benar-benar dihitung, angkanya kerap jauh di
              bawah dugaan.
            </p>
          </div>
          <div className={s.card}>
            <div className={s.cardNum}>02</div>
            <h3 className={s.cardTitle}>Dinilai berisiko oleh bank</h3>
            <p className={s.cardBody}>
              Tanpa laporan keuangan dan pemisahan uang usaha-pribadi, usaha
              yang sebenarnya sehat tetap sulit dipercaya bank atau koperasi,
              lalu berpaling ke pinjaman informal berbunga tinggi.
            </p>
            <p className={s.fine}>
              Seberapa besar proporsinya masih hipotesis lapangan yang sedang
              kami uji. Kami tidak mengutip angka yang belum terverifikasi.
            </p>
          </div>
          <div className={s.card}>
            <div className={s.cardNum}>03</div>
            <h3 className={s.cardTitle}>Enggan pada yang formal</h3>
            <p className={s.cardBody}>
              KUR dan perizinan dipersepsikan rumit dan pasti ditolak.
              Hambatannya psikologis, bukan sekadar dokumen. Banyak pelaku usaha
              tidak pernah ditolak, karena tidak pernah mencoba.
            </p>
          </div>
        </div>
      </section>

      {/* ═══ PRINSIP: ANGKA TIDAK DIKARANG ═══ */}
      <section className={s.dark}>
        <div className={s.darkInner}>
          <p className={s.kickerDark}>Aturan nomor satu di kode kami</p>
          <h2 className={s.h2Dark} style={{ maxWidth: "22ch" }}>
            Angka tidak pernah dikarang AI.
          </h2>
          <div className={s.grid3}>
            <div className={s.darkCard}>
              <div className={s.darkCardLabel}>AI hanya mendengarkan</div>
              <p className={s.darkCardBody}>
                AI membaca kalimat sehari-hari, misalnya &quot;laku 5 kotak
                risol 75rb&quot;, lalu menyusunnya menjadi catatan. Semua total,
                untung, dan modal dihitung oleh mesin kalkulasi yang diuji satu
                per satu, bukan oleh AI.
              </p>
            </div>
            <div className={s.darkCard}>
              <div className={s.darkCardLabel}>Ada penjaganya</div>
              <p className={s.darkCardBody}>
                Bila AI mengalikan sendiri, misalnya menuliskan &quot;75.000&quot;
                dari &quot;5 kotak kali 15 ribu&quot; padahal totalnya tidak
                pernah disebut, penjaga di dalam kode menolaknya dan aplikasi
                bertanya kembali. Kasus ini pernah benar-benar terjadi; itulah
                alasan penjaganya dibuat.
              </p>
            </div>
            <div className={s.darkCard}>
              <div className={s.darkCardLabel}>Mengaku saat tidak tahu</div>
              <p className={s.darkCardBody}>
                Resep belum lengkap atau harga bahan belum ada? Jawabannya
                &quot;belum diketahui&quot;, disertai apa yang kurang. Laporan
                selalu menyebut berapa persen penjualan yang modalnya benar-benar
                terhitung.
              </p>
            </div>
          </div>
          <div className={s.miniGrid}>
            {[
              [
                "Buku yang tidak menimpa",
                "Koreksi tidak menghapus catatan. Baris lama ditandai batal, baris baru masuk, sehingga selalu ada jawaban mengapa angka bulan lalu berubah.",
              ],
              [
                "Dua angka, dua peran",
                "Untung usaha satu periode dipisah tegas dari modal per produk. Modal per produk selalu berlabel kelengkapan datanya dan tidak pernah disajikan sebagai untung usaha.",
              ],
              [
                "Skor bukan untuk bank",
                "Skor kesehatan usaha hanya untuk memotivasi pengguna. Yang kelak disodorkan ke penyalur hanyalah fakta mentah yang bisa ditelusuri, bukan penilaian versi kami.",
              ],
              [
                "Satuan tidak ditebak",
                "Satuan “kg” dan “gram” yang bertabrakan membuat perhitungan berhenti dan masalahnya ditunjukkan, alih-alih meleset seribu kali lipat dengan percaya diri.",
              ],
              [
                "Informasi resmi bersumber",
                "Syarat KUR dan perizinan hanya diambil dari sumber resmi yang bertanggal, bukan dari ingatan AI, karena aturan bisa berubah.",
              ],
              [
                "Impor selalu ditinjau",
                "Hasil pembacaan AI masuk sebagai draf yang wajib disetujui pengguna. Salah baca yang lolos diam-diam akan mencemari seluruh pembukuan.",
              ],
            ].map(([t, b]) => (
              <div key={t} className={s.mini}>
                <div className={s.miniTitle}>{t}</div>
                <p className={s.miniBody}>{b}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ═══ UNTUK SIAPA ═══ */}
      <section id="siapa" className={`${s.section} ${s.sectionWide} ${s.scrollAnchor}`}>
        <p className={s.kicker}>Untuk siapa</p>
        <h2 className={s.h2} style={{ maxWidth: "26ch" }}>
          Paling berguna bagi usaha yang mengolah bahan menjadi produk.
        </h2>
        <p className={s.lead} style={{ maxWidth: "64ch" }}>
          Bukan soal besar-kecilnya usaha. Dua pertanyaan yang menentukan:
          apakah usaha Anda <strong>mengubah bahan menjadi produk lain</strong>{" "}
          (di situ modal per produk tersembunyi), dan apakah ada{" "}
          <strong>rencana modal konkret</strong> dalam beberapa bulan ke depan.
          Yang memenuhi keduanya merasakan manfaat penuhnya, dan satu aplikasi
          yang sama tetap melayani semuanya dengan kedalaman yang menyesuaikan
          sendiri.
        </p>
        <div className={s.grid3}>
          <div className={`${s.card} ${s.cardTarget}`}>
            <span className={`${s.pill} ${s.pillGreen}`} style={{ textTransform: "uppercase", letterSpacing: "0.04em" }}>
              Target utama
            </span>
            <h3 className={s.cardTitle} style={{ marginTop: 14 }}>
              Produsen rumahan
            </h3>
            <p className={s.audienceTag}>
              Risol, ayam crispy, katering, frozen food, kue
            </p>
            <p className={s.cardBody} style={{ marginTop: 12 }}>
              Modal per porsi tersembunyi di balik resep. AI menanyakan resep
              lewat percakapan, lalu modal dan untung kotor per porsi dihitung
              dari harga belanjaan sendiri. Di sinilah momen &quot;ternyata
              untung saya segini&quot;.
            </p>
            <p className={s.fine} style={{ fontSize: 12.5 }}>
              Ukuran bukan patokan: penjual ayam crispy pinggir jalan pun
              terhitung produsen, karena bahannya diubah menjadi produk lain.
            </p>
          </div>
          <div className={s.card}>
            <span className={`${s.pill} ${s.pillMuted}`}>Tetap terlayani</span>
            <h3 className={s.cardTitle} style={{ marginTop: 14 }}>
              Penjual ulang
            </h3>
            <p className={s.audienceTag}>
              Warung kelontong, penjual sayur, toko beras
            </p>
            <p className={s.cardBody} style={{ marginTop: 12 }}>
              Modalnya sederhana: harga kulakan terakhir. Cukup mencatat dan
              melihat untung, dan <strong>tidak akan pernah ditanya resep</strong>.
              Membeli per karung lalu menjual per liter pun terhitung, lengkap
              dengan susutnya.
            </p>
          </div>
          <div className={s.card}>
            <span className={`${s.pill} ${s.pillMuted}`}>Pelengkap sistem</span>
            <h3 className={s.cardTitle} style={{ marginTop: 14 }}>
              Usaha yang sudah bersistem
            </h3>
            <p className={s.audienceTag}>
              Rumah makan, produsen menengah, pengguna aplikasi kasir
            </p>
            <p className={s.cardBody} style={{ marginTop: 12 }}>
              Aplikasi kasir mencatat penjualan, tapi jarang menjawab pertanyaan
              modal: berapa biaya per porsi <em>hari ini</em>, saat harga ayam,
              minyak, dan tepung berubah tiap pekan? JembatanModal berperan
              sebagai <strong>pemantau modal dan margin per produk</strong> di
              samping sistem yang sudah ada, dengan riwayat harga bahan yang
              bertanggal.
            </p>
            <p className={s.fine} style={{ fontSize: 12.5 }}>
              Data penjualan dari sistem lama nantinya cukup diimpor, tidak
              diketik ulang.{" "}
              <span className={s.amberNote}>(Impor masih dalam rencana.)</span>
            </p>
          </div>
        </div>
        <div className={s.sectionCallout}>
          <span className={s.calloutDot} />
          <p>
            Tidak ada menu &quot;pilih jenis usaha&quot;. AI menyimpulkannya
            dari cara Anda bercerita soal dagangan. &quot;Jualan ayam&quot; bisa
            berarti penjual ayam potong atau produsen ayam crispy, dan yang
            membedakan hanya konteks bahasanya. Setelah itu, hanya kedalaman
            yang relevan yang dimunculkan.
          </p>
        </div>
        <p className={s.postscript}>
          Positioning-nya sengaja sempit: yang diutamakan adalah produsen
          rumahan yang ingin naik kelas. Satu mesin yang sama memang bisa
          melayani lebih luas, tapi menjual keluasan berarti menjadi
          &quot;aplikasi serba bisa&quot; yang tidak punya alasan untuk dipilih.
          Sektor jasa (salon, laundry, jahit) belum dilayani untuk sekarang; itu
          penundaan yang disengaja, bukan kelalaian.
        </p>
      </section>

      {/* ═══ TANGGA NILAI ═══ */}
      <section className={s.section}>
        <p className={s.kicker}>Tangga nilai</p>
        <h2 className={s.h2} style={{ maxWidth: "28ch" }}>
          Aplikasi pembukuan berhenti di mencatat. Ini dirancang sampai
          bertindak.
        </h2>
        <div className={s.grid4}>
          <div className={s.ladderCard}>
            <div className={s.ladderNum}>Level 1</div>
            <h3 className={s.ladderTitle}>Mencatat</h3>
            <p className={s.ladderBody}>
              &quot;Apa yang terjadi di usaha saya?&quot; Transaksi terkumpul
              rapi lewat percakapan.
            </p>
          </div>
          <div className={s.ladderCard}>
            <div className={s.ladderNum}>Level 2</div>
            <h3 className={s.ladderTitle}>Memahami</h3>
            <p className={s.ladderBody}>
              &quot;Apa arti angka-angka ini?&quot; Modal per porsi, untung
              bersih, ke mana uang mengalir.
            </p>
          </div>
          <div className={s.ladderCard}>
            <div className={s.ladderNum}>Level 3</div>
            <h3 className={s.ladderTitle}>Menasihati</h3>
            <p className={s.ladderBody}>
              &quot;Apa yang harus saya lakukan?&quot; Penjelasan apa yang
              sehat, apa yang menahan, dan langkah konkretnya.
            </p>
          </div>
          <div className={s.ladderCardDark}>
            <div className={`${s.ladderNum} ${s.ladderNumDark}`}>Level 4</div>
            <h3 className={s.ladderTitle}>Bertindak</h3>
            <p className={`${s.ladderBody} ${s.ladderBodyDark}`}>
              &quot;Kerjakan untuk saya.&quot; Laporan siap bank, draf proposal
              KUR, checklist dokumen.
            </p>
          </div>
        </div>
      </section>

      {/* ═══ 4 PILAR ═══ */}
      <section id="pilar" className={`${s.section} ${s.scrollAnchor}`}>
        <p className={s.kicker}>Empat pilar</p>
        <h2 className={s.h2}>Empat hal yang dikerjakannya</h2>
        <p className={s.lead} style={{ maxWidth: "60ch" }}>
          Keempatnya saling mengunci: pencatatan memberi data, hitungan modal
          membuatnya jujur, impor mempercepat, dan dokumen adalah buahnya. Kami
          menggarapnya sesuai urutan yang masuk akal, dan setiap bagian diberi
          label status apa adanya.
        </p>
        <div className={s.grid2}>
          <div className={`${s.card} ${s.cardPad28}`}>
            <div className={s.pilarHead}>
              <div className={s.pilarNum}>Pilar 1</div>
              <span className={`${s.pill} ${s.pillGreen}`}>
                <span className={`${s.dot} ${s.dotGreen}`} />
                Sudah berjalan &amp; teruji
              </span>
            </div>
            <h3 className={s.pilarTitle}>Mencatat lewat percakapan</h3>
            <p className={s.pilarBody}>
              &quot;Beli minyak 2 liter 38rb untuk dagang&quot; sudah cukup. AI
              memahami nominal, barang, sampai takarannya, lalu mengelompokkan
              sendiri: pemasukan, belanja barang, biaya operasional, atau
              keperluan pribadi. Setiap catatan dikonfirmasi; bila keliru cukup
              diketuk untuk dikoreksi, dan koreksi tidak pernah menghapus jejak.
            </p>
          </div>
          <div className={`${s.card} ${s.cardPad28}`}>
            <div className={s.pilarHead}>
              <div className={s.pilarNum}>Pilar 4</div>
              <span className={`${s.pill} ${s.pillGreen}`}>
                <span className={`${s.dot} ${s.dotGreen}`} />
                Mesin hitung selesai &amp; teruji
              </span>
            </div>
            <h3 className={s.pilarTitle}>Menghitung modal per produk</h3>
            <p className={s.pilarBody}>
              Untuk usaha yang mengolah sendiri, AI menanyakan resep lewat
              percakapan, bukan form. Dari harga belanjaan sendiri, mesin
              menghitung modal dan untung kotor per porsi. Sumber setiap angka
              selalu ditunjukkan; bila harga bahan belum ada, sistem
              menyatakannya terus terang.
            </p>
            <p className={s.pilarStatus}>
              Kartu untung per produk sudah tampil di jendela chat; wawancara
              resep lewat percakapan masih dalam rencana.
            </p>
          </div>
          <div className={s.cardWarm}>
            <div className={s.pilarHead}>
              <div className={s.pilarNum}>Pilar 2</div>
              <span className={`${s.pill} ${s.pillAmber}`}>
                <span className={`${s.dot} ${s.dotAmber}`} />
                Dalam rencana
              </span>
            </div>
            <h3 className={s.pilarTitle}>Membaca catatan yang sudah ada</h3>
            <p className={s.pilarBody}>
              Catatan lama tidak hangus. Foto buku tulis, tangkapan layar
              percakapan, spreadsheet, sampai ekspor aplikasi kasir: AI
              membacanya dan mengusulkan draf. Yang masuk pembukuan hanya yang
              sudah ditinjau dan disetujui. Tidak dikunci ke format aplikasi
              tertentu.
            </p>
          </div>
          <div className={s.cardWarm}>
            <div className={s.pilarHead}>
              <div className={s.pilarNum}>Pilar 3</div>
              <span className={`${s.pill} ${s.pillAmber}`}>
                <span className={`${s.dot} ${s.dotAmber}`} />
                Dalam rencana
              </span>
            </div>
            <h3 className={s.pilarTitle}>Menyiapkan pertemuan dengan bank</h3>
            <p className={s.pilarBody}>
              Dari catatan yang sudah rapi: laporan laba-rugi dengan format yang
              dikenal petugas bank, draf proposal KUR, dan checklist dokumen.
              Ada juga skor kesehatan usaha untuk memantau kemajuan sendiri,
              serta penjelasan urusan perizinan dalam bahasa sehari-hari.
              Informasi persyaratan selalu diambil dari sumber resmi yang
              bertanggal.
            </p>
            <p className={s.pilarStatus}>
              Semua dokumen kredit adalah alat bantu persiapan, bukan jaminan
              persetujuan. Keputusan tetap di bank atau koperasi.
            </p>
          </div>
        </div>
      </section>

      {/* ═══ DIFERENSIASI ═══ */}
      <section id="banding" className={`${s.section} ${s.scrollAnchor}`}>
        <p className={s.kicker}>Bedanya di mana</p>
        <h2 className={s.h2} style={{ maxWidth: "28ch" }}>
          Tujuannya bukan &quot;catatan saya rapi&quot;, melainkan &quot;usaha
          saya layak mendapat modal&quot;.
        </h2>
        <div className={s.compare}>
          <div className={s.compareScroll}>
            <div className={`${s.compareRow} ${s.compareHead}`}>
              <div className={s.compareLabel} />
              <div className={s.compareCellHead}>Aplikasi pembukuan umum</div>
              <div className={s.compareCellHead}>Aplikasi akuntansi</div>
              <div className={s.compareCellHeadUs}>JembatanModal</div>
            </div>
            <div className={s.compareRow}>
              <div className={s.compareLabel}>Cara input</div>
              <div className={s.compareCell}>Form, pilih kategori manual</div>
              <div className={s.compareCell}>
                Form kompleks, perlu paham akuntansi
              </div>
              <div className={s.compareUs}>Percakapan bahasa sehari-hari</div>
            </div>
            <div className={s.compareRow}>
              <div className={s.compareLabel}>Cara mulai</div>
              <div className={s.compareCell}>Mengisi dari nol</div>
              <div className={s.compareCell}>Mengisi dari nol / impor teknis</div>
              <div className={s.compareUs}>
                Foto buku tulis yang sudah ada{" "}
                <span className={s.amberNote}>(rencana)</span>
              </div>
            </div>
            <div className={s.compareRow}>
              <div className={s.compareLabel}>Modal per produk (HPP)</div>
              <div className={s.compareCell}>Manual, bila ada</div>
              <div className={s.compareCell}>Perlu penyusunan BOM formal</div>
              <div className={s.compareUs}>
                Diwawancarai lewat percakapan, dipantau saat harga bahan berubah
              </div>
            </div>
            <div className={s.compareRow}>
              <div className={s.compareLabel}>Tujuan akhir</div>
              <div className={s.compareCell}>&quot;Catatan saya rapi&quot;</div>
              <div className={s.compareCell}>&quot;Pembukuan saya benar&quot;</div>
              <div className={`${s.compareUs} ${s.compareUsStrong}`}>
                &quot;Usaha saya layak mendapat modal&quot;
              </div>
            </div>
          </div>
        </div>
        <p className={s.postscript} style={{ fontSize: 13 }}>
          AI dipakai persis di tempat yang mustahil bagi aplikasi berbasis
          aturan: memahami &quot;75rb&quot; dan &quot;setengah kilo&quot;,
          membaca foto buku yang tidak rapi, menyimpulkan jenis usaha dari
          konteks, mewawancarai resep, dan menyusun draf dokumen. Namun tidak
          pernah untuk menghitung. Dan ini bukan pengganti aplikasi kasir atau
          POS; posisinya pelengkap, bukan pesaing.
        </p>
      </section>

      {/* ═══ SETELAH MODAL CAIR ═══ */}
      <section className={s.section}>
        <div className={s.grid2} style={{ marginTop: 0 }}>
          <div className={`${s.card} ${s.cardPad30}`}>
            <p className={s.kicker}>Kebutuhan yang berulang</p>
            <h3 className={s.pilarTitle} style={{ fontSize: 24, marginTop: 12 }}>
              Harga bahan pokok tidak pernah diam
            </h3>
            <p className={s.pilarBody}>
              Harga minyak, ayam, tepung, dan cabai bergerak setiap pekan,
              sehingga margin ikut bergeser tanpa terasa. Bagi usaha dengan
              banyak produk, mengetahui modal per porsi bukan hitungan sekali
              jadi melainkan kebutuhan rutin. Karena itu setiap harga bahan
              disimpan bertanggal sejak hari pertama: riwayatnya menjadi dasar
              pemantauan margin.
            </p>
            <p className={s.pilarBody}>
              Kelak aplikasi dapat menyapa lebih dulu: &quot;ayam naik
              Rp4.000/kg minggu ini, margin risol turun dari 73% ke 66%&quot;.
            </p>
            <p className={s.pilarStatus}>
              Pemantauan margin otomatis masih dalam rencana. Fondasi datanya
              yang sudah disiapkan sekarang.
            </p>
          </div>
          <div className={`${s.card} ${s.cardPad30}`}>
            <p className={s.kicker}>Soal biaya</p>
            <h3 className={s.pilarTitle} style={{ fontSize: 24, marginTop: 12 }}>
              Belum ada harga, dan itu disengaja
            </h3>
            <p className={s.pilarBody}>
              Model harga belum dikunci karena kami belum selesai mendengarkan
              calon pengguna dan pihak penyalur. Mengunci harga sebelum itu
              selesai adalah keputusan mahal yang sulit dibalik.
            </p>
            <p className={s.pilarBody}>
              Satu hal yang sudah dikunci adalah pagar etisnya: bila kelak ada
              kerja sama dengan penyalur, kami dibayar untuk{" "}
              <strong>pemohon yang jujur dan siap</strong>, bukan untuk pemohon
              yang lolos. Begitu bayaran bergantung pada persetujuan, godaannya
              adalah memoles laporan, dan itu mengkhianati aturan nomor satu
              kami.
            </p>
          </div>
        </div>
      </section>

      {/* ═══ STATUS HARI INI ═══ */}
      <section id="status" className={`${s.section} ${s.scrollAnchor}`}>
        <p className={s.kicker}>Status hari ini</p>
        <h2 className={s.h2} style={{ maxWidth: "26ch" }}>
          Sejauh mana produk ini nyata, apa adanya.
        </h2>
        <div className={s.grid2}>
          <div className={`${s.card} ${s.cardPad30}`}>
            <span className={`${s.pill} ${s.pillGreen}`}>
              <span className={`${s.dot} ${s.dotGreen}`} />
              Sudah berjalan &amp; teruji
            </span>
            <div className={s.statusList}>
              {[
                "Pencatatan dan koreksi lewat chat, dari kalimat sehari-hari sampai tersimpan, dengan penjaga yang menolak angka hasil hitungan AI.",
                "Mesin hitung modal yang matang: penjual ulang (termasuk susut dan konversi kemasan), produsen (resep, bahan setengah jadi, faktor kehilangan, harga jual bertingkat), untung per periode, dan semua jalur “belum diketahui” teruji.",
                "Antarmuka chat web mobile-first yang tidak terkunci ke satu penyedia AI, plus data contoh Bu Sari. Delapan belas berkas pengujian menjaga semuanya.",
              ].map((t) => (
                <div key={t.slice(0, 20)} className={s.statusItem}>
                  <span className={s.statusTick}>
                    <i />
                  </span>
                  <p>{t}</p>
                </div>
              ))}
            </div>
          </div>
          <div className={`${s.cardWarm} ${s.cardPad30}`}>
            <span className={`${s.pill} ${s.pillAmber}`}>
              <span className={`${s.dot} ${s.dotAmber}`} />
              Belum, dan kami sampaikan apa adanya
            </span>
            <div className={s.statusList}>
              {[
                "Wawancara resep lewat chat belum tersambung: kartu untung per produk sudah tampil, tapi resep belum bisa diisi lewat percakapan.",
                "Impor foto buku tulis, laporan PDF, skor, dokumen KUR, dan WhatsApp semuanya masih rencana.",
                "Yang paling penting: validasi lapangan belum berjalan. Premis “sulit dipercaya bank karena tidak ada laporan” masih hipotesis yang akan diuji langsung ke pelaku UMKM dan petugas bank.",
              ].map((t) => (
                <div key={t.slice(0, 20)} className={`${s.statusItem} ${s.statusItemMuted}`}>
                  <span className={s.statusDash} />
                  <p>{t}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* ═══ BU SARI ═══ */}
      <section className={s.section} style={{ paddingBottom: 80 }}>
        <div className={s.busari}>
          <div>
            <p className={s.kicker}>Contoh perjalanan</p>
            <h2 className={s.busariH2}>
              Bu Sari, katering &amp; frozen food rumahan.
            </h2>
            <p className={s.busariP}>
              Pesanan lewat WhatsApp, catatan di buku tulis yang sering
              terlewat. Ingin membeli freezer kedua, butuh modal sekitar Rp15
              juta, tapi tidak pernah mengajukan KUR karena merasa pasti ditolak
              tanpa pembukuan.
            </p>
            <p className={s.busariP}>
              Bu Sari adalah persona yang memandu seluruh desain produk; data
              contohnya bahkan hidup di kode kami. Momen yang kami kejar: saat
              pertama kali ia mengetahui untung bersihnya <strong>yang
              sebenarnya</strong>. Biasanya mengejutkan, karena selama ini omzet
              dikira untung.
            </p>
          </div>
          <div className={s.timeline}>
            <div className={s.timeRow}>
              <span className={s.timeWhen}>Minggu 1</span>
              <p>
                Mulai mencatat lewat chat setiap selesai transaksi. Tiga puluh
                detik, sambil menjaga dagangan.
              </p>
            </div>
            <div className={s.timeRow}>
              <span className={s.timeWhen}>Minggu 2</span>
              <p>
                Ditanya resep risolnya lewat percakapan. Modal per kotak
                ditemukan: <span className={s.mono}>Rp3.950</span>, dihitung
                dari harga belanjaannya sendiri.
              </p>
            </div>
            <div className={s.timeRow}>
              <span className={s.timeWhen}>Bulan 2</span>
              <p>
                Laporan dua bulan siap dibawa: laba-rugi dan arus kas, lengkap
                dengan keterangan seberapa lengkap datanya.
              </p>
            </div>
            <div className={s.timeRow}>
              <span className={s.timeWhen}>Bulan 3</span>
              <p>
                Datang ke bank bukan sebagai &quot;pedagang tanpa
                pembukuan&quot;, melainkan pemilik usaha dengan laporan dan
                proposal yang jelas.
              </p>
            </div>
            <p className={s.fine} style={{ fontSize: 12 }}>
              Gambaran perjalanan yang dirancang. Sebagian tahapannya masih
              dalam rencana; lihat label status pada tiap pilar.
            </p>
          </div>
        </div>
      </section>

      {/* ═══ PENUTUP ═══ */}
      <section className={s.dark}>
        <div className={s.darkInner} style={{ paddingTop: 64, paddingBottom: 64 }}>
          <div className={s.closing}>
            <p className={s.kickerDark}>Taruhannya</p>
            <h2 className={s.closingH2}>
              Jembatan antara usaha kecil dan modal formal bisa dibangun dari
              satu bahan: kejujuran angka.
            </h2>
            <p className={s.closingLead}>
              Kekuatan produk ini bukan fitur AI-nya, melainkan disiplinnya: AI
              hanya memahami dan menarasikan, tidak pernah berhitung; produk
              mengaku tidak tahu daripada mengarang; dan yang disodorkan ke bank
              hanyalah fakta yang bisa ditelusuri ke transaksi.
            </p>
            <Link href="/demo/" className={s.closingCta}>
              Coba demonya
            </Link>
          </div>
        </div>
      </section>

      {/* ═══ FOOTER ═══ */}
      <footer className={s.footer}>
        <div className={s.footerInner}>
          <div className={s.footerTop}>
            <div className={s.footerCol}>
              <div className={s.brand}>
                <Logo size={28} />
                <span className={s.footerBrandName}>JembatanModal</span>
              </div>
              <p className={s.footerText}>
                Proyek portofolio yang sedang dikembangkan dan belum tersedia
                untuk publik. Fondasi pencatatan dan mesin hitung modal sudah
                berjalan dan teruji; impor data dan dokumen modal menyusul sesuai
                urutan garap.
              </p>
              <p className={s.footerContact}>
                Ingin berdiskusi soal proyek ini?{" "}
                <a href="mailto:halo@jembatanmodal.id">halo@jembatanmodal.id</a>
              </p>
            </div>
            <div className={s.footerNote}>
              <div className={s.footerNoteHead}>
                <i />
                Catatan penting
              </div>
              <p className={s.footerNoteBody}>
                Dokumen terkait kredit yang kelak dihasilkan adalah alat bantu
                persiapan, bukan jaminan persetujuan pinjaman. Keputusan
                sepenuhnya di lembaga penyalur.
              </p>
            </div>
          </div>
          <p className={s.footerLegal}>
            Tidak menggantikan POS/aplikasi kasir · Tidak memegang uang atau
            menyalurkan pinjaman · Tidak mengurus perizinan ke badan berwenang
          </p>
        </div>
      </footer>
    </main>
  );
}
