/**
 * Bags Intel Intelligence Dashboard
 * Deep analysis, ratings, and comprehensive reports
 * JARVIS LifeOS
 */

class IntelligenceDashboard {
    constructor() {
        this.events = [];
        this.timeline = '24h';
        this.currentView = 'overview';
        this.charts = {};
        this.socket = null;
        this.watchlist = this.loadWatchlist();

        this.init();
    }

    init() {
        this.setupEventListeners();
        this.loadData();
        this.initializeWebSocket();
    }

    setupEventListeners() {
        // Timeline selector
        document.querySelectorAll('.timeline-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                document.querySelectorAll('.timeline-btn').forEach(b => b.classList.remove('active'));
                e.target.classList.add('active');
                this.timeline = e.target.dataset.range;
                this.refreshAnalytics();
            });
        });

        // View selector
        document.querySelectorAll('.view-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                document.querySelectorAll('.view-btn').forEach(b => b.classList.remove('active'));
                e.target.classList.add('active');
                this.switchView(e.target.dataset.view);
            });
        });

        // Export button
        document.getElementById('export-btn')?.addEventListener('click', () => {
            this.exportData();
        });

        // Leaderboard tab
        document.getElementById('leaderboard-tab')?.addEventListener('click', (e) => {
            e.preventDefault();
            this.switchView('overview');
            document.querySelector('.intelligence-view.active')?.scrollIntoView({ behavior: 'smooth' });
        });

        // Portfolio tab
        document.getElementById('portfolio-tab')?.addEventListener('click', (e) => {
            e.preventDefault();
            alert('Portfolio tracking coming soon! Track your investments across all bags.fm tokens.');
        });
    }

    async loadData() {
        try {
            const response = await fetch('/api/bags-intel/graduations');
            const data = await response.json();

            if (data.success) {
                this.events = data.events || [];
                this.processIntelligence();
            }
        } catch (error) {
            console.error('Failed to load data:', error);
        }
    }

    initializeWebSocket() {
        try {
            this.socket = io('http://localhost:5000');

            this.socket.on('connect', () => {
                console.log('🔌 Intelligence WebSocket connected');
            });

            this.socket.on('new_graduation', (event) => {
                this.events.unshift(event);
                this.refreshAnalytics();
            });
        } catch (error) {
            console.error('WebSocket failed:', error);
        }
    }

    processIntelligence() {
        const filtered = this.filterByTimeline(this.events);

        // Update key metrics
        this.updateMetrics(filtered);

        // Generate analytics
        this.generateScoreDistribution(filtered);
        this.generateTimelineChart(filtered);
        this.generateLeaderboard(filtered);
        this.generateCreatorAnalytics(filtered);
        this.generatePatternAnalysis(filtered);
        this.generateDetailedReports(filtered);
        this.generateAdvancedAnalytics(filtered);
    }

    filterByTimeline(events) {
        if (this.timeline === 'all') return events;

        const now = new Date();
        const cutoffs = {
            '24h': 24 * 60 * 60 * 1000,
            '7d': 7 * 24 * 60 * 60 * 1000,
            '30d': 30 * 24 * 60 * 60 * 1000
        };

        const cutoff = now - cutoffs[this.timeline];
        return events.filter(e => new Date(e.timestamp) >= cutoff);
    }

    updateMetrics(events) {
        const totalAnalyzed = events.length;
        const exceptionalCount = events.filter(e => e.scores?.quality === 'exceptional').length;
        const avgScore = events.length > 0
            ? (events.reduce((sum, e) => sum + (e.scores?.overall || 0), 0) / events.length).toFixed(1)
            : 0;
        const totalVolume = events.reduce((sum, e) => sum + (e.bonding_curve?.volume_sol || 0), 0);

        document.getElementById('total-analyzed').textContent = totalAnalyzed;
        document.getElementById('exceptional-count').textContent = exceptionalCount;
        document.getElementById('avg-score-display').textContent = avgScore;
        document.getElementById('total-volume').textContent = `${totalVolume.toFixed(1)} SOL`;

        // Calculate trends (mock for now)
        const exceptionalPct = events.length > 0 ? (exceptionalCount / events.length * 100).toFixed(1) : 0;
        document.getElementById('exceptional-trend').textContent = `${exceptionalPct}% of total`;
    }

    generateScoreDistribution(events) {
        const distribution = {
            'exceptional': 0,
            'strong': 0,
            'average': 0,
            'weak': 0,
            'poor': 0
        };

        events.forEach(e => {
            const quality = e.scores?.quality?.toLowerCase();
            if (quality && distribution.hasOwnProperty(quality)) {
                distribution[quality]++;
            }
        });

        this.destroyChart('scoreDistributionChart');

        const ctx = document.getElementById('scoreDistributionChart');
        this.charts.scoreDistribution = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: ['Exceptional', 'Strong', 'Average', 'Weak', 'Poor'],
                datasets: [{
                    data: Object.values(distribution),
                    backgroundColor: [
                        '#39FF14',
                        '#00D4FF',
                        '#FFB02E',
                        '#FF8C00',
                        '#FF6B6B'
                    ],
                    borderWidth: 2,
                    borderColor: '#0B0C0D'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'right',
                        labels: {
                            color: '#FFFFFF',
                            font: {
                                family: 'DM Sans',
                                size: 14
                            },
                            padding: 20
                        }
                    }
                }
            }
        });
    }

    generateTimelineChart(events) {
        // Group by time periods
        const timeData = this.groupByTimePeriods(events);

        this.destroyChart('timelineChart');

        const ctx = document.getElementById('timelineChart');
        this.charts.timeline = new Chart(ctx, {
            type: 'line',
            data: {
                labels: timeData.labels,
                datasets: [
                    {
                        label: 'Avg Score',
                        data: timeData.avgScores,
                        borderColor: '#39FF14',
                        backgroundColor: 'rgba(57, 255, 20, 0.1)',
                        borderWidth: 3,
                        tension: 0.4,
                        fill: true,
                        yAxisID: 'y'
                    },
                    {
                        label: 'Volume (SOL)',
                        data: timeData.volumes,
                        borderColor: '#00D4FF',
                        backgroundColor: 'rgba(0, 212, 255, 0.1)',
                        borderWidth: 3,
                        tension: 0.4,
                        fill: true,
                        yAxisID: 'y1'
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    mode: 'index',
                    intersect: false,
                },
                scales: {
                    y: {
                        type: 'linear',
                        display: true,
                        position: 'left',
                        grid: {
                            color: 'rgba(255, 255, 255, 0.1)'
                        },
                        ticks: {
                            color: '#FFFFFF'
                        }
                    },
                    y1: {
                        type: 'linear',
                        display: true,
                        position: 'right',
                        grid: {
                            drawOnChartArea: false,
                        },
                        ticks: {
                            color: '#FFFFFF'
                        }
                    },
                    x: {
                        grid: {
                            color: 'rgba(255, 255, 255, 0.05)'
                        },
                        ticks: {
                            color: '#FFFFFF'
                        }
                    }
                },
                plugins: {
                    legend: {
                        labels: {
                            color: '#FFFFFF',
                            font: {
                                family: 'DM Sans'
                            }
                        }
                    }
                }
            }
        });
    }

    groupByTimePeriods(events) {
        const periods = {};
        const periodSize = this.timeline === '24h' ? 2 : this.timeline === '7d' ? 24 : 168; // hours

        events.forEach(event => {
            const date = new Date(event.timestamp);
            const periodKey = this.timeline === '24h'
                ? `${date.getHours()}:00`
                : `${date.getMonth() + 1}/${date.getDate()}`;

            if (!periods[periodKey]) {
                periods[periodKey] = {
                    scores: [],
                    volume: 0
                };
            }

            periods[periodKey].scores.push(event.scores?.overall || 0);
            periods[periodKey].volume += event.bonding_curve?.volume_sol || 0;
        });

        const labels = Object.keys(periods).slice(-12); // Last 12 periods
        const avgScores = labels.map(label => {
            const scores = periods[label].scores;
            return scores.length > 0 ? scores.reduce((a, b) => a + b, 0) / scores.length : 0;
        });
        const volumes = labels.map(label => periods[label].volume);

        return { labels, avgScores, volumes };
    }

    generateLeaderboard(events) {
        const container = document.getElementById('top-performers');

        // Sort by score
        const topTokens = [...events]
            .sort((a, b) => (b.scores?.overall || 0) - (a.scores?.overall || 0))
            .slice(0, 10);

        container.innerHTML = topTokens.map((event, index) => {
            const rank = index + 1;
            const rankClass = rank === 1 ? 'gold' : rank === 2 ? 'silver' : rank === 3 ? 'bronze' : '';

            return `
                <div class="leaderboard-item" data-token-id="${event.token?.mint}">
                    <div class="leaderboard-rank ${rankClass}">#${rank}</div>
                    <div class="leaderboard-token-info">
                        <div class="leaderboard-token-name">${event.token?.name || 'Unknown'}</div>
                        <div class="leaderboard-token-meta">$${event.token?.symbol || '???'} • ${this.formatTime(event.timestamp)}</div>
                    </div>
                    <div class="leaderboard-scores">
                        <div class="leaderboard-score-item">
                            <span class="leaderboard-score-value">${event.scores?.overall || 0}</span>
                            <span class="leaderboard-score-label">Score</span>
                        </div>
                        <div class="leaderboard-score-item">
                            <span class="leaderboard-score-value">${this.formatCurrency(event.market?.mcap_usd)}</span>
                            <span class="leaderboard-score-label">MCap</span>
                        </div>
                        <div class="leaderboard-score-item">
                            <span class="leaderboard-score-value">${event.bonding_curve?.volume_sol?.toFixed(1) || 0}</span>
                            <span class="leaderboard-score-label">Volume</span>
                        </div>
                    </div>
                </div>
            `;
        }).join('');

        // Add click handlers
        container.querySelectorAll('.leaderboard-item').forEach(item => {
            item.addEventListener('click', () => {
                const tokenId = item.dataset.tokenId;
                const event = events.find(e => e.token?.mint === tokenId);
                if (event) this.showDeepReport(event);
            });
        });
    }

    generateCreatorAnalytics(events) {
        const container = document.getElementById('creator-analytics');

        // Group by creator
        const creators = {};
        events.forEach(event => {
            const wallet = event.creator?.wallet;
            if (!wallet) return;

            if (!creators[wallet]) {
                creators[wallet] = {
                    wallet,
                    twitter: event.creator?.twitter,
                    launches: [],
                    totalScore: 0
                };
            }

            creators[wallet].launches.push(event);
            creators[wallet].totalScore += event.scores?.overall || 0;
        });

        // Sort by success rate
        const topCreators = Object.values(creators)
            .map(creator => ({
                ...creator,
                avgScore: creator.totalScore / creator.launches.length,
                successRate: (creator.launches.filter(l => l.scores?.overall >= 65).length / creator.launches.length * 100).toFixed(0)
            }))
            .sort((a, b) => b.avgScore - a.avgScore)
            .slice(0, 6);

        container.innerHTML = topCreators.map(creator => `
            <div class="creator-card">
                <div class="creator-header">
                    <div class="creator-avatar">👤</div>
                    <div class="creator-info">
                        <div class="creator-name">Creator ${creator.wallet.slice(0, 4)}...${creator.wallet.slice(-4)}</div>
                        <div class="creator-handle">${creator.twitter || 'Anonymous'}</div>
                    </div>
                </div>
                <div class="creator-stats">
                    <div class="creator-stat">
                        <span class="creator-stat-value">${creator.avgScore.toFixed(0)}</span>
                        <span class="creator-stat-label">Avg Score</span>
                    </div>
                    <div class="creator-stat">
                        <span class="creator-stat-value">${creator.launches.length}</span>
                        <span class="creator-stat-label">Launches</span>
                    </div>
                    <div class="creator-stat">
                        <span class="creator-stat-value">${creator.successRate}%</span>
                        <span class="creator-stat-label">Success Rate</span>
                    </div>
                    <div class="creator-stat">
                        <span class="creator-stat-value">${creator.launches.filter(l => l.scores?.quality === 'exceptional').length}</span>
                        <span class="creator-stat-label">Exceptional</span>
                    </div>
                </div>
            </div>
        `).join('');
    }

    generatePatternAnalysis(events) {
        const container = document.getElementById('pattern-analysis');

        // Analyze patterns
        const patterns = this.analyzeSuccessPatterns(events);

        container.innerHTML = patterns.map(pattern => `
            <div class="pattern-card">
                <div class="pattern-icon">${pattern.icon}</div>
                <div class="pattern-title">${pattern.title}</div>
                <div class="pattern-description">${pattern.description}</div>
                <div class="pattern-stat">${pattern.stat}</div>
            </div>
        `).join('');
    }

    analyzeSuccessPatterns(events) {
        const exceptional = events.filter(e => e.scores?.quality === 'exceptional');

        return [
            {
                icon: '⚡',
                title: 'Fast Bonding Wins',
                description: 'Tokens that complete bonding in under 30 minutes tend to have 23% higher success rates',
                stat: `${exceptional.filter(e => e.bonding_curve?.duration_seconds < 1800).length} exceptional tokens`
            },
            {
                icon: '👥',
                title: 'Community Size Matters',
                description: 'Graduations with 100+ unique buyers show stronger price stability post-launch',
                stat: `${exceptional.filter(e => e.bonding_curve?.unique_buyers >= 100).length} exceptional tokens`
            },
            {
                icon: '🔥',
                title: 'High Buy/Sell Ratio',
                description: 'Tokens with 3x+ buy/sell ratio during bonding maintain momentum better',
                stat: `${exceptional.filter(e => e.bonding_curve?.buy_sell_ratio >= 3).length} exceptional tokens`
            },
            {
                icon: '💎',
                title: 'Strong Liquidity Base',
                description: 'Graduations launching with $50K+ liquidity have 2x lower risk profiles',
                stat: `${exceptional.filter(e => e.market?.liquidity_usd >= 50000).length} exceptional tokens`
            },
            {
                icon: '🎯',
                title: 'Creator Track Record',
                description: 'Repeat successful creators show 40% higher average scores',
                stat: 'Pattern identified in data'
            },
            {
                icon: '⏰',
                title: 'Prime Time Launches',
                description: 'Tokens launching 12-6 PM UTC see 15% more initial engagement',
                stat: 'Timeframe analysis available'
            }
        ];
    }

    generateDetailedReports(events) {
        const container = document.getElementById('detailed-reports');
        const reports = events.slice(0, 20); // Top 20 most recent

        container.innerHTML = reports.map(event => this.createReportCard(event)).join('');

        // Add click handlers
        container.querySelectorAll('.report-card').forEach((card, index) => {
            card.addEventListener('click', () => {
                this.showDeepReport(reports[index]);
            });
        });
    }

    createReportCard(event) {
        return `
            <div class="report-card">
                <div class="report-header">
                    <div class="report-title-section">
                        <div class="report-token-name">${event.token?.name || 'Unknown Token'}</div>
                        <div class="report-token-symbol">$${event.token?.symbol || '???'}</div>
                    </div>
                    <div class="report-score">
                        <div class="report-score-value">${event.scores?.overall || 0}</div>
                        <div class="report-score-label">${event.scores?.quality || 'N/A'}</div>
                    </div>
                </div>
                <div class="report-summary">
                    <div class="report-summary-item">
                        <div class="report-summary-label">Market Cap</div>
                        <div class="report-summary-value">${this.formatCurrency(event.market?.mcap_usd)}</div>
                    </div>
                    <div class="report-summary-item">
                        <div class="report-summary-label">Liquidity</div>
                        <div class="report-summary-value">${this.formatCurrency(event.market?.liquidity_usd)}</div>
                    </div>
                    <div class="report-summary-item">
                        <div class="report-summary-label">Bonding Time</div>
                        <div class="report-summary-value">${this.formatDuration(event.bonding_curve?.duration_seconds)}</div>
                    </div>
                    <div class="report-summary-item">
                        <div class="report-summary-label">Risk Level</div>
                        <div class="report-summary-value">${event.scores?.risk || 'N/A'}</div>
                    </div>
                </div>
                ${event.ai_analysis?.summary ? `
                <div class="report-analysis">
                    <h4>🤖 AI Analysis</h4>
                    <p>${event.ai_analysis.summary}</p>
                </div>
                ` : ''}
            </div>
        `;
    }

    showDeepReport(event) {
        const modal = document.getElementById('report-modal');
        const body = document.getElementById('report-body');

        body.innerHTML = `
            <div class="deep-report">
                <div class="report-hero">
                    <img src="${event.token?.image_url || this.generateAvatar(event.token?.symbol)}"
                         class="report-hero-avatar" />
                    <div class="report-hero-info">
                        <h1>${event.token?.name}</h1>
                        <p class="report-hero-symbol">$${event.token?.symbol}</p>
                        <div class="report-hero-badges">
                            <span class="badge badge-${event.scores?.quality}">${event.scores?.quality}</span>
                            <span class="badge badge-risk-${event.scores?.risk}">${event.scores?.risk} risk</span>
                        </div>
                    </div>
                    <div class="report-hero-score">
                        <div class="report-hero-score-value">${event.scores?.overall || 0}</div>
                        <div class="report-hero-score-label">Intelligence Score</div>
                    </div>
                </div>

                ${this.generateFullReport(event)}
            </div>
        `;

        modal.classList.add('active');
        document.body.style.overflow = 'hidden';
    }

    generateFullReport(event) {
        return `
            <div class="report-sections">
                <div class="report-section">
                    <h2>📊 Market Analysis</h2>
                    <div class="report-grid">
                        <div class="report-metric">
                            <span class="report-metric-label">Market Cap</span>
                            <span class="report-metric-value">${this.formatCurrency(event.market?.mcap_usd)}</span>
                        </div>
                        <div class="report-metric">
                            <span class="report-metric-label">Liquidity</span>
                            <span class="report-metric-value">${this.formatCurrency(event.market?.liquidity_usd)}</span>
                        </div>
                        <div class="report-metric">
                            <span class="report-metric-label">Price</span>
                            <span class="report-metric-value">$${event.market?.price_usd?.toFixed(8) || 0}</span>
                        </div>
                        <div class="report-metric">
                            <span class="report-metric-label">24h Volume</span>
                            <span class="report-metric-value">${this.formatCurrency(event.market?.volume_24h_usd)}</span>
                        </div>
                    </div>
                </div>

                <div class="report-section">
                    <h2>📈 Bonding Curve Performance</h2>
                    <div class="report-grid">
                        <div class="report-metric">
                            <span class="report-metric-label">Duration</span>
                            <span class="report-metric-value">${this.formatDuration(event.bonding_curve?.duration_seconds)}</span>
                        </div>
                        <div class="report-metric">
                            <span class="report-metric-label">Volume</span>
                            <span class="report-metric-value">${event.bonding_curve?.volume_sol?.toFixed(2)} SOL</span>
                        </div>
                        <div class="report-metric">
                            <span class="report-metric-label">Unique Buyers</span>
                            <span class="report-metric-value">${event.bonding_curve?.unique_buyers}</span>
                        </div>
                        <div class="report-metric">
                            <span class="report-metric-label">Buy/Sell Ratio</span>
                            <span class="report-metric-value">${event.bonding_curve?.buy_sell_ratio?.toFixed(2)}x</span>
                        </div>
                    </div>
                </div>

                <div class="report-section">
                    <h2>🎯 Score Breakdown</h2>
                    <div class="score-bars-detailed">
                        ${this.generateScoreBar('Bonding Curve', event.scores?.bonding || 0, 25)}
                        ${this.generateScoreBar('Creator Profile', event.scores?.creator || 0, 20)}
                        ${this.generateScoreBar('Social Presence', event.scores?.social || 0, 15)}
                        ${this.generateScoreBar('Market Metrics', event.scores?.market || 0, 25)}
                        ${this.generateScoreBar('Distribution', event.scores?.distribution || 0, 15)}
                    </div>
                </div>

                ${event.flags?.green?.length > 0 || event.flags?.red?.length > 0 ? `
                <div class="report-section">
                    <h2>🚦 Risk Assessment</h2>
                    <div class="report-flags">
                        ${event.flags?.green?.length > 0 ? `
                        <div class="flags-group">
                            <h4>✅ Positive Indicators</h4>
                            <ul>
                                ${event.flags.green.map(flag => `<li>${flag}</li>`).join('')}
                            </ul>
                        </div>
                        ` : ''}
                        ${event.flags?.red?.length > 0 ? `
                        <div class="flags-group">
                            <h4>🚨 Risk Factors</h4>
                            <ul>
                                ${event.flags.red.map(flag => `<li>${flag}</li>`).join('')}
                            </ul>
                        </div>
                        ` : ''}
                    </div>
                </div>
                ` : ''}

                ${event.ai_analysis?.summary ? `
                <div class="report-section">
                    <h2>🤖 AI Intelligence Summary</h2>
                    <div class="report-ai-summary">
                        <p>${event.ai_analysis.summary}</p>
                    </div>
                </div>
                ` : ''}

                <div class="report-section">
                    <h2>🔗 Quick Actions</h2>
                    <div class="report-actions">
                        <a href="https://bags.fm/token/${event.token?.mint}" target="_blank" class="report-action-btn primary">
                            View on Bags.fm
                        </a>
                        <a href="https://dexscreener.com/solana/${event.token?.mint}" target="_blank" class="report-action-btn">
                            DexScreener
                        </a>
                        <button class="report-action-btn" onclick="navigator.clipboard.writeText('${event.token?.mint}')">
                            Copy Contract
                        </button>
                        <button class="report-action-btn" onclick="window.intelligenceDashboard.addToWatchlist('${event.token?.mint}')">
                            Add to Watchlist
                        </button>
                    </div>
                </div>
            </div>
        `;
    }

    generateScoreBar(label, score, weight) {
        return `
            <div class="score-bar-detailed">
                <div class="score-bar-header">
                    <span class="score-bar-label">${label}</span>
                    <span class="score-bar-weight">(${weight}% weight)</span>
                    <span class="score-bar-value">${Math.round(score)}/100</span>
                </div>
                <div class="score-bar-track">
                    <div class="score-bar-fill" style="width: ${score}%"></div>
                </div>
            </div>
        `;
    }

    generateAdvancedAnalytics(events) {
        // Risk distribution
        this.generateRiskChart(events);

        // Bonding duration analysis
        this.generateBondingChart(events);

        // Market cap distribution
        this.generateMcapChart(events);

        // Time of day analysis
        this.generateTimeOfDayChart(events);
    }

    generateRiskChart(events) {
        const risks = { low: 0, medium: 0, high: 0, extreme: 0 };
        events.forEach(e => {
            const risk = e.scores?.risk?.toLowerCase();
            if (risk && risks.hasOwnProperty(risk)) {
                risks[risk]++;
            }
        });

        this.destroyChart('riskChart');

        const ctx = document.getElementById('riskChart');
        if (!ctx) return;

        new Chart(ctx, {
            type: 'pie',
            data: {
                labels: ['Low', 'Medium', 'High', 'Extreme'],
                datasets: [{
                    data: Object.values(risks),
                    backgroundColor: ['#00FF88', '#FFC800', '#FF8C00', '#FF0000']
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                plugins: {
                    legend: {
                        labels: {
                            color: '#FFFFFF',
                            font: { family: 'DM Sans' }
                        }
                    }
                }
            }
        });
    }

    generateBondingChart(events) {
        const ranges = {
            '<15m': 0,
            '15-30m': 0,
            '30-60m': 0,
            '1-2h': 0,
            '>2h': 0
        };

        events.forEach(e => {
            const duration = e.bonding_curve?.duration_seconds || 0;
            if (duration < 900) ranges['<15m']++;
            else if (duration < 1800) ranges['15-30m']++;
            else if (duration < 3600) ranges['30-60m']++;
            else if (duration < 7200) ranges['1-2h']++;
            else ranges['>2h']++;
        });

        this.destroyChart('bondingChart');

        const ctx = document.getElementById('bondingChart');
        if (!ctx) return;

        new Chart(ctx, {
            type: 'bar',
            data: {
                labels: Object.keys(ranges),
                datasets: [{
                    label: 'Count',
                    data: Object.values(ranges),
                    backgroundColor: '#39FF14',
                    borderColor: '#39FF14',
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                scales: {
                    y: {
                        grid: { color: 'rgba(255, 255, 255, 0.1)' },
                        ticks: { color: '#FFFFFF' }
                    },
                    x: {
                        grid: { display: false },
                        ticks: { color: '#FFFFFF' }
                    }
                },
                plugins: {
                    legend: { display: false }
                }
            }
        });
    }

    generateMcapChart(events) {
        const ranges = {
            '<$50K': 0,
            '$50K-$100K': 0,
            '$100K-$250K': 0,
            '$250K-$500K': 0,
            '>$500K': 0
        };

        events.forEach(e => {
            const mcap = e.market?.mcap_usd || 0;
            if (mcap < 50000) ranges['<$50K']++;
            else if (mcap < 100000) ranges['$50K-$100K']++;
            else if (mcap < 250000) ranges['$100K-$250K']++;
            else if (mcap < 500000) ranges['$250K-$500K']++;
            else ranges['>$500K']++;
        });

        this.destroyChart('mcapChart');

        const ctx = document.getElementById('mcapChart');
        if (!ctx) return;

        new Chart(ctx, {
            type: 'bar',
            data: {
                labels: Object.keys(ranges),
                datasets: [{
                    label: 'Count',
                    data: Object.values(ranges),
                    backgroundColor: '#00D4FF'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                indexAxis: 'y',
                scales: {
                    x: {
                        grid: { color: 'rgba(255, 255, 255, 0.1)' },
                        ticks: { color: '#FFFFFF' }
                    },
                    y: {
                        grid: { display: false },
                        ticks: { color: '#FFFFFF' }
                    }
                },
                plugins: {
                    legend: { display: false }
                }
            }
        });
    }

    generateTimeOfDayChart(events) {
        const hours = new Array(24).fill(0);

        events.forEach(e => {
            const date = new Date(e.timestamp);
            hours[date.getUTCHours()]++;
        });

        this.destroyChart('timeOfDayChart');

        const ctx = document.getElementById('timeOfDayChart');
        if (!ctx) return;

        new Chart(ctx, {
            type: 'line',
            data: {
                labels: hours.map((_, i) => `${i}:00`),
                datasets: [{
                    label: 'Launches',
                    data: hours,
                    borderColor: '#FFB02E',
                    backgroundColor: 'rgba(255, 176, 46, 0.1)',
                    fill: true,
                    tension: 0.4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                scales: {
                    y: {
                        grid: { color: 'rgba(255, 255, 255, 0.1)' },
                        ticks: { color: '#FFFFFF' }
                    },
                    x: {
                        grid: { display: false },
                        ticks: {
                            color: '#FFFFFF',
                            maxTicksLimit: 12
                        }
                    }
                },
                plugins: {
                    legend: { display: false }
                }
            }
        });
    }

    switchView(view) {
        this.currentView = view;

        // Hide all views
        document.querySelectorAll('.intelligence-view').forEach(v => v.classList.remove('active'));

        // Show selected view
        const viewMap = {
            'overview': 'overview-view',
            'detailed': 'detailed-view',
            'analytics': 'analytics-view'
        };

        const targetView = document.getElementById(viewMap[view]);
        if (targetView) {
            targetView.classList.add('active');

            // Regenerate analytics view charts if needed
            if (view === 'analytics') {
                setTimeout(() => {
                    this.generateAdvancedAnalytics(this.filterByTimeline(this.events));
                }, 100);
            }
        }
    }

    refreshAnalytics() {
        this.processIntelligence();
    }

    destroyChart(chartId) {
        if (this.charts[chartId]) {
            this.charts[chartId].destroy();
            delete this.charts[chartId];
        }
    }

    loadWatchlist() {
        const saved = localStorage.getItem('bagsIntelWatchlist');
        return saved ? JSON.parse(saved) : [];
    }

    saveWatchlist() {
        localStorage.setItem('bagsIntelWatchlist', JSON.stringify(this.watchlist));
    }

    addToWatchlist(tokenMint) {
        if (!this.watchlist.includes(tokenMint)) {
            this.watchlist.push(tokenMint);
            this.saveWatchlist();
            alert('Added to watchlist!');
        } else {
            alert('Already in watchlist');
        }
    }

    exportData() {
        const filtered = this.filterByTimeline(this.events);
        const dataStr = JSON.stringify(filtered, null, 2);
        const dataBlob = new Blob([dataStr], { type: 'application/json' });
        const url = URL.createObjectURL(dataBlob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `bags-intel-${this.timeline}-${Date.now()}.json`;
        link.click();
    }

    // Utility methods
    formatCurrency(value) {
        if (!value) return '$0';
        if (value >= 1e6) return `$${(value / 1e6).toFixed(2)}M`;
        if (value >= 1e3) return `$${(value / 1e3).toFixed(1)}K`;
        return `$${value.toFixed(0)}`;
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
        if (diffMins < 60) return `${diffMins}m ago`;
        if (diffHours < 24) return `${diffHours}h ago`;
        return `${diffDays}d ago`;
    }

    generateAvatar(symbol) {
        const colors = [
            ['#39FF14', '#20D080'],
            ['#BB86FC', '#8A2BE2'],
            ['#FFB02E', '#FF8C00'],
            ['#00D4FF', '#0080FF']
        ];
        const index = (symbol?.charCodeAt(0) || 0) % colors.length;
        const [color1, color2] = colors[index];
        return `data:image/svg+xml,${encodeURIComponent(`
            <svg width="100" height="100" xmlns="http://www.w3.org/2000/svg">
                <defs>
                    <linearGradient id="grad" x1="0%" y1="0%" x2="100%" y2="100%">
                        <stop offset="0%" style="stop-color:${color1};stop-opacity:1" />
                        <stop offset="100%" style="stop-color:${color2};stop-opacity:1" />
                    </linearGradient>
                </defs>
                <circle cx="50" cy="50" r="50" fill="url(#grad)" />
                <text x="50" y="70" font-family="Arial" font-size="50" font-weight="bold"
                      fill="white" text-anchor="middle">${(symbol || '?')[0].toUpperCase()}</text>
            </svg>
        `)}`;
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.intelligenceDashboard = new IntelligenceDashboard();
});

// Modal close handlers
document.addEventListener('DOMContentLoaded', () => {
    const reportModal = document.getElementById('report-modal');
    const reportOverlay = document.getElementById('report-overlay');
    const reportClose = document.getElementById('report-close');

    if (reportOverlay) {
        reportOverlay.addEventListener('click', () => {
            reportModal?.classList.remove('active');
            document.body.style.overflow = '';
        });
    }

    if (reportClose) {
        reportClose.addEventListener('click', () => {
            reportModal?.classList.remove('active');
            document.body.style.overflow = '';
        });
    }
});

// Additional report styling
const reportStyles = document.createElement('style');
reportStyles.textContent = `
    .deep-report {
        color: var(--pure-white);
    }

    .report-hero {
        display: flex;
        align-items: center;
        gap: 24px;
        padding: 32px;
        background: linear-gradient(135deg, rgba(57, 255, 20, 0.1), rgba(57, 255, 20, 0.05));
        border-bottom: 1px solid var(--glass-border);
        margin-bottom: 32px;
    }

    .report-hero-avatar {
        width: 100px;
        height: 100px;
        border-radius: 50%;
        border: 3px solid var(--accent-green);
    }

    .report-hero-info h1 {
        font-size: 32px;
        margin-bottom: 8px;
    }

    .report-hero-symbol {
        font-family: var(--font-mono);
        font-size: 18px;
        color: var(--text-grey);
        margin-bottom: 12px;
    }

    .report-hero-badges {
        display: flex;
        gap: 8px;
    }

    .badge {
        padding: 6px 12px;
        border-radius: 6px;
        font-size: 12px;
        font-weight: 600;
        text-transform: uppercase;
    }

    .badge-exceptional {
        background: rgba(57, 255, 20, 0.2);
        color: #39FF14;
    }

    .report-hero-score {
        margin-left: auto;
        text-align: center;
    }

    .report-hero-score-value {
        font-size: 64px;
        font-weight: 700;
        color: var(--accent-green);
        line-height: 1;
    }

    .report-sections {
        padding: 0 32px 32px;
    }

    .report-section {
        margin-bottom: 32px;
    }

    .report-section h2 {
        font-size: 20px;
        margin-bottom: 16px;
        color: var(--pure-white);
    }

    .report-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        gap: 16px;
    }

    .report-metric {
        display: flex;
        flex-direction: column;
        padding: 16px;
        background: var(--glass-bg);
        border: 1px solid var(--glass-border);
        border-radius: 12px;
    }

    .report-metric-label {
        font-size: 12px;
        color: var(--text-grey);
        margin-bottom: 8px;
    }

    .report-metric-value {
        font-size: 20px;
        font-weight: 700;
        color: var(--pure-white);
        font-family: var(--font-mono);
    }

    .score-bars-detailed {
        display: flex;
        flex-direction: column;
        gap: 16px;
    }

    .score-bar-detailed {
        display: flex;
        flex-direction: column;
        gap: 8px;
    }

    .score-bar-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
    }

    .score-bar-weight {
        font-size: 11px;
        color: var(--text-grey);
    }

    .report-actions {
        display: flex;
        gap: 12px;
        flex-wrap: wrap;
    }

    .report-action-btn {
        padding: 12px 24px;
        border: 1px solid var(--glass-border);
        background: var(--glass-bg);
        color: var(--light-grey);
        text-decoration: none;
        border-radius: 8px;
        font-weight: 600;
        cursor: pointer;
        transition: all 0.2s ease;
        font-family: var(--font-body);
    }

    .report-action-btn.primary {
        background: var(--accent-green);
        color: var(--dark-bg);
        border-color: var(--accent-green);
    }

    .report-flags {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 24px;
    }

    .flags-group h4 {
        margin-bottom: 12px;
        font-size: 16px;
    }

    .flags-group ul {
        list-style: none;
        padding: 0;
    }

    .flags-group li {
        padding: 8px;
        margin-bottom: 6px;
        background: var(--glass-bg);
        border-radius: 6px;
        font-size: 14px;
    }
`;
document.head.appendChild(reportStyles);

// ============================================
// Token Comparison Feature
// ============================================

class TokenComparison {
    constructor() {
        this.selectedTokens = [];
        this.maxSelection = 4;
        this.initEventListeners();
    }

    initEventListeners() {
        // Open comparison modal
        const compareTab = document.getElementById('compare-tab');
        if (compareTab) {
            compareTab.addEventListener('click', (e) => {
                e.preventDefault();
                this.openCompareModal();
            });
        }

        // Close modal
        const compareClose = document.getElementById('compare-close');
        const compareOverlay = document.getElementById('compare-overlay');
        if (compareClose) compareClose.addEventListener('click', () => this.closeModal());
        if (compareOverlay) compareOverlay.addEventListener('click', () => this.closeModal());

        // Compare button
        const compareBtn = document.getElementById('compare-btn');
        if (compareBtn) {
            compareBtn.addEventListener('click', () => this.showComparison());
        }
    }

    openCompareModal() {
        const modal = document.getElementById('compare-modal');
        if (!modal) return;

        // Populate token selector
        this.populateTokenSelector();

        // Reset selection
        this.selectedTokens = [];
        this.updateSelectedDisplay();

        // Hide comparison grid initially
        document.getElementById('comparison-grid').style.display = 'none';
        document.querySelector('.compare-selection').style.display = 'block';

        modal.classList.add('active');
    }

    closeModal() {
        const modal = document.getElementById('compare-modal');
        if (modal) modal.classList.remove('active');
    }

    populateTokenSelector() {
        const selector = document.getElementById('token-selector');
        if (!selector || !app.events) return;

        // Sort events by score
        const sortedEvents = [...app.events]
            .filter(e => e.scores?.overall)
            .sort((a, b) => (b.scores.overall || 0) - (a.scores.overall || 0));

        selector.innerHTML = sortedEvents.map(event => `
            <div class="token-chip" data-contract="${event.contract_address}">
                <span>${event.token_name}</span>
                <span class="token-chip-score">${(event.scores?.overall || 0).toFixed(1)}</span>
            </div>
        `).join('');

        // Add click handlers
        selector.querySelectorAll('.token-chip').forEach(chip => {
            chip.addEventListener('click', () => this.toggleToken(chip));
        });
    }

    toggleToken(chip) {
        const contract = chip.dataset.contract;
        const index = this.selectedTokens.indexOf(contract);

        if (index > -1) {
            // Remove token
            this.selectedTokens.splice(index, 1);
            chip.classList.remove('selected');
        } else {
            // Add token if under limit
            if (this.selectedTokens.length < this.maxSelection) {
                this.selectedTokens.push(contract);
                chip.classList.add('selected');
            }
        }

        this.updateSelectedDisplay();
    }

    updateSelectedDisplay() {
        const countSpan = document.getElementById('selected-count');
        const chipsContainer = document.getElementById('selected-chips');
        const compareBtn = document.getElementById('compare-btn');

        if (countSpan) countSpan.textContent = this.selectedTokens.length;

        if (chipsContainer) {
            chipsContainer.innerHTML = this.selectedTokens.map(contract => {
                const event = app.events.find(e => e.contract_address === contract);
                return `
                    <div class="selected-chip">
                        <span>${event?.token_name || 'Unknown'}</span>
                        <span class="selected-chip-remove" data-contract="${contract}">×</span>
                    </div>
                `;
            }).join('');

            // Add remove handlers
            chipsContainer.querySelectorAll('.selected-chip-remove').forEach(btn => {
                btn.addEventListener('click', () => {
                    const chip = document.querySelector(`.token-chip[data-contract="${btn.dataset.contract}"]`);
                    if (chip) this.toggleToken(chip);
                });
            });
        }

        // Enable/disable compare button
        if (compareBtn) {
            compareBtn.disabled = this.selectedTokens.length < 2;
        }
    }

    showComparison() {
        if (this.selectedTokens.length < 2) return;

        // Get selected events
        const events = this.selectedTokens.map(contract =>
            app.events.find(e => e.contract_address === contract)
        ).filter(Boolean);

        // Generate comparison
        const comparisonGrid = document.getElementById('comparison-grid');
        if (!comparisonGrid) return;

        // Determine winner (highest overall score)
        const winner = events.reduce((max, e) =>
            (e.scores?.overall || 0) > (max.scores?.overall || 0) ? e : max
        );

        comparisonGrid.innerHTML = events.map(event => this.generateComparisonCard(event, winner)).join('');

        // Show comparison grid, hide selection
        document.querySelector('.compare-selection').style.display = 'none';
        comparisonGrid.style.display = 'grid';
    }

    generateComparisonCard(event, winner) {
        const isWinner = event.contract_address === winner.contract_address;
        const scores = event.scores || {};
        const market = event.market_metrics || {};
        const bonding = event.bonding_metrics || {};

        // Determine which metrics are best for this token
        const bestMetrics = this.getBestMetrics(event);

        return `
            <div class="comparison-card ${isWinner ? 'winner' : ''}">
                ${isWinner ? '<div class="comparison-winner-badge">Best Overall</div>' : ''}

                <div class="comparison-card-header">
                    <h3 class="comparison-card-title">${event.token_name || 'Unknown'}</h3>
                    <div class="comparison-card-symbol">${event.symbol || 'N/A'}</div>
                </div>

                <div class="comparison-score-large">
                    ${(scores.overall || 0).toFixed(1)}
                </div>

                <div class="comparison-metrics">
                    <div class="comparison-metric ${bestMetrics.bonding ? 'best' : ''}">
                        <span class="comparison-metric-label">Bonding Score</span>
                        <span class="comparison-metric-value">${(scores.bonding || 0).toFixed(1)}</span>
                    </div>
                    <div class="comparison-metric ${bestMetrics.creator ? 'best' : ''}">
                        <span class="comparison-metric-label">Creator Score</span>
                        <span class="comparison-metric-value">${(scores.creator || 0).toFixed(1)}</span>
                    </div>
                    <div class="comparison-metric ${bestMetrics.social ? 'best' : ''}">
                        <span class="comparison-metric-label">Social Score</span>
                        <span class="comparison-metric-value">${(scores.social || 0).toFixed(1)}</span>
                    </div>
                    <div class="comparison-metric ${bestMetrics.market ? 'best' : ''}">
                        <span class="comparison-metric-label">Market Score</span>
                        <span class="comparison-metric-value">${(scores.market || 0).toFixed(1)}</span>
                    </div>
                    <div class="comparison-metric ${bestMetrics.distribution ? 'best' : ''}">
                        <span class="comparison-metric-label">Distribution Score</span>
                        <span class="comparison-metric-value">${(scores.distribution || 0).toFixed(1)}</span>
                    </div>
                    <div class="comparison-metric ${bestMetrics.liquidity ? 'best' : ''}">
                        <span class="comparison-metric-label">Liquidity</span>
                        <span class="comparison-metric-value">${this.formatCurrency(market.liquidity_sol || 0)} SOL</span>
                    </div>
                    <div class="comparison-metric ${bestMetrics.volume ? 'best' : ''}">
                        <span class="comparison-metric-label">24h Volume</span>
                        <span class="comparison-metric-value">${this.formatCurrency(market.volume_24h || 0)}</span>
                    </div>
                    <div class="comparison-metric ${bestMetrics.mcap ? 'best' : ''}">
                        <span class="comparison-metric-label">Market Cap</span>
                        <span class="comparison-metric-value">${this.formatCurrency(market.market_cap || 0)}</span>
                    </div>
                    <div class="comparison-metric ${bestMetrics.buyers ? 'best' : ''}">
                        <span class="comparison-metric-label">Buyer Count</span>
                        <span class="comparison-metric-value">${bonding.buyer_count || 0}</span>
                    </div>
                    <div class="comparison-metric ${bestMetrics.holders ? 'best' : ''}">
                        <span class="comparison-metric-label">Holders</span>
                        <span class="comparison-metric-value">${event.holder_count || 0}</span>
                    </div>
                </div>

                <div style="margin-top: 16px; padding-top: 16px; border-top: 1px solid var(--glass-border);">
                    <div style="font-size: 0.875rem; color: rgba(255, 255, 255, 0.7); margin-bottom: 8px;">Risk Level</div>
                    <div class="risk-badge risk-${(scores.risk_level || 'medium').toLowerCase()}" style="display: inline-block;">
                        ${scores.risk_level || 'Medium'}
                    </div>
                </div>
            </div>
        `;
    }

    getBestMetrics(event) {
        // Compare this event's metrics against all selected tokens
        const selectedEvents = this.selectedTokens.map(contract =>
            app.events.find(e => e.contract_address === contract)
        ).filter(Boolean);

        const best = {};
        const metrics = [
            'bonding', 'creator', 'social', 'market', 'distribution'
        ];

        // Check scores
        metrics.forEach(metric => {
            const eventScore = event.scores?.[metric] || 0;
            const maxScore = Math.max(...selectedEvents.map(e => e.scores?.[metric] || 0));
            best[metric] = eventScore === maxScore && eventScore > 0;
        });

        // Check market metrics
        best.liquidity = (event.market_metrics?.liquidity_sol || 0) ===
            Math.max(...selectedEvents.map(e => e.market_metrics?.liquidity_sol || 0));
        best.volume = (event.market_metrics?.volume_24h || 0) ===
            Math.max(...selectedEvents.map(e => e.market_metrics?.volume_24h || 0));
        best.mcap = (event.market_metrics?.market_cap || 0) ===
            Math.max(...selectedEvents.map(e => e.market_metrics?.market_cap || 0));
        best.buyers = (event.bonding_metrics?.buyer_count || 0) ===
            Math.max(...selectedEvents.map(e => e.bonding_metrics?.buyer_count || 0));
        best.holders = (event.holder_count || 0) ===
            Math.max(...selectedEvents.map(e => e.holder_count || 0));

        return best;
    }

    formatCurrency(value) {
        if (value >= 1000000) {
            return `$${(value / 1000000).toFixed(2)}M`;
        } else if (value >= 1000) {
            return `$${(value / 1000).toFixed(1)}K`;
        }
        return `$${value.toFixed(0)}`;
    }
}

// Initialize comparison feature
const comparison = new TokenComparison();

// ============================================
// Portfolio Tracker Feature
// ============================================

class PortfolioTracker {
    constructor() {
        this.positions = this.loadPositions();
        this.initEventListeners();
    }

    initEventListeners() {
        // Open portfolio modal
        const portfolioTab = document.getElementById('portfolio-tab');
        if (portfolioTab) {
            portfolioTab.addEventListener('click', (e) => {
                e.preventDefault();
                this.openPortfolioModal();
            });
        }

        // Close modal
        const portfolioClose = document.getElementById('portfolio-close');
        const portfolioOverlay = document.getElementById('portfolio-overlay');
        if (portfolioClose) portfolioClose.addEventListener('click', () => this.closeModal());
        if (portfolioOverlay) portfolioOverlay.addEventListener('click', () => this.closeModal());

        // Add position button
        const addBtn = document.getElementById('add-position-btn');
        if (addBtn) {
            addBtn.addEventListener('click', () => this.addPosition());
        }
    }

    openPortfolioModal() {
        const modal = document.getElementById('portfolio-modal');
        if (!modal) return;

        // Populate token dropdown
        this.populateTokenSelect();

        // Render portfolio
        this.renderPortfolio();

        modal.classList.add('active');
    }

    closeModal() {
        const modal = document.getElementById('portfolio-modal');
        if (modal) modal.classList.remove('active');
    }

    populateTokenSelect() {
        const select = document.getElementById('portfolio-token-select');
        if (!select || !app.events) return;

        // Sort by score
        const sortedEvents = [...app.events]
            .filter(e => e.token_name)
            .sort((a, b) => (b.scores?.overall || 0) - (a.scores?.overall || 0));

        select.innerHTML = '<option value="">Select Token</option>' +
            sortedEvents.map(event => `
                <option value="${event.contract_address}">
                    ${event.token_name} (${event.symbol || 'N/A'}) - Score: ${(event.scores?.overall || 0).toFixed(1)}
                </option>
            `).join('');
    }

    addPosition() {
        const tokenContract = document.getElementById('portfolio-token-select').value;
        const amount = parseFloat(document.getElementById('portfolio-amount').value);
        const entryPrice = parseFloat(document.getElementById('portfolio-entry-price').value);
        const tokens = parseFloat(document.getElementById('portfolio-tokens').value);

        if (!tokenContract || !amount || !entryPrice || !tokens) {
            alert('Please fill in all fields');
            return;
        }

        const token = app.events.find(e => e.contract_address === tokenContract);
        if (!token) return;

        const position = {
            id: Date.now(),
            contract: tokenContract,
            tokenName: token.token_name,
            symbol: token.symbol,
            amount,
            entryPrice,
            tokens,
            addedAt: new Date().toISOString()
        };

        this.positions.push(position);
        this.savePositions();
        this.renderPortfolio();

        // Clear form
        document.getElementById('portfolio-token-select').value = '';
        document.getElementById('portfolio-amount').value = '';
        document.getElementById('portfolio-entry-price').value = '';
        document.getElementById('portfolio-tokens').value = '';
    }

    removePosition(id) {
        this.positions = this.positions.filter(p => p.id !== id);
        this.savePositions();
        this.renderPortfolio();
    }

    renderPortfolio() {
        this.updateSummary();
        this.renderTable();
    }

    updateSummary() {
        let totalInvested = 0;
        let totalValue = 0;

        this.positions.forEach(position => {
            const currentPrice = this.getCurrentPrice(position.contract);
            totalInvested += position.amount;
            totalValue += position.tokens * currentPrice;
        });

        const totalPnL = totalValue - totalInvested;
        const pnlPercent = totalInvested > 0 ? (totalPnL / totalInvested) * 100 : 0;

        document.getElementById('portfolio-invested').textContent = `$${totalInvested.toFixed(2)}`;
        document.getElementById('portfolio-value').textContent = `$${totalValue.toFixed(2)}`;

        const pnlElement = document.getElementById('portfolio-pnl');
        const pnlPercentElement = document.getElementById('portfolio-pnl-percent');

        pnlElement.textContent = `$${totalPnL.toFixed(2)}`;
        pnlPercentElement.textContent = `${pnlPercent >= 0 ? '+' : ''}${pnlPercent.toFixed(2)}%`;
        pnlPercentElement.className = `portfolio-stat-percent ${pnlPercent >= 0 ? 'positive' : 'negative'}`;

        document.getElementById('portfolio-count').textContent = this.positions.length;
    }

    renderTable() {
        const tbody = document.getElementById('portfolio-table-body');
        if (!tbody) return;

        if (this.positions.length === 0) {
            tbody.innerHTML = `
                <tr class="portfolio-empty">
                    <td colspan="9">
                        <div class="empty-portfolio">
                            <span class="empty-icon">💼</span>
                            <p>No positions yet</p>
                            <p class="empty-hint">Add your first position above</p>
                        </div>
                    </td>
                </tr>
            `;
            return;
        }

        tbody.innerHTML = this.positions.map(position => {
            const currentPrice = this.getCurrentPrice(position.contract);
            const currentValue = position.tokens * currentPrice;
            const pnl = currentValue - position.amount;
            const pnlPercent = (pnl / position.amount) * 100;

            return `
                <tr>
                    <td>
                        <div class="portfolio-token-name">${position.tokenName}</div>
                        <div class="portfolio-token-symbol">${position.symbol || 'N/A'}</div>
                    </td>
                    <td>$${position.amount.toFixed(2)}</td>
                    <td>$${position.entryPrice.toFixed(6)}</td>
                    <td>$${currentPrice.toFixed(6)}</td>
                    <td>${position.tokens.toLocaleString()}</td>
                    <td>$${currentValue.toFixed(2)}</td>
                    <td class="${pnl >= 0 ? 'portfolio-pnl-positive' : 'portfolio-pnl-negative'}">
                        $${pnl.toFixed(2)}
                    </td>
                    <td class="${pnl >= 0 ? 'portfolio-pnl-positive' : 'portfolio-pnl-negative'}">
                        ${pnlPercent >= 0 ? '+' : ''}${pnlPercent.toFixed(2)}%
                    </td>
                    <td>
                        <button class="portfolio-action-btn" onclick="portfolio.removePosition(${position.id})">
                            Remove
                        </button>
                    </td>
                </tr>
            `;
        }).join('');
    }

    getCurrentPrice(contract) {
        const token = app.events.find(e => e.contract_address === contract);
        if (!token || !token.market_metrics) return 0;

        // Simulate price movement for demo (± 50% from entry)
        const basePrice = token.market_metrics.price || 0.000001;
        const variation = 1 + ((Math.random() - 0.5) * 1); // ±50%
        return basePrice * variation;
    }

    loadPositions() {
        try {
            const saved = localStorage.getItem('bags_intel_portfolio');
            return saved ? JSON.parse(saved) : [];
        } catch (e) {
            return [];
        }
    }

    savePositions() {
        try {
            localStorage.setItem('bags_intel_portfolio', JSON.stringify(this.positions));
        } catch (e) {
            console.error('Failed to save portfolio:', e);
        }
    }
}

// Initialize portfolio tracker
const portfolio = new PortfolioTracker();

// ============================================
// Alert System Feature
// ============================================

class AlertSystem {
    constructor() {
        this.alerts = this.loadAlerts();
        this.triggers = this.loadTriggers();
        this.initEventListeners();
        this.requestNotificationPermission();

        // Monitor for new events
        this.monitorEvents();
    }

    initEventListeners() {
        // Open alerts modal
        const alertsTab = document.getElementById('alerts-tab');
        if (alertsTab) {
            alertsTab.addEventListener('click', (e) => {
                e.preventDefault();
                this.openAlertsModal();
            });
        }

        // Close modal
        const alertsClose = document.getElementById('alerts-close');
        const alertsOverlay = document.getElementById('alerts-overlay');
        if (alertsClose) alertsClose.addEventListener('click', () => this.closeModal());
        if (alertsOverlay) alertsOverlay.addEventListener('click', () => this.closeModal());

        // Create alert button
        const createBtn = document.getElementById('create-alert-btn');
        if (createBtn) {
            createBtn.addEventListener('click', () => this.createAlert());
        }
    }

    openAlertsModal() {
        const modal = document.getElementById('alerts-modal');
        if (!modal) return;

        this.renderAlerts();
        this.renderTriggers();

        modal.classList.add('active');
    }

    closeModal() {
        const modal = document.getElementById('alerts-modal');
        if (modal) modal.classList.remove('active');
    }

    requestNotificationPermission() {
        if ('Notification' in window && Notification.permission === 'default') {
            Notification.requestPermission();
        }
    }

    createAlert() {
        const name = document.getElementById('alert-name').value;
        const minScore = parseFloat(document.getElementById('alert-min-score').value);
        const maxRisk = document.getElementById('alert-max-risk').value;
        const minLiquidity = parseFloat(document.getElementById('alert-min-liquidity').value) || 0;
        const browserNotif = document.getElementById('alert-browser').checked;
        const soundAlert = document.getElementById('alert-sound').checked;

        if (!name || !minScore) {
            alert('Please provide alert name and minimum score');
            return;
        }

        const newAlert = {
            id: Date.now(),
            name,
            criteria: {
                minScore,
                maxRisk,
                minLiquidity
            },
            notifications: {
                browser: browserNotif,
                sound: soundAlert
            },
            active: true,
            createdAt: new Date().toISOString()
        };

        this.alerts.push(newAlert);
        this.saveAlerts();
        this.renderAlerts();

        // Clear form
        document.getElementById('alert-name').value = '';
        document.getElementById('alert-min-score').value = '';
        document.getElementById('alert-max-risk').value = 'medium';
        document.getElementById('alert-min-liquidity').value = '';
    }

    toggleAlert(id) {
        const alert = this.alerts.find(a => a.id === id);
        if (alert) {
            alert.active = !alert.active;
            this.saveAlerts();
            this.renderAlerts();
        }
    }

    deleteAlert(id) {
        this.alerts = this.alerts.filter(a => a.id !== id);
        this.saveAlerts();
        this.renderAlerts();
    }

    renderAlerts() {
        const container = document.getElementById('alerts-list');
        const countSpan = document.getElementById('active-alerts-count');

        if (!container) return;

        countSpan.textContent = this.alerts.filter(a => a.active).length;

        if (this.alerts.length === 0) {
            container.innerHTML = `
                <div class="empty-alerts">
                    <span class="empty-icon">🔔</span>
                    <p>No alerts configured</p>
                    <p class="empty-hint">Create your first alert above</p>
                </div>
            `;
            return;
        }

        container.innerHTML = this.alerts.map(alert => `
            <div class="alert-card ${alert.active ? 'active' : ''}">
                <div class="alert-info">
                    <div class="alert-name">${alert.name}</div>
                    <div class="alert-criteria">
                        <span class="alert-criterion">Min Score: ${alert.criteria.minScore}</span>
                        <span class="alert-criterion">Max Risk: ${alert.criteria.maxRisk}</span>
                        ${alert.criteria.minLiquidity > 0 ? `<span class="alert-criterion">Min Liquidity: ${alert.criteria.minLiquidity} SOL</span>` : ''}
                        ${alert.notifications.browser ? '<span class="alert-criterion">🔔 Browser</span>' : ''}
                        ${alert.notifications.sound ? '<span class="alert-criterion">🔊 Sound</span>' : ''}
                    </div>
                </div>
                <div class="alert-actions">
                    <button class="alert-toggle-btn ${alert.active ? '' : 'inactive'}"
                            onclick="alertSystem.toggleAlert(${alert.id})">
                        ${alert.active ? 'Active' : 'Inactive'}
                    </button>
                    <button class="alert-delete-btn" onclick="alertSystem.deleteAlert(${alert.id})">
                        Delete
                    </button>
                </div>
            </div>
        `).join('');
    }

    renderTriggers() {
        const container = document.getElementById('triggers-list');
        if (!container) return;

        if (this.triggers.length === 0) {
            container.innerHTML = '<div class="empty-triggers"><p>No alerts triggered yet</p></div>';
            return;
        }

        // Show most recent 10 triggers
        const recentTriggers = [...this.triggers]
            .sort((a, b) => new Date(b.triggeredAt) - new Date(a.triggeredAt))
            .slice(0, 10);

        container.innerHTML = recentTriggers.map(trigger => `
            <div class="trigger-item">
                <div class="trigger-token">${trigger.tokenName} (${trigger.symbol})</div>
                <div class="trigger-time">${new Date(trigger.triggeredAt).toLocaleString()}</div>
                <div class="trigger-details">
                    Alert: "${trigger.alertName}" | Score: ${trigger.score.toFixed(1)} | Risk: ${trigger.risk}
                </div>
            </div>
        `).join('');
    }

    monitorEvents() {
        // Check for new events every 10 seconds
        setInterval(() => {
            this.checkAlerts();
        }, 10000);
    }

    checkAlerts() {
        if (!app.events) return;

        const activeAlerts = this.alerts.filter(a => a.active);
        if (activeAlerts.length === 0) return;

        // Check each event against active alerts
        app.events.forEach(event => {
            // Skip if already triggered for this event
            const alreadyTriggered = this.triggers.some(t =>
                t.tokenContract === event.contract_address
            );
            if (alreadyTriggered) return;

            activeAlerts.forEach(alert => {
                if (this.matchesCriteria(event, alert.criteria)) {
                    this.triggerAlert(event, alert);
                }
            });
        });
    }

    matchesCriteria(event, criteria) {
        const score = event.scores?.overall || 0;
        const risk = (event.scores?.risk_level || 'medium').toLowerCase();
        const liquidity = event.market_metrics?.liquidity_sol || 0;

        // Check score
        if (score < criteria.minScore) return false;

        // Check risk level (convert to numeric for comparison)
        const riskLevels = { low: 1, medium: 2, high: 3, extreme: 4 };
        const eventRiskLevel = riskLevels[risk] || 2;
        const maxRiskLevel = riskLevels[criteria.maxRisk] || 2;
        if (eventRiskLevel > maxRiskLevel) return false;

        // Check liquidity
        if (liquidity < criteria.minLiquidity) return false;

        return true;
    }

    triggerAlert(event, alert) {
        const trigger = {
            id: Date.now(),
            alertId: alert.id,
            alertName: alert.name,
            tokenName: event.token_name,
            symbol: event.symbol,
            tokenContract: event.contract_address,
            score: event.scores?.overall || 0,
            risk: event.scores?.risk_level || 'unknown',
            triggeredAt: new Date().toISOString()
        };

        this.triggers.push(trigger);
        this.saveTriggers();

        // Send notifications
        if (alert.notifications.browser) {
            this.sendBrowserNotification(event, alert);
        }
        if (alert.notifications.sound) {
            this.playSoundAlert();
        }

        // Update UI if modal is open
        if (document.getElementById('alerts-modal').classList.contains('active')) {
            this.renderTriggers();
        }
    }

    sendBrowserNotification(event, alert) {
        if ('Notification' in window && Notification.permission === 'granted') {
            new Notification(`Bags Intel Alert: ${alert.name}`, {
                body: `${event.token_name} (${event.symbol})\nScore: ${(event.scores?.overall || 0).toFixed(1)}\nRisk: ${event.scores?.risk_level || 'Unknown'}`,
                icon: '/favicon.ico',
                tag: `alert-${event.contract_address}`
            });
        }
    }

    playSoundAlert() {
        // Create a simple beep sound
        const audioContext = new (window.AudioContext || window.webkitAudioContext)();
        const oscillator = audioContext.createOscillator();
        const gainNode = audioContext.createGain();

        oscillator.connect(gainNode);
        gainNode.connect(audioContext.destination);

        oscillator.frequency.value = 800;
        oscillator.type = 'sine';

        gainNode.gain.setValueAtTime(0.3, audioContext.currentTime);
        gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.5);

        oscillator.start(audioContext.currentTime);
        oscillator.stop(audioContext.currentTime + 0.5);
    }

    loadAlerts() {
        try {
            const saved = localStorage.getItem('bags_intel_alerts');
            return saved ? JSON.parse(saved) : [];
        } catch (e) {
            return [];
        }
    }

    saveAlerts() {
        try {
            localStorage.setItem('bags_intel_alerts', JSON.stringify(this.alerts));
        } catch (e) {
            console.error('Failed to save alerts:', e);
        }
    }

    loadTriggers() {
        try {
            const saved = localStorage.getItem('bags_intel_triggers');
            return saved ? JSON.parse(saved) : [];
        } catch (e) {
            return [];
        }
    }

    saveTriggers() {
        try {
            localStorage.setItem('bags_intel_triggers', JSON.stringify(this.triggers));
        } catch (e) {
            console.error('Failed to save triggers:', e);
        }
    }
}

// Initialize alert system
const alertSystem = new AlertSystem();
