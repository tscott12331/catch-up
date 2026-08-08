import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Browser tests use an isolated output directory so they can run beside `bun run dev`.
  distDir: process.env.NEXT_DIST_DIR || ".next",
};

export default nextConfig;
