import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: 'standalone',
  reactStrictMode: true,
  experimental: {
    // Next 16 enables isolated dev builds by default. On Windows (especially under OneDrive),
    // this can generate types/build artifacts in temp folders where module resolution breaks.
    isolatedDevBuild: false,
  },
  turbopack: {
    root: __dirname,
  },
  webpack: (config, { dev }) => {
    // Keep dev server stable while running Playwright smoke tests (screenshots/logs land in .jarvis-cache).
    if (dev) {
      const watchOptions = config.watchOptions || {};
      const base = watchOptions.ignored;
      const nextIgnored: string[] = ['**/.next/**', '**/node_modules/**'];

      const pushString = (v: unknown) => {
        if (typeof v !== 'string') return;
        const s = v.trim();
        if (!s) return;
        nextIgnored.push(s);
      };

      if (Array.isArray(base)) {
        for (const it of base) pushString(it);
      } else {
        pushString(base);
      }

      nextIgnored.push('**/.jarvis-cache/**', '**/.planning/**', '**/.firebase/**', '**/debug/**');

      // De-dupe while preserving order.
      const deduped: string[] = [];
      const seen = new Set<string>();
      for (const it of nextIgnored) {
        if (seen.has(it)) continue;
        seen.add(it);
        deduped.push(it);
      }

      config.watchOptions = { ...watchOptions, ignored: deduped };
    }
    return config;
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
            value: "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval' blob:; worker-src 'self' blob:; style-src 'self' 'unsafe-inline' https://api.fontshare.com; font-src 'self' https://api.fontshare.com https://cdn.fontshare.com; img-src 'self' data: blob: https: https://raw.githubusercontent.com https://arweave.net https://ipfs.io https://*.dexscreener.com; connect-src 'self' ws: wss: https://api.mainnet-beta.solana.com https://*.helius-rpc.com https://*.jito.wtf https://api.dexscreener.com https://api.geckoterminal.com https://api.coingecko.com https://bags.fm https://*.bags.fm https://pro-api.solscan.io https://scanner.tradingview.com; frame-src https://birdeye.so https://dexscreener.com https://www.geckoterminal.com; object-src 'none'; base-uri 'self'; form-action 'self'",
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
