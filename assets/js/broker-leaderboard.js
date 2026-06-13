document.addEventListener('DOMContentLoaded', () => {
    const elements = {
        grid: document.getElementById('leaderboard-grid'),
        search: document.getElementById('leaderboard-search'),
        sortTabs: document.querySelectorAll('.sort-tab'),
        totalBrokers: document.getElementById('total-brokers'),
        activeToday: document.getElementById('active-today'),
        scrapedAt: document.getElementById('scraped-at'),
        marquee: document.getElementById('indices-marquee-track'),
        podiumSection: document.getElementById('podium-section'),
        modal: document.getElementById('stock-modal'),
        modalBody: document.getElementById('modal-body'),
        modalCloseBtn: document.getElementById('modal-close'),
        modalBackdrop: document.getElementById('modal-backdrop'),
    };

    const DATA_ROOT = window.location.pathname.includes('/pages/') ? '../data/' : 'data/';
    let allBrokers = [];
    let securitiesMap = {};
    let currentSort = 'todayTurnover';
    let animationTimer = null;
    let podiumClickHandler = null;
    let marketPrices = {};
    let lastBroker = null;

    const TOOLTIPS = {
        rating: 'Average user rating out of 5 stars',
        totalRatings: 'Total number of user ratings received',
        shareTransfer: 'Average days taken to transfer shares to client demat account',
        cashDeposit: 'Average days taken to deposit cash proceeds to client bank account',
        todayTurnover: 'Total buy + sell amount transacted today through this broker',
        thirtyDayTurnover: 'Total turnover over the trailing 30-day period',
        branches: 'Total number of physical branch offices nationwide',
        buyAmount: 'Total value of shares purchased by clients through this broker today',
        sellAmount: 'Total value of shares sold by clients through this broker today',
        buyRate: 'Average per-share rate at which clients bought today',
        sellRate: 'Average per-share rate at which clients sold today',
    };

    const SORT_METRIC_LABEL = {
        todayTurnover: 'Today\'s Turnover',
        thirtyDayTurnover: '30-Day Turnover',
        rating: 'Avg Rating',
        mostRated: 'Total Reviews',
        branches: 'Total Branches',
    };

    function safeText(value) {
        return String(value ?? '').replace(/[&<>"']/g, (c) => {
            const m = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
            return m[c] || c;
        });
    }

    function formatIndexChange(changeValue, perChange) {
        const safeChange = Number(changeValue);
        const safePer = Number(perChange);
        if (!Number.isFinite(safeChange) || !Number.isFinite(safePer)) return '';
        const sign = safeChange > 0 ? '+' : '';
        return `${sign}${safeChange.toFixed(2)} (${sign}${safePer.toFixed(2)}%)`;
    }

    async function loadIndicesMarquee() {
        if (!elements.marquee) return;
        try {
            const res = await fetch(`${DATA_ROOT}market/indices.json`, { cache: 'no-store' });
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const indices = await res.json();
            if (!Array.isArray(indices) || indices.length === 0) {
                elements.marquee.innerHTML = '<span class="text-sm text-[#a0a0a0]">No indices available.</span>';
                return;
            }
            const itemsHtml = indices.map((idx) => {
                const name = idx.index ?? idx.indexName ?? 'Index';
                const close = idx.close ?? idx.currentValue ?? '';
                const change = idx.change ?? 0;
                const perChange = idx.perChange ?? 0;
                const isUp = Number(change) >= 0;
                const color = isUp ? '#22c55e' : '#ef4444';
                const changeText = formatIndexChange(change, perChange);
                return `<span class="inline-flex items-center gap-2 text-[0.82rem] text-[#a0a0a0]">
                    <span class="mr-1 font-bold text-white">${safeText(name)}:</span>
                    <span>${safeText(close)}</span>
                    <span style="color:${color}; margin-left:0.5rem;">${safeText(changeText)}</span>
                </span>`;
            }).join('');
            elements.marquee.innerHTML = itemsHtml + itemsHtml;
        } catch {
            elements.marquee.innerHTML = '<span class="text-sm text-[#a0a0a0]">Unable to load market indices.</span>';
        }
    }

    async function loadSecurities() {
        try {
            const res = await fetch(`${DATA_ROOT}all_securities.json`, { cache: 'no-store' });
            if (!res.ok) return;
            const list = await res.json();
            if (!Array.isArray(list)) return;
            list.forEach(s => { securitiesMap[s.symbol] = s; });
        } catch { }
    }

    async function loadMarketPrices() {
        try {
            const res = await fetch(`${DATA_ROOT}market/top_stocks.json`, { cache: 'no-store' });
            if (!res.ok) return;
            const data = await res.json();
            Object.values(data).forEach(section => {
                if (Array.isArray(section)) {
                    section.forEach(s => {
                        if (s.symbol) {
                            const price = s.ltp ?? s.lastTradedPrice;
                            if (price != null) marketPrices[s.symbol] = price;
                        }
                    });
                }
            });
        } catch { }
    }

    function formatNepaliNum(value, digits = 0) {
        const num = Number(value);
        if (!Number.isFinite(num)) return '-';
        const fixed = num.toFixed(digits);
        const parts = fixed.split('.');
        let intPart = parts[0];
        const decPart = parts[1] || '';
        const negative = intPart.startsWith('-');
        if (negative) intPart = intPart.slice(1);
        if (intPart.length <= 3) {
            intPart = intPart.replace(/\B(?=(\d{3})+(?!\d))/g, ',');
        } else {
            const last3 = intPart.slice(-3);
            const rest = intPart.slice(0, -3);
            const groups = [];
            let i = rest.length;
            while (i > 0) {
                const start = Math.max(0, i - 2);
                groups.unshift(rest.slice(start, i));
                i = start;
            }
            intPart = groups.join(',') + ',' + last3;
        }
        return (negative ? '-' : '') + intPart + (decPart ? '.' + decPart : '');
    }

    function formatCurrency(value) {
        const num = Number(value);
        if (!Number.isFinite(num)) return '-';
        if (num >= 1e9) return 'Rs. ' + formatNepaliNum(num / 1e9, 2) + ' B';
        if (num >= 1e7) return 'Rs. ' + formatNepaliNum(num / 1e7, 2) + ' Cr';
        if (num >= 1e5) return 'Rs. ' + formatNepaliNum(num / 1e5, 2) + ' L';
        return 'Rs. ' + formatNepaliNum(num, 2);
    }

    function formatNumber(value, digits = 0) {
        return formatNepaliNum(value, digits);
    }

    function formatRating(value) {
        const num = Number(value);
        if (!Number.isFinite(num)) return '-';
        return num.toFixed(2);
    }

    function renderStars(rating) {
        const num = Number(rating);
        if (!Number.isFinite(num)) return '';
        const full = Math.floor(num);
        const half = num - full >= 0.5;
        let stars = '';
        for (let i = 0; i < full; i++) stars += '<i class="fa-solid fa-star"></i>';
        if (half) stars += '<i class="fa-solid fa-star-half-stroke"></i>';
        const empty = 5 - full - (half ? 1 : 0);
        for (let i = 0; i < empty; i++) stars += '<i class="fa-regular fa-star"></i>';
        return stars;
    }

    function getSortValue(broker, sortKey) {
        switch (sortKey) {
            case 'todayTurnover':
                return broker.todayStats ? Number(broker.todayStats.totalAmount) : -1;
            case 'thirtyDayTurnover':
                return Number(broker.thirtyDaysTurnover) || 0;
            case 'rating':
                return Number(broker.rating?.averageRating) || 0;
            case 'mostRated':
                return Number(broker.rating?.totalRatings) || 0;
            case 'branches':
                return Number(broker.totalBranches) || 0;
            default:
                return 0;
        }
    }

    function getSortLabel(sortKey) {
        return SORT_METRIC_LABEL[sortKey] || sortKey;
    }

    function getSortDisplayValue(broker, sortKey) {
        const val = getSortValue(broker, sortKey);
        switch (sortKey) {
            case 'rating':
                return formatRating(val) + ' / 5';
            case 'mostRated':
                return formatNumber(val) + ' reviews';
            case 'branches':
                return formatNumber(val) + ' branches';
            default:
                return formatCurrency(val);
        }
    }

    function getRankClass(index) {
        if (index === 0) return 'top-1';
        if (index === 1) return 'top-2';
        if (index === 2) return 'top-3';
        return '';
    }

    function getSortUnit(sortKey) {
        switch (sortKey) {
            case 'todayTurnover':
            case 'thirtyDayTurnover':
                return 'currency';
            default:
                return 'other';
        }
    }

    function getMaxSortValue(sortedBrokers, sortKey) {
        if (sortedBrokers.length === 0) return 1;
        const top = getSortValue(sortedBrokers[0], sortKey);
        return top > 0 ? top : 1;
    }

    function getMembershipLabel(membership) {
        const m = String(membership || '').toLowerCase();
        if (m.includes('trading cum clearing')) return 'TCCM';
        if (m.includes('trading cum self')) return 'TCSCM';
        return membership || '';
    }

    function openBrokerModal(broker) {
        if (!elements.modal || !broker) return;
        lastBroker = broker;
        elements.modal.classList.add('show');
        document.body.style.overflow = 'hidden';

        const ts = broker.todayStats;
        const membership = getMembershipLabel(broker.membershipType);
        const districts = Array.isArray(broker.districts) ? broker.districts.join(', ') : '';
        const provinces = broker.provinces ? [broker.provinces] : [];
        const membershipTag = membership ? `<span class="modal-broker-tag"><i class="fa-solid fa-building"></i> ${safeText(membership)}</span>` : '';
        const phoneTag = broker.phone ? `<span class="modal-broker-tag"><i class="fa-solid fa-phone"></i> ${safeText(broker.phone)}</span>` : '';
        const tmsUrl = broker.tmsLink || broker.tmsUrl || '';
        const tmsTag = tmsUrl ? `<a href="https://${safeText(tmsUrl)}" target="_blank" rel="noopener" class="modal-broker-tag" style="text-decoration:none;"><i class="fa-solid fa-globe"></i> ${safeText(tmsUrl)}</a>` : '';

        const ratingHtml = broker.rating
            ? `<span style="display:inline-flex;align-items:center;gap:0.4rem;">
                <span style="color:#fbbf24;">${renderStars(broker.rating.averageRating)}</span>
                <span style="color:#e0e0e0;font-weight:700;font-size:1.1rem;">${formatRating(broker.rating.averageRating)}</span>
                <span style="color:#a0a0a0;font-size:0.85rem;">(${formatNumber(broker.rating.totalRatings)} reviews)</span>
               </span>`
            : '<span style="color:#a0a0a0;">N/A</span>';

        const todayHtml = ts ? `
            <div class="modal-section">
                <div class="modal-section-title"><i class="fa-solid fa-chart-line" style="margin-right:0.35rem;"></i>Today's Activity</div>
                <div class="modal-today-grid">
                    <div class="modal-today-item">
                        <span class="label"><i class="fa-solid fa-arrow-up" style="margin-right:0.2rem;font-size:0.55rem;"></i>Buy Amount</span>
                        <span class="value green">${formatCurrency(ts.buyAmount)}</span>
                    </div>
                    <div class="modal-today-item">
                        <span class="label"><i class="fa-solid fa-arrow-down" style="margin-right:0.2rem;font-size:0.55rem;"></i>Sell Amount</span>
                        <span class="value red">${formatCurrency(ts.sellAmount)}</span>
                    </div>
                    <div class="modal-today-item">
                        <span class="label">Buy Transactions</span>
                        <span class="value">${formatNumber(ts.buyTransactions)}</span>
                    </div>
                    <div class="modal-today-item">
                        <span class="label">Sell Transactions</span>
                        <span class="value">${formatNumber(ts.sellTransactions)}</span>
                    </div>
                </div>
            </div>` : '';

        const topStockHtml = ts?.topStock ? `
            <div class="modal-section">
                <div class="modal-section-title"><i class="fa-solid fa-star" style="margin-right:0.35rem;"></i>Top Stock Today</div>
                <div class="modal-topstock">
                    <span class="modal-topstock-symbol clickable-stock-podium"
                        data-symbol="${safeText(ts.topStock.symbol)}" data-broker="${safeText(broker.name)}"
                        data-amount="${ts.topStock.totalAmount}" data-buy="${ts.topStock.buyAmount}"
                        data-sell="${ts.topStock.sellAmount}" data-name="${safeText(ts.topStock.name)}">
                        ${safeText(ts.topStock.symbol)}
                    </span>
                    <div class="modal-topstock-info">
                        <div class="modal-topstock-name">${safeText(ts.topStock.name)}</div>
                        <div class="modal-topstock-amount">Rs. ${formatNepaliNum(ts.topStock.totalAmount)}</div>
                    </div>
                </div>
            </div>` : '';

        const districtsHtml = districts ? `
            <div class="modal-section">
                <div class="modal-section-title"><i class="fa-solid fa-location-dot" style="margin-right:0.35rem;"></i>Service Areas</div>
                <div style="display:flex;flex-wrap:wrap;gap:0.4rem;margin-bottom:0.4rem;">
                    ${districts.split(', ').map(d => `<span class="modal-broker-tag">${safeText(d)}</span>`).join('')}
                </div>
                ${provinces.length ? `<div style="display:flex;flex-wrap:wrap;gap:0.35rem;font-size:0.72rem;color:#a0a0a0;"><span>P${safeText(provinces[0])}</span></div>` : ''}
            </div>` : '';

        elements.modalBody.innerHTML = `
            <div class="modal-body-content active">
                <div style="display:flex;align-items:center;gap:1rem;margin-bottom:1.25rem;">
                    <img src="${safeText(broker.imageUrl)}" alt="" style="width:52px;height:52px;border-radius:14px;object-fit:cover;border:2px solid rgba(255,255,255,0.08);flex-shrink:0;"
                        onerror="this.style.display='none'">
                    <div style="flex:1;min-width:0;">
                        <div style="font-size:0.7rem;color:#818cf8;font-weight:600;letter-spacing:0.3px;">Broker #${safeText(broker.code)}</div>
                        <div style="font-size:1.15rem;font-weight:700;margin:0.1rem 0 0.35rem;">${safeText(broker.name)}</div>
                        <div style="display:flex;flex-wrap:wrap;gap:0.35rem;">
                            ${tmsTag}${membershipTag}${phoneTag}
                        </div>
                    </div>
                </div>
                <div style="margin-bottom:1rem;"><div class="modal-stat-card">${ratingHtml}</div></div>
                <div class="modal-section">
                    <div class="modal-section-title"><i class="fa-solid fa-gauge-high" style="margin-right:0.35rem;"></i>Performance</div>
                    <div class="modal-pills">
                        <span class="modal-pill">
                            <span class="pill-label">Share Xfer</span>
                            <span class="pill-value amber">${broker.rating ? formatNumber(broker.rating.averageShareTransferDays, 1) : '-'}</span>
                            <span class="pill-unit">days</span>
                        </span>
                        <span class="modal-pill">
                            <span class="pill-label">Cash Deposit</span>
                            <span class="pill-value">${broker.rating ? formatNumber(broker.rating.averageCashDepositDays, 1) : '-'}</span>
                            <span class="pill-unit">days</span>
                        </span>
                        <span class="modal-pill">
                            <span class="pill-label">30-Day Turnover</span>
                            <span class="pill-value green">${formatCurrency(broker.thirtyDaysTurnover)}</span>
                        </span>
                        <span class="modal-pill">
                            <span class="pill-label">Branches</span>
                            <span class="pill-value">${broker.totalBranches || '0'}</span>
                        </span>
                    </div>
                </div>
                ${todayHtml}
                ${topStockHtml}
                ${districtsHtml}
            </div>
        `;

        document.querySelectorAll('.clickable-stock-podium').forEach(el => {
            el.addEventListener('click', (e) => {
                e.stopPropagation();
                const symbol = el.dataset.symbol;
                const brokerName = el.dataset.broker;
                openStockModal(symbol, brokerName, {
                    name: el.dataset.name,
                    totalAmount: Number(el.dataset.amount) || 0,
                    buyAmount: Number(el.dataset.buy) || 0,
                    sellAmount: Number(el.dataset.sell) || 0,
                });
            });
        });
    }

    function renderPodium(topThree) {
        const section = elements.podiumSection;
        if (!section || topThree.length < 3) return;
        section.classList.remove('hidden');

        const slots = section.querySelectorAll('.podium-slot');
        slots.forEach(s => { s.classList.remove('podium-visible'); });

        const label = getSortLabel(currentSort);

        for (let i = 0; i < 3; i++) {
            const broker = topThree[i];
            const rank = i + 1;

            document.getElementById(`podium-${rank}-img`).src = broker.imageUrl || '';
            document.getElementById(`podium-${rank}-name`).textContent = broker.name;
            document.getElementById(`podium-${rank}-code`).textContent = `Broker #${broker.code}`;
            const metricEl = document.getElementById(`podium-${rank}-metric`);
            if (metricEl) {
                metricEl.innerHTML = getSortDisplayValue(broker, currentSort) + '<small>' + label + '</small>';
            }
            document.getElementById(`podium-${rank}-stars`).innerHTML = renderStars(broker.rating?.averageRating || 0);
            document.getElementById(`podium-${rank}-reviews`).textContent = broker.rating?.totalRatings ? `${broker.rating.totalRatings} reviews` : 'No reviews';

            // Store broker reference on the slot element's dataset for click handler
            const slot = document.querySelector(`.podium-slot-${rank}`);
            if (slot) {
                slot.style.cursor = 'pointer';
                slot.dataset.brokerId = broker.id;
            }
        }

        // Add click handler to section if not already added (one-time only)
        if (!section._podiumHandlerAttached) {
            section.addEventListener('click', (e) => {
                const slot = e.target.closest('.podium-slot');
                if (slot && slot.dataset.brokerId) {
                    const brokerId = slot.dataset.brokerId;
                    const broker = allBrokers.find(b => b.id == brokerId);
                    if (broker) openBrokerModal(broker);
                }
            });
            section._podiumHandlerAttached = true;
        }

        requestAnimationFrame(() => {
            slots.forEach(s => s.classList.add('podium-visible'));
        });
    }

    function animateValue(el, start, end, duration) {
        const startTime = performance.now();
        function tick(now) {
            const elapsed = now - startTime;
            const progress = Math.min(elapsed / duration, 1);
            const eased = 1 - Math.pow(1 - progress, 3);
            const current = start + (end - start) * eased;
            el.textContent = 'Rs. ' + formatNepaliNum(Math.round(current));
            if (progress < 1) requestAnimationFrame(tick);
        }
        requestAnimationFrame(tick);
    }

    function openStockModal(symbol, brokerName, topStock) {
        if (!elements.modal || !symbol) return;
        elements.modal.classList.add('show');
        document.body.style.overflow = 'hidden';

        const sec = securitiesMap[symbol];
        const companyName = topStock?.name || sec?.companyName || sec?.securityName || symbol;
        const sector = sec?.sectorName || null;
        const instrument = sec?.instrumentType || null;
        const ltp = marketPrices[symbol];
        const canGoBack = !!lastBroker;

        elements.modalBody.innerHTML = `
            <div class="modal-body-content active">
                ${canGoBack ? `<div style="margin-bottom:0.85rem;"><button id="stock-modal-back" class="modal-back-btn" style="font-size:0.72rem;padding:0.35rem 0.8rem;background:rgba(129,140,248,0.08);"><i class="fa-solid fa-arrow-left" style="font-size:0.6rem;"></i> Back to Broker Details</button></div>` : ''}
                <div class="modal-broker-tag"><i class="fa-solid fa-building-columns"></i> Traded via ${safeText(brokerName)}</div>
                <div class="modal-symbol" style="color:${sec ? '#22c55e' : '#fbbf24'}">${safeText(symbol)}</div>
                <div class="modal-company-name">${safeText(companyName)}</div>
                ${ltp ? `
                <div style="background:rgba(34,197,94,0.06);border:1px solid rgba(34,197,94,0.12);border-radius:14px;padding:0.75rem 1rem;margin-bottom:1rem;display:flex;align-items:center;gap:0.75rem;">
                    <div style="font-size:0.62rem;color:#a0a0a0;text-transform:uppercase;letter-spacing:0.4px;">LTP</div>
                    <div style="font-size:1.35rem;font-weight:800;color:#22c55e;">Rs. ${formatNepaliNum(ltp)}</div>
                </div>` : ''}
                <div class="modal-section-title"><i class="fa-solid fa-chart-bar" style="margin-right:0.35rem;"></i>Today's Broker Activity</div>
                <div class="modal-stats">
                    <div class="modal-stat-card">
                        <div class="modal-stat-label">Total Traded</div>
                        <div class="modal-stat-value gold">${formatCurrency(topStock?.totalAmount || 0)}</div>
                    </div>
                    <div class="modal-stat-card">
                        <div class="modal-stat-label">Buy Amount</div>
                        <div class="modal-stat-value green">${formatCurrency(topStock?.buyAmount || 0)}</div>
                    </div>
                    <div class="modal-stat-card">
                        <div class="modal-stat-label">Sell Amount</div>
                        <div class="modal-stat-value red">${formatCurrency(topStock?.sellAmount || 0)}</div>
                    </div>
                    <div class="modal-stat-card">
                        <div class="modal-stat-label">Net (Buy - Sell)</div>
                        <div class="modal-stat-value ${Number(topStock?.buyAmount) > Number(topStock?.sellAmount) ? 'green' : 'red'}">
                            ${formatCurrency((Number(topStock?.buyAmount) || 0) - (Number(topStock?.sellAmount) || 0))}
                        </div>
                    </div>
                </div>
                <div style="display:flex;flex-wrap:wrap;gap:0.5rem;margin-bottom:1rem;">
                    ${sector ? `<span class="modal-sector"><i class="fa-solid fa-tag"></i> ${safeText(sector)}</span>` : ''}
                    ${instrument ? `<span class="modal-sector"><i class="fa-solid fa-chart-simple"></i> ${safeText(instrument)}</span>` : ''}
                </div>
                <a href="${DATA_ROOT === '../data/' ? '../' : ''}index.html" target="_blank" rel="noopener" style="display:inline-flex;align-items:center;gap:0.35rem;font-size:0.75rem;color:#818cf8;text-decoration:none;border:1px solid rgba(129,140,248,0.2);border-radius:999px;padding:0.3rem 0.75rem;background:rgba(129,140,248,0.06);transition:all 0.15s;">
                    <i class="fa-solid fa-chart-simple"></i> Explore ${safeText(symbol)} on Market
                    <i class="fa-solid fa-arrow-up-right-from-square" style="font-size:0.55rem;"></i>
                </a>
            </div>
        `;

        const backBtn = document.getElementById('stock-modal-back');
        if (backBtn) {
            backBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                if (lastBroker) openBrokerModal(lastBroker);
            });
        }
    }

    function closeModal() {
        if (elements.modal) {
            elements.modal.classList.remove('show');
            document.body.style.overflow = '';
        }
    }

    function render() {
        const query = (elements.search.value || '').trim().toLowerCase();

        const compareDesc = (a, b) => {
            const va = getSortValue(a, currentSort);
            const vb = getSortValue(b, currentSort);
            return vb - va;
        };

        const sorted = [...allBrokers].sort(compareDesc);

        const isSearching = !!query;
        if (isSearching) {
            elements.podiumSection.classList.add('hidden');
        } else {
            const topThree = sorted.slice(0, 3);
            renderPodium(topThree);
        }

        let listSource = sorted;
        if (isSearching) {
            listSource = sorted.filter(b =>
                b.name.toLowerCase().includes(query) ||
                b.code.toLowerCase().includes(query)
            );
        } else {
            listSource = sorted.slice(3);
        }

        if (listSource.length === 0) {
            elements.grid.innerHTML = `<div class="no-data"><i class="fa-solid fa-search text-2xl mb-2"></i><p>No more brokers to show.</p></div>`;
            return;
        }

        if (animationTimer) {
            clearTimeout(animationTimer);
            animationTimer = null;
        }

        const globalMaxVal = getMaxSortValue(sorted, currentSort);
        const isCurrency = getSortUnit(currentSort) === 'currency';

        // Build a rank lookup: broker code -> overall position in sorted list
        const rankMap = {};
        sorted.forEach((b, i) => { rankMap[b.code] = i; });

        elements.grid.innerHTML = '';

        listSource.forEach((broker, idx) => {
            const overallIdx = rankMap[broker.code] ?? idx;
            const rank = overallIdx + 1;
            const isActive = !!broker.todayStats;
            const turnover = isActive ? broker.todayStats.totalAmount : broker.latestTurnover;
            const avgRating = broker.rating?.averageRating;
            const totalRatings = broker.rating?.totalRatings;
            const rankClass = getRankClass(overallIdx);
            const sortVal = getSortValue(broker, currentSort);
            const barPct = globalMaxVal > 0 ? Math.max((sortVal / globalMaxVal) * 100, 1.5) : 1.5;

            let detailsHtml = '';
            if (isActive) {
                const ts = broker.todayStats;
                const topStock = ts.topStock;
                const clickAttr = topStock
                    ? ` style="cursor:pointer;" class="top-stock-chip clickable-stock" data-symbol="${safeText(topStock.symbol)}" data-broker="${safeText(broker.name)}" data-amount="${topStock.totalAmount}" data-buy="${topStock.buyAmount}" data-sell="${topStock.sellAmount}" data-name="${safeText(topStock.name)}"`
                    : ' class="top-stock-chip"';
                detailsHtml = `
                    <div class="broker-details" id="details-${broker.id}">
                        <div class="detail-grid">
                            <div class="detail-item">
                                <div class="detail-label">Buy Amount</div>
                                <div class="detail-value green">${formatCurrency(ts.buyAmount)}</div>
                            </div>
                            <div class="detail-item">
                                <div class="detail-label">Sell Amount</div>
                                <div class="detail-value">${formatCurrency(ts.sellAmount)}</div>
                            </div>
                            <div class="detail-item">
                                <div class="detail-label">Buy Quantity</div>
                                <div class="detail-value">${formatNumber(ts.buyQuantity)}</div>
                            </div>
                            <div class="detail-item">
                                <div class="detail-label">Buy Transactions</div>
                                <div class="detail-value">${formatNumber(ts.buyTransactions)}</div>
                            </div>
                            <div class="detail-item">
                                <div class="detail-label">Sell Quantity</div>
                                <div class="detail-value">${formatNumber(ts.sellQuantity)}</div>
                            </div>
                            <div class="detail-item">
                                <div class="detail-label">Sell Transactions</div>
                                <div class="detail-value">${formatNumber(ts.sellTransactions)}</div>
                            </div>
                            <div class="detail-item">
                                <div class="detail-label">Avg Buy Rate</div>
                                <div class="detail-value">Rs. ${formatNumber(ts.averageBuyRate, 2)}</div>
                            </div>
                            <div class="detail-item">
                                <div class="detail-label">Avg Sell Rate</div>
                                <div class="detail-value">Rs. ${formatNumber(ts.averageSellRate, 2)}</div>
                            </div>
                            ${topStock ? `
                            <div class="detail-item" style="grid-column: 1 / -1;">
                                <div class="detail-label">Top Stock Today</div>
                                <div class="detail-value flex items-center gap-2 mt-1">
                                    <span ${clickAttr}>
                                        <i class="fa-solid fa-crown" style="color:#fbbf24;font-size:0.7rem;"></i>
                                        ${safeText(topStock.symbol)} - ${safeText(topStock.name)}
                                    </span>
                                    <span style="font-size:0.75rem;color:#a0a0a0;">Rs. ${formatCurrency(topStock.totalAmount)}</span>
                                </div>
                            </div>` : ''}
                        </div>
                    </div>
                `;
            }

            const barColor = rankClass === 'top-1' ? 'bg-gradient-to-r from-amber-400 to-yellow-300' :
                             rankClass === 'top-2' ? 'bg-gradient-to-r from-slate-400 to-slate-300' :
                             rankClass === 'top-3' ? 'bg-gradient-to-r from-amber-700 to-orange-500' :
                             'bg-gradient-to-r from-indigo-500/60 to-indigo-400/40';

            const card = document.createElement('div');
            card.className = `broker-card ${rankClass}${isActive ? ' has-details' : ''}`;
            card.dataset.brokerId = broker.id;

            card.innerHTML = `
                <div class="broker-rank ${rankClass}">#${rank}</div>
                <div class="broker-info">
                    <div class="flex items-center gap-3">
                        <img class="broker-logo" src="${safeText(broker.imageUrl)}" alt="${safeText(broker.name)}" loading="lazy"
                            onerror="this.style.display='none'">
                        <div>
                            <div class="broker-name" title="${safeText(broker.name)}">${safeText(broker.name)}</div>
                            <div class="broker-code">
                                Broker #${safeText(broker.code)}
                                ${broker.totalBranches > 0 ? `&middot; ${broker.totalBranches} branch${broker.totalBranches > 1 ? 'es' : ''}` : ''}
                                ${(broker.tmsLink || broker.tmsUrl) ? `&middot; TMS: ${safeText(broker.tmsLink || broker.tmsUrl)}` : ''}
                                ${broker.membershipType ? `&middot; ${safeText(getMembershipLabel(broker.membershipType))}` : ''}
                            </div>
                        </div>
                    </div>
                    <div class="broker-metrics">
                        <span class="broker-metric" title="${TOOLTIPS.rating}">
                            <i class="fa-solid fa-star" style="color:#fbbf24;font-size:0.7rem;"></i>
                            <span class="metric-value">${formatRating(avgRating)}</span>
                            <span class="metric-sublabel" title="${TOOLTIPS.totalRatings}">(${formatNumber(totalRatings)})</span>
                        </span>
                        <span class="broker-metric" title="${TOOLTIPS.shareTransfer}">
                            <i class="fa-regular fa-clock" style="font-size:0.7rem;"></i>
                            <span class="metric-value amber">${formatNumber(broker.rating?.averageShareTransferDays, 1)}d</span> transfer
                        </span>
                        <span class="broker-metric" title="${TOOLTIPS.cashDeposit}">
                            <i class="fa-regular fa-building" style="font-size:0.7rem;"></i>
                            <span class="metric-value">${formatNumber(broker.rating?.averageCashDepositDays, 1)}d</span> deposit
                        </span>
                        ${broker.totalBranches > 0 ? `
                        <span class="broker-metric" title="${TOOLTIPS.branches}">
                            <i class="fa-solid fa-location-dot" style="font-size:0.7rem;color:#a0a0a0;"></i>
                            <span class="metric-value">${broker.totalBranches}</span> branches
                        </span>` : ''}
                    </div>
                    <div class="progress-bar-track" title="${isCurrency ? 'Rs. ' + formatNepaliNum(sortVal) : sortVal}">
                        <div class="progress-bar-fill ${barColor}" style="width: ${barPct}%"></div>
                    </div>
                    ${detailsHtml}
                </div>
                <div class="broker-right">
                    ${isActive ? '<span class="today-badge"><i class="fa-solid fa-circle" style="font-size:0.4rem;"></i> Active Today</span>' : ''}
                    <div class="turnover-big">${formatCurrency(turnover)}</div>
                    <div class="total-turnover-label">${currentSort === 'thirtyDayTurnover' ? '30-Day' : isActive ? 'Today\'s' : 'Latest'} Turnover</div>
                    ${avgRating ? `<div class="rating-stars" title="${TOOLTIPS.rating}">${renderStars(avgRating)}</div>` : ''}
                    ${isActive ? `<span class="expand-hint"><i class="fa-solid fa-chevron-down"></i></span>` : ''}
                </div>
            `;

            elements.grid.appendChild(card);

            const delay = Math.min(idx * 30, 600);
            animationTimer = setTimeout(() => {
                card.classList.add('card-visible');
                const turnEl = card.querySelector('.turnover-big');
                if (turnEl && isCurrency) {
                    const numVal = Number(turnover);
                    if (Number.isFinite(numVal) && numVal > 0) {
                        turnEl.textContent = 'Rs. 0';
                        setTimeout(() => animateValue(turnEl, 0, numVal, 800), 50);
                    }
                }
            }, delay);
        });

        document.querySelectorAll('.broker-card.has-details').forEach(card => {
            card.addEventListener('click', (e) => {
                if (e.target.closest('.clickable-stock') || e.target.closest('.broker-details')) return;
                const id = card.dataset.brokerId;
                const details = document.getElementById(`details-${id}`);
                const hint = card.querySelector('.expand-hint i');
                if (!details) return;
                const isOpen = details.classList.toggle('open');
                card.classList.toggle('details-open', isOpen);
                if (hint) hint.className = isOpen ? 'fa-solid fa-chevron-up' : 'fa-solid fa-chevron-down';
                if (isOpen) {
                    details.style.maxHeight = '0px';
                    details.style.overflow = 'hidden';
                    requestAnimationFrame(() => { details.style.maxHeight = details.scrollHeight + 'px'; });
                } else {
                    details.style.maxHeight = '0px';
                }
            });
        });

        document.querySelectorAll('.clickable-stock').forEach(el => {
            el.addEventListener('click', (e) => {
                e.stopPropagation();
                openStockModal(el.dataset.symbol, el.dataset.broker, {
                    name: el.dataset.name,
                    totalAmount: Number(el.dataset.amount) || 0,
                    buyAmount: Number(el.dataset.buy) || 0,
                    sellAmount: Number(el.dataset.sell) || 0,
                });
            });
        });
    }

    function handleSortChange(sortKey) {
        currentSort = sortKey;
        elements.sortTabs.forEach(tab => {
            const isActive = tab.dataset.sort === sortKey;
            tab.classList.toggle('active-tab', isActive);
            tab.setAttribute('aria-selected', isActive);
        });
        render();
    }

    async function init() {
        loadIndicesMarquee();
        await Promise.all([loadSecurities(), loadMarketPrices()]);

        if (elements.modalCloseBtn) elements.modalCloseBtn.addEventListener('click', closeModal);
        if (elements.modal) elements.modal.addEventListener('click', (e) => { if (e.target === elements.modal) closeModal(); });
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') closeModal();
        });

        try {
            const [brokersRes, metaRes] = await Promise.all([
                fetch(`${DATA_ROOT}other/brokers.json`, { cache: 'no-store' }),
                fetch(`${DATA_ROOT}sharehub_brokers.json`, { cache: 'no-store' })
            ]);
            if (!brokersRes.ok) throw new Error(`HTTP ${brokersRes.status}`);
            const brokerList = await brokersRes.json();
            const meta = metaRes.ok ? await metaRes.json() : {};

            allBrokers = Array.isArray(brokerList) ? brokerList : (brokerList.brokers || []);
            const activeBrokers = allBrokers.filter(b => b.todayStats);

            elements.totalBrokers.textContent = `${allBrokers.length} Brokers`;
            elements.activeToday.textContent = `${activeBrokers.length} Active Today`;
            elements.scrapedAt.textContent = `Updated: ${meta.scrapedAt ? new Date(meta.scrapedAt).toLocaleString() : 'N/A'}`;

            elements.sortTabs.forEach(tab => {
                tab.addEventListener('click', () => handleSortChange(tab.dataset.sort));
            });

            elements.search.addEventListener('input', render);

            handleSortChange('todayTurnover');
        } catch (err) {
            elements.grid.innerHTML = `<div class="no-data"><i class="fa-solid fa-triangle-exclamation text-2xl mb-2" style="color:#ef4444;"></i><p>Failed to load broker data.</p></div>`;
        }
    }

    init();
});
