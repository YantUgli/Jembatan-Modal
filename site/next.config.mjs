/** @type {import('next').NextConfig} */
const nextConfig = {
  // Situs portofolio statis — tidak butuh server Node saat deploy.
  output: "export",
  // Tiap rute jadi folder sendiri (out/index.html, out/demo/index.html),
  // sehingga tautan antarhalaman resolve mulus di static hosting mana pun.
  trailingSlash: true,
  reactStrictMode: true,
};

export default nextConfig;
