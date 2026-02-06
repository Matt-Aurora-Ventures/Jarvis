'use client';

/**
 * xStocks Panel
 * 
 * Displays tokenized stocks from backed.fi with direction indicators.
 */

import { StockPick } from '@/types/sentiment-types';
import { LineChart, TrendingUp, TrendingDown, ExternalLink } from 'lucide-react';

interface xStocksPanelProps {
    stocks: StockPick[];
    isLoading?: boolean;
}

export function xStocksPanel({ stocks, isLoading }: xStocksPanelProps) {
    if (isLoading) {
        return (
            <div className="sentiment-panel">
                <div className="sentiment-panel-header">
                    <LineChart className="w-5 h-5 text-accent-primary" />
                    <h3>xStocks</h3>
                </div>
                <div className="animate-pulse text-text-muted text-center py-6">
                    Loading stocks...
                </div>
            </div>
        );
    }

    return (
        <div className="sentiment-panel">
            <div className="sentiment-panel-header">
                <LineChart className="w-5 h-5 text-blue-400" />
                <h3>📈 Tokenized Stocks</h3>
                <a
                    href="https://backed.fi"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="ml-auto flex items-center gap-1 text-xs text-text-muted hover:text-accent-primary transition-colors"
                >
                    backed.fi <ExternalLink className="w-3 h-3" />
                </a>
            </div>

            <div className="space-y-2">
                {stocks.map((stock, i) => (
                    <div
                        key={stock.ticker}
                        className="flex items-center gap-3 p-3 rounded-lg bg-bg-secondary/50 border border-white/5 hover:border-white/10 transition-all"
                    >
                        {/* Direction Icon */}
                        <div className={`p-2 rounded-lg ${stock.direction === 'LONG' ? 'bg-emerald-500/20' : 'bg-red-500/20'}`}>
                            {stock.direction === 'LONG'
                                ? <TrendingUp className="w-4 h-4 text-emerald-400" />
                                : <TrendingDown className="w-4 h-4 text-red-400" />
                            }
                        </div>

                        {/* Stock Info */}
                        <div className="flex-1">
                            <div className="flex items-center gap-2">
                                <span className="font-semibold text-text-primary">{stock.ticker}</span>
                                <span className={`px-1.5 py-0.5 text-xs rounded ${stock.direction === 'LONG' ? 'bg-emerald-500/20 text-emerald-400' : 'bg-red-500/20 text-red-400'}`}>
                                    {stock.direction}
                                </span>
                            </div>
                            <div className="text-xs text-text-muted">{stock.underlying}</div>
                        </div>

                        {/* Targets */}
                        <div className="text-right">
                            <div className="text-xs text-emerald-400">TP: {stock.target}</div>
                            <div className="text-xs text-red-400">SL: {stock.stopLoss}</div>
                        </div>
                    </div>
                ))}

                {stocks.length === 0 && (
                    <div className="text-center text-text-muted py-6">
                        No stock picks available
                    </div>
                )}
            </div>
        </div>
    );
}
