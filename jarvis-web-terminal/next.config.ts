import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /* config options here */
  turbopack: {
    // Prevent Turbopack from "walking up" to unrelated lockfiles (e.g. in the user home dir)
    // and incorrectly inferring the workspace root.
    root: process.cwd(),
  },
  transpilePackages: [
    "@solana/wallet-adapter-base",
    "@solana/wallet-adapter-react",
    "@solana/wallet-adapter-react-ui",
    "@solana/wallet-adapter-wallets",
    "@solana/web3.js",
  ],
  typescript: {
    ignoreBuildErrors: true,
  },
};

export default nextConfig;
