document.addEventListener('DOMContentLoaded', () => {
    const stockGrid = document.getElementById('stock-grid');
    const searchInput = document.getElementById('search-input');
    const updateTimeEl = document.getElementById('update-time');
    const totalScannedEl = document.getElementById('total-scanned');
    const marketSummaryEl = document.getElementById('market-summary');
    const stockModal = document.getElementById('stock-modal');
    const closeModalBtn = document.getElementById('close-modal');
    const modalDividendOpenBtn = document.getElementById('modal-dividend-open');
    const modalDividendBackBtn = document.getElementById('modal-dividend-back');
    const modalLtpHistoryOpenBtn = document.getElementById('modal-ltp-history-open');
    const modalLtpHistoryBackBtn = document.getElementById('modal-ltp-history-back');
    const modalFinancialOpenBtn = document.getElementById('modal-financial-open');
    const modalFinancialBackBtn = document.getElementById('modal-financial-back');
    const modalLtpHistoryBlockEl = document.getElementById('modal-ltp-history-block');
    const modalLtpHistoryStatusEl = document.getElementById('modal-ltp-history-status');
    const modalLtpHistorySummaryEl = document.getElementById('modal-ltp-history-summary');
    const modalLtpHistoryListEl = document.getElementById('modal-ltp-history-list');
    const modalLtpHistoryChartEl = document.getElementById('modal-ltp-history-chart');
    const modalLtpHistoryTooltipEl = document.getElementById('modal-ltp-history-tooltip');
    const modalLtpHistoryStatsEl = document.getElementById('modal-ltp-history-stats');
    const modalFinancialBlockEl = document.getElementById('modal-financial-block');
    const modalFinancialStatusEl = document.getElementById('modal-financial-status');
    const modalFinancialSummaryEl = document.getElementById('modal-financial-summary');
    const modalFinancialListEl = document.getElementById('modal-financial-list');
    const modalFinancialDocumentViewerEl = document.getElementById('modal-financial-document-viewer');
    const modalFinancialDocumentTitleEl = document.getElementById('modal-financial-document-title');
    const modalFinancialDocumentOpenEl = document.getElementById('modal-financial-document-open');
    const modalFinancialDocumentBackBtn = document.getElementById('modal-financial-document-back');
    const modalCompanyProfilePreviewEl = document.getElementById('modal-company-profile-preview');
    const modalCompanyProfileToggleBtn = document.getElementById('modal-company-profile-toggle');
    const modalCompanyProfileTitleEl = document.getElementById('modal-company-profile-title');
    const modalCompanyProfileBodyEl = document.getElementById('modal-company-profile-body');
    const modalCompanyProfileTextEl = document.getElementById('modal-company-profile-text');
    const modalCompanyProfileFactsEl = document.getElementById('modal-company-profile-facts');
    const modalDividendBlockEl = document.getElementById('modal-dividend-block');
    const modalMarketGridEl = document.getElementById('modal-market-grid');
    const modalDividendStatusEl = document.getElementById('modal-dividend-status');
    const modalDividendSummaryEl = document.getElementById('modal-dividend-summary');
    const modalDividendAnalysisEl = document.getElementById('modal-dividend-analysis');
    const modalDividendListEl = document.getElementById('modal-dividend-list');
    const modalNewsOpenBtn = document.getElementById('modal-news-open');
    const modalNewsBackBtn = document.getElementById('modal-news-back');
    const modalNewsBlockEl = document.getElementById('modal-news-block');
    const modalNewsStatusEl = document.getElementById('modal-news-status');
    const modalNewsListEl = document.getElementById('modal-news-list');

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
    const ipoStatusChartEl = document.getElementById('ipo-status-chart');
    const dashboardSectionEls = Array.from(document.querySelectorAll('.dash-main .intel-section'));
    const ipoSectionEl = document.getElementById('ipo-section');

    let currentSelectedSector = 'all';
    let allStocks = [];
    let sectorMap = {};
    let companyNameMap = {};
    let uniqueSectors = new Set();
    const expandedSectors = new Set();
    const DEFAULT_VISIBLE_STOCKS_PER_SECTOR = 2;
    let activeModalTrigger = null;
    let currentModalSymbol = '';
    let dividendHistoryCache = null;
    let financialReportsCache = null;
    let financialMetadataCache = null;
    let companyProfilesCache = null;
    let modalNewsCache = null;
    let ltpHistoryManifestCache = null;
    const ltpHistoryShardCache = {};
    let currentLtpHistoryRows = [];
    let currentLtpHistoryRange = '1m';
    let currentLtpChartState = { rows: [], points: [], cssWidth: 0, cssHeight: 0 };
    let currentLtpChartHoverIndex = null;
    let currentLtpChartPinnedIndex = null;
    let hasRenderableIpos = false;
    let showAllIpos = false;
    let ipoChartSnapshot = { open: 0, upcoming: 0, closed: 0 };

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
        const optionItem = e.target.closest('.option-item');
        if (!optionItem || !dropdownOptions.contains(optionItem)) return;

        const value = optionItem.getAttribute('data-value') || 'all';
        const text = optionItem.textContent || 'All Sectors';

        currentSelectedSector = value;
        selectedSectorText.textContent = text;

        dropdownOptions.querySelectorAll('.option-item').forEach(item => {
            item.classList.remove('selected');
            item.setAttribute('aria-selected', 'false');
        });
        optionItem.classList.add('selected');
        optionItem.setAttribute('aria-selected', 'true');

        applyFilters();
        setDropdownOpen(false);
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

    function normalizeSymbol(symbol) {
        return String(symbol || '').trim().toUpperCase();
    }

    function parseDateValue(value) {
        const d = new Date(value);
        return Number.isNaN(d.getTime()) ? 0 : d.getTime();
    }

    function safeValue(value, fallback = '-') {
        if (value === null || value === undefined || value === '') return fallback;
        return value;
    }

    function escapeAttribute(value) {
        return String(value ?? '').replace(/[&<>"']/g, (char) => {
            const map = {
                '&': '&amp;',
                '<': '&lt;',
                '>': '&gt;',
                '"': '&quot;',
                "'": '&#39;'
            };
            return map[char] || char;
        });
    }

    async function getDividendHistoryData() {
        if (Array.isArray(dividendHistoryCache)) return dividendHistoryCache;
        const raw = await fetchJson('proposed_dividend/history_all_years.json');
        dividendHistoryCache = Array.isArray(raw) ? raw : [];
        return dividendHistoryCache;
    }

    async function getFinancialReportsData() {
        if (Array.isArray(financialReportsCache)) return financialReportsCache;
        const raw = await fetchJson('company/financials.json');
        financialReportsCache = Array.isArray(raw) ? raw : [];
        return financialReportsCache;
    }

    async function getFinancialMetadata() {
        if (financialMetadataCache) return financialMetadataCache;
        const raw = await fetchJson('company/metadata.json');
        financialMetadataCache = raw && typeof raw === 'object' ? raw : {};
        return financialMetadataCache;
    }

    async function getCompanyProfilesData() {
        if (Array.isArray(companyProfilesCache)) return companyProfilesCache;
        const raw = await fetchJson('company/profiles.json');
        companyProfilesCache = Array.isArray(raw) ? raw : [];
        return companyProfilesCache;
    }

    async function getModalNewsData() {
        if (Array.isArray(modalNewsCache)) return modalNewsCache;
        const [disclosures, exchangeMessages, notices] = await Promise.all([
            fetchJson('notify/disclosures.json'),
            fetchJson('notify/exchange_messages.json'),
            fetchJson('notify/notices.json')
        ]);
        modalNewsCache = [
            ...normalizeNewsRows(disclosures, 'Disclosure'),
            ...normalizeNewsRows(exchangeMessages, 'Exchange'),
            ...normalizeNotices(notices).map((item) => ({ ...item, category: item.category || 'Notice' }))
        ].sort((a, b) => parseDateValue(b.date) - parseDateValue(a.date));
        return modalNewsCache;
    }

    function buildDocumentUrl(path, metadata) {
        const baseUrl = metadata?.document_base_url || 'https://www.nepalstock.com.np/api/nots/security/fetchFiles?fileLocation=';
        const encodedPath = String(path || '')
            .split('/')
            .map((part) => encodeURIComponent(part))
            .join('/');
        return `${baseUrl}${encodedPath}`;
    }

    async function getLtpHistoryManifest() {
        if (ltpHistoryManifestCache) return ltpHistoryManifestCache;
        const raw = await fetchJson('ltp/manifest.json');
        ltpHistoryManifestCache = raw && typeof raw === 'object' ? raw : {};
        return ltpHistoryManifestCache;
    }

    async function getLtpHistoryShard(month) {
        if (ltpHistoryShardCache[month]) return ltpHistoryShardCache[month];
        const raw = await fetchJson(`ltp/monthly/${month}.json`);
        ltpHistoryShardCache[month] = raw && typeof raw === 'object' ? raw : null;
        return ltpHistoryShardCache[month];
    }

    function normalizeHistoryRow(shard, row) {
        if (!shard || !Array.isArray(shard.dates) || !Array.isArray(shard.columns) || !Array.isArray(row)) {
            return null;
        }

        const dateIndex = row[0];
        if (!Number.isInteger(dateIndex) || dateIndex < 0 || dateIndex >= shard.dates.length) return null;

        const item = { date: shard.dates[dateIndex] };
        shard.columns.forEach((column, index) => {
            if (index === 0) return;
            item[column] = row[index];
        });
        return item;
    }

    async function getLtpHistoryForSymbol(symbol) {
        const manifest = await getLtpHistoryManifest();
        const months = Array.isArray(manifest.availableMonths)
            ? manifest.availableMonths
            : [];
        if (months.length === 0) return [];

        const shards = await Promise.all(months.map(getLtpHistoryShard));
        return shards
            .filter(Boolean)
            .flatMap((shard) => {
                const rows = shard.series && Array.isArray(shard.series[symbol])
                    ? shard.series[symbol]
                    : [];
                return rows.map((row) => normalizeHistoryRow(shard, row)).filter(Boolean);
            })
            .sort((a, b) => String(b.date || '').localeCompare(String(a.date || '')));
    }

    function filterLtpRowsByRange(rows, range) {
        if (!Array.isArray(rows) || rows.length === 0 || range === 'all') return rows.slice();

        const sorted = rows.slice().sort((a, b) => String(a.date || '').localeCompare(String(b.date || '')));
        const latest = sorted[sorted.length - 1];
        const latestTime = parseDateValue(latest.date);
        if (!latestTime) return rows.slice();

        const rangeDays = {
            '1m': 31,
            '3m': 92,
            '6m': 183,
            '1y': 365
        };
        const days = rangeDays[range] || 31;
        const cutoff = latestTime - (days * 24 * 60 * 60 * 1000);
        return rows.filter((row) => parseDateValue(row.date) >= cutoff);
    }

    function resetDividendSection(symbol) {
        modalDividendStatusEl.textContent = `Open dividend history for ${symbol}.`;
        modalDividendSummaryEl.textContent = '';
        modalDividendAnalysisEl.textContent = '';
        modalDividendListEl.innerHTML = '';
    }

    function resetLtpHistorySection(symbol) {
        if (!modalLtpHistoryStatusEl) return;
        currentLtpHistoryRows = [];
        currentLtpHistoryRange = '1m';
        currentLtpChartHoverIndex = null;
        currentLtpChartPinnedIndex = null;
        hideLtpChartTooltip();
        modalLtpHistoryStatusEl.textContent = `Open price history for ${symbol}.`;
        modalLtpHistorySummaryEl.textContent = '';
        modalLtpHistoryListEl.innerHTML = '';
        if (modalLtpHistoryStatsEl) modalLtpHistoryStatsEl.innerHTML = '';
        updateLtpRangeButtons();
        drawLtpHistoryChart([]);
    }

    function resetFinancialSection(symbol) {
        if (!modalFinancialStatusEl) return;
        modalFinancialStatusEl.textContent = `Open financial reports for ${symbol}.`;
        modalFinancialSummaryEl.innerHTML = '';
        modalFinancialListEl.innerHTML = '';
        closeFinancialDocumentViewer();
    }

    function resetNewsSection(symbol) {
        if (!modalNewsStatusEl) return;
        modalNewsStatusEl.textContent = `Open related news for ${symbol}.`;
        modalNewsListEl.innerHTML = '';
    }

    function resetCompanyProfilePreview(symbol) {
        if (modalCompanyProfileTitleEl) modalCompanyProfileTitleEl.textContent = `Loading profile for ${symbol}...`;
        if (modalCompanyProfileTextEl) modalCompanyProfileTextEl.textContent = 'Company profile loads on demand for this symbol.';
        if (modalCompanyProfileFactsEl) modalCompanyProfileFactsEl.innerHTML = '';
    }

    function setCompanyProfileOpen(isOpen) {
        if (!modalCompanyProfileBodyEl || !modalCompanyProfileToggleBtn) return;
        modalCompanyProfileBodyEl.classList.toggle('is-hidden', !isOpen);
        modalCompanyProfileToggleBtn.setAttribute('aria-expanded', String(isOpen));
        modalCompanyProfileToggleBtn.classList.toggle('is-collapsed', !isOpen);
    }

    function closeFinancialDocumentViewer() {
        if (modalFinancialDocumentViewerEl) modalFinancialDocumentViewerEl.classList.add('is-hidden');
        if (modalFinancialListEl) modalFinancialListEl.classList.remove('is-hidden');
        if (modalFinancialSummaryEl) modalFinancialSummaryEl.classList.remove('is-hidden');
    }

    function openFinancialDocumentViewer(url, title) {
        if (!modalFinancialDocumentViewerEl) return;
        modalFinancialDocumentTitleEl.textContent = title || 'Report document';
        if (modalFinancialDocumentOpenEl) {
            modalFinancialDocumentOpenEl.href = url;
        }
        modalFinancialSummaryEl.classList.add('is-hidden');
        modalFinancialListEl.classList.add('is-hidden');
        modalFinancialDocumentViewerEl.classList.remove('is-hidden');
    }

    function renderCompanyProfilePreview(profile) {
        if (!profile) {
            if (modalCompanyProfileTitleEl) modalCompanyProfileTitleEl.textContent = 'No company profile found';
            if (modalCompanyProfileTextEl) modalCompanyProfileTextEl.textContent = 'NEPSE has no profile text for this symbol in the current dataset.';
            if (modalCompanyProfileFactsEl) modalCompanyProfileFactsEl.innerHTML = '';
            return;
        }

        const profileText = String(profile.profile || '').replace(/\s+/g, ' ').trim();
        if (modalCompanyProfileTitleEl) {
            modalCompanyProfileTitleEl.textContent = profileText ? 'Brief profile from NEPSE' : 'Contact details from NEPSE';
        }
        if (modalCompanyProfileTextEl) {
            modalCompanyProfileTextEl.textContent = profileText || 'NEPSE has contact details for this symbol, but no profile description yet.';
        }

        const facts = [
            ['Address', profile.address],
            ['Phone', profile.phone],
            ['Email', profile.email],
            ['Contact', profile.contact_person],
        ].filter(([, value]) => value);

        if (modalCompanyProfileFactsEl) {
            modalCompanyProfileFactsEl.innerHTML = facts.length
                ? facts.map(([label, value]) => `<span><strong>${escapeAttribute(label)}</strong>${escapeAttribute(value)}</span>`).join('')
                : '';
        }
    }

    async function loadCompanyProfilePreviewForCurrentSymbol() {
        if (!currentModalSymbol) return;
        try {
            const rows = await getCompanyProfilesData();
            const profile = rows.find((row) => normalizeSymbol(row.symbol) === currentModalSymbol);
            renderCompanyProfilePreview(profile);
        } catch (err) {
            console.error('Company profile load failed:', err);
            if (modalCompanyProfileTitleEl) modalCompanyProfileTitleEl.textContent = 'Company profile unavailable';
            if (modalCompanyProfileTextEl) modalCompanyProfileTextEl.textContent = 'Could not load the company profile right now.';
            if (modalCompanyProfileFactsEl) modalCompanyProfileFactsEl.innerHTML = '';
        }
    }

    function setModalFocusMode(mode) {
        const isDividend = mode === 'dividend';
        const isLtpHistory = mode === 'ltp-history';
        const isFinancial = mode === 'financial';
        const isNews = mode === 'news';

        stockModal.classList.toggle('dividend-focus', isDividend);
        stockModal.classList.toggle('ltp-history-focus', isLtpHistory);
        stockModal.classList.toggle('financial-focus', isFinancial);
        stockModal.classList.toggle('news-focus', isNews);
        modalDividendBlockEl.classList.toggle('is-hidden', !isDividend);
        if (modalLtpHistoryBlockEl) {
            modalLtpHistoryBlockEl.classList.toggle('is-hidden', !isLtpHistory);
        }
        if (modalFinancialBlockEl) {
            modalFinancialBlockEl.classList.toggle('is-hidden', !isFinancial);
        }
        if (modalNewsBlockEl) {
            modalNewsBlockEl.classList.toggle('is-hidden', !isNews);
        }
        if (modalMarketGridEl) {
            modalMarketGridEl.classList.toggle('is-hidden', isDividend || isLtpHistory || isFinancial || isNews);
        }
        if (modalCompanyProfilePreviewEl) {
            modalCompanyProfilePreviewEl.classList.toggle('is-hidden', isDividend || isLtpHistory || isFinancial || isNews);
        }
    }

    function numberValue(value) {
        const n = Number(value);
        return Number.isFinite(n) ? n : 0;
    }

    function buildDividendAnalysis(rows) {
        if (!rows.length) return 'No analysis available.';
        const totals = rows.map(r => numberValue(r.total_dividend));
        const latest = totals[0] || 0;
        const avg = totals.reduce((a, b) => a + b, 0) / totals.length;
        const max = Math.max(...totals);
        const min = Math.min(...totals);
        const latest3 = totals.slice(0, 3);
        const prev3 = totals.slice(3, 6);
        const latest3Avg = latest3.length ? latest3.reduce((a, b) => a + b, 0) / latest3.length : 0;
        const prev3Avg = prev3.length ? prev3.reduce((a, b) => a + b, 0) / prev3.length : latest3Avg;
        const trend = latest3Avg >= prev3Avg ? 'improving' : 'softening';
        return `Analysis: latest total dividend is ${latest.toFixed(2)}%. Average across ${rows.length} records is ${avg.toFixed(2)}% (min ${min.toFixed(2)}%, max ${max.toFixed(2)}%). Recent pattern looks ${trend}.`;
    }

    function renderDividendHistoryRows(rows) {
        if (!rows.length) {
            modalDividendListEl.innerHTML = '';
            return;
        }

        const topRows = rows.slice(0, 12);
        const cards = topRows.map((row) => `
            <div class="dividend-row">
                <div class="dividend-row-head">
                    <strong>${safeValue(row.fiscal_year)}</strong>
                    <span>${safeValue(row.announcement_date)}</span>
                </div>
                <div class="dividend-row-meta">
                    <span>Total: ${safeValue(row.total_dividend, '0')}%</span>
                    <span>Bonus: ${safeValue(row.bonus_share, '0')}%</span>
                    <span>Cash: ${safeValue(row.cash_dividend, '0')}%</span>
                    <span>Book Close: ${safeValue(row.bookclose_date)}</span>
                </div>
            </div>
        `).join('');

        modalDividendListEl.innerHTML = cards;
    }

    function buildLtpHistorySummary(rows) {
        if (!rows.length) return '';
        const sorted = rows.slice().sort((a, b) => String(a.date || '').localeCompare(String(b.date || '')));
        const first = sorted[0];
        const latest = sorted[sorted.length - 1];
        const firstLtp = Number(first.ltp);
        const latestLtp = Number(latest.ltp);
        const change = Number.isFinite(firstLtp) && Number.isFinite(latestLtp)
            ? latestLtp - firstLtp
            : 0;
        const percent = firstLtp ? (change / firstLtp) * 100 : 0;
        const sign = change > 0 ? '+' : '';
        return `${rows.length} daily records from ${safeValue(first.date)} to ${safeValue(latest.date)}. Latest close Rs. ${formatNumber(latestLtp, 2)} with ${sign}${change.toFixed(2)} (${sign}${percent.toFixed(2)}%) over this range.`;
    }

    function updateLtpRangeButtons() {
        document.querySelectorAll('[data-history-range]').forEach((button) => {
            const isActive = button.getAttribute('data-history-range') === currentLtpHistoryRange;
            button.classList.toggle('active', isActive);
            button.setAttribute('aria-pressed', String(isActive));
        });
    }

    function renderLtpHistoryStats(rows) {
        if (!modalLtpHistoryStatsEl) return;
        if (!rows.length) {
            modalLtpHistoryStatsEl.innerHTML = '';
            return;
        }

        const ltpValues = rows.map((row) => Number(row.ltp)).filter(Number.isFinite);
        const volumeTotal = rows.reduce((sum, row) => sum + (Number(row.volume) || 0), 0);
        const turnoverTotal = rows.reduce((sum, row) => sum + (Number(row.turnover) || 0), 0);
        const tradesTotal = rows.reduce((sum, row) => sum + (Number(row.trades) || 0), 0);
        const high = ltpValues.length ? Math.max(...ltpValues) : NaN;
        const low = ltpValues.length ? Math.min(...ltpValues) : NaN;
        const sorted = rows.slice().sort((a, b) => String(a.date || '').localeCompare(String(b.date || '')));
        const first = sorted[0] || {};
        const latest = sorted[sorted.length - 1] || {};
        const change = Number(latest.ltp) - Number(first.ltp);
        const percent = Number(first.ltp) ? (change / Number(first.ltp)) * 100 : 0;
        const sign = change > 0 ? '+' : '';
        const avgVolume = rows.length ? volumeTotal / rows.length : 0;

        modalLtpHistoryStatsEl.innerHTML = `
            <div><span>Latest</span><strong>Rs. ${formatNumber(Number(latest.ltp), 2)}</strong></div>
            <div><span>Range Change</span><strong class="${change >= 0 ? 'up-text' : 'down-text'}">${sign}${formatNumber(change, 2)} (${sign}${percent.toFixed(2)}%)</strong></div>
            <div><span>High</span><strong>Rs. ${formatNumber(high, 2)}</strong></div>
            <div><span>Low</span><strong>Rs. ${formatNumber(low, 2)}</strong></div>
            <div><span>Avg Volume</span><strong>${formatCompactNumber(avgVolume)}</strong></div>
            <div><span>Total Volume</span><strong>${formatCompactNumber(volumeTotal)}</strong></div>
            <div><span>Turnover</span><strong>Rs. ${formatCompactNumber(turnoverTotal)}</strong></div>
            <div><span>Trades</span><strong>${formatCompactNumber(tradesTotal)}</strong></div>
        `;
    }

    function hideLtpChartTooltip() {
        if (modalLtpHistoryTooltipEl) modalLtpHistoryTooltipEl.classList.add('is-hidden');
    }

    function drawLtpChartSelection(ctx, point, row, cssHeight, pinned) {
        if (!point || !row) return;
        ctx.save();
        ctx.strokeStyle = pinned ? 'rgba(251, 191, 36, 0.9)' : 'rgba(226, 232, 240, 0.55)';
        ctx.lineWidth = 1;
        ctx.setLineDash([4, 4]);
        ctx.beginPath();
        ctx.moveTo(point.x, 12);
        ctx.lineTo(point.x, cssHeight - 22);
        ctx.stroke();
        ctx.setLineDash([]);
        ctx.fillStyle = pinned ? 'rgba(251, 191, 36, 1)' : 'rgba(248, 250, 252, 1)';
        ctx.strokeStyle = 'rgba(10, 10, 10, 0.9)';
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.arc(point.x, point.y, pinned ? 5.5 : 4.5, 0, Math.PI * 2);
        ctx.fill();
        ctx.stroke();
        ctx.restore();
    }

    function showLtpChartTooltip(index, pinned = false) {
        if (!modalLtpHistoryTooltipEl || !currentLtpChartState.rows[index] || !currentLtpChartState.points[index]) return;
        const row = currentLtpChartState.rows[index];
        const point = currentLtpChartState.points[index];
        const tooltipWidth = 190;
        const left = Math.min(
            Math.max(point.x - tooltipWidth / 2, 8),
            Math.max(8, currentLtpChartState.cssWidth - tooltipWidth - 8)
        );
        const top = point.y > 78 ? point.y - 70 : point.y + 16;

        modalLtpHistoryTooltipEl.innerHTML = `
            <span>${pinned ? 'Selected' : 'Price point'} | ${escapeAttribute(row.date)}</span>
            <strong>Rs. ${formatNumber(Number(row.ltp), 2)}</strong>
            <small>Vol ${formatCompactNumber(Number(row.volume))} | Trades ${formatNumber(Number(row.trades), 0)}</small>
        `;
        modalLtpHistoryTooltipEl.style.left = `${left}px`;
        modalLtpHistoryTooltipEl.style.top = `${top}px`;
        modalLtpHistoryTooltipEl.classList.remove('is-hidden');
    }

    function drawLtpHistoryChart(rows, activeIndex = null) {
        if (!modalLtpHistoryChartEl) return;
        const ctx = modalLtpHistoryChartEl.getContext('2d');
        if (!ctx) return;

        const dpr = window.devicePixelRatio || 1;
        const cssWidth = Math.max(280, Math.floor(modalLtpHistoryChartEl.clientWidth || 620));
        const cssHeight = Math.max(150, Math.floor(modalLtpHistoryChartEl.clientHeight || 150));
        modalLtpHistoryChartEl.width = Math.floor(cssWidth * dpr);
        modalLtpHistoryChartEl.height = Math.floor(cssHeight * dpr);
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        ctx.clearRect(0, 0, cssWidth, cssHeight);

        const sorted = rows
            .slice()
            .sort((a, b) => String(a.date || '').localeCompare(String(b.date || '')))
            .filter((row) => Number.isFinite(Number(row.ltp)));

        if (sorted.length === 0) {
            currentLtpChartState = { rows: [], points: [], cssWidth, cssHeight };
            hideLtpChartTooltip();
            ctx.fillStyle = 'rgba(160, 168, 200, 0.9)';
            ctx.font = '500 13px Inter, sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText('No price history available', cssWidth / 2, cssHeight / 2);
            return;
        }

        const values = sorted.map((row) => Number(row.ltp));
        const min = Math.min(...values);
        const max = Math.max(...values);
        const span = max - min || 1;
        const pad = { top: 18, right: 16, bottom: 24, left: 42 };
        const chartW = cssWidth - pad.left - pad.right;
        const chartH = cssHeight - pad.top - pad.bottom;

        ctx.strokeStyle = 'rgba(255,255,255,0.09)';
        ctx.lineWidth = 1;
        for (let i = 0; i <= 3; i += 1) {
            const y = pad.top + (chartH / 3) * i;
            ctx.beginPath();
            ctx.moveTo(pad.left, y);
            ctx.lineTo(pad.left + chartW, y);
            ctx.stroke();
        }

        const gradient = ctx.createLinearGradient(0, pad.top, 0, pad.top + chartH);
        gradient.addColorStop(0, 'rgba(99, 102, 241, 0.3)');
        gradient.addColorStop(1, 'rgba(99, 102, 241, 0.02)');

        const points = values.map((value, index) => {
            const x = pad.left + (sorted.length === 1 ? chartW : (chartW * index) / (sorted.length - 1));
            const y = pad.top + chartH - ((value - min) / span) * chartH;
            return { x, y };
        });
        currentLtpChartState = { rows: sorted, points, cssWidth, cssHeight };

        ctx.beginPath();
        points.forEach((point, index) => {
            if (index === 0) ctx.moveTo(point.x, point.y);
            else ctx.lineTo(point.x, point.y);
        });
        ctx.strokeStyle = 'rgba(129, 140, 248, 1)';
        ctx.lineWidth = 2.5;
        ctx.stroke();

        if (points.length > 1) {
            ctx.lineTo(points[points.length - 1].x, pad.top + chartH);
            ctx.lineTo(points[0].x, pad.top + chartH);
            ctx.closePath();
            ctx.fillStyle = gradient;
            ctx.fill();
        }

        const last = points[points.length - 1];
        ctx.fillStyle = 'rgba(129, 140, 248, 1)';
        ctx.beginPath();
        ctx.arc(last.x, last.y, 4, 0, Math.PI * 2);
        ctx.fill();

        ctx.fillStyle = 'rgba(203, 213, 225, 0.9)';
        ctx.font = '500 11px Inter, sans-serif';
        ctx.textAlign = 'left';
        ctx.fillText(`Rs. ${formatNumber(max, 2)}`, 4, pad.top + 4);
        ctx.fillText(`Rs. ${formatNumber(min, 2)}`, 4, pad.top + chartH);
        ctx.textAlign = 'center';
        ctx.fillText(sorted[0].date, pad.left, cssHeight - 6);
        ctx.fillText(sorted[sorted.length - 1].date, pad.left + chartW, cssHeight - 6);

        const selectedIndex = Number.isInteger(activeIndex) ? activeIndex : currentLtpChartPinnedIndex;
        if (Number.isInteger(selectedIndex) && points[selectedIndex]) {
            drawLtpChartSelection(ctx, points[selectedIndex], sorted[selectedIndex], cssHeight, selectedIndex === currentLtpChartPinnedIndex);
            showLtpChartTooltip(selectedIndex, selectedIndex === currentLtpChartPinnedIndex);
        } else {
            hideLtpChartTooltip();
        }
    }

    function renderCurrentLtpHistoryRange() {
        const rows = filterLtpRowsByRange(currentLtpHistoryRows, currentLtpHistoryRange);
        currentLtpChartHoverIndex = null;
        currentLtpChartPinnedIndex = null;
        modalLtpHistorySummaryEl.textContent = buildLtpHistorySummary(rows);
        renderLtpHistoryStats(rows);
        drawLtpHistoryChart(rows);
        renderLtpHistoryRows(rows);
        updateLtpRangeButtons();
    }

    function getNearestLtpChartIndex(event) {
        if (!modalLtpHistoryChartEl || !currentLtpChartState.points.length) return null;
        const rect = modalLtpHistoryChartEl.getBoundingClientRect();
        const x = event.clientX - rect.left;
        const y = event.clientY - rect.top;
        let nearest = null;
        let nearestDistance = Infinity;

        currentLtpChartState.points.forEach((point, index) => {
            const distance = Math.hypot(point.x - x, point.y - y);
            if (distance < nearestDistance) {
                nearestDistance = distance;
                nearest = index;
            }
        });

        return nearestDistance <= 28 ? nearest : null;
    }

    function renderLtpHistoryRows(rows) {
        if (!modalLtpHistoryListEl) return;
        if (!rows.length) {
            modalLtpHistoryListEl.innerHTML = '';
            return;
        }

        const sorted = rows
            .slice()
            .sort((a, b) => String(b.date || '').localeCompare(String(a.date || '')));

        modalLtpHistoryListEl.innerHTML = sorted.slice(0, 30).map((row) => `
            <div class="history-row">
                <div class="history-row-head">
                    <strong>${safeValue(row.date)}</strong>
                    <span>Rs. ${formatNumber(Number(row.ltp), 2)}</span>
                </div>
                <div class="history-row-meta">
                    <span>Volume: ${formatCompactNumber(Number(row.volume))}</span>
                    <span>Turnover: Rs. ${formatCompactNumber(Number(row.turnover))}</span>
                    <span>Trades: ${formatNumber(Number(row.trades), 0)}</span>
                </div>
            </div>
        `).join('');
    }

    async function loadLtpHistoryForCurrentSymbol() {
        if (!currentModalSymbol) return;
        setModalFocusMode('ltp-history');
        modalLtpHistoryStatusEl.textContent = `Loading price history for ${currentModalSymbol}...`;
        modalLtpHistorySummaryEl.textContent = '';
        modalLtpHistoryListEl.innerHTML = '';

        try {
            const rows = await getLtpHistoryForSymbol(currentModalSymbol);
            if (!rows.length) {
                modalLtpHistoryStatusEl.textContent = `No price history found for ${currentModalSymbol}.`;
                return;
            }

            currentLtpHistoryRows = rows;
            modalLtpHistoryStatusEl.textContent = `Loaded ${rows.length} price history records for ${currentModalSymbol}.`;
            renderCurrentLtpHistoryRange();
        } catch (err) {
            console.error('LTP history load failed:', err);
            modalLtpHistoryStatusEl.textContent = 'Failed to load price history.';
        }
    }

    function getLatestReport(reports) {
        if (!Array.isArray(reports) || reports.length === 0) return null;
        const sorted = reports.slice().sort((a, b) => {
            const aDoc = Array.isArray(a.documents) ? a.documents[0] : null;
            const bDoc = Array.isArray(b.documents) ? b.documents[0] : null;
            return parseDateValue(bDoc?.submitted_date) - parseDateValue(aDoc?.submitted_date);
        });
        return sorted[0];
    }

    function renderFinancialSummary(company, reports) {
        const latest = getLatestReport(reports);
        if (!latest) {
            modalFinancialSummaryEl.innerHTML = '';
            return;
        }

        const latestDoc = Array.isArray(latest.documents) ? latest.documents[0] : null;
        modalFinancialSummaryEl.innerHTML = `
            <div class="financial-kpi-grid">
                <div class="financial-kpi"><span>Latest Report</span><strong>${safeValue(latest.type)}</strong><small>${safeValue(latest.quarter || latest.fy_nepali || latest.fy)}</small></div>
                <div class="financial-kpi"><span>EPS</span><strong>${formatNumber(Number(latest.eps), 2)}</strong><small>Earnings per share</small></div>
                <div class="financial-kpi"><span>P/E</span><strong>${formatNumber(Number(latest.pe), 2)}</strong><small>Price to earnings</small></div>
                <div class="financial-kpi"><span>Profit</span><strong>Rs. ${formatCompactNumber(Number(latest.profit))}</strong><small>${safeValue(latest.fy_nepali || latest.fy)}</small></div>
                <div class="financial-kpi"><span>Paid-up Capital</span><strong>Rs. ${formatCompactNumber(Number(latest.paid_up_capital))}</strong><small>Reported capital</small></div>
                <div class="financial-kpi"><span>Net Worth / Share</span><strong>${formatNumber(Number(latest.net_worth_per_share), 2)}</strong><small>Submitted ${safeValue(latestDoc?.submitted_date)}</small></div>
            </div>
            <p class="financial-note">NPL / Non-performing loan is not available in NEPSE's structured financial JSON; it may exist only inside attached PDF reports.</p>
        `;
    }

    function renderFinancialReports(company, metadata) {
        const reports = Array.isArray(company?.reports) ? company.reports : [];
        renderFinancialSummary(company, reports);

        if (!reports.length) {
            modalFinancialListEl.innerHTML = '';
            return;
        }

        const rowsHtml = reports.map((report) => {
            const documents = Array.isArray(report.documents) ? report.documents : [];
            const documentLinks = documents.length
                ? documents.map((doc, index) => {
                    const docUrl = buildDocumentUrl(doc.path, metadata);
                    const docTitle = `${safeValue(report.type)} ${safeValue(report.quarter || report.fy_nepali || report.fy)}`;
                    return `
                    <button type="button" data-doc-url="${escapeAttribute(docUrl)}" data-doc-title="${escapeAttribute(docTitle)}">
                        <i class="fa-regular fa-file-pdf"></i> ${index + 1}${doc.submitted_date ? ` (${safeValue(doc.submitted_date)})` : ''}
                    </button>
                `;
                }).join('')
                : '<span class="financial-document-empty">No attached documents</span>';

            return `
                <tr>
                    <td>
                        <strong>${safeValue(report.type)}</strong>
                        <span>${safeValue(report.quarter || 'Annual')}</span>
                    </td>
                    <td>
                        <strong>${safeValue(report.fy_nepali || report.fy)}</strong>
                        <span>${safeValue(report.fy)}</span>
                    </td>
                    <td>${formatNumber(Number(report.eps), 2)}</td>
                    <td>${formatNumber(Number(report.pe), 2)}</td>
                    <td>Rs. ${formatCompactNumber(Number(report.profit))}</td>
                    <td>Rs. ${formatCompactNumber(Number(report.paid_up_capital))}</td>
                    <td>${formatNumber(Number(report.net_worth_per_share), 2)}</td>
                    <td><div class="financial-documents">${documentLinks}</div></td>
                </tr>
            `;
        }).join('');

        modalFinancialListEl.innerHTML = `
            <div class="financial-table-wrap">
                <table class="financial-report-table">
                    <thead>
                        <tr>
                            <th>Report</th>
                            <th>Fiscal Year</th>
                            <th>EPS</th>
                            <th>P/E</th>
                            <th>Profit</th>
                            <th>Paid-up Capital</th>
                            <th>Net Worth / Share</th>
                            <th>Documents</th>
                        </tr>
                    </thead>
                    <tbody>${rowsHtml}</tbody>
                </table>
            </div>
        `;
    }

    async function loadFinancialReportsForCurrentSymbol() {
        if (!currentModalSymbol) return;
        setModalFocusMode('financial');
        modalFinancialStatusEl.textContent = `Loading financial reports for ${currentModalSymbol}...`;
        modalFinancialSummaryEl.innerHTML = '';
        modalFinancialListEl.innerHTML = '';
        closeFinancialDocumentViewer();

        try {
            const [rows, metadata] = await Promise.all([
                getFinancialReportsData(),
                getFinancialMetadata()
            ]);
            const company = rows.find((row) => normalizeSymbol(row.symbol) === currentModalSymbol);
            if (!company || !Array.isArray(company.reports) || company.reports.length === 0) {
                modalFinancialStatusEl.textContent = `No structured financial reports found for ${currentModalSymbol}.`;
                return;
            }

            modalFinancialStatusEl.textContent = `Loaded ${company.reports.length} financial reports for ${currentModalSymbol}.`;
            renderFinancialReports(company, metadata);
        } catch (err) {
            console.error('Financial reports load failed:', err);
            modalFinancialStatusEl.textContent = 'Failed to load financial reports.';
        }
    }

    async function loadDividendHistoryForCurrentSymbol() {
        if (!currentModalSymbol) return;
        setModalFocusMode('dividend');
        modalDividendStatusEl.textContent = `Loading dividend history for ${currentModalSymbol}...`;
        modalDividendSummaryEl.textContent = '';
        modalDividendListEl.innerHTML = '';

        try {
            const rows = await getDividendHistoryData();
            const matched = rows
                .filter((row) => normalizeSymbol(row.symbol) === currentModalSymbol)
                .sort((a, b) => parseDateValue(b.announcement_date) - parseDateValue(a.announcement_date));

            if (!matched.length) {
                modalDividendStatusEl.textContent = `No dividend history found for ${currentModalSymbol}.`;
                return;
            }

            const latest = matched[0];
            modalDividendStatusEl.textContent = `Loaded ${matched.length} records for ${currentModalSymbol}.`;
            modalDividendSummaryEl.textContent = `Latest: ${safeValue(latest.announcement_date)} | FY ${safeValue(latest.fiscal_year)} | Total ${safeValue(latest.total_dividend, '0')}%`;
            modalDividendAnalysisEl.textContent = buildDividendAnalysis(matched);
            renderDividendHistoryRows(matched);
        } catch (err) {
            console.error('Dividend history load failed:', err);
            modalDividendStatusEl.textContent = 'Failed to load dividend history.';
        }
    }

    function normalizeNewsRows(rows, category) {
        if (!Array.isArray(rows)) return [];
        return rows.map((item) => ({
            category,
            symbol: normalizeSymbol(item.symbol || ''),
            title: item.title || item.noticeHeading || item.newsHeadline || item.messageTitle || 'Untitled update',
            body: stripHtml(item.body || item.noticeBody || item.newsBody || item.messageBody || ''),
            source: item.source || '',
            date: item.publishedAt || item.modifiedDate || item.addedDate || item.expiresAt || item.noticeExpiryDate || '',
            documents: Array.isArray(item.documents) ? item.documents : [],
            filePath: item.filePath || item.noticeFilePath || item.fileUrl || ''
        })).filter((item) => item.title || item.body);
    }

    function relatedNewsMatches(item, symbol, companyName) {
        if (item.symbol && item.symbol === symbol) return true;
        const haystack = `${item.title || ''} ${item.body || ''} ${item.source || ''}`.toUpperCase();
        if (haystack.includes(symbol)) return true;

        const usefulWords = String(companyName || '')
            .toUpperCase()
            .split(/\s+/)
            .map((word) => word.replace(/[^A-Z0-9]/g, ''))
            .filter((word) => word.length >= 4 && !['LIMITED', 'BITTIYA', 'SANSTHA', 'COMPANY'].includes(word));
        return usefulWords.slice(0, 3).some((word) => haystack.includes(word));
    }

    function renderModalNewsRows(rows) {
        if (!rows.length) {
            modalNewsListEl.innerHTML = '';
            return;
        }

        modalNewsListEl.innerHTML = rows.slice(0, 16).map((item) => {
            const firstDoc = Array.isArray(item.documents) ? item.documents[0] : null;
            const docUrl = firstDoc?.fileUrl || item.filePath || '';
            const docLink = docUrl
                ? `<a href="${escapeAttribute(docUrl)}" target="_blank" rel="noopener noreferrer">Open document</a>`
                : '';
            return `
                <article class="modal-news-item">
                    <div class="notice-head">
                        <span class="chip small">${escapeAttribute(item.category)}</span>
                        <span class="notice-date">${item.date ? new Date(item.date).toLocaleDateString() : 'N/A'}</span>
                    </div>
                    <h4>${escapeAttribute(item.title)}</h4>
                    <p>${escapeAttribute(item.body || 'No description provided.')}</p>
                    ${docLink}
                </article>
            `;
        }).join('');
    }

    async function loadNewsForCurrentSymbol() {
        if (!currentModalSymbol) return;
        setModalFocusMode('news');
        modalNewsStatusEl.textContent = `Loading related news for ${currentModalSymbol}...`;
        modalNewsListEl.innerHTML = '';

        try {
            const companyName = document.getElementById('modal-company-name')?.textContent || '';
            const rows = await getModalNewsData();
            const matched = rows.filter((item) => relatedNewsMatches(item, currentModalSymbol, companyName));
            if (!matched.length) {
                modalNewsStatusEl.textContent = `No related news found for ${currentModalSymbol}.`;
                return;
            }

            modalNewsStatusEl.textContent = `Loaded ${matched.length} related updates for ${currentModalSymbol}.`;
            renderModalNewsRows(matched);
        } catch (err) {
            console.error('Related news load failed:', err);
            modalNewsStatusEl.textContent = 'Failed to load related news.';
        }
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
                fetchJson('other/sector_codes.json'),
                fetchJson('ipo/upcoming.json'),
                fetchJson('market/summary.json'),
                fetchJson('market/indices.json'),
                fetchJson('market/top_stocks.json'),
                fetchJson('notify/notices.json'),
                fetchJson('market/status.json'),
                fetchJson('market/history.json'),
                fetchJson('market/supply_demand.json')
            ]);

            if (!stocks || stocks.length === 0) {
                throw new Error('Failed to fetch stock data');
            }

            allStocks = stocks;
            renderStocks(allStocks);
            updateMetadata(allStocks);

            if (sectors && typeof sectors === 'object' && !Array.isArray(sectors)) {
                Object.entries(sectors).forEach(([sector, items]) => {
                    if (!Array.isArray(items)) return;
                    uniqueSectors.add(sector);
                    items.forEach(item => {
                        if (!item || !item.symbol) return;
                        sectorMap[item.symbol] = sector;
                        if (item.name) companyNameMap[item.symbol] = item.name;
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
        const noticeGroups = notices && typeof notices === 'object' && !Array.isArray(notices)
            ? notices
            : { general: Array.isArray(notices) ? notices : [] };

        categories.forEach(category => {
            if (!Array.isArray(noticeGroups[category])) return;
            noticeGroups[category].forEach(item => {
                const title = item.title || item.noticeHeading || item.newsHeadline || item.messageTitle || 'Untitled notice';
                const body = item.body || item.noticeBody || item.newsBody || item.messageBody || '';
                const rawDate = item.publishedAt || item.modifiedDate || item.addedDate || item.expiresAt || item.noticeExpiryDate || item.expiryDate || '';
                const type = item.type || (category === 'general' ? 'Notice' : category);
                rows.push({
                    category: type,
                    title,
                    body: stripHtml(body),
                    date: rawDate,
                    filePath: item.filePath || item.noticeFilePath || item.fileUrl || ''
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
                    <span class="chip small">${escapeAttribute(item.category)}</span>
                    <span class="notice-date">${item.date ? new Date(item.date).toLocaleDateString() : 'N/A'}</span>
                </div>
                <p class="notice-title">${escapeAttribute(item.title)}</p>
                <p class="notice-body">${escapeAttribute(item.body || 'No description provided.')}</p>
            </div>
        `).join('');
    }

    function renderIPOs(ipos) {
        const ipoSection = document.getElementById('ipo-section');
        const ipoGrid = document.getElementById('ipo-grid');
        const ipoStatusFilter = document.getElementById('ipo-status-filter');
        const ipoSummaryMeta = document.getElementById('ipo-summary-meta');
        hasRenderableIpos = false;

        if (!Array.isArray(ipos) || ipos.length === 0) {
            ipoSection.classList.add('is-hidden');
            ipoChartSnapshot = { open: 0, upcoming: 0, closed: 0 };
            renderIpoStatusChart(0, 0, 0);
            updateTopSectionsVisibility();
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
            hasRenderableIpos = true;
            ipoSection.classList.remove('is-hidden');
            ipoGrid.innerHTML = '<p class="intel-empty">Unable to parse IPO windows from source data.</p>';
            if (ipoSummaryMeta) ipoSummaryMeta.textContent = '0 active | 0 closed';
            ipoChartSnapshot = { open: 0, upcoming: 0, closed: 0 };
            renderIpoStatusChart(0, 0, 0);
            updateTopSectionsVisibility();
            return;
        }

        const openIpos = classifiedIpos.filter(({ status }) => status === 'open');
        const upcomingIpos = classifiedIpos.filter(({ status }) => status === 'upcoming');
        const closedIpos = classifiedIpos.filter(({ status }) => status === 'closed');

        if (openIpos.length === 0 && upcomingIpos.length === 0 && closedIpos.length === 0) {
            ipoSection.classList.add('is-hidden');
            ipoChartSnapshot = { open: 0, upcoming: 0, closed: 0 };
            renderIpoStatusChart(0, 0, 0);
            updateTopSectionsVisibility();
            return;
        }

        hasRenderableIpos = true;
        ipoSection.classList.remove('is-hidden');
        ipoChartSnapshot = {
            open: openIpos.length,
            upcoming: upcomingIpos.length,
            closed: closedIpos.length
        };
        renderIpoStatusChart(ipoChartSnapshot.open, ipoChartSnapshot.upcoming, ipoChartSnapshot.closed);

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
            const visibleRows = showAllIpos ? rows : rows.slice(0, 4);
            visibleRows.forEach((item) => renderIpoCard(ipoGrid, item));

            if (rows.length > 4) {
                const toggleWrap = document.createElement('div');
                toggleWrap.style.gridColumn = '1 / -1';
                toggleWrap.style.display = 'flex';
                toggleWrap.style.justifyContent = 'center';
                toggleWrap.style.marginTop = '0.5rem';

                const toggleBtn = document.createElement('button');
                toggleBtn.type = 'button';
                toggleBtn.className = 'ipo-toggle-btn';
                toggleBtn.textContent = showAllIpos ? 'Show less' : `View more (${rows.length - 4})`;
                toggleBtn.addEventListener('click', () => {
                    showAllIpos = !showAllIpos;
                    renderByFilter();
                });

                toggleWrap.appendChild(toggleBtn);
                ipoGrid.appendChild(toggleWrap);
            }
        };

        if (ipoStatusFilter) {
            ipoStatusFilter.onchange = () => {
                showAllIpos = false;
                renderByFilter();
            };
        }
        renderByFilter();
        updateTopSectionsVisibility();
    }

    function renderIpoStatusChart(openCount, upcomingCount, closedCount) {
        if (!ipoStatusChartEl) return;
        const ctx = ipoStatusChartEl.getContext('2d');
        if (!ctx) return;

        const dpr = window.devicePixelRatio || 1;
        const cssWidth = Math.max(320, Math.floor(ipoStatusChartEl.clientWidth || 900));
        const cssHeight = Math.max(120, Math.floor(ipoStatusChartEl.clientHeight || 130));
        ipoStatusChartEl.width = Math.floor(cssWidth * dpr);
        ipoStatusChartEl.height = Math.floor(cssHeight * dpr);
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        ctx.clearRect(0, 0, cssWidth, cssHeight);

        const data = [
            { label: 'Open', value: openCount, color: '#22c55e' },
            { label: 'Upcoming', value: upcomingCount, color: '#f59e0b' },
            { label: 'Closed', value: closedCount, color: '#ef4444' }
        ];

        const maxValue = Math.max(1, ...data.map(d => d.value));
        const pad = { top: 18, right: 14, bottom: 28, left: 20 };
        const chartW = cssWidth - pad.left - pad.right;
        const chartH = cssHeight - pad.top - pad.bottom;
        const slotW = chartW / data.length;
        const barW = Math.min(68, Math.max(30, slotW * 0.56));

        ctx.fillStyle = 'rgba(255,255,255,0.07)';
        ctx.fillRect(pad.left, pad.top + chartH, chartW, 1);

        data.forEach((item, i) => {
            const x = pad.left + i * slotW + (slotW - barW) / 2;
            const h = (item.value / maxValue) * (chartH - 8);
            const y = pad.top + chartH - h;

            ctx.fillStyle = item.color;
            ctx.fillRect(x, y, barW, h);

            ctx.fillStyle = '#d7def8';
            ctx.font = '600 12px Outfit, Inter, sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText(String(item.value), x + barW / 2, y - 6);

            ctx.fillStyle = '#a0a8c8';
            ctx.font = '500 11px Outfit, Inter, sans-serif';
            ctx.fillText(item.label, x + barW / 2, cssHeight - 10);
        });
    }

    function updateTopSectionsVisibility() {
        const term = (searchInput?.value || '').trim();
        const hasActiveFilter = term.length > 0 || currentSelectedSector !== 'all';
        document.body.classList.toggle('filter-active', hasActiveFilter);

        dashboardSectionEls.forEach((el) => {
            el.classList.toggle('is-hidden', hasActiveFilter);
            el.style.display = hasActiveFilter ? 'none' : '';
        });

        if (ipoSectionEl) {
            const shouldHideIpo = hasActiveFilter || !hasRenderableIpos;
            ipoSectionEl.classList.toggle('is-hidden', shouldHideIpo);
            ipoSectionEl.style.display = shouldHideIpo ? 'none' : '';
        }
    }

    function populateSectorDropdown() {
        const sortedSectors = Array.from(uniqueSectors).sort();
        const allOption = dropdownOptions.querySelector('[data-value="all"]');
        const existingDynamicOptions = dropdownOptions.querySelectorAll('.option-item:not([data-value="all"])');
        existingDynamicOptions.forEach((node) => node.remove());

        if (allOption) {
            allOption.classList.add('selected');
            allOption.setAttribute('aria-selected', 'true');
        }

        const fragment = document.createDocumentFragment();
        sortedSectors.forEach(sector => {
            const option = document.createElement('div');
            option.className = 'option-item';
            option.setAttribute('role', 'option');
            option.setAttribute('tabindex', '0');
            option.setAttribute('aria-selected', 'false');
            option.setAttribute('data-value', sector);
            option.textContent = sector;
            fragment.appendChild(option);
        });
        dropdownOptions.appendChild(fragment);
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
        updateTopSectionsVisibility();
    }

    function showStockDetails(stock) {
        activeModalTrigger = document.activeElement;
        const isUp = stock.change >= 0;
        const companyName = companyNameMap[stock.symbol] || stock.name || 'Company Name Not Available';
        const sector = sectorMap[stock.symbol] || 'Others';
        currentModalSymbol = normalizeSymbol(stock.symbol);

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
        document.getElementById('modal-turnover').textContent = `Rs. ${formatCompactNumber(Number(stock.turnover || 0))}`;
        document.getElementById('modal-trades').textContent = formatNumber(Number(stock.trades || 0), 0);
        document.getElementById('modal-market-cap').textContent = stock.market_cap ? `Rs. ${formatCompactNumber(Number(stock.market_cap))}` : '-';
        document.getElementById('modal-day-range').textContent = `${formatNumber(Number(stock.low), 2)} - ${formatNumber(Number(stock.high), 2)}`;

        const lastUpdated = new Date(stock.last_updated);
        document.getElementById('modal-last-updated').textContent = lastUpdated.toLocaleString([], {
            year: 'numeric',
            month: 'long',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });

        resetDividendSection(currentModalSymbol);
        resetLtpHistorySection(currentModalSymbol);
        resetFinancialSection(currentModalSymbol);
        resetNewsSection(currentModalSymbol);
        resetCompanyProfilePreview(currentModalSymbol);
        setCompanyProfileOpen(false);
        setModalFocusMode(null);
        loadCompanyProfilePreviewForCurrentSymbol();

        stockModal.classList.add('show');
        document.body.style.overflow = 'hidden';
        closeModalBtn.focus();
    }

    function closeModal() {
        stockModal.classList.remove('show');
        setModalFocusMode(null);
        document.body.style.overflow = '';
        if (activeModalTrigger && typeof activeModalTrigger.focus === 'function') {
            activeModalTrigger.focus();
        }
    }

    closeModalBtn.addEventListener('click', closeModal);
    if (modalDividendOpenBtn) {
        modalDividendOpenBtn.addEventListener('click', loadDividendHistoryForCurrentSymbol);
    }
    if (modalDividendBackBtn) {
        modalDividendBackBtn.addEventListener('click', () => setModalFocusMode(null));
    }
    if (modalLtpHistoryOpenBtn) {
        modalLtpHistoryOpenBtn.addEventListener('click', loadLtpHistoryForCurrentSymbol);
    }
    if (modalLtpHistoryBackBtn) {
        modalLtpHistoryBackBtn.addEventListener('click', () => setModalFocusMode(null));
    }
    if (modalFinancialOpenBtn) {
        modalFinancialOpenBtn.addEventListener('click', loadFinancialReportsForCurrentSymbol);
    }
    if (modalNewsOpenBtn) {
        modalNewsOpenBtn.addEventListener('click', loadNewsForCurrentSymbol);
    }
    if (modalNewsBackBtn) {
        modalNewsBackBtn.addEventListener('click', () => setModalFocusMode(null));
    }
    if (modalCompanyProfileToggleBtn) {
        modalCompanyProfileToggleBtn.addEventListener('click', () => {
            const isOpen = modalCompanyProfileToggleBtn.getAttribute('aria-expanded') !== 'false';
            setCompanyProfileOpen(!isOpen);
        });
    }
    if (modalFinancialBackBtn) {
        modalFinancialBackBtn.addEventListener('click', () => {
            closeFinancialDocumentViewer();
            setModalFocusMode(null);
        });
    }
    if (modalFinancialDocumentBackBtn) {
        modalFinancialDocumentBackBtn.addEventListener('click', closeFinancialDocumentViewer);
    }
    if (modalFinancialListEl) {
        modalFinancialListEl.addEventListener('click', (event) => {
            const button = event.target.closest('[data-doc-url]');
            if (!button) return;
            openFinancialDocumentViewer(button.getAttribute('data-doc-url'), button.getAttribute('data-doc-title'));
        });
    }
    document.querySelectorAll('[data-history-range]').forEach((button) => {
        button.addEventListener('click', () => {
            currentLtpHistoryRange = button.getAttribute('data-history-range') || '1m';
            renderCurrentLtpHistoryRange();
        });
    });
    if (modalLtpHistoryChartEl) {
        modalLtpHistoryChartEl.addEventListener('mousemove', (event) => {
            if (currentLtpChartPinnedIndex !== null) return;
            const nearest = getNearestLtpChartIndex(event);
            if (nearest === currentLtpChartHoverIndex) return;
            currentLtpChartHoverIndex = nearest;
            modalLtpHistoryChartEl.classList.toggle('is-point-hovered', nearest !== null);
            drawLtpHistoryChart(
                filterLtpRowsByRange(currentLtpHistoryRows, currentLtpHistoryRange),
                nearest
            );
        });
        modalLtpHistoryChartEl.addEventListener('mouseleave', () => {
            if (currentLtpChartPinnedIndex !== null) return;
            currentLtpChartHoverIndex = null;
            modalLtpHistoryChartEl.classList.remove('is-point-hovered');
            drawLtpHistoryChart(filterLtpRowsByRange(currentLtpHistoryRows, currentLtpHistoryRange));
        });
        modalLtpHistoryChartEl.addEventListener('click', (event) => {
            const nearest = getNearestLtpChartIndex(event);
            if (nearest === null) {
                currentLtpChartPinnedIndex = null;
                currentLtpChartHoverIndex = null;
                drawLtpHistoryChart(filterLtpRowsByRange(currentLtpHistoryRows, currentLtpHistoryRange));
                return;
            }
            const wasPinned = currentLtpChartPinnedIndex === nearest;
            currentLtpChartPinnedIndex = wasPinned ? null : nearest;
            currentLtpChartHoverIndex = nearest;
            drawLtpHistoryChart(filterLtpRowsByRange(currentLtpHistoryRows, currentLtpHistoryRange), wasPinned ? null : nearest);
        });
    }

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

    window.addEventListener('resize', () => {
        renderIpoStatusChart(ipoChartSnapshot.open, ipoChartSnapshot.upcoming, ipoChartSnapshot.closed);
        if (stockModal.classList.contains('ltp-history-focus')) {
            drawLtpHistoryChart(filterLtpRowsByRange(currentLtpHistoryRows, currentLtpHistoryRange));
        }
    });

    fetchStocks();
});
