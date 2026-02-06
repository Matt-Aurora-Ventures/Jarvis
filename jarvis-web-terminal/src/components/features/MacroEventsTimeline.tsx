'use client';

/**
 * Macro Events Timeline
 * 
 * Displays short/medium/long term market outlook
 * with key upcoming events.
 */

import { MacroAnalysis } from '@/types/sentiment-types';
import { Clock, Calendar, TrendingUp, AlertCircle } from 'lucide-react';

interface MacroEventsTimelineProps {
    macro: MacroAnalysis;
    isLoading?: boolean;
}

export function MacroEventsTimeline({ macro, isLoading }: MacroEventsTimelineProps) {
    if (isLoading) {
        return (
            <div className="sentiment-panel">
                <div className="sentiment-panel-header">
                    <Calendar className="w-5 h-5 text-accent-primary" />
                    <h3>Macro Outlook</h3>
                </div>
                <div className="animate-pulse text-text-muted text-center py-8">
                    Loading macro analysis...
                </div>
            </div>
        );
    }

    const timeframes = [
        { label: '24h', title: 'Short Term', content: macro.shortTerm, icon: Clock, color: 'text-blue-400', bg: 'bg-blue-500/10' },
        { label: '3d', title: 'Medium Term', content: macro.mediumTerm, icon: TrendingUp, color: 'text-purple-400', bg: 'bg-purple-500/10' },
        { label: '1w+', title: 'Long Term', content: macro.longTerm, icon: Calendar, color: 'text-amber-400', bg: 'bg-amber-500/10' },
    ];

    return (
        <div className="sentiment-panel">
            <div className="sentiment-panel-header">
                <Calendar className="w-5 h-5 text-purple-400" />
                <h3>📊 Macro Outlook</h3>
            </div>

            {/* Timeframe Cards */}
            <div className="space-y-3 mb-4">
                {timeframes.map((tf) => (
                    <div
                        key={tf.label}
                        className={`p-3 rounded-lg ${tf.bg} border border-white/5`}
                    >
                        <div className="flex items-center gap-2 mb-2">
                            <tf.icon className={`w-4 h-4 ${tf.color}`} />
                            <span className={`text-sm font-medium ${tf.color}`}>{tf.title}</span>
                            <span className="text-xs text-text-muted ml-auto">{tf.label}</span>
                        </div>
                        <p className="text-sm text-text-secondary leading-relaxed">
                            {tf.content || 'Analysis pending...'}
                        </p>
                    </div>
                ))}
            </div>

            {/* Key Events */}
            {macro.keyEvents.length > 0 && (
                <div>
                    <div className="flex items-center gap-2 mb-2">
                        <AlertCircle className="w-4 h-4 text-yellow-400" />
                        <span className="text-sm font-medium text-text-primary">Key Events</span>
                    </div>
                    <div className="flex flex-wrap gap-2">
                        {macro.keyEvents.map((event, i) => (
                            <span
                                key={i}
                                className="px-2 py-1 text-xs rounded bg-bg-tertiary text-text-secondary border border-white/5"
                            >
                                {event}
                            </span>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
}
