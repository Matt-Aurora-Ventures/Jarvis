/**
 * Bags Intel Feed - Enhanced with advanced features
 * Search, filters, sorting, modals, notifications
 * JARVIS LifeOS
 */

class BagsIntelFeed {
    constructor() {
        // DOM elements
        this.feed = document.getElementById('feed');
        this.loading = document.getElementById('loading');
        this.emptyState = document.getElementById('empty-state');
        this.trackedCount = document.getElementById('tracked-count');
        this.template = document.getElementById('intel-card-template');

        // Search & filter elements
        this.searchInput = document.getElementById('search-input');
        this.searchClear = document.getElementById('search-clear');
        this.sortSelect = document.getElementById('sort-select');
        this.advancedFilterBtn = document.getElementById('advanced-filter-btn');
        this.advancedFilters = document.getElementById('advanced-filters');

        // Stats elements
        this.showingCount = document.getElementById('showing-count');
        this.avgScore = document.getElementById('avg-score');
        this.totalMcap = document.getElementById('total-mcap');

        // Modal elements
        this.tokenModal = document.getElementById('token-modal');
        this.modalOverlay = document.getElementById('modal-overlay');
        this.modalClose = document.getElementById('modal-close');
        this.modalBody = document.getElementById('modal-body');

        // Settings elements
        this.settingsBtn = document.getElementById('settings-btn');
        this.settingsModal = document.getElementById('settings-modal');
        this.settingsOverlay = document.getElementById('settings-overlay');
        this.settingsClose = document.getElementById('settings-close');

        // Data
        this.events = [];
        this.filteredEvents = [];
        this.currentFilter = 'all';
        this.currentSort = 'time-desc';
        this.searchQuery = '';
        this.socket = null;

        // Advanced filters state
        this.advancedFiltersState = {
            scoreMin: null,
            scoreMax: null,
            riskLevels: ['low', 'medium', 'high', 'extreme'],
            mcapMin: null,
            mcapMax: null,
            timeRange: 'all'
        };

        // Settings state
        this.settings = {
            notifyExceptional: true,
            notifyStrong: false,
            soundEnabled: false,
            autoRefresh: true,
            compactMode: false
        };

        this.loadSettings();
        this.init();
    }

    init() {
        this.setupEventListeners();
        this.loadEvents();
        this.initializeWebSocket();
    }

    setupEventListeners() {
        // Quality filters
        const filterButtons = document.querySelectorAll('.filter-btn');
        filterButtons.forEach(btn => {
            btn.addEventListener('click', () => {
                filterButtons.forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                this.currentFilter = btn.dataset.filter;
                this.filterAndRender();
            });
        });

        // Search
        this.searchInput.addEventListener('input', (e) => {
            this.searchQuery = e.target.value.toLowerCase();
            this.searchClear.style.display = this.searchQuery ? 'flex' : 'none';
            this.filterAndRender();
        });

        this.searchClear.addEventListener('click', () => {
            this.searchInput.value = '';
            this.searchQuery = '';
            this.searchClear.style.display = 'none';
            this.filterAndRender();
        });

        // Sort
        this.sortSelect.addEventListener('change', (e) => {
            this.currentSort = e.target.value;
            this.filterAndRender();
        });

        // Advanced filters toggle
        this.advancedFilterBtn.addEventListener('click', () => {
            const isVisible = this.advancedFilters.style.display === 'block';
            this.advancedFilters.style.display = isVisible ? 'none' : 'block';
            this.advancedFilterBtn.classList.toggle('active');
        });

        // Advanced filters apply
        document.getElementById('apply-filters').addEventListener('click', () => {
            this.applyAdvancedFilters();
        });

        document.getElementById('reset-filters').addEventListener('click', () => {
            this.resetAdvancedFilters();
        });

        // Modal events
        this.modalOverlay.addEventListener('click', () => this.closeTokenModal());
        this.modalClose.addEventListener('click', () => this.closeTokenModal());

        // Settings
        this.settingsBtn.addEventListener('click', () => this.openSettings());
        this.settingsOverlay.addEventListener('click', () => this.closeSettings());
        this.settingsClose.addEventListener('click', () => this.closeSettings());

        // Settings checkboxes
        document.getElementById('notify-exceptional').addEventListener('change', (e) => {
            this.settings.notifyExceptional = e.target.checked;
            this.saveSettings();
        });

        document.getElementById('notify-strong').addEventListener('change', (e) => {
            this.settings.notifyStrong = e.target.checked;
            this.saveSettings();
        });

        document.getElementById('sound-enabled').addEventListener('change', (e) => {
            this.settings.soundEnabled = e.target.checked;
            this.saveSettings();
        });

        document.getElementById('auto-refresh').addEventListener('change', (e) => {
            this.settings.autoRefresh = e.target.checked;
            this.saveSettings();
        });

        document.getElementById('compact-mode').addEventListener('change', (e) => {
            this.settings.compactMode = e.target.checked;
            this.saveSettings();
            this.filterAndRender(); // Re-render with compact mode
        });

        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                this.closeTokenModal();
                this.closeSettings();
            }
            if (e.key === '/' && !this.isTyping()) {
                e.preventDefault();
                this.searchInput.focus();
            }
        });
    }

    isTyping() {
        return document.activeElement.tagName === 'INPUT' ||
               document.activeElement.tagName === 'TEXTAREA';
    }

    loadSettings() {
        const saved = localStorage.getItem('bagsIntelSettings');
        if (saved) {
            this.settings = { ...this.settings, ...JSON.parse(saved) };

            // Apply settings to checkboxes
            setTimeout(() => {
                document.getElementById('notify-exceptional').checked = this.settings.notifyExceptional;
                document.getElementById('notify-strong').checked = this.settings.notifyStrong;
                document.getElementById('sound-enabled').checked = this.settings.soundEnabled;
                document.getElementById('auto-refresh').checked = this.settings.autoRefresh;
                document.getElementById('compact-mode').checked = this.settings.compactMode;
            }, 100);
        }
    }

    saveSettings() {
        localStorage.setItem('bagsIntelSettings', JSON.stringify(this.settings));
    }

    applyAdvancedFilters() {
        this.advancedFiltersState.scoreMin = parseInt(document.getElementById('score-min').value) || null;
        this.advancedFiltersState.scoreMax = parseInt(document.getElementById('score-max').value) || null;
        this.advancedFiltersState.mcapMin = parseInt(document.getElementById('mcap-min').value) || null;
        this.advancedFiltersState.mcapMax = parseInt(document.getElementById('mcap-max').value) || null;
        this.advancedFiltersState.timeRange = document.getElementById('time-range').value;

        // Risk levels
        const riskCheckboxes = document.querySelectorAll('.checkbox-group input[type="checkbox"]');
        this.advancedFiltersState.riskLevels = Array.from(riskCheckboxes)
            .filter(cb => cb.checked)
            .map(cb => cb.value);

        this.filterAndRender();
        this.advancedFilters.style.display = 'none';
        this.advancedFilterBtn.classList.remove('active');
    }

    resetAdvancedFilters() {
        document.getElementById('score-min').value = '';
        document.getElementById('score-max').value = '';
        document.getElementById('mcap-min').value = '';
        document.getElementById('mcap-max').value = '';
        document.getElementById('time-range').value = 'all';

        document.querySelectorAll('.checkbox-group input[type="checkbox"]').forEach(cb => {
            cb.checked = true;
        });

        this.advancedFiltersState = {
            scoreMin: null,
            scoreMax: null,
            riskLevels: ['low', 'medium', 'high', 'extreme'],
            mcapMin: null,
            mcapMax: null,
            timeRange: 'all'
        };

        this.filterAndRender();
    }

    initializeWebSocket() {
        if (typeof io === 'undefined') {
            const script = document.createElement('script');
            script.src = 'https://cdn.socket.io/4.5.4/socket.io.min.js';
            script.onload = () => this.connectWebSocket();
            document.head.appendChild(script);
        } else {
            this.connectWebSocket();
        }
    }

    connectWebSocket() {
        try {
            this.socket = io('http://localhost:5000', {
                transports: ['websocket', 'polling']
            });

            this.socket.on('connect', () => {
                console.log('🔌 WebSocket connected');
                this.showConnectionStatus('connected');
            });

            this.socket.on('disconnect', () => {
                console.log('🔌 WebSocket disconnected');
                this.showConnectionStatus('disconnected');
            });

            this.socket.on('new_graduation', (event) => {
                console.log('📡 New graduation received:', event.token?.symbol);
                this.addNewEvent(event);
            });

        } catch (error) {
            console.error('WebSocket connection failed:', error);
            this.fallbackToPolling();
        }
    }

    showConnectionStatus(status) {
        const statusDot = document.querySelector('.pulse-dot');
        if (statusDot) {
            if (status === 'connected') {
                statusDot.style.background = '#39FF14';
                statusDot.style.boxShadow = '0 0 8px #39FF14';
            } else {
                statusDot.style.background = '#FF6B6B';
                statusDot.style.boxShadow = '0 0 8px #FF6B6B';
            }
        }
    }

    fallbackToPolling() {
        if (this.settings.autoRefresh) {
            setInterval(() => {
                this.loadEvents();
            }, 30000);
        }
    }

    addNewEvent(event) {
        this.events.unshift(event);

        if (this.events.length > 100) {
            this.events.pop();
        }

        this.filterAndRender();
        this.updateTrackedCount();
        this.showNewEventNotification(event);

        // Check if we should notify
        const score = event.scores?.overall || 0;
        if ((this.settings.notifyExceptional && score >= 80) ||
            (this.settings.notifyStrong && score >= 65)) {
            if (this.settings.soundEnabled) {
                this.playNotificationSound();
            }
        }
    }

    playNotificationSound() {
        // Simple beep using Web Audio API
        try {
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
        } catch (error) {
            console.error('Failed to play sound:', error);
        }
    }

    showNewEventNotification(event) {
        const notification = document.createElement('div');
        notification.className = 'new-event-notification';
        notification.innerHTML = `
            <div class="notification-content">
                <span class="notification-icon">🎯</span>
                <div class="notification-text">
                    <strong>${event.token?.symbol || 'New Token'}</strong>
                    <span>Score: ${event.scores?.overall || 0}/100</span>
                </div>
            </div>
        `;

        document.body.appendChild(notification);
        setTimeout(() => notification.classList.add('show'), 10);

        setTimeout(() => {
            notification.classList.remove('show');
            setTimeout(() => notification.remove(), 300);
        }, 5000);
    }

    async loadEvents() {
        try {
            const response = await fetch('/api/bags-intel/graduations');
            const data = await response.json();

            if (data.success) {
                this.events = data.events || [];
                this.filterAndRender();
                this.updateTrackedCount();
            }
        } catch (error) {
            console.error('Failed to load events:', error);
            this.showEmptyState();
        } finally {
            this.hideLoading();
        }
    }

    filterAndRender() {
        let filtered = [...this.events];

        // Apply quality filter
        if (this.currentFilter !== 'all') {
            filtered = filtered.filter(event => {
                const quality = event.scores?.quality?.toLowerCase();
                return quality === this.currentFilter;
            });
        }

        // Apply search
        if (this.searchQuery) {
            filtered = filtered.filter(event => {
                const name = event.token?.name?.toLowerCase() || '';
                const symbol = event.token?.symbol?.toLowerCase() || '';
                return name.includes(this.searchQuery) || symbol.includes(this.searchQuery);
            });
        }

        // Apply advanced filters
        if (this.advancedFiltersState.scoreMin !== null) {
            filtered = filtered.filter(e => (e.scores?.overall || 0) >= this.advancedFiltersState.scoreMin);
        }
        if (this.advancedFiltersState.scoreMax !== null) {
            filtered = filtered.filter(e => (e.scores?.overall || 0) <= this.advancedFiltersState.scoreMax);
        }
        if (this.advancedFiltersState.mcapMin !== null) {
            filtered = filtered.filter(e => (e.market?.mcap_usd || 0) >= this.advancedFiltersState.mcapMin);
        }
        if (this.advancedFiltersState.mcapMax !== null) {
            filtered = filtered.filter(e => (e.market?.mcap_usd || 0) <= this.advancedFiltersState.mcapMax);
        }
        if (this.advancedFiltersState.riskLevels.length > 0) {
            filtered = filtered.filter(e => this.advancedFiltersState.riskLevels.includes(e.scores?.risk?.toLowerCase()));
        }
        if (this.advancedFiltersState.timeRange !== 'all') {
            const cutoff = this.getTimeCutoff(this.advancedFiltersState.timeRange);
            filtered = filtered.filter(e => new Date(e.timestamp) >= cutoff);
        }

        // Apply sorting
        filtered = this.sortEvents(filtered);

        this.filteredEvents = filtered;
        this.renderEvents();
        this.updateStats();
    }

    getTimeCutoff(range) {
        const now = new Date();
        switch (range) {
            case '1h': return new Date(now - 60 * 60 * 1000);
            case '6h': return new Date(now - 6 * 60 * 60 * 1000);
            case '24h': return new Date(now - 24 * 60 * 60 * 1000);
            case '7d': return new Date(now - 7 * 24 * 60 * 60 * 1000);
            default: return new Date(0);
        }
    }

    sortEvents(events) {
        const sorted = [...events];

        switch (this.currentSort) {
            case 'time-desc':
                return sorted.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
            case 'time-asc':
                return sorted.sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));
            case 'score-desc':
                return sorted.sort((a, b) => (b.scores?.overall || 0) - (a.scores?.overall || 0));
            case 'score-asc':
                return sorted.sort((a, b) => (a.scores?.overall || 0) - (b.scores?.overall || 0));
            case 'mcap-desc':
                return sorted.sort((a, b) => (b.market?.mcap_usd || 0) - (a.market?.mcap_usd || 0));
            case 'mcap-asc':
                return sorted.sort((a, b) => (a.market?.mcap_usd || 0) - (b.market?.mcap_usd || 0));
            default:
                return sorted;
        }
    }

    updateStats() {
        this.showingCount.textContent = this.filteredEvents.length;

        if (this.filteredEvents.length > 0) {
            const avgScore = this.filteredEvents.reduce((sum, e) => sum + (e.scores?.overall || 0), 0) / this.filteredEvents.length;
            this.avgScore.textContent = Math.round(avgScore);

            const totalMcap = this.filteredEvents.reduce((sum, e) => sum + (e.market?.mcap_usd || 0), 0);
            this.totalMcap.textContent = this.formatCurrency(totalMcap);
        } else {
            this.avgScore.textContent = '0';
            this.totalMcap.textContent = '$0';
        }
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

        // Apply compact mode if enabled
        if (this.settings.compactMode) {
            article.classList.add('compact');
        }

        // Set data attribute for modal
        article.dataset.tokenId = event.token?.mint;

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

        // DEXTools link
        const dextoolsLink = card.querySelector('.dextools-link');
        if (dextoolsLink) {
            dextoolsLink.href = `https://www.dextools.io/app/en/solana/pair-explorer/${mint}`;
        }

        // Swap button
        const swapBtn = card.querySelector('.swap-btn');
        if (swapBtn) {
            swapBtn.addEventListener('click', () => {
                this.swapToken(mint);
            });
        }

        // Action buttons
        const copyLink = card.querySelector('.copy-link');
        copyLink.addEventListener('click', (e) => {
            e.preventDefault();
            this.copyToClipboard(mint);
        });

        const shareBtn = card.querySelector('.share-btn');
        shareBtn.addEventListener('click', () => {
            this.shareToken(event);
        });

        const viewDetailBtn = card.querySelector('.view-detail-btn');
        viewDetailBtn.addEventListener('click', () => {
            this.openTokenModal(event);
        });

        // Load founder research asynchronously
        this.loadFounderResearch(card, mint);

        // Animation
        article.style.opacity = '0';
        article.style.transform = 'translateY(20px)';

        setTimeout(() => {
            article.style.transition = 'all 0.4s ease';
            article.style.opacity = '1';
            article.style.transform = 'translateY(0)';
        }, 50);

        return card;
    }

    swapToken(mint) {
        // TODO: Get actual referral code from bags.fm
        const referralCode = 'jarvis-intel';
        const swapUrl = `https://bags.fm/swap?token=${mint}&ref=${referralCode}`;
        window.open(swapUrl, '_blank');
    }

    async loadFounderResearch(card, mint) {
        try {
            const response = await fetch(`/api/bags-intel/research/${mint}`);
            const data = await response.json();

            if (data.success && data.research) {
                this.populateFounderResearch(card, data.research);
            }
        } catch (error) {
            console.error('Failed to load founder research:', error);
        }
    }

    populateFounderResearch(card, research) {
        const founderProfile = research.founder_profile;
        const pmf = research.product_market_fit;

        // Show founder section if we have data
        const founderSection = card.querySelector('.founder-research-section');
        if (founderProfile && founderSection) {
            founderSection.style.display = 'block';

            // Twitter link
            const twitterLink = card.querySelector('.twitter-link');
            if (founderProfile.twitter_handle && twitterLink) {
                twitterLink.href = `https://twitter.com/${founderProfile.twitter_handle}`;
                twitterLink.style.display = 'inline-flex';
            }

            // LinkedIn link
            const linkedinLink = card.querySelector('.linkedin-link');
            if (founderProfile.linkedin_url && linkedinLink) {
                linkedinLink.href = founderProfile.linkedin_url;
                linkedinLink.style.display = 'inline-flex';
            }

            // GitHub link
            const githubLink = card.querySelector('.github-link');
            if (founderProfile.github_username && githubLink) {
                githubLink.href = `https://github.com/${founderProfile.github_username}`;
                githubLink.style.display = 'inline-flex';
            }

            // Doxxed status
            const doxxedBadge = card.querySelector('.doxxed-badge');
            const doxxedConfidence = card.querySelector('.doxxed-confidence');
            if (doxxedBadge && doxxedConfidence) {
                if (founderProfile.is_doxxed) {
                    doxxedBadge.textContent = '✅ Doxxed';
                    doxxedBadge.classList.add('doxxed');
                    doxxedConfidence.textContent = `${Math.round(founderProfile.doxx_confidence * 100)}% confidence`;
                } else {
                    doxxedBadge.textContent = '❓ Anonymous';
                    doxxedBadge.classList.add('anonymous');
                    doxxedConfidence.textContent = `${Math.round(founderProfile.doxx_confidence * 100)}% confidence`;
                }
            }

            // Green/Red flags
            const founderGreenFlags = card.querySelector('.founder-green-flags');
            const founderRedFlags = card.querySelector('.founder-red-flags');

            if (founderGreenFlags && founderProfile.green_flags?.length > 0) {
                founderGreenFlags.innerHTML = founderProfile.green_flags.map(flag => `<div>${flag}</div>`).join('');
            }

            if (founderRedFlags && founderProfile.red_flags?.length > 0) {
                founderRedFlags.innerHTML = founderProfile.red_flags.map(flag => `<div>${flag}</div>`).join('');
            }
        }

        // Show PMF section if we have data
        const pmfSection = card.querySelector('.pmf-section');
        if (pmf && pmfSection) {
            pmfSection.style.display = 'block';

            // PMF score bar
            const pmfFill = card.querySelector('.pmf-score-fill');
            const pmfValue = card.querySelector('.pmf-score-value');
            if (pmfFill && pmfValue) {
                pmfFill.style.width = `${pmf.pmf_score}%`;
                pmfValue.textContent = Math.round(pmf.pmf_score);
            }

            // PMF details
            const pmfUtility = card.querySelector('.pmf-utility');
            const pmfMarket = card.querySelector('.pmf-market');
            const pmfCompetition = card.querySelector('.pmf-competition');
            const pmfCommunity = card.querySelector('.pmf-community');

            if (pmfUtility) pmfUtility.textContent = `Utility: ${pmf.token_utility} (${Math.round(pmf.utility_score)}/100)`;
            if (pmfMarket) pmfMarket.textContent = `Market: ${pmf.target_market} (${pmf.market_size_estimate})`;
            if (pmfCompetition) pmfCompetition.textContent = `Competition: ${pmf.competition_level}`;
            if (pmfCommunity) pmfCommunity.textContent = `Community: ${pmf.community_size} members (${pmf.community_engagement} engagement)`;
        }
    }

    shareToken(event) {
        const url = `https://bags.fm/token/${event.token?.mint}`;
        const text = `Check out ${event.token?.symbol} on Bags.fm - Score: ${event.scores?.overall}/100`;

        if (navigator.share) {
            navigator.share({
                title: event.token?.name,
                text: text,
                url: url
            }).catch(err => console.log('Share failed:', err));
        } else {
            this.copyToClipboard(url, 'Link copied to clipboard!');
        }
    }

    openTokenModal(event) {
        this.tokenModal.classList.add('active');
        document.body.style.overflow = 'hidden';

        // Render detailed view
        this.modalBody.innerHTML = `
            <div class="token-detail">
                <div class="token-detail-header">
                    <img src="${event.token?.image_url || this.generateAvatar(event.token?.symbol)}" alt="${event.token?.name}" class="token-detail-avatar">
                    <div>
                        <h2>${event.token?.name}</h2>
                        <p>$${event.token?.symbol}</p>
                    </div>
                </div>

                <div class="token-detail-score">
                    <h3>Intel Score: ${event.scores?.overall}/100 ${this.getQualityEmoji(event.scores?.quality)}</h3>
                    <p>Quality: ${event.scores?.quality} | Risk: ${event.scores?.risk}</p>
                </div>

                ${event.ai_analysis?.summary ? `
                <div class="token-detail-section">
                    <h3>🤖 Grok Analysis</h3>
                    <p>${event.ai_analysis.summary}</p>
                </div>
                ` : ''}

                <div class="token-detail-section">
                    <h3>📊 Market Metrics</h3>
                    <ul>
                        <li>Market Cap: ${this.formatCurrency(event.market?.mcap_usd)}</li>
                        <li>Liquidity: ${this.formatCurrency(event.market?.liquidity_usd)}</li>
                        <li>Price: $${event.market?.price_usd?.toFixed(8) || '0'}</li>
                        <li>24h Volume: ${this.formatCurrency(event.market?.volume_24h_usd)}</li>
                    </ul>
                </div>

                <div class="token-detail-section">
                    <h3>📈 Bonding Curve</h3>
                    <ul>
                        <li>Duration: ${this.formatDuration(event.bonding_curve?.duration_seconds)}</li>
                        <li>Volume: ${event.bonding_curve?.volume_sol?.toFixed(2)} SOL</li>
                        <li>Unique Buyers: ${event.bonding_curve?.unique_buyers}</li>
                        <li>Buy/Sell Ratio: ${event.bonding_curve?.buy_sell_ratio?.toFixed(2)}x</li>
                    </ul>
                </div>

                <div class="token-detail-section">
                    <h3>🎯 Score Breakdown</h3>
                    <ul>
                        <li>Bonding: ${Math.round(event.scores?.bonding || 0)}/100</li>
                        <li>Creator: ${Math.round(event.scores?.creator || 0)}/100</li>
                        <li>Social: ${Math.round(event.scores?.social || 0)}/100</li>
                        <li>Market: ${Math.round(event.scores?.market || 0)}/100</li>
                        <li>Distribution: ${Math.round(event.scores?.distribution || 0)}/100</li>
                    </ul>
                </div>

                ${event.flags?.green?.length > 0 ? `
                <div class="token-detail-section">
                    <h3>✅ Green Flags</h3>
                    <ul>
                        ${event.flags.green.map(flag => `<li>${flag}</li>`).join('')}
                    </ul>
                </div>
                ` : ''}

                ${event.flags?.red?.length > 0 ? `
                <div class="token-detail-section">
                    <h3>🚨 Red Flags</h3>
                    <ul>
                        ${event.flags.red.map(flag => `<li>${flag}</li>`).join('')}
                    </ul>
                </div>
                ` : ''}

                <div class="token-detail-actions">
                    <a href="https://bags.fm/token/${event.token?.mint}" target="_blank" class="detail-action-btn primary">View on Bags.fm</a>
                    <a href="https://dexscreener.com/solana/${event.token?.mint}" target="_blank" class="detail-action-btn">DexScreener</a>
                    <button class="detail-action-btn" onclick="navigator.clipboard.writeText('${event.token?.mint}')">Copy CA</button>
                </div>
            </div>
        `;
    }

    closeTokenModal() {
        this.tokenModal.classList.remove('active');
        document.body.style.overflow = '';
    }

    openSettings() {
        this.settingsModal.classList.add('active');
        document.body.style.overflow = 'hidden';
    }

    closeSettings() {
        this.settingsModal.classList.remove('active');
        document.body.style.overflow = '';
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

    copyToClipboard(text, message = 'Contract address copied!') {
        navigator.clipboard.writeText(text).then(() => {
            const notification = document.createElement('div');
            notification.textContent = message;
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
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    new BagsIntelFeed();
});

// Additional CSS for modal details
const style = document.createElement('style');
style.textContent = `
    .token-detail {
        color: var(--pure-white);
    }

    .token-detail-header {
        display: flex;
        align-items: center;
        gap: 20px;
        margin-bottom: 24px;
        padding-bottom: 24px;
        border-bottom: 1px solid var(--glass-border);
    }

    .token-detail-avatar {
        width: 80px;
        height: 80px;
        border-radius: 50%;
        border: 2px solid var(--glass-border);
    }

    .token-detail-header h2 {
        font-family: var(--font-display);
        font-size: 32px;
        margin-bottom: 4px;
    }

    .token-detail-header p {
        font-family: var(--font-mono);
        color: var(--text-grey);
        font-size: 16px;
    }

    .token-detail-score {
        background: linear-gradient(135deg, rgba(57, 255, 20, 0.1), rgba(57, 255, 20, 0.05));
        border: 1px solid rgba(57, 255, 20, 0.2);
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 24px;
        text-align: center;
    }

    .token-detail-score h3 {
        font-size: 28px;
        margin-bottom: 8px;
        color: var(--accent-green);
    }

    .token-detail-section {
        margin-bottom: 24px;
    }

    .token-detail-section h3 {
        font-size: 18px;
        margin-bottom: 12px;
        color: var(--pure-white);
    }

    .token-detail-section ul {
        list-style: none;
        display: flex;
        flex-direction: column;
        gap: 8px;
    }

    .token-detail-section li {
        padding: 10px;
        background: var(--glass-bg);
        border: 1px solid var(--glass-border);
        border-radius: 8px;
        font-size: 14px;
        color: var(--light-grey);
    }

    .token-detail-actions {
        display: flex;
        gap: 12px;
        margin-top: 24px;
        flex-wrap: wrap;
    }

    .detail-action-btn {
        flex: 1;
        min-width: 150px;
        padding: 12px 24px;
        border: 1px solid var(--glass-border);
        background: var(--glass-bg);
        color: var(--light-grey);
        text-decoration: none;
        text-align: center;
        border-radius: 8px;
        font-size: 14px;
        font-weight: 600;
        cursor: pointer;
        transition: all 0.2s ease;
        font-family: var(--font-body);
    }

    .detail-action-btn:hover {
        background: var(--glass-hover);
        border-color: var(--accent-green);
        color: var(--accent-green);
        transform: translateY(-2px);
    }

    .detail-action-btn.primary {
        background: var(--accent-green);
        color: var(--dark-bg);
        border-color: var(--accent-green);
    }

    .detail-action-btn.primary:hover {
        box-shadow: 0 4px 12px rgba(57, 255, 20, 0.4);
    }
`;
document.head.appendChild(style);
