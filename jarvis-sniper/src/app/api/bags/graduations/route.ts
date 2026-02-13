import { NextResponse } from 'next/server';
import { fetchGraduations } from '@/lib/bags-api';

/**
 * Bags.fm Graduations API — powered by Jupiter Gems
 *
 * Returns 200+ bags.fm tokens scored by the KR8TIV 5-dimension system.
 * Data comes from Jupiter Gems API (POST datapi.jup.ag/v1/pools/gems)
 * filtered to bags.fun launchpad only.
 *
 * Caching is handled in bags-api.ts (45s TTL).
 */

export async function GET() {
  try {
    const tokens = await fetchGraduations(200);
    return NextResponse.json(
      { graduations: tokens },
      {
        headers: {
          'Cache-Control': 'public, s-maxage=30, stale-while-revalidate=60',
        },
      },
    );
  } catch (err) {
    console.error('[BagsGraduations] Error:', err);
    return NextResponse.json({ graduations: [] });
  }
}
