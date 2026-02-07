'use client';

import { useState } from 'react';
import { NewsDashboard } from '@/components/features/NewsDashboard';
import { NeuralLattice } from '@/components/visuals/NeuralLattice';
import { getDexterIntelClient, StockAnalysis, SectorAnalysis } from '@/lib/dexter-intel';
import {
    Brain,
    Newspaper,
    TrendingUp,
    TrendingDown,
    BarChart3,
    Building2,
    Coins,
    Gamepad2,
    Sparkles,
    Search,
    Globe,
    Activity,
    AlertTriangle,
    CheckCircle,
    XCircle
} from 'lucide-react';

// Popular sectors to analyze
const SECTORS = ['DeFi', 'NFT', 'Gaming', 'AI', 'Memes', 'Infrastructure'];

// Demo xStocks for analysis
const XSTOCKS = ['AAPL', 'TSLA', 'NVDA', 'MSFT', 'GOOGL', 'AMZN'];

export default function IntelPage() {
    const [selectedSector, setSelectedSector] = useState<string | null>(null);
    const [sectorAnalysis, setSectorAnalysis] = useState<SectorAnalysis | null>(null);
    const [loadingSector, setLoadingSector] = useState(false);

    const [selectedStock, setSelectedStock] = useState<string | null>(null);
    const [stockAnalysis, setStockAnalysis] = useState<StockAnalysis | null>(null);
    const [loadingStock, setLoadingStock] = useState(false);

    // Analyze sector
    const analyzeSector = async (sector: string) => {
        setSelectedSector(sector);
        setLoadingSector(true);
        setSectorAnalysis(null);

        try {
            const client = getDexterIntelClient();
            const analysis = await client.analyzeSector(sector);
            setSectorAnalysis(analysis);
        } catch (error) {
            console.error('Sector analysis failed:', error);
        } finally {
            setLoadingSector(false);
        }
    };

    // Analyze stock
    const analyzeStock = async (symbol: string) => {
        setSelectedStock(symbol);
        setLoadingStock(true);
        setStockAnalysis(null);

        try {
            const client = getDexterIntelClient();
            const analysis = await client.analyzeStock(symbol);
            setStockAnalysis(analysis);
        } catch (error) {
            console.error('Stock analysis failed:', error);
        } finally {
            setLoadingStock(false);
        }
    };

    return (
        <div className="min-h-screen flex flex-col relative overflow-hidden">
            <NeuralLattice />

            <div className="relative z-10 pt-24 pb-12 px-4 max-w-7xl mx-auto w-full">
                {/* Header */}
                <section className="text-center mb-8">
                    <div className="flex items-center justify-center gap-2 mb-2">
                        <Brain className="w-6 h-6 text-accent-neon" />
                        <span className="text-sm text-accent-neon font-mono">DEXTER AI</span>
                    </div>
                    <h1 className="font-display text-4xl md:text-5xl font-bold text-text-primary mb-4">
                        Market Intelligence
                    </h1>
                    <p className="text-text-secondary text-lg max-w-2xl mx-auto">
                        AI-powered market analysis, sector trends, and actionable insights
                    </p>
                </section>

                {/* Main Grid */}
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                    {/* Left Column: Analysis Tools */}
                    <div className="space-y-6">
                        {/* Sector Analysis */}
                        <div className="card-glass p-6">
                            <div className="flex items-center gap-2 mb-4">
                                <BarChart3 className="w-5 h-5 text-accent-neon" />
                                <h3 className="font-display font-bold text-lg text-text-primary">
                                    Sector Analysis
                                </h3>
                            </div>

                            <div className="grid grid-cols-2 gap-2 mb-4">
                                {SECTORS.map(sector => (
                                    <button
                                        key={sector}
                                        onClick={() => analyzeSector(sector)}
                                        className={`
                                            px-3 py-2 rounded-lg text-sm font-mono transition-all
                                            ${selectedSector === sector
                                                ? 'bg-accent-neon/20 text-accent-neon border border-accent-neon/30'
                                                : 'bg-bg-secondary/50 text-text-muted hover:bg-bg-secondary border border-border-primary/30'}
                                        `}
                                    >
                                        {sector}
                                    </button>
                                ))}
                            </div>

                            {/* Sector Result */}
                            {loadingSector ? (
                                <div className="text-center py-4">
                                    <Activity className="w-6 h-6 text-accent-neon animate-pulse mx-auto mb-2" />
                                    <p className="text-xs text-text-muted">Analyzing {selectedSector}...</p>
                                </div>
                            ) : sectorAnalysis ? (
                                <div className="space-y-3">
                                    <div className="flex items-center justify-between">
                                        <span className="font-display font-bold text-text-primary">
                                            {sectorAnalysis.sector}
                                        </span>
                                        <div className="flex items-center gap-2">
                                            <span className={`
                                                text-lg font-mono font-bold
                                                ${sectorAnalysis.score >= 65 ? 'text-accent-success' :
                                                    sectorAnalysis.score >= 45 ? 'text-text-muted' : 'text-accent-danger'}
                                            `}>
                                                {sectorAnalysis.score}
                                            </span>
                                            {sectorAnalysis.trend === 'bullish' ? (
                                                <TrendingUp className="w-4 h-4 text-accent-success" />
                                            ) : sectorAnalysis.trend === 'bearish' ? (
                                                <TrendingDown className="w-4 h-4 text-accent-danger" />
                                            ) : null}
                                        </div>
                                    </div>

                                    <div className="p-3 rounded-lg bg-bg-secondary/30">
                                        <p className="text-xs text-text-muted mb-2">Top Tokens</p>
                                        <div className="flex flex-wrap gap-1">
                                            {sectorAnalysis.topTokens.map(token => (
                                                <span
                                                    key={token}
                                                    className="px-2 py-0.5 rounded-full bg-accent-neon/20 text-accent-neon text-xs font-mono"
                                                >
                                                    {token}
                                                </span>
                                            ))}
                                        </div>
                                    </div>

                                    <div className="space-y-1">
                                        <p className="text-xs text-text-muted">Key Drivers</p>
                                        {sectorAnalysis.keyDrivers.map((driver, i) => (
                                            <p key={i} className="text-xs text-text-secondary flex items-start gap-1">
                                                <CheckCircle className="w-3 h-3 text-accent-success shrink-0 mt-0.5" />
                                                {driver}
                                            </p>
                                        ))}
                                    </div>

                                    <div className="space-y-1">
                                        <p className="text-xs text-text-muted">Risks</p>
                                        {sectorAnalysis.risks.map((risk, i) => (
                                            <p key={i} className="text-xs text-text-secondary flex items-start gap-1">
                                                <AlertTriangle className="w-3 h-3 text-text-muted shrink-0 mt-0.5" />
                                                {risk}
                                            </p>
                                        ))}
                                    </div>
                                </div>
                            ) : (
                                <p className="text-xs text-text-muted text-center py-4">
                                    Select a sector to analyze
                                </p>
                            )}
                        </div>

                        {/* xStock Analysis */}
                        <div className="card-glass p-6">
                            <div className="flex items-center gap-2 mb-4">
                                <Building2 className="w-5 h-5 text-accent-neon" />
                                <h3 className="font-display font-bold text-lg text-text-primary">
                                    xStock Analysis
                                </h3>
                            </div>

                            <div className="grid grid-cols-3 gap-2 mb-4">
                                {XSTOCKS.map(symbol => (
                                    <button
                                        key={symbol}
                                        onClick={() => analyzeStock(symbol)}
                                        className={`
                                            px-3 py-2 rounded-lg text-sm font-mono transition-all
                                            ${selectedStock === symbol
                                                ? 'bg-accent-neon/20 text-accent-neon border border-accent-neon/30'
                                                : 'bg-bg-secondary/50 text-text-muted hover:bg-bg-secondary border border-border-primary/30'}
                                        `}
                                    >
                                        {symbol}
                                    </button>
                                ))}
                            </div>

                            {/* Stock Result */}
                            {loadingStock ? (
                                <div className="text-center py-4">
                                    <Activity className="w-6 h-6 text-accent-neon animate-pulse mx-auto mb-2" />
                                    <p className="text-xs text-text-muted">Analyzing {selectedStock}...</p>
                                </div>
                            ) : stockAnalysis ? (
                                <div className="space-y-3">
                                    <div className="flex items-center justify-between">
                                        <div>
                                            <span className="font-display font-bold text-text-primary">
                                                {stockAnalysis.symbol}
                                            </span>
                                            <p className="text-xs text-text-muted">{stockAnalysis.name}</p>
                                        </div>
                                        <div className="text-right">
                                            <p className="font-mono font-bold text-text-primary">
                                                ${stockAnalysis.priceUsd.toFixed(2)}
                                            </p>
                                            <p className={`text-xs font-mono ${stockAnalysis.change24h >= 0 ? 'text-accent-success' : 'text-accent-danger'}`}>
                                                {stockAnalysis.change24h >= 0 ? '+' : ''}{stockAnalysis.change24h.toFixed(2)}%
                                            </p>
                                        </div>
                                    </div>

                                    {/* Sentiment Gauge */}
                                    <div className="p-3 rounded-lg bg-bg-secondary/30">
                                        <div className="flex justify-between text-xs mb-1">
                                            <span className="text-text-muted">Sentiment</span>
                                            <span className={
                                                stockAnalysis.sentiment >= 65 ? 'text-accent-success' :
                                                    stockAnalysis.sentiment >= 45 ? 'text-text-muted' : 'text-accent-danger'
                                            }>
                                                {stockAnalysis.sentiment}/100
                                            </span>
                                        </div>
                                        <div className="h-2 bg-bg-secondary rounded-full overflow-hidden">
                                            <div
                                                className={`h-full transition-all ${stockAnalysis.sentiment >= 65 ? 'bg-accent-success' :
                                                        stockAnalysis.sentiment >= 45 ? 'bg-accent-warning' : 'bg-accent-danger'
                                                    }`}
                                                style={{ width: `${stockAnalysis.sentiment}%` }}
                                            />
                                        </div>
                                    </div>

                                    {/* Recommendation */}
                                    <div className={`
                                        p-3 rounded-lg text-center font-mono font-bold uppercase
                                        ${stockAnalysis.recommendation === 'strong_buy' ? 'bg-emerald-500/20 text-emerald-400' :
                                            stockAnalysis.recommendation === 'buy' ? 'bg-accent-success/20 text-accent-success' :
                                                stockAnalysis.recommendation === 'hold' ? 'bg-accent-warning/20 text-text-muted' :
                                                    stockAnalysis.recommendation === 'sell' ? 'bg-accent-warning/20 text-accent-warning' :
                                                        'bg-accent-error/20 text-accent-error'}
                                    `}>
                                        {stockAnalysis.recommendation.replace('_', ' ')}
                                    </div>

                                    {/* Key Factors */}
                                    <div className="space-y-1">
                                        <p className="text-xs text-text-muted">Key Factors</p>
                                        {stockAnalysis.keyFactors.slice(0, 3).map((factor, i) => (
                                            <p key={i} className="text-xs text-text-secondary">• {factor}</p>
                                        ))}
                                    </div>
                                </div>
                            ) : (
                                <p className="text-xs text-text-muted text-center py-4">
                                    Select a stock to analyze
                                </p>
                            )}
                        </div>
                    </div>

                    {/* Right Column: News Dashboard */}
                    <div className="lg:col-span-2">
                        <NewsDashboard />
                    </div>
                </div>
            </div>
        </div>
    );
}
