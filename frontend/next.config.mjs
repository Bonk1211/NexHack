/** @type {import('next').NextConfig} */
const nextConfig = {
  // Backend (FastAPI) base URL — the persona wall + matrix read run results from here.
  env: { NEXT_PUBLIC_API_BASE: process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000" },
};

export default nextConfig;
