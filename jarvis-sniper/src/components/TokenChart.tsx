'use client';

import { X, Maximize2, Minimize2, ExternalLink, BarChart3, RefreshCw, GripHorizontal, Copy, Check, Loader2 } from 'lucide-react';
import { useState, useMemo, useCallback, useRef, useEffect } from 'react';
import { useSniperStore } from '@/stores/useSniperStore';

type ChartProvider = 'birdeye' | 'dexscreener' | 'geckoterminal';

function getChartUrl(mint: string, provider: ChartProvider): string {
  switch (provider) {
    case 'birdeye':
      return `https://birdeye.so/tv-widget/${mint}?chain=solana&viewMode=pair&chartInterval=15&chartType=CANDLE&chartLeftToolbar=show&theme=dark`;
    case 'dexscreener':
      return `https://dexscreener.com/solana/${mint}?embed=1&theme=dark&trades=0&info=0`;
    case 'geckoterminal':
      return `https://www.geckoterminal.com/solana/tokens/${mint}?embed=1&info=0&swaps=0`;
  }
}

const PROVIDERS: { id: ChartProvider; label: string }[] = [
  { id: 'birdeye', label: 'Birdeye' },
  { id: 'dexscreener', label: 'DexScreener' },
  { id: 'geckoterminal', label: 'Gecko' },
];

const MIN_HEIGHT = 200;
const MAX_HEIGHT = 800;
const DEFAULT_HEIGHT = 420;

export function TokenChart() {
  const { selectedMint, setSelectedMint, graduations, positions } = useSniperStore();
  const [expanded, setExpanded] = useState(false);
  const [provider, setProvider] = useState<ChartProvider>('dexscreener');
  const [iframeKey, setIframeKey] = useState(0);
  const [height, setHeight] = useState(DEFAULT_HEIGHT);
  const [isDragging, setIsDragging] = useState(false);
  const [mintCopied, setMintCopied] = useState(false);
  const [chartLoading, setChartLoading] = useState(true);
  const containerRef = useRef<HTMLDivElement>(null);
  const startY = useRef(0);
  const startHeight = useRef(0);

  // Resolve symbol from graduations or positions
  const grad = graduations.find(g => g.mint === selectedMint);
  const pos = positions.find(p => p.mint === selectedMint);
  const symbol = grad?.symbol || pos?.symbol || (selectedMint ? selectedMint.slice(0, 6) : '');

  const embedUrl = useMemo(
    () => selectedMint ? getChartUrl(selectedMint, provider) : null,
    [selectedMint, provider]
  );

  // Reset loading spinner whenever the chart source changes
  useEffect(() => {
    setChartLoading(true);
  }, [selectedMint, provider, iframeKey]);

  const handleDragStart = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    setIsDragging(true);
    startY.current = e.clientY;
    startHeight.current = height;

    const handleDragMove = (moveEvent: MouseEvent) => {
      const delta = moveEvent.clientY - startY.current;
      const newHeight = Math.min(MAX_HEIGHT, Math.max(MIN_HEIGHT, startHeight.current + delta));
      setHeight(newHeight);
    };

    const handleDragEnd = () => {
      setIsDragging(false);
      document.removeEventListener('mousemove', handleDragMove);
      document.removeEventListener('mouseup', handleDragEnd);
    };

    document.addEventListener('mousemove', handleDragMove);
    document.addEventListener('mouseup', handleDragEnd);
  }, [height]);

  // Empty state when no token selected
  if (!selectedMint) {
    return (
      <div className="card-glass flex flex-col items-center justify-center py-10 gap-3">
        <div className="w-12 h-12 rounded-xl bg-bg-tertiary flex items-center justify-center">
          <BarChart3 className="w-6 h-6 text-text-muted" />
        </div>
        <div className="text-center">
          <p className="text-xs font-medium text-text-muted">No token selected</p>
          <p className="text-[10px] text-text-muted/60 mt-1">Click a token in the Scanner or a Position to view its chart</p>
        </div>
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      className={`card-glass overflow-hidden flex flex-col ${
        expanded ? 'fixed inset-4 z-[100]' : ''
      }`}
      style={expanded ? undefined : { height: `${height}px` }}
    >
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-border-primary bg-bg-secondary/60">
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-accent-neon sniper-dot" />
          <span className="text-sm font-bold text-text-primary">{symbol}</span>
          <button
            onClick={async () => {
              try { await navigator.clipboard.writeText(selectedMint); setMintCopied(true); setTimeout(() => setMintCopied(false), 1500); } catch {}
            }}
            className="flex items-center gap-1 text-[10px] font-mono text-text-muted hover:text-text-primary transition-colors group/mint"
            title="Click to copy contract address"
          >
            {mintCopied ? <Check className="w-3 h-3 text-accent-neon" /> : <Copy className="w-3 h-3 opacity-40 group-hover/mint:opacity-100 transition-opacity" />}
            <span className={mintCopied ? 'text-accent-neon' : ''}>{mintCopied ? 'Copied!' : selectedMint}</span>
          </button>
        </div>
        <div className="flex items-center gap-1.5">
          {/* Chart provider switcher */}
          <div className="flex items-center bg-bg-tertiary rounded-lg overflow-hidden">
            {PROVIDERS.map((p) => (
              <button
                key={p.id}
                onClick={() => setProvider(p.id)}
                className={`px-2 py-1 text-[9px] font-medium transition-colors ${
                  provider === p.id
                    ? 'bg-accent-neon/20 text-accent-neon'
                    : 'text-text-muted hover:text-text-primary'
                }`}
              >
                {p.label}
              </button>
            ))}
          </div>
          <button
            onClick={() => setIframeKey(k => k + 1)}
            className="w-7 h-7 rounded-lg flex items-center justify-center bg-bg-tertiary text-text-muted hover:text-text-primary hover:bg-bg-tertiary/80 transition-colors"
            title="Reload chart"
          >
            <RefreshCw className="w-3.5 h-3.5" />
          </button>
          <a
            href={`https://dexscreener.com/solana/${selectedMint}`}
            target="_blank"
            rel="noopener noreferrer"
            className="w-7 h-7 rounded-lg flex items-center justify-center bg-bg-tertiary text-text-muted hover:text-text-primary hover:bg-bg-tertiary/80 transition-colors"
            title="Open in DexScreener"
          >
            <ExternalLink className="w-3.5 h-3.5" />
          </a>
          <button
            onClick={() => setExpanded(!expanded)}
            className="w-7 h-7 rounded-lg flex items-center justify-center bg-bg-tertiary text-text-muted hover:text-text-primary hover:bg-bg-tertiary/80 transition-colors"
            title={expanded ? 'Minimize' : 'Maximize'}
          >
            {expanded ? <Minimize2 className="w-3.5 h-3.5" /> : <Maximize2 className="w-3.5 h-3.5" />}
          </button>
          <button
            onClick={() => { setSelectedMint(null); setExpanded(false); }}
            className="w-7 h-7 rounded-lg flex items-center justify-center bg-bg-tertiary text-text-muted hover:text-accent-error hover:bg-accent-error/10 transition-colors"
            title="Close chart"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Chart iframe */}
      <div className="flex-1 relative bg-black">
        {chartLoading && (
          <div className="absolute inset-0 z-10 flex flex-col items-center justify-center bg-black/80 backdrop-blur-sm gap-3">
            <Loader2 className="w-6 h-6 text-accent-neon animate-spin" />
            <span className="text-[11px] font-mono text-text-muted">Loading chart...</span>
          </div>
        )}
        <iframe
          key={`${selectedMint}-${provider}-${iframeKey}`}
          src={embedUrl!}
          className="absolute inset-0 w-full h-full border-0"
          style={isDragging ? { pointerEvents: 'none' } : undefined}
          title={`${symbol} chart`}
          allow="clipboard-write"
          loading="lazy"
          onLoad={() => setChartLoading(false)}
        />
      </div>

      {/* Drag-to-resize handle */}
      {!expanded && (
        <div
          onMouseDown={handleDragStart}
          className="h-3 flex items-center justify-center cursor-ns-resize bg-bg-secondary/80 border-t border-border-primary hover:bg-accent-neon/10 transition-colors group"
        >
          <GripHorizontal className="w-4 h-3 text-text-muted/40 group-hover:text-accent-neon/60" />
        </div>
      )}
    </div>
  );
}
