/**
 * Quick Actions Component - Fast Trading Shortcuts
 * Beautiful button grid for instant trades
 */
import React, { useState } from 'react';
import { Zap, Search, TrendingUp, Star, Sparkles, Target } from 'lucide-react';
import clsx from 'clsx';

interface QuickAction {
  id: string;
  icon: React.ReactNode;
  label: string;
  description: string;
  color: string;
  action: () => void;
}

export const QuickActions: React.FC = () => {
  const [selectedAction, setSelectedAction] = useState<string | null>(null);

  const actions: QuickAction[] = [
    {
      id: 'insta-snipe',
      icon: <Zap size={24} />,
      label: 'Insta Snipe',
      description: 'One-click trade on trending token',
      color: 'accent',
      action: () => handleAction('insta-snipe'),
    },
    {
      id: 'token-search',
      icon: <Search size={24} />,
      label: 'Token Search',
      description: 'Search and analyze any token',
      color: 'info',
      action: () => handleAction('token-search'),
    },
    {
      id: 'trending',
      icon: <TrendingUp size={24} />,
      label: 'Trending',
      description: 'View top trending tokens',
      color: 'success',
      action: () => handleAction('trending'),
    },
    {
      id: 'ai-picks',
      icon: <Sparkles size={24} />,
      label: 'AI Picks',
      description: 'AI-recommended tokens',
      color: 'warning',
      action: () => handleAction('ai-picks'),
    },
    {
      id: 'watchlist',
      icon: <Star size={24} />,
      label: 'Watchlist',
      description: 'Your saved tokens',
      color: 'primary',
      action: () => handleAction('watchlist'),
    },
    {
      id: 'quick-trade',
      icon: <Target size={24} />,
      label: 'Quick Trade',
      description: 'Fast buy/sell panel',
      color: 'accent',
      action: () => handleAction('quick-trade'),
    },
  ];

  const handleAction = (actionId: string) => {
    setSelectedAction(actionId);
    // TODO: Navigate to appropriate component or open modal
    console.log(`Action triggered: ${actionId}`);

    // Reset selection after animation
    setTimeout(() => setSelectedAction(null), 300);
  };

  const getColorClass = (color: string) => {
    const colorMap: Record<string, string> = {
      accent: 'bg-accent/20 hover:bg-accent/30 border-accent/30 text-accent',
      info: 'bg-info/20 hover:bg-info/30 border-info/30 text-info',
      success: 'bg-success/20 hover:bg-success/30 border-success/30 text-success',
      warning: 'bg-warning/20 hover:bg-warning/30 border-warning/30 text-warning',
      primary: 'bg-primary/20 hover:bg-primary/30 border-primary/30 text-primary',
    };
    return colorMap[color] || colorMap.accent;
  };

  return (
    <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
      {actions.map((action) => (
        <button
          key={action.id}
          onClick={action.action}
          className={clsx(
            'p-4 rounded-xl border transition-all duration-300',
            'hover:scale-105 hover:shadow-lg',
            'active:scale-95',
            getColorClass(action.color),
            selectedAction === action.id && 'scale-95'
          )}
        >
          <div className="flex flex-col items-center text-center gap-2">
            <div className="p-3 rounded-lg bg-bg-dark/50">
              {action.icon}
            </div>
            <div>
              <p className="font-semibold mb-1">
                {action.label}
              </p>
              <p className="text-xs text-muted">
                {action.description}
              </p>
            </div>
          </div>
        </button>
      ))}
    </div>
  );
};
