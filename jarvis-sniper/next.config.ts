import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: 'standalone',
  reactStrictMode: true,
  turbopack: {
    root: __dirname,
  },
  async headers() {
    return [
      {
        source: '/:path*',
        headers: [
          { key: 'X-Frame-Options', value: 'DENY' },
          { key: 'X-Content-Type-Options', value: 'nosniff' },
          { key: 'X-XSS-Protection', value: '1; mode=block' },
          { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
          { key: 'Permissions-Policy', value: 'camera=(), microphone=(), geolocation=()' },
          {
            key: 'Content-Security-Policy',
            value: "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval' blob:; worker-src 'self' blob:; style-src 'self' 'unsafe-inline' https://api.fontshare.com; font-src 'self' https://api.fontshare.com https://cdn.fontshare.com; img-src 'self' data: blob: https: https://raw.githubusercontent.com https://arweave.net https://ipfs.io https://*.dexscreener.com; connect-src 'self' ws: wss: https://*.a.run.app https://api.mainnet-beta.solana.com https://*.helius-rpc.com https://*.jito.wtf https://api.dexscreener.com https://api.geckoterminal.com https://api.coingecko.com https://bags.fm https://*.bags.fm https://pro-api.solscan.io https://scanner.tradingview.com; frame-src https://birdeye.so https://dexscreener.com https://www.geckoterminal.com; object-src 'none'; base-uri 'self'; form-action 'self'",
          },
          { key: 'Strict-Transport-Security', value: 'max-age=31536000; includeSubDomains' },
        ],
      },
      {
        source: '/api/:path*',
        headers: [
          { key: 'X-RateLimit-Policy', value: 'sliding-window' },
        ],
      },
    ];
  },
};

export default nextConfig;
