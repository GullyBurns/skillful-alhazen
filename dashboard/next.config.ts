import type { NextConfig } from "next";
import path from "path";

const nextConfig: NextConfig = {
  output: 'standalone',
  experimental: {
    externalDir: true,   // Allow resolving files outside dashboard/ (needed for local_skills/ symlinks)
  },
  turbopack: {
    root: path.resolve(__dirname, '..'),  // Project root — allows Turbopack to resolve local_skills/ symlinks in worktrees
  },
  env: {
    PROJECT_ROOT: path.resolve(__dirname, '..'),  // dashboard/../ = skillful-alhazen/
  },
};

export default nextConfig;
