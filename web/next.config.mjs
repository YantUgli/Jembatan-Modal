/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Server dipertahankan (bukan output:export) supaya Route Handler bisa jadi
  // BFF proxy ke FastAPI internal.
};

export default nextConfig;
