import type { NextConfig } from "next";
import path from "path";

const nextConfig: NextConfig = {
  output: 'standalone',
  experimental: {
    externalDir: true,   // Allow resolving files outside dashboard/ (needed for local_skills/ symlinks)
  },
  env: {
    PROJECT_ROOT: path.resolve(__dirname, '..'),  // dashboard/../ = skillful-alhazen/
  },
};

export default nextConfig;
