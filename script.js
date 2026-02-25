document.addEventListener('DOMContentLoaded', () => {
    const stockGrid = document.getElementById('stock-grid');
    const searchInput = document.getElementById('search-input');
    const updateTimeEl = document.getElementById('update-time');
    const totalScannedEl = document.getElementById('total-scanned');
    const marketSummaryEl = document.getElementById('market-summary');
    const stockModal = document.getElementById('stock-modal');
    const closeModalBtn = document.getElementById('close-modal');

    // Custom Dropdown Logic
    const dropdownTrigger = document.getElementById('dropdown-trigger');
    const dropdownOptions = document.getElementById('dropdown-options');
    const selectedSectorText = document.getElementById('selected-sector');
    const customDropdown = document.querySelector('.custom-dropdown');

    // Intelligence elements
    const marketOpenStatusEl = document.getElementById('market-open-status');
    const snapshotGridEl = document.getElementById('snapshot-grid');
    const indicesListEl = document.getElementById('indices-list');
    const indicesMarqueeTrackEl = document.getElementById('indices-marquee-track');
    const topGainersListEl = document.getElementById('top-gainers-list');
    const topLosersListEl = document.getElementById('top-losers-list');
    const noticeFeedEl = document.getElementById('notice-feed');

    let currentSelectedSector = 'all';
    let allStocks = [];
    let sectorMap = {};
    let companyNameMap = {};
    let uniqueSectors = new Set();
    const expandedSectors = new Set();
    const DEFAULT_VISIBLE_STOCKS_PER_SECTOR = 2;
    let activeModalTrigger = null;

    function setDropdownOpen(isOpen) {
        customDropdown.classList.toggle('open', isOpen);
        dropdownTrigger.setAttribute('aria-expanded', String(isOpen));
    }

    // Toggle Dropdown
    dropdownTrigger.addEventListener('click', (e) => {
        e.stopPropagation();
        setDropdownOpen(!customDropdown.classList.contains('open'));
    });

    dropdownTrigger.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            setDropdownOpen(!customDropdown.classList.contains('open'));
        } else if (e.key === 'ArrowDown') {
            e.preventDefault();
            setDropdownOpen(true);
            const firstOption = dropdownOptions.querySelector('.option-item');
            if (firstOption) firstOption.focus();
        }
    });

    // Close dropdown when clicking outside
    document.addEventListener('click', () => {
        setDropdownOpen(false);
    });

    // Handle Option Selection (Delegation)
    dropdownOptions.addEventListener('click', (e) => {
        if (e.target.classList.contains('option-item')) {
            const value = e.target.getAttribute('data-value');
            const text = e.target.textContent;

            currentSelectedSector = value;
            selectedSectorText.textContent = text;

            document.querySelectorAll('.option-item').forEach(item => {
                item.classList.remove('selected');
                item.setAttribute('aria-selected', 'false');
            });
            e.target.classList.add('selected');
            e.target.setAttribute('aria-selected', 'true');

            applyFilters();
            setDropdownOpen(false);
        }
    });

    dropdownOptions.addEventListener('keydown', (e) => {
        const options = Array.from(dropdownOptions.querySelectorAll('.option-item'));
        const currentIndex = options.indexOf(document.activeElement);
        if (e.key === 'ArrowDown') {
            e.preventDefault();
            const next = options[Math.min(currentIndex + 1, options.length - 1)];
            if (next) next.focus();
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            const prev = options[Math.max(currentIndex - 1, 0)];
            if (prev) prev.focus();
        } else if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            if (document.activeElement.classList.contains('option-item')) {
                document.activeElement.click();
            }
        } else if (e.key === 'Escape') {
            e.preventDefault();
            setDropdownOpen(false);
            dropdownTrigger.focus();
        }
    });

    async function fetchJson(fileName) {
        const candidates = [`data/${fileName}`, fileName];
        for (const url of candidates) {
            try {
                const res = await fetch(url);
                if (res.ok) {
                    return await res.json();
                }
            } catch {
                // Continue to fallback path.
            }
        }
        return null;
    }

    function formatNumber(value, digits = 2) {
        if (typeof value !== 'number' || Number.isNaN(value)) return '-';
        return value.toLocaleString(undefined, {
            minimumFractionDigits: 0,
            maximumFractionDigits: digits
        });
    }

    function formatCompactNumber(value) {
        if (typeof value !== 'number' || Number.isNaN(value)) return '-';
        return new Intl.NumberFormat(undefined, {
            notation: 'compact',
            maximumFractionDigits: 2
        }).format(value);
    }

    function stripHtml(html) {
        if (!html) return '';
        return String(html).replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ').trim();
    }

    const BS_MONTH_INDEX = {
        baisakh: 0, baishakh: 0,
        jestha: 1, jeth: 1,
        ashad: 2, asar: 2, ashadh: 2,
        shrawan: 3, shravan: 3, saun: 3,
        bhadra: 4, bhadu: 4,
        ashwin: 5, aswin: 5, asoj: 5,
        kartik: 6,
        mangsir: 7, mansir: 7, margsir: 7, margshir: 7,
        poush: 8, pous: 8, pus: 8,
        magh: 9, mgh: 9, math: 9,
        falgun: 10, phagun: 10,
        chaitra: 11, chait: 11
    };
    const BS_MONTH_NAMES = [
        'Baisakh', 'Jestha', 'Ashad', 'Shrawan', 'Bhadra', 'Ashwin',
        'Kartik', 'Mangsir', 'Poush', 'Magh', 'Falgun', 'Chaitra'
    ];

    function formatADDate(date) {
        if (!(date instanceof Date) || Number.isNaN(date.getTime())) return '-';
        return date.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
    }

    function cleanIpoDateText(text) {
        return String(text || '')
            .replace(/\b(starting|started|from|to|till|until|upto|up to|on)\b/gi, ' ')
            .replace(/[,;|]/g, ' ')
            .replace(/\s+/g, ' ')
            .trim();
    }

    function getCurrentBsYear() {
        try {
            const NepaliDateCtor = typeof NepaliDate === 'function'
                ? NepaliDate
                : (typeof NepaliDate !== 'undefined' && NepaliDate && typeof NepaliDate.default === 'function'
                    ? NepaliDate.default
                    : null);
            if (!NepaliDateCtor) return null;
            const nowBs = new NepaliDateCtor();
            if (typeof nowBs.getYear === 'function') return nowBs.getYear();
        } catch {
            // ignore and fallback
        }
        return null;
    }

    function detectMonthIndex(part) {
        const partText = String(part || '').toLowerCase();
        for (const [monthName, monthIndex] of Object.entries(BS_MONTH_INDEX)) {
            if (partText.includes(monthName)) return monthIndex;
        }
        return undefined;
    }

    function parseRangePart(part, fallbackMonth) {
        const dayMatch = String(part || '').match(/(\d{1,2})/);
        if (!dayMatch) return null;
        const day = Number(dayMatch[1]);
        const month = detectMonthIndex(part);
        const monthIndex = month !== undefined ? month : fallbackMonth;
        if (!Number.isInteger(day) || monthIndex === undefined) return null;
        return { day, month: monthIndex };
    }

    function extractRangeCandidate(text) {
        const raw = String(text || '');
        const patterns = [
            /(\d{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+\s*-\s*\d{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+,\s*\d{4})/i,
            /(\d{1,2}(?:st|nd|rd|th)?\s*-\s*\d{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+,\s*\d{4})/i,
            /(\d{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+,\s*\d{4})/i,
            /([A-Za-z]+\s+\d{1,2},\s*\d{4})/i
        ];
        for (const pattern of patterns) {
            const match = raw.match(pattern);
            if (match) return match[1];
        }
        return raw;
    }

    function parseNepaliDateRange(rangeStr) {
        try {
            const candidate = cleanIpoDateText(extractRangeCandidate(rangeStr));
            if (!candidate) return null;

            const yearMatch = candidate.match(/(\d{4})(?!.*\d{4})/);
            const bsYear = yearMatch ? Number(yearMatch[1]) : (getCurrentBsYear() ?? NaN);
            if (!Number.isInteger(bsYear)) return null;

            const rangeWithoutYear = yearMatch
                ? candidate.replace(yearMatch[1], '').trim()
                : candidate;

            const splitParts = rangeWithoutYear.split(/\s*(?:-|to|till)\s*/i);
            const startRaw = splitParts[0] || '';
            const endRaw = splitParts[1] || splitParts[0] || '';

            const endInfo = parseRangePart(endRaw);
            if (!endInfo) return null;
            const startInfo = parseRangePart(startRaw, endInfo.month);
            if (!startInfo) return null;

            const endYear = endInfo.month < startInfo.month ? bsYear + 1 : bsYear;
            const startDate = bsToAdDate(bsYear, startInfo.month, startInfo.day);
            const endDate = bsToAdDate(endYear, endInfo.month, endInfo.day);
            if (!startDate || !endDate) return null;

            const bsStart = `${startInfo.day} ${BS_MONTH_NAMES[startInfo.month]}, ${bsYear}`;
            const bsEnd = `${endInfo.day} ${BS_MONTH_NAMES[endInfo.month]}, ${endYear}`;

            return {
                start: startDate,
                end: endDate,
                bsStart,
                bsEnd,
                bsRange: `${bsStart} - ${bsEnd}`
            };
        } catch {
            return null;
        }
    }

    function startOfDay(date) {
        return new Date(date.getFullYear(), date.getMonth(), date.getDate());
    }

    function daysBetween(fromDate, toDate) {
        const ms = startOfDay(toDate).getTime() - startOfDay(fromDate).getTime();
        return Math.ceil(ms / (24 * 60 * 60 * 1000));
    }

    function bsToAdDate(year, month, day) {
        const NepaliDateCtor = typeof NepaliDate === 'function'
            ? NepaliDate
            : (typeof NepaliDate !== 'undefined' && NepaliDate && typeof NepaliDate.default === 'function'
                ? NepaliDate.default
                : null);
        if (!NepaliDateCtor) return null;
        const monthIdx = Number(month);
        if (!Number.isInteger(monthIdx) || !Number.isInteger(day) || !Number.isInteger(year)) return null;

        try {
            const adDate = new NepaliDateCtor(year, monthIdx, day).toJsDate();
            adDate.setHours(0, 0, 0, 0);
            return adDate;
        } catch {
            return null;
        }
    }

    function parseIpoWindow(ipo) {
        const sources = [ipo.date_range, ipo.full_text];
        for (const src of sources) {
            const parsed = parseNepaliDateRange(src);
            if (!parsed) continue;

            return {
                bsRange: parsed.bsRange,
                bsStart: parsed.bsStart,
                bsEnd: parsed.bsEnd,
                adStart: parsed.start,
                adEnd: parsed.end
            };
        }
        return null;
    }

    function getIPOStatus(startDate, endDate) {
        const now = new Date();
        const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
        const start = new Date(startDate.getFullYear(), startDate.getMonth(), startDate.getDate());
        const end = new Date(endDate.getFullYear(), endDate.getMonth(), endDate.getDate());

        const DAYS = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
        const openingDay = DAYS[startDate.getDay()];
        const closingDay = DAYS[endDate.getDay()];

        if (today < start) {
            return {
                status: 'upcoming',
                daysRemaining: daysBetween(today, start),
                openingDay,
                closingDay
            };
        }
        if (today <= end) {
            return {
                status: 'open',
                daysRemaining: daysBetween(today, end),
                openingDay,
                closingDay
            };
        }
        return {
            status: 'closed',
            daysRemaining: 0,
            openingDay,
            closingDay
        };
    }

    async function fetchStocks() {
        try {
            const [
                stocks,
                sectors,
                ipos,
                marketSummary,
                indices,
                topStocks,
                notices,
                marketStatus,
                marketSummaryHistory,
                supplyDemand
            ] = await Promise.all([
                fetchJson('nepse_data.json'),
                fetchJson('nepse_sector_wise_codes.json'),
                fetchJson('upcoming_ipo.json'),
                fetchJson('market_summary.json'),
                fetchJson('indices.json'),
                fetchJson('top_stocks.json'),
                fetchJson('notices.json'),
                fetchJson('market_status.json'),
                fetchJson('market_summary_history.json'),
                fetchJson('supply_demand.json')
            ]);

            if (!stocks || stocks.length === 0) {
                throw new Error('Failed to fetch stock data');
            }

            allStocks = stocks;
            renderStocks(allStocks);
            updateMetadata(allStocks);

            if (sectors) {
                Object.entries(sectors).forEach(([sector, items]) => {
                    uniqueSectors.add(sector);
                    items.forEach(item => {
                        sectorMap[item.symbol] = sector;
                        companyNameMap[item.symbol] = item.name;
                    });
                });
                populateSectorDropdown();
                applyFilters();
            }

            renderIPOs(ipos || []);
            renderMarketSnapshot(marketSummary || [], marketStatus, marketSummaryHistory || [], supplyDemand || {});
            renderIndices(indices || []);
            renderTopMovers(topStocks || {});
            renderNoticeFeed(notices || {});

        } catch (error) {
            console.error('Error:', error);
            stockGrid.innerHTML = `
                <div class="status-item" style="color: var(--danger); grid-column: 1/-1;">
                    <i class="fa-solid fa-circle-exclamation"></i>
                    Failed to load market data.
                </div>
            `;
        }
    }

    function renderMarketSnapshot(summary, status, history, supplyDemand) {
        if (marketOpenStatusEl) {
            const isOpen = Boolean(status && status.is_open);
            marketOpenStatusEl.textContent = isOpen ? 'Market Open' : 'Market Closed';
            marketOpenStatusEl.className = `chip ${status ? (isOpen ? 'open' : 'closed') : 'neutral'}`;

            const statusDot = document.querySelector('.status-dot');
            if (statusDot) {
                statusDot.style.backgroundColor = isOpen ? 'var(--success)' : 'var(--danger)';
                statusDot.style.boxShadow = isOpen ? '0 0 10px var(--success)' : '0 0 10px var(--danger)';
            }
        }

        if (!snapshotGridEl) return;

        const tiles = [];
        summary.slice(0, 4).forEach(item => {
            tiles.push({
                label: item.detail.replace(':', ''),
                value: formatCompactNumber(item.value)
            });
        });

        if (Array.isArray(history) && history.length > 0) {
            const latest = history[history.length - 1];
            tiles.push({
                label: 'History Entries',
                value: history.length.toLocaleString()
            });
            tiles.push({
                label: 'Last Business Date',
                value: latest.businessDate || '-'
            });
        }

        if (supplyDemand && Array.isArray(supplyDemand.supplyList) && Array.isArray(supplyDemand.demandList)) {
            tiles.push({
                label: 'Supply Records',
                value: supplyDemand.supplyList.length.toLocaleString()
            });
            tiles.push({
                label: 'Demand Records',
                value: supplyDemand.demandList.length.toLocaleString()
            });
        }

        if (tiles.length === 0) {
            snapshotGridEl.innerHTML = '<p class="intel-empty">No summary data available.</p>';
            return;
        }

        snapshotGridEl.innerHTML = tiles.slice(0, 8).map(tile => `
            <div class="snapshot-tile">
                <span class="snapshot-label">${tile.label}</span>
                <span class="snapshot-value">${tile.value}</span>
            </div>
        `).join('');
    }

    function renderIndices(indices) {
        if (!indicesListEl) return;
        if (!Array.isArray(indices) || indices.length === 0) {
            indicesListEl.innerHTML = '<p class="intel-empty">No index data available.</p>';
            renderIndicesMarquee([]);
            return;
        }

        const sorted = [...indices]
            .sort((a, b) => Math.abs(b.perChange || 0) - Math.abs(a.perChange || 0))
            .slice(0, 6);

        indicesListEl.innerHTML = sorted.map(item => {
            const up = (item.change || 0) >= 0;
            return `
                <div class="index-row">
                    <div>
                        <p class="index-name">${item.index}</p>
                        <p class="index-meta">Close ${formatNumber(item.close, 2)}</p>
                    </div>
                    <div class="${up ? 'up-text' : 'down-text'} index-change">
                        <i class="fa-solid ${up ? 'fa-caret-up' : 'fa-caret-down'} trend-icon" aria-hidden="true"></i>
                        ${Math.abs(item.perChange || 0).toFixed(2)}%
                    </div>
                </div>
            `;
        }).join('');

        renderIndicesMarquee(indices);
    }

    function renderIndicesMarquee(indices) {
        if (!indicesMarqueeTrackEl) return;
        if (!Array.isArray(indices) || indices.length === 0) {
            indicesMarqueeTrackEl.innerHTML = '<span class="indices-marquee-empty">No index data available.</span>';
            return;
        }

        const sorted = [...indices]
            .sort((a, b) => Math.abs(b.perChange || 0) - Math.abs(a.perChange || 0))
            .slice(0, 12);

        const itemsHtml = sorted.map(item => {
            const up = (item.change || 0) >= 0;
            const sign = up ? '+' : '-';
            return `
                <span class="indices-marquee-item">
                    <span class="indices-marquee-name">${item.index}</span>
                    <span class="${up ? 'up-text' : 'down-text'}">
                        <i class="fa-solid ${up ? 'fa-caret-up' : 'fa-caret-down'} trend-icon" aria-hidden="true"></i>
                        ${Math.abs(item.perChange || 0).toFixed(2)}%
                    </span>
                    <span>(${formatNumber(item.close, 2)})</span>
                </span>
            `;
        }).join('');

        indicesMarqueeTrackEl.innerHTML = `${itemsHtml}${itemsHtml}`;
    }

    function renderTopMovers(topStocks) {
        const gainers = Array.isArray(topStocks.top_gainer) ? topStocks.top_gainer.slice(0, 5) : [];
        const losers = Array.isArray(topStocks.top_loser) ? topStocks.top_loser.slice(0, 5) : [];

        const renderMoverList = (items, up) => {
            if (items.length === 0) return '<p class="intel-empty">No data.</p>';
            return items.map(item => `
                <div class="mover-row">
                    <div>
                        <p class="mover-symbol">${item.symbol}</p>
                        <p class="mover-price">Rs. ${formatNumber(item.ltp, 2)}</p>
                    </div>
                    <div class="${up ? 'up-text' : 'down-text'} mover-change">
                        <i class="fa-solid ${up ? 'fa-caret-up' : 'fa-caret-down'} trend-icon" aria-hidden="true"></i>
                        ${Math.abs(item.percentageChange || 0).toFixed(2)}%
                    </div>
                </div>
            `).join('');
        };

        if (topGainersListEl) {
            topGainersListEl.innerHTML = renderMoverList(gainers, true);
        }
        if (topLosersListEl) {
            topLosersListEl.innerHTML = renderMoverList(losers, false);
        }
    }

    function normalizeNotices(notices) {
        const rows = [];
        const categories = ['general', 'company', 'exchange'];

        categories.forEach(category => {
            if (!Array.isArray(notices[category])) return;
            notices[category].forEach(item => {
                const title = item.noticeHeading || item.newsHeadline || item.messageTitle || 'Untitled notice';
                const body = item.noticeBody || item.newsBody || item.messageBody || '';
                const rawDate = item.modifiedDate || item.addedDate || item.noticeExpiryDate || item.expiryDate || '';
                rows.push({
                    category,
                    title,
                    body: stripHtml(body),
                    date: rawDate
                });
            });
        });

        return rows
            .sort((a, b) => new Date(b.date || 0) - new Date(a.date || 0))
            .slice(0, 8);
    }

    function renderNoticeFeed(notices) {
        if (!noticeFeedEl) return;

        const entries = normalizeNotices(notices);
        if (entries.length === 0) {
            noticeFeedEl.innerHTML = '<p class="intel-empty">No notices available.</p>';
            return;
        }

        noticeFeedEl.innerHTML = entries.map(item => `
            <div class="notice-item">
                <div class="notice-head">
                    <span class="chip small">${item.category}</span>
                    <span class="notice-date">${item.date ? new Date(item.date).toLocaleDateString() : 'N/A'}</span>
                </div>
                <p class="notice-title">${item.title}</p>
                <p class="notice-body">${item.body || 'No description provided.'}</p>
            </div>
        `).join('');
    }

    function renderIPOs(ipos) {
        const ipoSection = document.getElementById('ipo-section');
        const ipoGrid = document.getElementById('ipo-grid');
        const ipoStatusFilter = document.getElementById('ipo-status-filter');
        const ipoSummaryMeta = document.getElementById('ipo-summary-meta');

        if (!Array.isArray(ipos) || ipos.length === 0) {
            ipoSection.classList.add('is-hidden');
            return;
        }

        const statusRank = { open: 0, upcoming: 1, closed: 2 };

        const classifiedIpos = ipos
            .map(ipo => {
                const window = parseIpoWindow(ipo);
                if (!window) {
                    return {
                        ipo,
                        window: null,
                        status: 'closed',
                        daysRemaining: 0
                    };
                }

                const statusInfo = getIPOStatus(window.adStart, window.adEnd);
                return {
                    ipo,
                    window,
                    status: statusInfo.status,
                    daysRemaining: statusInfo.daysRemaining,
                    openingDay: statusInfo.openingDay,
                    closingDay: statusInfo.closingDay
                };
            })
            .sort((a, b) => {
                const rankDiff = (statusRank[a.status] ?? 3) - (statusRank[b.status] ?? 3);
                if (rankDiff !== 0) return rankDiff;
                const aStart = a.window ? a.window.adStart.getTime() : 0;
                const bStart = b.window ? b.window.adStart.getTime() : 0;
                return aStart - bStart;
            });

        if (classifiedIpos.length === 0) {
            ipoSection.classList.remove('is-hidden');
            ipoGrid.innerHTML = '<p class="intel-empty">Unable to parse IPO windows from source data.</p>';
            if (ipoSummaryMeta) ipoSummaryMeta.textContent = '0 active | 0 closed';
            return;
        }

        const openIpos = classifiedIpos.filter(({ status }) => status === 'open');
        const upcomingIpos = classifiedIpos.filter(({ status }) => status === 'upcoming');
        const closedIpos = classifiedIpos.filter(({ status }) => status === 'closed');

        if (openIpos.length === 0 && upcomingIpos.length === 0 && closedIpos.length === 0) {
            ipoSection.classList.add('is-hidden');
            return;
        }

        ipoSection.classList.remove('is-hidden');

        const renderIpoCard = (container, { ipo, window, status, daysRemaining, openingDay, closingDay }) => {
            const card = document.createElement('div');
            card.className = 'ipo-card';
            card.setAttribute('role', 'button');
            card.setAttribute('tabindex', '0');
            card.setAttribute('aria-expanded', 'false');
            const statusLabel = status === 'open' ? 'Open' : status === 'upcoming' ? 'Upcoming' : 'Closed';
            const statusClass = status === 'open' ? 'open' : status === 'upcoming' ? 'upcoming' : 'closed';
            const isReservedShare = Boolean(ipo.is_reserved_share) || /nepalese citizens working abroad/i.test(ipo.full_text || '');
            const reservedFor = ipo.reserved_for || (isReservedShare ? 'Nepalese citizens working abroad' : '');
            const adRange = window ? `${formatADDate(window.adStart)} - ${formatADDate(window.adEnd)}` : 'Unavailable';
            const bsRange = window ? window.bsRange : (ipo.date_range || 'Unavailable');
            const bsStart = window ? window.bsStart : 'Unavailable';
            const bsEnd = window ? window.bsEnd : 'Unavailable';
            const unitsText = ipo.units && String(ipo.units).toLowerCase() !== 'unknown'
                ? `${ipo.units} units`
                : 'Units not published';
            const noticeText = ipo.announcement_date || 'Not available';
            const daysText = status === 'open'
                ? (daysRemaining > 0 ? `Closing in ${daysRemaining} day${daysRemaining === 1 ? '' : 's'}` : 'Closing today')
                : status === 'upcoming'
                    ? `Opening in ${daysRemaining} day${daysRemaining === 1 ? '' : 's'}`
                    : '';
            const sourceLink = ipo.url
                ? `<a rel="noopener noreferrer" href="${ipo.url}" target="_blank" class="ipo-view-details">
                        View Details <i class="fa-solid fa-arrow-right-long"></i>
                   </a>`
                : '<span class="ipo-view-details ipo-view-details-disabled">Source unavailable</span>';

            card.innerHTML = `
                <div class="ipo-card-topline">
                    <div class="ipo-card-badges">
                        <span class="chip small ${statusClass}">${statusLabel}</span>
                        ${isReservedShare ? '<span class="chip small reserved-share">Reserved Share</span>' : ''}
                    </div>
                    ${daysText ? `<span class="ipo-card-countdown">${daysText}</span>` : ''}
                </div>
                <div class="ipo-company">${ipo.company}</div>
                ${reservedFor ? `<div class="ipo-company-sub"><i class="fa-solid fa-user-check"></i> Reserved for: ${reservedFor}</div>` : ''}
                <div class="ipo-stats-grid">
                    <div class="ipo-stat-tile">
                        <span class="detail-label">Units</span>
                        <span class="detail-val ipo-strong">${unitsText}</span>
                    </div>
                    <div class="ipo-stat-tile">
                        <span class="detail-label">BS IPO Window</span>
                        <span class="detail-val">${bsRange}</span>
                    </div>
                </div>
                <div class="ipo-card-hint">Click card to view dates</div>
                <div class="ipo-card-details is-hidden">
                    <div class="ipo-detail-row">
                        <span class="ipo-detail-key"><i class="fa-regular fa-clock"></i> AD Window</span>
                        <span class="ipo-detail-value">${adRange}</span>
                    </div>
                    <div class="ipo-detail-row">
                        <span class="ipo-detail-key"><i class="fa-regular fa-calendar-days"></i> Weekdays</span>
                        <span class="ipo-detail-value">Opens on ${openingDay || '-'} | Closes on ${closingDay || '-'}</span>
                    </div>
                    <div class="ipo-detail-row">
                        <span class="ipo-detail-key"><i class="fa-regular fa-newspaper"></i> Notice Published</span>
                        <span class="ipo-detail-value">${noticeText}</span>
                    </div>
                    <div class="ipo-full-text-wrap">
                        <div class="ipo-detail-key"><i class="fa-regular fa-file-lines"></i> Full Notice</div>
                        <p class="ipo-full-text">${ipo.full_text || 'Not available'}</p>
                    </div>
                </div>
                <div class="ipo-card-footer">
                    ${sourceLink}
                </div>
            `;

            const detailsEl = card.querySelector('.ipo-card-details');
            const hintEl = card.querySelector('.ipo-card-hint');
            const toggleDetails = () => {
                const isHidden = detailsEl && detailsEl.classList.contains('is-hidden');
                if (!detailsEl || !hintEl) return;
                detailsEl.classList.toggle('is-hidden', !isHidden);
                card.classList.toggle('expanded', isHidden);
                card.setAttribute('aria-expanded', String(isHidden));
                hintEl.textContent = isHidden ? 'Click card to hide dates' : 'Click card to view dates';
            };

            card.addEventListener('click', (event) => {
                if (event.target && event.target.closest('a')) return;
                toggleDetails();
            });
            card.addEventListener('keydown', (event) => {
                if (event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault();
                    toggleDetails();
                }
            });
            container.appendChild(card);
        };

        if (ipoSummaryMeta) {
            ipoSummaryMeta.textContent = `${openIpos.length} open | ${upcomingIpos.length} upcoming | ${closedIpos.length} closed`;
        }

        const renderByFilter = () => {
            const selected = ipoStatusFilter ? ipoStatusFilter.value : 'all';
            let rows = classifiedIpos;
            if (selected !== 'all') {
                rows = classifiedIpos.filter((item) => item.status === selected);
            }
            ipoGrid.innerHTML = '';
            if (rows.length === 0) {
                ipoGrid.innerHTML = '<p class="intel-empty">No IPOs in this status.</p>';
                return;
            }
            rows.forEach((item) => renderIpoCard(ipoGrid, item));
        };

        if (ipoStatusFilter) {
            ipoStatusFilter.onchange = renderByFilter;
        }
        renderByFilter();
    }

    function populateSectorDropdown() {
        const sortedSectors = Array.from(uniqueSectors).sort();
        const allOption = dropdownOptions.querySelector('[data-value="all"]');
        if (allOption) {
            allOption.classList.add('selected');
            allOption.setAttribute('aria-selected', 'true');
        }

        sortedSectors.forEach(sector => {
            const option = document.createElement('div');
            option.className = 'option-item';
            option.setAttribute('role', 'option');
            option.setAttribute('tabindex', '0');
            option.setAttribute('aria-selected', 'false');
            option.setAttribute('data-value', sector);
            option.textContent = sector;
            dropdownOptions.appendChild(option);
        });
    }

    function updateMetadata(stocks) {
        if (stocks.length === 0) return;

        const lastUpdated = new Date(stocks[0].last_updated);
        updateTimeEl.textContent = `Live as of ${lastUpdated.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`;
        totalScannedEl.textContent = `${stocks.length} Companies Tracked`;

        const gainers = stocks.filter(s => s.change > 0).length;
        const losers = stocks.filter(s => s.change < 0).length;
        marketSummaryEl.textContent = `${gainers} Gainers / ${losers} Losers`;
    }

    function renderStocks(stocks) {
        stockGrid.innerHTML = '';

        if (stocks.length === 0) {
            stockGrid.innerHTML = '<p style="text-align: center; padding: 3rem; color: var(--text-secondary);">No stocks found matching your search.</p>';
            return;
        }

        const selectedSector = currentSelectedSector;
        const grouped = {};
        const uncategorized = [];

        stocks.forEach(stock => {
            const sector = sectorMap[stock.symbol];

            if (selectedSector !== 'all') {
                if (sector && sector !== selectedSector) return;
                if (!sector && selectedSector !== 'Others') return;
            }

            if (sector) {
                if (!grouped[sector]) grouped[sector] = [];
                grouped[sector].push(stock);
            } else {
                uncategorized.push(stock);
            }
        });

        const sortedSectors = Object.keys(grouped).sort();

        if (uncategorized.length > 0 && (selectedSector === 'all' || selectedSector === 'Others')) {
            sortedSectors.push('Others');
            grouped.Others = uncategorized;
        }

        if (selectedSector !== 'all' && selectedSector !== 'Others' && !grouped[selectedSector]) {
            stockGrid.innerHTML = '<p style="text-align: center; padding: 3rem; color: var(--text-secondary);">No stocks found in the selected sector matching your search.</p>';
            return;
        }
        if (selectedSector === 'Others' && uncategorized.length === 0) {
            stockGrid.innerHTML = '<p style="text-align: center; padding: 3rem; color: var(--text-secondary);">No uncategorized stocks found matching your search.</p>';
            return;
        }

        sortedSectors.forEach(sector => {
            if (selectedSector !== 'all' && sector !== selectedSector && !(selectedSector === 'Others' && sector === 'Others')) {
                return;
            }

            const sectorStocks = grouped[sector];
            if (!sectorStocks || sectorStocks.length === 0) return;

            const sectorHeader = document.createElement('div');
            sectorHeader.className = 'sector-header';

            const sectorTitle = document.createElement('h2');
            sectorTitle.className = 'sector-title';
            sectorTitle.textContent = sector;
            sectorHeader.appendChild(sectorTitle);

            const isExpanded = expandedSectors.has(sector);
            const hasMoreItems = sectorStocks.length > DEFAULT_VISIBLE_STOCKS_PER_SECTOR;
            const visibleStocks = isExpanded
                ? sectorStocks
                : sectorStocks.slice(0, DEFAULT_VISIBLE_STOCKS_PER_SECTOR);

            if (hasMoreItems) {
                const viewMoreBtn = document.createElement('button');
                viewMoreBtn.type = 'button';
                viewMoreBtn.className = 'sector-view-more';
                viewMoreBtn.textContent = isExpanded
                    ? 'Show less'
                    : `View more (${sectorStocks.length - visibleStocks.length})`;
                viewMoreBtn.addEventListener('click', () => {
                    if (expandedSectors.has(sector)) {
                        expandedSectors.delete(sector);
                    } else {
                        expandedSectors.add(sector);
                    }
                    renderStocks(stocks);
                });
                sectorHeader.appendChild(viewMoreBtn);
            }

            stockGrid.appendChild(sectorHeader);

            if (visibleStocks.length > 0) {
                const sectorGrid = document.createElement('div');
                sectorGrid.className = 'sector-grid';

                visibleStocks.forEach(stock => {
                    const isUp = stock.change >= 0;
                    const companyName = companyNameMap[stock.symbol] || '';
                    const card = document.createElement('div');
                    card.className = 'stock-card';

                    card.innerHTML = `
                        <div class="card-header">
                            <div class="symbol-info">
                                <div class="symbol-name">${stock.symbol}</div>
                                <div class="company-name-small">${companyName}</div>
                                <div class="detail-label">LTP</div>
                                <div class="ltp-value ${isUp ? 'up' : 'down'}">Rs. ${formatNumber(stock.ltp, 2)}</div>
                            </div>
                            <div class="change-indicators">
                                <div class="percent-badge ${isUp ? 'up' : 'down'}">
                                    <i class="fa-solid ${isUp ? 'fa-caret-up' : 'fa-caret-down'} trend-icon" aria-hidden="true"></i>
                                    ${Math.abs(Number(stock.percent_change || 0)).toFixed(2)}%
                                </div>
                                <div class="change-val ${isUp ? 'up' : 'down'}" style="font-size: 0.9rem; font-weight: 500;">
                                    <i class="fa-solid ${isUp ? 'fa-caret-up' : 'fa-caret-down'} trend-icon" aria-hidden="true"></i>
                                    ${Math.abs(Number(stock.change || 0)).toFixed(2)}
                                </div>
                            </div>
                        </div>
                        <div class="card-details">
                            <div class="detail-item">
                                <span class="detail-label">Prev Close</span>
                                <span class="detail-val">${formatNumber(stock.previous_close, 2)}</span>
                            </div>
                            <div class="detail-item">
                                <span class="detail-label">Volume</span>
                                <span class="detail-val" style="color: var(--accent-primary)">${formatNumber(Math.floor(Number(stock.volume || 0)), 0)}</span>
                            </div>
                            <div class="detail-item">
                                <span class="detail-label">High</span>
                                <span class="detail-val" style="color: var(--success)">${formatNumber(stock.high, 2)}</span>
                            </div>
                            <div class="detail-item">
                                <span class="detail-label">Low</span>
                                <span class="detail-val" style="color: var(--danger)">${formatNumber(stock.low, 2)}</span>
                            </div>
                        </div>
                    `;
                    card.addEventListener('click', () => showStockDetails(stock));
                    sectorGrid.appendChild(card);
                });

                stockGrid.appendChild(sectorGrid);
            }
        });
    }

    searchInput.addEventListener('input', () => {
        applyFilters();
    });

    function applyFilters() {
        const term = searchInput.value.toUpperCase();
        const filtered = allStocks.filter(stock => {
            const name = companyNameMap[stock.symbol] || '';
            return stock.symbol.toUpperCase().includes(term) ||
                name.toUpperCase().includes(term) ||
                (stock.name && stock.name.toUpperCase().includes(term));
        });
        renderStocks(filtered);
    }

    function showStockDetails(stock) {
        activeModalTrigger = document.activeElement;
        const isUp = stock.change >= 0;
        const companyName = companyNameMap[stock.symbol] || stock.name || 'Company Name Not Available';
        const sector = sectorMap[stock.symbol] || 'Others';

        document.getElementById('modal-symbol').textContent = stock.symbol;
        document.getElementById('modal-company-name').textContent = companyName;
        document.getElementById('modal-sector-badge').textContent = sector;

        const ltpEl = document.getElementById('modal-ltp');
        ltpEl.textContent = `Rs. ${formatNumber(stock.ltp, 2)}`;
        ltpEl.className = `modal-ltp ${isUp ? 'up-text' : 'down-text'}`;

        const changeEl = document.getElementById('modal-change');
        changeEl.innerHTML = `
            <i class="fa-solid ${isUp ? 'fa-caret-up' : 'fa-caret-down'} trend-icon" aria-hidden="true"></i>
            ${Math.abs(Number(stock.change || 0)).toFixed(2)} (${Math.abs(Number(stock.percent_change || 0)).toFixed(2)}%)
        `;
        changeEl.className = `modal-change ${isUp ? 'up-text' : 'down-text'}`;

        document.getElementById('modal-prev-close').textContent = formatNumber(stock.previous_close, 2);
        document.getElementById('modal-high').textContent = formatNumber(stock.high, 2);
        document.getElementById('modal-low').textContent = formatNumber(stock.low, 2);
        document.getElementById('modal-volume').textContent = formatNumber(Math.floor(Number(stock.volume || 0)), 0);

        const lastUpdated = new Date(stock.last_updated);
        document.getElementById('modal-last-updated').textContent = lastUpdated.toLocaleString([], {
            year: 'numeric',
            month: 'long',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });

        stockModal.classList.add('show');
        document.body.style.overflow = 'hidden';
        closeModalBtn.focus();
    }

    function closeModal() {
        stockModal.classList.remove('show');
        document.body.style.overflow = '';
        if (activeModalTrigger && typeof activeModalTrigger.focus === 'function') {
            activeModalTrigger.focus();
        }
    }

    closeModalBtn.addEventListener('click', closeModal);

    window.addEventListener('click', (e) => {
        if (e.target === stockModal) {
            closeModal();
        }
    });

    window.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && stockModal.classList.contains('show')) {
            closeModal();
        }
    });

    fetchStocks();
});
