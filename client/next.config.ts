import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /* config options here */
  reactStrictMode: true,
  turbopack: {
    root: import.meta.dirname,
  },
};

export default nextConfig;
