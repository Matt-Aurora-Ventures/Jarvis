'use client';

import { useState, useEffect, useCallback, createContext, useContext, ReactNode } from 'react';
import { Check, X, AlertTriangle, Info, ExternalLink } from 'lucide-react';

type ToastType = 'success' | 'error' | 'warning' | 'info';

interface Toast {
    id: string;
    type: ToastType;
    message: string;
    txHash?: string;
    duration?: number;
}

interface ToastContextType {
    toast: (type: ToastType, message: string, options?: { txHash?: string; duration?: number }) => void;
    success: (message: string, txHash?: string) => void;
    error: (message: string) => void;
    warning: (message: string) => void;
    info: (message: string) => void;
}

const ToastContext = createContext<ToastContextType | null>(null);

const ICONS: Record<ToastType, React.ReactNode> = {
    success: <Check className="w-4 h-4" />,
    error: <X className="w-4 h-4" />,
    warning: <AlertTriangle className="w-4 h-4" />,
    info: <Info className="w-4 h-4" />,
};

const COLORS: Record<ToastType, string> = {
    success: 'border-green-500/50 bg-green-500/10 text-green-400',
    error: 'border-red-500/50 bg-red-500/10 text-red-400',
    warning: 'border-yellow-500/50 bg-yellow-500/10 text-yellow-400',
    info: 'border-blue-500/50 bg-blue-500/10 text-blue-400',
};

const ICON_BG: Record<ToastType, string> = {
    success: 'bg-green-500/20',
    error: 'bg-red-500/20',
    warning: 'bg-yellow-500/20',
    info: 'bg-blue-500/20',
};

function ToastItem({ toast, onDismiss }: { toast: Toast; onDismiss: (id: string) => void }) {
    const [exiting, setExiting] = useState(false);

    useEffect(() => {
        const duration = toast.duration || (toast.type === 'error' ? 6000 : 4000);
        const timer = setTimeout(() => {
            setExiting(true);
            setTimeout(() => onDismiss(toast.id), 300);
        }, duration);
        return () => clearTimeout(timer);
    }, [toast, onDismiss]);

    return (
        <div
            className={`
                flex items-start gap-3 px-4 py-3 rounded-lg border backdrop-blur-md
                shadow-lg shadow-black/20 max-w-sm w-full
                transition-all duration-300 ease-out
                ${COLORS[toast.type]}
                ${exiting ? 'opacity-0 translate-x-8' : 'opacity-100 translate-x-0'}
            `}
        >
            <div className={`p-1 rounded ${ICON_BG[toast.type]} flex-shrink-0 mt-0.5`}>
                {ICONS[toast.type]}
            </div>
            <div className="flex-1 min-w-0">
                <p className="text-sm font-medium leading-tight">{toast.message}</p>
                {toast.txHash && (
                    <a
                        href={`https://solscan.io/tx/${toast.txHash}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-xs text-accent-neon hover:underline flex items-center gap-1 mt-1"
                    >
                        View on Solscan <ExternalLink className="w-3 h-3" />
                    </a>
                )}
            </div>
            <button
                onClick={() => {
                    setExiting(true);
                    setTimeout(() => onDismiss(toast.id), 300);
                }}
                className="text-text-muted hover:text-text-primary transition-colors flex-shrink-0"
            >
                <X className="w-3.5 h-3.5" />
            </button>
        </div>
    );
}

export function ToastProvider({ children }: { children: ReactNode }) {
    const [toasts, setToasts] = useState<Toast[]>([]);

    const dismiss = useCallback((id: string) => {
        setToasts(prev => prev.filter(t => t.id !== id));
    }, []);

    const addToast = useCallback((type: ToastType, message: string, options?: { txHash?: string; duration?: number }) => {
        const id = `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
        setToasts(prev => [...prev, { id, type, message, ...options }]);
    }, []);

    const contextValue: ToastContextType = {
        toast: addToast,
        success: (message, txHash?) => addToast('success', message, { txHash }),
        error: (message) => addToast('error', message),
        warning: (message) => addToast('warning', message),
        info: (message) => addToast('info', message),
    };

    return (
        <ToastContext.Provider value={contextValue}>
            {children}
            {/* Toast Container */}
            <div className="fixed top-4 right-4 z-[9999] flex flex-col gap-2 pointer-events-none">
                {toasts.map(t => (
                    <div key={t.id} className="pointer-events-auto">
                        <ToastItem toast={t} onDismiss={dismiss} />
                    </div>
                ))}
            </div>
        </ToastContext.Provider>
    );
}

export function useToast(): ToastContextType {
    const context = useContext(ToastContext);
    if (!context) throw new Error('useToast must be used within a ToastProvider');
    return context;
}
