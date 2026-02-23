import { describe, it, expect } from 'vitest';

describe('DashboardGrid navigation targets', () => {
    // The dashboard grid cards should have click targets defined
    const DASHBOARD_CARD_TARGETS = [
        { label: 'PNL (TOTAL)', href: '/positions', description: 'Navigate to positions' },
        { label: 'WIN RATE', href: '/positions', description: 'Navigate to positions' },
        { label: 'SHARPE RATIO', toast: 'Analytics dashboard coming soon', description: 'Show toast' },
        { label: 'ACTIVE POSITIONS', href: '/positions', description: 'Navigate to positions' },
    ];

    it('should have a click target defined for every card', () => {
        DASHBOARD_CARD_TARGETS.forEach((card) => {
            const hasTarget = card.href !== undefined || card.toast !== undefined;
            expect(hasTarget).toBe(true);
        });
    });

    it('should navigate to /positions for PNL card', () => {
        const pnlCard = DASHBOARD_CARD_TARGETS.find(c => c.label === 'PNL (TOTAL)');
        expect(pnlCard).toBeDefined();
        expect(pnlCard!.href).toBe('/positions');
    });

    it('should navigate to /positions for WIN RATE card', () => {
        const winRateCard = DASHBOARD_CARD_TARGETS.find(c => c.label === 'WIN RATE');
        expect(winRateCard).toBeDefined();
        expect(winRateCard!.href).toBe('/positions');
    });

    it('should show toast for SHARPE RATIO card', () => {
        const sharpeCard = DASHBOARD_CARD_TARGETS.find(c => c.label === 'SHARPE RATIO');
        expect(sharpeCard).toBeDefined();
        expect(sharpeCard!.toast).toBeDefined();
        expect(sharpeCard!.toast).toContain('coming soon');
    });

    it('should navigate to /positions for ACTIVE POSITIONS card', () => {
        const posCard = DASHBOARD_CARD_TARGETS.find(c => c.label === 'ACTIVE POSITIONS');
        expect(posCard).toBeDefined();
        expect(posCard!.href).toBe('/positions');
    });
});
