import { NextResponse } from 'next/server';

const SNIPER_API = process.env.SNIPER_API_URL || 'http://localhost:3002';

export async function GET() {
  try {
    const resp = await fetch(`${SNIPER_API}/api/backtest`, {
      signal: AbortSignal.timeout(5000),
      cache: 'no-store',
    });

    if (!resp.ok) throw new Error(`Backend returned ${resp.status}`);

    const data = await resp.json();
    return NextResponse.json(data);
  } catch {
    // Fallback: read directly from winning/ directory
    const fs = await import('fs');
    const path = await import('path');
    const winningDir = path.resolve(process.cwd(), '..', 'winning');

    let bestEver = null;
    let bestConfig = null;
    const agents: Record<string, unknown[]> = {};

    try {
      const bestPath = path.join(winningDir, 'BEST_EVER.json');
      if (fs.existsSync(bestPath)) {
        bestEver = JSON.parse(fs.readFileSync(bestPath, 'utf8'));
      }
    } catch { /* ignore */ }

    try {
      const cfgPath = path.join(winningDir, 'best-config.json');
      if (fs.existsSync(cfgPath)) {
        bestConfig = JSON.parse(fs.readFileSync(cfgPath, 'utf8'));
      }
    } catch { /* ignore */ }

    try {
      const files = fs.readdirSync(winningDir).filter((f: string) => f.startsWith('continuous-run-log'));
      for (const file of files) {
        const agentId = file.replace('continuous-run-log-', '').replace('.json', '');
        try {
          agents[agentId || 'default'] = JSON.parse(fs.readFileSync(path.join(winningDir, file), 'utf8'));
        } catch { /* ignore */ }
      }
    } catch { /* ignore */ }

    return NextResponse.json({
      bestEver,
      bestConfig,
      agents,
      summary: {
        totalIterations: Object.values(agents).flat().length,
        activeAgents: Object.keys(agents).length,
        source: 'filesystem-fallback',
      },
    });
  }
}
