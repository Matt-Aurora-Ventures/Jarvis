/**
 * Bags Intel Feed - Real-time intelligence on bags.fm graduations
 * JARVIS LifeOS
 */

class BagsIntelFeed {
    constructor() {
        this.feed = document.getElementById('feed');
        this.loading = document.getElementById('loading');
        this.emptyState = document.getElementById('empty-state');
        this.trackedCount = document.getElementById('tracked-count');
        this.template = document.getElementById('intel-card-template');

        this.events = [];
        this.filteredEvents = [];
        this.currentFilter = 'all';

        this.init();
    }

    init() {
        this.setupFilters();
        this.loadEvents();
        this.startPolling();
    }

    setupFilters() {
        const filterButtons = document.querySelectorAll('.filter-btn');
        filterButtons.forEach(btn => {
            btn.addEventListener('click', () => {
                filterButtons.forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                this.currentFilter = btn.dataset.filter;
                this.filterAndRender();
            });
        });
    }

    async loadEvents() {
        try {
            // Load from static data.json (updated periodically)
            const response = await fetch('data.json?t=' + Date.now());
            const data = await response.json();

            if (data.success) {
                this.events = data.events || [];
                this.filterAndRender();
                this.updateTrackedCount();
                
                // Update last updated timestamp
                if (data.lastUpdated) {
                    const lastUpdated = new Date(data.lastUpdated);
                    console.log('Data last updated:', lastUpdated.toLocaleString());
                }
            }
        } catch (error) {
            console.error('Failed to load events:', error);
            this.showEmptyState();
        } finally {
            this.hideLoading();
        }
    }

    filterAndRender() {
        // Filter events based on current filter
        if (this.currentFilter === 'all') {
            this.filteredEvents = [...this.events];
        } else {
            this.filteredEvents = this.events.filter(event => {
                const quality = event.scores?.quality?.toLowerCase();
                return quality === this.currentFilter;
            });
        }

        // Render filtered events
        this.renderEvents();
    }

    renderEvents() {
        this.feed.innerHTML = '';

        if (this.filteredEvents.length === 0) {
            this.showEmptyState();
            return;
        }

        this.hideEmptyState();

        this.filteredEvents.forEach(event => {
            const card = this.createCard(event);
            this.feed.appendChild(card);
        });
    }

    createCard(event) {
        const card = this.template.content.cloneNode(true);
        const article = card.querySelector('.intel-card');

        // Token info
        const avatar = card.querySelector('.token-avatar');
        avatar.src = event.token?.image_url || this.generateAvatar(event.token?.symbol);
        avatar.alt = event.token?.name || 'Token';

        card.querySelector('.token-name').textContent = event.token?.name || 'Unknown Token';
        card.querySelector('.token-symbol').textContent = `$${event.token?.symbol || '???'}`;
        card.querySelector('.token-time').textContent = this.formatTime(event.timestamp);

        // Score banner
        const scoreValue = card.querySelector('.score-value');
        scoreValue.textContent = event.scores?.overall || '0';

        const qualityBadge = card.querySelector('.quality-badge');
        qualityBadge.textContent = this.getQualityEmoji(event.scores?.quality);

        const riskBadge = card.querySelector('.risk-badge');
        riskBadge.textContent = event.scores?.risk?.toUpperCase() || 'UNKNOWN';
        riskBadge.classList.add(event.scores?.risk?.toLowerCase() || 'medium');

        // AI summary
        const aiText = card.querySelector('.ai-text');
        if (event.ai_analysis?.summary) {
            aiText.textContent = event.ai_analysis.summary;
        } else {
            aiText.textContent = 'AI analysis pending...';
        }

        // Metrics
        card.querySelector('.mcap-value').textContent = this.formatCurrency(event.market?.mcap_usd);
        card.querySelector('.liq-value').textContent = this.formatCurrency(event.market?.liquidity_usd);
        card.querySelector('.duration-value').textContent = this.formatDuration(event.bonding_curve?.duration_seconds);
        card.querySelector('.buyers-value').textContent = this.formatNumber(event.bonding_curve?.unique_buyers);

        // Score bars
        this.setScoreBar(card, 'bonding', event.scores?.bonding || 0);
        this.setScoreBar(card, 'creator', event.scores?.creator || 0);
        this.setScoreBar(card, 'social', event.scores?.social || 0);
        this.setScoreBar(card, 'market', event.scores?.market || 0);

        // Flags
        const greenFlagsList = card.querySelector('.green-flags-list');
        const redFlagsList = card.querySelector('.red-flags-list');

        greenFlagsList.innerHTML = '';
        redFlagsList.innerHTML = '';

        (event.flags?.green || []).slice(0, 5).forEach(flag => {
            const li = document.createElement('li');
            li.textContent = flag;
            greenFlagsList.appendChild(li);
        });

        (event.flags?.red || []).slice(0, 5).forEach(flag => {
            const li = document.createElement('li');
            li.textContent = flag;
            redFlagsList.appendChild(li);
        });

        // Links
        const mint = event.token?.mint;
        card.querySelector('.bags-link').href = `https://bags.fm/token/${mint}`;
        card.querySelector('.dex-link').href = `https://dexscreener.com/solana/${mint}`;

        const copyLink = card.querySelector('.copy-link');
        copyLink.addEventListener('click', (e) => {
            e.preventDefault();
            this.copyToClipboard(mint);
        });

        // Add animation
        article.style.opacity = '0';
        article.style.transform = 'translateY(20px)';

        setTimeout(() => {
            article.style.transition = 'all 0.4s ease';
            article.style.opacity = '1';
            article.style.transform = 'translateY(0)';
        }, 50);

        return card;
    }

    setScoreBar(card, name, value) {
        const fill = card.querySelector(`.${name}-score`);
        const valueSpan = card.querySelector(`.${name}-score-value`);

        fill.style.width = `${value}%`;
        valueSpan.textContent = Math.round(value);
    }

    getQualityEmoji(quality) {
        const map = {
            'exceptional': '🌟',
            'strong': '✅',
            'average': '➖',
            'weak': '⚠️',
            'poor': '🚨'
        };
        return map[quality?.toLowerCase()] || '❓';
    }

    formatCurrency(value) {
        if (!value) return '$0';
        if (value >= 1e6) return `$${(value / 1e6).toFixed(2)}M`;
        if (value >= 1e3) return `$${(value / 1e3).toFixed(1)}K`;
        return `$${value.toFixed(0)}`;
    }

    formatNumber(value) {
        if (!value) return '0';
        if (value >= 1e6) return `${(value / 1e6).toFixed(2)}M`;
        if (value >= 1e3) return `${(value / 1e3).toFixed(1)}K`;
        return value.toString();
    }

    formatDuration(seconds) {
        if (!seconds) return '0m';
        const hours = Math.floor(seconds / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);

        if (hours > 0) return `${hours}h ${minutes}m`;
        return `${minutes}m`;
    }

    formatTime(timestamp) {
        if (!timestamp) return 'now';

        const date = new Date(timestamp);
        const now = new Date();
        const diffMs = now - date;
        const diffMins = Math.floor(diffMs / 60000);
        const diffHours = Math.floor(diffMs / 3600000);
        const diffDays = Math.floor(diffMs / 86400000);

        if (diffMins < 1) return 'now';
        if (diffMins < 60) return `${diffMins}m`;
        if (diffHours < 24) return `${diffHours}h`;
        return `${diffDays}d`;
    }

    generateAvatar(symbol) {
        // Generate a placeholder gradient avatar
        const colors = [
            ['#39FF14', '#20D080'],
            ['#BB86FC', '#8A2BE2'],
            ['#FFB02E', '#FF8C00'],
            ['#00D4FF', '#0080FF']
        ];

        const index = (symbol?.charCodeAt(0) || 0) % colors.length;
        const [color1, color2] = colors[index];

        return `data:image/svg+xml,${encodeURIComponent(`
            <svg width="48" height="48" xmlns="http://www.w3.org/2000/svg">
                <defs>
                    <linearGradient id="grad" x1="0%" y1="0%" x2="100%" y2="100%">
                        <stop offset="0%" style="stop-color:${color1};stop-opacity:1" />
                        <stop offset="100%" style="stop-color:${color2};stop-opacity:1" />
                    </linearGradient>
                </defs>
                <circle cx="24" cy="24" r="24" fill="url(#grad)" />
                <text x="24" y="32" font-family="Arial" font-size="20" font-weight="bold"
                      fill="white" text-anchor="middle">${(symbol || '?')[0].toUpperCase()}</text>
            </svg>
        `)}`;
    }

    copyToClipboard(text) {
        navigator.clipboard.writeText(text).then(() => {
            // Show temporary feedback
            const notification = document.createElement('div');
            notification.textContent = 'Contract address copied!';
            notification.style.cssText = `
                position: fixed;
                bottom: 20px;
                right: 20px;
                background: rgba(57, 255, 20, 0.9);
                color: #0B0C0D;
                padding: 12px 24px;
                border-radius: 8px;
                font-weight: 600;
                z-index: 1000;
                animation: slideIn 0.3s ease;
            `;
            document.body.appendChild(notification);

            setTimeout(() => {
                notification.style.animation = 'slideOut 0.3s ease';
                setTimeout(() => notification.remove(), 300);
            }, 2000);
        });
    }

    updateTrackedCount() {
        this.trackedCount.textContent = this.events.length;
    }

    showEmptyState() {
        this.emptyState.style.display = 'block';
        this.feed.style.display = 'none';
    }

    hideEmptyState() {
        this.emptyState.style.display = 'none';
        this.feed.style.display = 'flex';
    }

    hideLoading() {
        this.loading.style.display = 'none';
    }

    startPolling() {
        // Poll for new events every 30 seconds
        setInterval(() => {
            this.loadEvents();
        }, 30000);
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    new BagsIntelFeed();
});

// Add CSS animations
const style = document.createElement('style');
style.textContent = `
    @keyframes slideIn {
        from {
            transform: translateX(100%);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }

    @keyframes slideOut {
        from {
            transform: translateX(0);
            opacity: 1;
        }
        to {
            transform: translateX(100%);
            opacity: 0;
        }
    }
`;
document.head.appendChild(style);
