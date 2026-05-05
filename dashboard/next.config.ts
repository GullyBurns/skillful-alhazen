import type { NextConfig } from "next";
import path from "path";

const nextConfig: NextConfig = {
  output: 'standalone',
  experimental: {
    externalDir: true,
  },
  env: {
    PROJECT_ROOT: path.resolve(__dirname, '..'),  // dashboard/../ = skillful-alhazen/
  },
};

export default nextConfig;
