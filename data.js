document.addEventListener('DOMContentLoaded', () => {
    const brokerTableBody = document.getElementById('broker-table-body');
    const brokerSearch = document.getElementById('broker-search');
    const membershipFilter = document.getElementById('membership-filter');
    const districtFilter = document.getElementById('district-filter');
    const tmsOnly = document.getElementById('tms-only');
    const brokerCount = document.getElementById('broker-count');
    const datasetCount = document.getElementById('dataset-count');
    const datasetList = document.getElementById('dataset-list');
    const updatesFeed = document.getElementById('updates-feed');
    const historySearch = document.getElementById('history-search');
    const historyRowLimit = document.getElementById('history-row-limit');
    const historyTableBody = document.getElementById('history-table-body');
    const oldIpoTableBody = document.getElementById('old-ipo-table-body');
    const brokerDirectoryToggle = document.getElementById('broker-directory-toggle');
    const brokerDirectoryContent = document.getElementById('broker-directory-content');
    const historyToggle = document.getElementById('history-toggle');
    const historyContent = document.getElementById('history-content');
    const oldIpoToggle = document.getElementById('old-ipo-toggle');
    const oldIpoContent = document.getElementById('old-ipo-content');

    const DATASET_FILES = [
        'all_securities.json',
        'brokers.json',
        'disclosures.json',
        'exchange_messages.json',
        'indices.json',
        'market_status.json',
        'market_summary.json',
        'market_summary_history.json',
        'nepse_data.json',
        'nepse_sector_wise_codes.json',
        'notices.json',
        'sector_indices.json',
        'supply_demand.json',
        'top_stocks.json',
        'upcoming_ipo.json',
        'oldipo.json'
    ];

    let brokers = [];
    let marketSummaryHistory = [];

    async function fetchJson(fileName) {
        const candidates = [`data/${fileName}`, fileName];
        for (const url of candidates) {
            try {
                const res = await fetch(url);
                if (res.ok) {
                    return await res.json();
                }
            } catch {
                // Try fallback path.
            }
        }
        return null;
    }

    function safeText(value) {
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

    function formatNumber(value, digits = 0) {
        const num = Number(value);
        if (!Number.isFinite(num)) return '-';
        return num.toLocaleString(undefined, {
            minimumFractionDigits: digits,
            maximumFractionDigits: digits
        });
    }

    function getMembership(broker) {
        return broker.membershipTypeMaster?.membershipType || 'N/A';
    }

    function getDistrictNames(broker) {
        if (!Array.isArray(broker.districtList) || broker.districtList.length === 0) return [];
        return broker.districtList.map((item) => item.districtName).filter(Boolean);
    }

    function getDistricts(broker) {
        const districts = getDistrictNames(broker);
        return districts.length > 0 ? districts.join(', ') : '-';
    }

    function getProvinceNames(broker) {
        if (!Array.isArray(broker.provinceList) || broker.provinceList.length === 0) return [];
        return broker.provinceList.map((item) => item.description || item.name).filter(Boolean);
    }

    function getProvinces(broker) {
        const provinces = getProvinceNames(broker);
        return provinces.length > 0 ? provinces.join(', ') : '-';
    }

    function getBranchCount(broker) {
        return Array.isArray(broker.memberBranchMappings) ? broker.memberBranchMappings.length : 0;
    }

    function getTmsLink(broker) {
        return broker.memberTMSLinkMapping?.tmsLink || '';
    }

    function buildBrokerCountReason(rows) {
        const codes = rows
            .map((item) => Number(item.memberCode))
            .filter((code) => Number.isFinite(code))
            .sort((a, b) => a - b);
        const uniqueCodes = Array.from(new Set(codes));
        if (uniqueCodes.length === 0) {
            return 'Broker count is based on loaded records.';
        }

        const minCode = uniqueCodes[0];
        const maxCode = uniqueCodes[uniqueCodes.length - 1];
        const missingCodes = [];
        const codeSet = new Set(uniqueCodes);
        for (let code = minCode; code <= maxCode; code += 1) {
            if (!codeSet.has(code)) {
                missingCodes.push(code);
            }
        }

        if (missingCodes.length === 0) {
            return `Loaded ${rows.length} broker records. Broker codes run ${minCode}-${maxCode} without gaps.`;
        }

        return `Loaded ${rows.length} broker records. Codes run ${minCode}-${maxCode}, but ${missingCodes.length} codes are not present (${missingCodes.join(', ')}).`;
    }

    function renderMembershipOptions() {
        const membershipTypes = Array.from(new Set(brokers.map(getMembership))).sort();
        membershipTypes.forEach((type) => {
            const option = document.createElement('option');
            option.value = type;
            option.textContent = type;
            membershipFilter.appendChild(option);
        });
    }

    function renderDistrictOptions() {
        const districts = Array.from(new Set(brokers.flatMap(getDistrictNames))).sort();
        districts.forEach((district) => {
            const option = document.createElement('option');
            option.value = district;
            option.textContent = district;
            districtFilter.appendChild(option);
        });
    }

    function applyBrokerFilters() {
        const term = brokerSearch.value.trim().toUpperCase();
        const selectedMembership = membershipFilter.value;
        const selectedDistrict = districtFilter.value;
        const onlyTms = tmsOnly.checked;

        const filtered = brokers.filter((broker) => {
            const code = String(broker.memberCode || '');
            const name = String(broker.memberName || '');
            const districts = getDistricts(broker);
            const provinces = getProvinces(broker);
            const tms = getTmsLink(broker);
            const membership = getMembership(broker);

            const searchHit = [code, name, districts, provinces, tms, membership].some((field) =>
                String(field).toUpperCase().includes(term)
            );
            const membershipHit = selectedMembership === 'all' || membership === selectedMembership;
            const districtHit = selectedDistrict === 'all' || getDistrictNames(broker).includes(selectedDistrict);
            const tmsHit = !onlyTms || Boolean(tms);

            return searchHit && membershipHit && districtHit && tmsHit;
        });

        renderBrokers(filtered);
    }

    function renderBrokers(rows) {
        if (!Array.isArray(rows) || rows.length === 0) {
            brokerTableBody.innerHTML = '<tr><td colspan="8" class="intel-empty">No brokers match the current filters.</td></tr>';
            return;
        }

        const html = rows
            .slice()
            .sort((a, b) => Number(a.memberCode || 0) - Number(b.memberCode || 0))
            .map((broker) => {
                const tms = getTmsLink(broker);
                const phone = broker.authorizedContactPersonNumber || '-';
                const membership = getMembership(broker);
                const branches = getBranchCount(broker);
                const provinceNames = getProvinceNames(broker);
                const districtNames = getDistrictNames(broker);
                const provinceText = provinceNames.length > 0 ? provinceNames.join(', ') : '-';
                const districtText = districtNames.length > 0 ? districtNames.join(', ') : '-';
                const territoryMeta = `${provinceNames.length || 0} province${provinceNames.length === 1 ? '' : 's'} | ${districtNames.length || 0} district${districtNames.length === 1 ? '' : 's'}`;
                const tmsCell = tms
                    ? `<a rel="noopener noreferrer" target="_blank" class="table-link" href="https://${safeText(tms)}">Open TMS <i class="fa-solid fa-arrow-up-right-from-square"></i></a>`
                    : '<span class="table-chip">N/A</span>';

                return `
                    <tr>
                        <td><span class="broker-code-chip">#${safeText(broker.memberCode)}</span></td>
                        <td>
                            <div class="broker-name-cell">
                                <p class="broker-name-primary">${safeText(broker.memberName)}</p>
                                <p class="broker-name-sub">${safeText(territoryMeta)}</p>
                            </div>
                        </td>
                        <td><span class="table-chip membership-chip">${safeText(membership)}</span></td>
                        <td><span class="metric-pill">${branches.toLocaleString()}</span></td>
                        <td class="table-clamp" title="${safeText(provinceText)}">${safeText(provinceText)}</td>
                        <td class="table-clamp" title="${safeText(districtText)}">${safeText(districtText)}</td>
                        <td>${tmsCell}</td>
                        <td><span class="phone-cell">${safeText(phone)}</span></td>
                    </tr>
                `;
            })
            .join('');

        brokerTableBody.innerHTML = html;
    }

    function applyHistoryFilters() {
        const term = historySearch.value.trim();
        const rowLimit = Number(historyRowLimit.value || 30);

        const filtered = marketSummaryHistory
            .filter((row) => String(row.businessDate || '').includes(term))
            .slice(0, rowLimit);

        renderHistoryTable(filtered);
    }

    function renderHistoryTable(rows) {
        if (!Array.isArray(rows) || rows.length === 0) {
            historyTableBody.innerHTML = '<tr><td colspan="5" class="intel-empty">No market history rows match the current filter.</td></tr>';
            return;
        }

        historyTableBody.innerHTML = rows.map((row) => `
            <tr>
                <td>${safeText(row.businessDate)}</td>
                <td>Rs. ${formatNumber(row.totalTurnover, 2)}</td>
                <td>${formatNumber(row.totalTradedShares, 0)}</td>
                <td>${formatNumber(row.totalTransactions, 0)}</td>
                <td>${formatNumber(row.tradedScrips, 0)}</td>
            </tr>
        `).join('');
    }

    function renderOldIpoTable(rows) {
        if (!oldIpoTableBody) return;
        if (!Array.isArray(rows) || rows.length === 0) {
            oldIpoTableBody.innerHTML = '<tr><td colspan="6" class="intel-empty">Old IPO archive unavailable.</td></tr>';
            return;
        }

        const sorted = rows
            .slice()
            .sort((a, b) => new Date(b.scraped_at || 0) - new Date(a.scraped_at || 0))
            .slice(0, 100);

        oldIpoTableBody.innerHTML = sorted.map((row) => {
            const reservedFor = row.reserved_for || (row.is_reserved_share ? 'Nepalese citizens working abroad' : '-');
            const source = row.url
                ? `<a rel="noopener noreferrer" target="_blank" href="${safeText(row.url)}">View</a>`
                : '<span class="table-chip">N/A</span>';

            return `
                <tr>
                    <td>${safeText(row.company || '-')}</td>
                    <td>${safeText(row.units || '-')}</td>
                    <td>${safeText(row.date_range || '-')}</td>
                    <td>${safeText(row.announcement_date || '-')}</td>
                    <td>${safeText(reservedFor)}</td>
                    <td>${source}</td>
                </tr>
            `;
        }).join('');
    }

    async function renderDatasets() {
        const rows = await Promise.all(DATASET_FILES.map(async (fileName) => {
            const data = await fetchJson(fileName);
            let count = 0;
            let type = 'object';

            if (Array.isArray(data)) {
                count = data.length;
                type = 'array';
            } else if (data && typeof data === 'object') {
                const values = Object.values(data);
                const arrays = values.filter((value) => Array.isArray(value));
                if (arrays.length > 0) {
                    count = arrays.reduce((sum, list) => sum + list.length, 0);
                    type = 'grouped';
                } else {
                    count = Object.keys(data).length;
                }
            }

            return {
                fileName,
                count,
                type,
                loaded: data !== null
            };
        }));

        const nonBrokerRows = rows.filter((row) => row.fileName !== 'brokers.json');
        datasetCount.textContent = `${rows.filter((row) => row.loaded).length}/${rows.length} datasets loaded`;

        datasetList.innerHTML = nonBrokerRows
            .map((row) => `
                <div class="dataset-row ${row.loaded ? '' : 'missing'}">
                    <div>
                        <p class="dataset-name">${safeText(row.fileName)}</p>
                        <p class="dataset-type">${safeText(row.type)}</p>
                    </div>
                    <div class="dataset-count">${Number(row.count || 0).toLocaleString()}</div>
                </div>
            `)
            .join('');
    }

    function normalizeUpdates(exchangeMessages, disclosures, notices) {
        const rows = [];

        if (Array.isArray(exchangeMessages)) {
            exchangeMessages.forEach((item) => {
                rows.push({
                    type: 'Exchange Message',
                    title: item.messageTitle || 'Untitled exchange message',
                    body: item.messageBody || '',
                    date: item.modifiedDate || item.approvedDate || item.addedDate || ''
                });
            });
        }

        if (Array.isArray(disclosures)) {
            disclosures.forEach((item) => {
                rows.push({
                    type: 'Disclosure',
                    title: item.newsHeadline || 'Untitled disclosure',
                    body: item.newsBody || '',
                    date: item.modifiedDate || item.approvedDate || item.addedDate || ''
                });
            });
        }

        const generalNotices = notices && Array.isArray(notices.general) ? notices.general : [];
        generalNotices.forEach((item) => {
            rows.push({
                type: 'Notice',
                title: item.noticeHeading || 'Untitled notice',
                body: item.noticeBody || '',
                date: item.modifiedDate || item.noticeExpiryDate || ''
            });
        });

        return rows
            .sort((a, b) => new Date(b.date || 0) - new Date(a.date || 0))
            .slice(0, 8);
    }

    function stripHtml(html) {
        if (!html) return '';
        return String(html).replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ').trim();
    }

    function renderUpdatesFeed(exchangeMessages, disclosures, notices) {
        const items = normalizeUpdates(exchangeMessages, disclosures, notices);
        if (!items.length) {
            updatesFeed.innerHTML = '<p class="intel-empty">No updates available.</p>';
            return;
        }

        updatesFeed.innerHTML = items.map((item) => `
            <div class="notice-item">
                <div class="notice-head">
                    <span class="chip small">${safeText(item.type)}</span>
                    <span class="notice-date">${item.date ? new Date(item.date).toLocaleDateString() : 'N/A'}</span>
                </div>
                <p class="notice-title">${safeText(item.title)}</p>
                <p class="notice-body">${safeText(stripHtml(item.body) || 'No description provided.')}</p>
            </div>
        `).join('');
    }

    async function init() {
        const [brokerData, exchangeMessages, disclosures, notices, historyData, oldIpoData] = await Promise.all([
            fetchJson('brokers.json'),
            fetchJson('exchange_messages.json'),
            fetchJson('disclosures.json'),
            fetchJson('notices.json'),
            fetchJson('market_summary_history.json'),
            fetchJson('oldipo.json')
        ]);

        brokers = Array.isArray(brokerData) ? brokerData : [];
        marketSummaryHistory = Array.isArray(historyData) ? historyData : [];

        brokerCount.textContent = `${brokers.length.toLocaleString()} brokers listed`;
        const brokerReason = buildBrokerCountReason(brokers);
        brokerCount.title = brokerReason;
        brokerCount.setAttribute('aria-label', brokerReason);

        if (brokers.length === 0) {
            brokerTableBody.innerHTML = '<tr><td colspan="8" class="intel-empty">Broker data unavailable.</td></tr>';
        } else {
            renderMembershipOptions();
            renderDistrictOptions();
            renderBrokers(brokers);
        }

        if (marketSummaryHistory.length === 0) {
            historyTableBody.innerHTML = '<tr><td colspan="5" class="intel-empty">Market summary history unavailable.</td></tr>';
        } else {
            applyHistoryFilters();
        }

        renderOldIpoTable(Array.isArray(oldIpoData) ? oldIpoData : []);

        renderUpdatesFeed(
            Array.isArray(exchangeMessages) ? exchangeMessages : [],
            Array.isArray(disclosures) ? disclosures : [],
            notices && typeof notices === 'object' ? notices : {}
        );

        await renderDatasets();
    }

    function bindSectionToggle(toggleEl, contentEl, showLabel, hideLabel) {
        if (!toggleEl || !contentEl) return;
        const sync = () => {
            const isHidden = contentEl.classList.contains('is-hidden');
            toggleEl.setAttribute('aria-expanded', String(!isHidden));
            toggleEl.classList.toggle('open', !isHidden);
            const labelEl = toggleEl.querySelector('span');
            if (labelEl) {
                labelEl.textContent = isHidden ? showLabel : hideLabel;
            }
        };
        toggleEl.addEventListener('click', () => {
            contentEl.classList.toggle('is-hidden');
            sync();
        });
        sync();
    }

    brokerSearch.addEventListener('input', applyBrokerFilters);
    membershipFilter.addEventListener('change', applyBrokerFilters);
    districtFilter.addEventListener('change', applyBrokerFilters);
    tmsOnly.addEventListener('change', applyBrokerFilters);
    historySearch.addEventListener('input', applyHistoryFilters);
    historyRowLimit.addEventListener('change', applyHistoryFilters);
    bindSectionToggle(brokerDirectoryToggle, brokerDirectoryContent, 'Show Directory', 'Hide Directory');
    bindSectionToggle(historyToggle, historyContent, 'Show History', 'Hide History');
    bindSectionToggle(oldIpoToggle, oldIpoContent, 'Show Archive', 'Hide Archive');

    init();
});
