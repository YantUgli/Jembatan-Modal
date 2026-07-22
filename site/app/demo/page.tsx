import type { Metadata } from "next";
import Link from "next/link";
import ChatDemo from "../../components/ChatDemo";
import s from "./demo.module.css";

const DESC =
  "Demo chat JembatanModal dengan data contoh Bu Sari — pencatatan lewat percakapan, koreksi kategori, kartu untung, dan laporan singkat. Berjalan tanpa server.";

export const metadata: Metadata = {
  title: "Demo",
  description: DESC,
  openGraph: {
    title: "Demo — JembatanModal",
    description: DESC,
    locale: "id_ID",
    type: "website",
  },
  other: {
    "dicoding:email": "bryantnanur@gmail.com",
  },
};

export default function DemoPage() {
  return (
    <div className={s.screen}>
      <div className={s.topbar}>
        <Link href="/" className={s.back}>
          ← Kembali ke halaman utama
        </Link>
        <span className={s.topbarNote}>Demo dengan data contoh · tanpa server</span>
      </div>
      <div className={s.phone}>
        <ChatDemo />
      </div>
      <p className={s.disclaimer}>
        Antarmuka ini direkonstruksi dari kode produk yang sudah berjalan. Pada
        demo ini jawaban disulih dari data contoh; pada produk aslinya,
        pencatatan dan koreksi diproses server sungguhan.
      </p>
    </div>
  );
}
