/* NEPSE Terminal — unified search for indices + scrips + ticks + volume.
 * Auto-detects index vs scrip from the unified symbol list.
 * Interval aggregation: 1D / 1W / 1M / 1Y.
 * DPR-aware canvas, crosshair tooltip, volume toggle. No dependencies. */
(() => {
    'use strict';

    const DATA_ROOT = '../data/';
    const INDICES = [
        { code: 'NEPSE', name: 'NEPSE Index' },
        { code: 'SENSIND', name: 'Sensitive Index' },
        { code: 'FLOATIND', name: 'Float Index' },
        { code: 'SENSFLTIND', name: 'Sensitive Float Index' },
        { code: 'BANKSUBIND', name: 'Banking SubIndex' },
        { code: 'DEVBANKIND', name: 'Development Bank Index' },
        { code: 'FININD', name: 'Finance Index' },
        { code: 'HOTELIND', name: 'Hotels And Tourism' },
        { code: 'HYDPOWIND', name: 'HydroPower Index' },
        { code: 'INVIDX', name: 'Investment Index' },
        { code: 'LIFINSIND', name: 'Life Insurance' },
        { code: 'MANPROCIND', name: 'Manufacturing And Processing' },
        { code: 'MICRFININD', name: 'Microfinance Index' },
        { code: 'MUTUALIND', name: 'Mutual Fund' },
        { code: 'NONLIFIND', name: 'Non Life Insurance' },
        { code: 'OTHERSIND', name: 'Others Index' },
        { code: 'TRDIND', name: 'Trading Index' }
    ];
    const INDEX_CODES = new Set(INDICES.map((i) => i.code));
    const RANGES = [
        { key: '1M', days: 31 },
        { key: '3M', days: 93 },
        { key: '6M', days: 186 },
        { key: '1Y', days: 366 },
        { key: '5Y', days: 1827 },
        { key: 'ALL', days: Infinity }
    ];
    const INTERVALS = [
        { key: '1D', label: '1D' },
        { key: '1W', label: '1W' },
        { key: '1M', label: '1M' },
        { key: '1Y', label: '1Y' }
    ];

    const els = {};
    const state = {
        code: 'NEPSE',
        range: '1Y',
        interval: '1D',
        tick: null,
        showVolume: true,
        manifests: {},
        shardCache: new Map(),
        symbolList: [],
        scripNames: {},
        unifiedList: [],
        series: [],
        points: [],
        cssWidth: 0,
        cssHeight: 0,
        hover: -1
    };

    function $(id) { return document.getElementById(id); }

    function fmt(value, digits = 2) {
        if (typeof value !== 'number' || Number.isNaN(value)) return '-';
        return value.toLocaleString(undefined, {
            minimumFractionDigits: 0, maximumFractionDigits: digits
        });
    }

    function fmtCompact(value) {
        if (typeof value !== 'number' || Number.isNaN(value)) return '-';
        return new Intl.NumberFormat(undefined, {
            notation: 'compact', maximumFractionDigits: 2
        }).format(value);
    }

    function esc(value) {
        return String(value ?? '').replace(/[&<>"']/g, (c) => ({
            '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
        })[c] || c);
    }

    async function fetchJson(path) {
        const res = await fetch(DATA_ROOT + path, { cache: 'no-store' });
        if (!res.ok) throw new Error(`HTTP ${res.status} for ${path}`);
        return res.json();
    }

    function addDays(dateStr, days) {
        const d = new Date(dateStr + 'T12:00:00');
        d.setDate(d.getDate() + days);
        return d.toISOString().slice(0, 10);
    }

    async function ensureManifest(kind) {
        if (!state.manifests[kind]) {
            state.manifests[kind] = await fetchJson(`${kind}/manifest.json`);
        }
        return state.manifests[kind];
    }

    async function loadShard(kind, month) {
        const key = `${kind}/${month}`;
        if (!state.shardCache.has(key)) {
            state.shardCache.set(key, await fetchJson(`${kind}/monthly/${month}.json`));
        }
        return state.shardCache.get(key);
    }

    function numAt(row, i) { return row.length > i ? Number(row[i]) : NaN; }

    /* ── Detect whether a code is an index or scrip ──────── */

    function isIndex(code) {
        return INDEX_CODES.has(code.toUpperCase());
    }

    function getIndexName(code) {
        const m = INDICES.find((i) => i.code === code);
        return m ? m.name : code;
    }

    function getScripName(code) {
        return state.scripNames[code.toUpperCase()] || code;
    }

    /* ── Series builders ─────────────────────────────────── */

    async function buildIndexSeries() {
        const manifest = await ensureManifest('indices');
        const latest = manifest.latestDate;
        const range = RANGES.find((r) => r.key === state.range) || RANGES[3];
        const cutoff = range.days === Infinity ? '0000-00-00' : addDays(latest, -range.days);
        const months = (manifest.availableMonths || []).filter((m) => `${m}-31` >= cutoff.slice(0, 7));
        const shards = await Promise.all(months.map((m) => loadShard('indices', m).catch(() => null)));
        const rows = [];
        for (const shard of shards) {
            if (!shard || !Array.isArray(shard.dates)) continue;
            const series = (shard.series || {})[state.code];
            if (!Array.isArray(series)) continue;
            for (const row of series) {
                if (!Array.isArray(row) || row.length < 2) continue;
                const date = shard.dates[row[0]];
                if (!date || date < cutoff || date > latest) continue;
                const close = Number(row[1]);
                if (!Number.isFinite(close)) continue;
                rows.push({
                    x: date, close,
                    open: numAt(row, 2), high: numAt(row, 3), low: numAt(row, 4),
                    turnover: numAt(row, 5), volume: numAt(row, 6), trades: numAt(row, 7)
                });
            }
        }
        rows.sort((a, b) => (a.x < b.x ? -1 : a.x > b.x ? 1 : 0));
        return rows;
    }

    async function buildLtpSeries() {
        const manifest = await ensureManifest('ltp');
        const latest = manifest.latestDate;
        const range = RANGES.find((r) => r.key === state.range) || RANGES[3];
        const cutoff = range.days === Infinity ? '0000-00-00' : addDays(latest, -range.days);
        const months = (manifest.availableMonths || []).filter((m) => `${m}-31` >= cutoff.slice(0, 7));
        const shards = await Promise.all(months.map((m) => loadShard('ltp', m).catch(() => null)));
        const rows = [];
        for (const shard of shards) {
            if (!shard || !Array.isArray(shard.dates)) continue;
            const series = (shard.series || {})[state.code];
            if (!Array.isArray(series)) continue;
            for (const row of series) {
                if (!Array.isArray(row) || row.length < 2) continue;
                const date = shard.dates[row[0]];
                if (!date || date < cutoff || date > latest) continue;
                const close = Number(row[1]);
                if (!Number.isFinite(close)) continue;
                rows.push({
                    x: date, close,
                    open: NaN, high: NaN, low: NaN,
                    turnover: numAt(row, 3), volume: numAt(row, 2), trades: numAt(row, 4)
                });
            }
        }
        rows.sort((a, b) => (a.x < b.x ? -1 : a.x > b.x ? 1 : 0));
        return rows;
    }

    async function buildTickSeries() {
        const day = await fetchJson(`ltp/daily/${state.tick}.json`);
        const times = Array.isArray(day.times) ? day.times : [];
        const series = ((day.series || {})[state.code]) || [];
        const rows = [];
        for (const row of series) {
            if (!Array.isArray(row) || row.length < 2) continue;
            const time = times[row[0]];
            if (!time) continue;
            const close = Number(row[1]);
            if (!Number.isFinite(close)) continue;
            rows.push({
                x: time.slice(0, 5), close,
                open: NaN, high: NaN, low: NaN,
                turnover: numAt(row, 3), volume: numAt(row, 2), trades: numAt(row, 4)
            });
        }
        return rows;
    }

    /* ── Interval aggregation ─────────────────────────────── */

    function isoWeekKey(dateStr) {
        const d = new Date(dateStr + 'T12:00:00');
        const jan4 = new Date(d.getFullYear(), 0, 4);
        const dayOfYear = Math.floor((d - jan4) / 86400000) + jan4.getDay() + 1;
        const weekNum = Math.ceil(dayOfYear / 7);
        return `${d.getFullYear()}-W${String(weekNum).padStart(2, '0')}`;
    }

    function aggregateSeries(rows, mode) {
        if (!mode || mode === '1D' || rows.length === 0) return rows;
        const groups = new Map();
        for (const r of rows) {
            let key;
            if (mode === '1W') key = isoWeekKey(r.x);
            else if (mode === '1M') key = r.x.slice(0, 7);
            else key = r.x.slice(0, 4);
            if (!groups.has(key)) groups.set(key, []);
            groups.get(key).push(r);
        }
        const result = [];
        for (const [, grp] of groups) {
            const first = grp[0];
            const last = grp[grp.length - 1];
            let high = -Infinity, low = Infinity, vol = 0, turnover = 0, trades = 0;
            let anyHigh = false, anyLow = false;
            for (const r of grp) {
                if (Number.isFinite(r.high)) { high = Math.max(high, r.high); anyHigh = true; }
                if (Number.isFinite(r.low)) { low = Math.min(low, r.low); anyLow = true; }
                if (Number.isFinite(r.volume)) vol += r.volume;
                if (Number.isFinite(r.turnover)) turnover += r.turnover;
                if (Number.isFinite(r.trades)) trades += r.trades;
            }
            result.push({
                x: first.x, close: last.close, open: first.open,
                high: anyHigh ? high : NaN, low: anyLow ? low : NaN,
                turnover, volume: vol, trades
            });
        }
        return result;
    }

    /* ── Stats ───────────────────────────────────────────── */

    function renderStats() {
        const rows = state.series;
        const set = (id, text, cls) => {
            const el = els[id];
            if (!el) return;
            el.textContent = text;
            el.classList.remove('up', 'down');
            if (cls) el.classList.add(cls);
        };
        if (rows.length === 0) {
            ['stat-last', 'stat-chg', 'stat-chgpct', 'stat-high', 'stat-low', 'stat-vol', 'stat-count']
                .forEach((id) => set(id, id === 'stat-count' ? '0 points' : '-'));
            return;
        }
        const first = rows[0].close;
        const last = rows[rows.length - 1].close;
        const chg = last - first;
        const pct = first !== 0 ? (chg / first) * 100 : NaN;
        const dir = chg >= 0 ? 'up' : 'down';
        let high = -Infinity, low = Infinity, vol = 0, volAny = false;
        for (const r of rows) {
            if (Number.isFinite(r.high)) high = Math.max(high, r.high);
            if (Number.isFinite(r.low)) low = Math.min(low, r.low);
            if (Number.isFinite(r.volume)) { vol += r.volume; volAny = true; }
        }
        high = Math.max(high, last);
        low = Math.min(low, last);
        set('stat-last', fmt(last), dir);
        set('stat-chg', `${chg >= 0 ? '+' : ''}${fmt(chg)}`, dir);
        set('stat-chgpct', `${chg >= 0 ? '+' : ''}${fmt(pct)}%`, dir);
        set('stat-high', fmt(high));
        set('stat-low', fmt(low));
        set('stat-vol', volAny ? fmtCompact(vol) : '-');
        set('stat-count', `${rows.length} pts · ${rows[0].x} → ${rows[rows.length - 1].x}`);
    }

    /* ── Stock details panel ──────────────────────────────── */

    function renderDetails() {
        const panel = els.details;
        if (!panel) return;
        const code = state.code;
        const isIdx = isIndex(code);
        const entry = state.unifiedList.find((item) => item.code === code);
        const live = state.nepseDataMap ? state.nepseDataMap[code] : null;

        if (state.tick) {
            panel.style.display = 'none';
            return;
        }

        const name = isIdx ? getIndexName(code) : (entry && entry.name) || getScripName(code);
        const type = isIdx ? 'Index' : 'Scrip';

        let html = `<div class="detail-head">
            <span class="detail-code">${esc(code)}</span>
            <span class="detail-name">${esc(name)}</span>
            <span class="detail-type">${esc(type)}</span>
        </div>`;

        if (!isIdx && live) {
            const chgDir = (live.change || 0) >= 0 ? 'up' : 'down';
            const chgSign = (live.change || 0) >= 0 ? '+' : '';
            html += `<div class="detail-grid">
                <div class="detail-item"><span class="lbl">LTP</span><span class="val ${chgDir}">Rs. ${esc(fmt(live.ltp))}</span></div>
                <div class="detail-item"><span class="lbl">Change</span><span class="val ${chgDir}">${chgSign}${esc(fmt(live.change))}</span></div>
                <div class="detail-item"><span class="lbl">Change %</span><span class="val ${chgDir}">${chgSign}${esc(fmt(live.percent_change))}%</span></div>
                <div class="detail-item"><span class="lbl">Prev Close</span><span class="val">Rs. ${esc(fmt(live.previous_close))}</span></div>
                <div class="detail-item"><span class="lbl">High</span><span class="val">Rs. ${esc(fmt(live.high))}</span></div>
                <div class="detail-item"><span class="lbl">Low</span><span class="val">Rs. ${esc(fmt(live.low))}</span></div>
                <div class="detail-item"><span class="lbl">Volume</span><span class="val">${esc(fmtCompact(live.volume))}</span></div>
                <div class="detail-item"><span class="lbl">Turnover</span><span class="val">Rs. ${esc(fmtCompact(live.turnover))}</span></div>
                <div class="detail-item"><span class="lbl">Trades</span><span class="val">${esc(fmt(live.trades, 0))}</span></div>
                <div class="detail-item"><span class="lbl">Mkt Cap</span><span class="val">Rs. ${esc(fmtCompact(live.market_cap))}M</span></div>
                <div class="detail-item detail-full"><span class="lbl">Updated</span><span class="val small">${esc(live.last_updated || '-')}</span></div>
            </div>`;
        } else if (isIdx) {
            const rows = state.series;
            if (rows.length > 0) {
                const last = rows[rows.length - 1];
                const first = rows[0];
                const chg = last.close - first.close;
                const pct = first.close !== 0 ? (chg / first.close) * 100 : NaN;
                const chgDir = chg >= 0 ? 'up' : 'down';
                const chgSign = chg >= 0 ? '+' : '';
                html += `<div class="detail-grid">
                    <div class="detail-item"><span class="lbl">Latest</span><span class="val ${chgDir}">${esc(fmt(last.close))}</span></div>
                    <div class="detail-item"><span class="lbl">Change</span><span class="val ${chgDir}">${chgSign}${esc(fmt(chg))}</span></div>
                    <div class="detail-item"><span class="lbl">Change %</span><span class="val ${chgDir}">${chgSign}${esc(fmt(pct))}%</span></div>
                    <div class="detail-item"><span class="lbl">Open</span><span class="val">${esc(fmt(last.open))}</span></div>
                    <div class="detail-item"><span class="lbl">High</span><span class="val">${esc(fmt(last.high))}</span></div>
                    <div class="detail-item"><span class="lbl">Low</span><span class="val">${esc(fmt(last.low))}</span></div>
                    <div class="detail-item"><span class="lbl">Volume</span><span class="val">${esc(fmtCompact(last.volume))}</span></div>
                    <div class="detail-item"><span class="lbl">Turnover</span><span class="val">Rs.${esc(fmtCompact(last.turnover))}</span></div>
                    <div class="detail-item"><span class="lbl">Trades</span><span class="val">${esc(fmt(last.trades, 0))}</span></div>
                    <div class="detail-item"><span class="lbl">Coverage</span><span class="val small">${esc(rows[0].x)} → ${esc(last.x)}</span></div>
                </div>`;
            } else {
                html += `<div class="detail-empty">No data available</div>`;
            }
        } else if (!isIdx && entry && entry.type === 'scrip') {
            html += `<div class="detail-grid">
                <div class="detail-item detail-full"><span class="lbl">Status</span><span class="val small">Live data unavailable — chart history loaded from data/ltp</span></div>
            </div>`;
        } else {
            html += `<div class="detail-empty">Select a stock to see details</div>`;
        }

        panel.innerHTML = html;
        panel.style.display = '';
    }

    /* ── Chart drawing ───────────────────────────────────── */

    function drawChart() {
        const canvas = els.chart;
        if (!canvas) return;
        const ctx = canvas.getContext('2d');
        if (!ctx) return;
        const dpr = window.devicePixelRatio || 1;
        const cssW = Math.max(300, Math.floor(canvas.clientWidth || 900));
        const cssH = Math.max(200, Math.floor(canvas.clientHeight || 400));
        canvas.width = Math.floor(cssW * dpr);
        canvas.height = Math.floor(cssH * dpr);
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        ctx.clearRect(0, 0, cssW, cssH);
        state.cssWidth = cssW;
        state.cssHeight = cssH;

        const rows = state.series;
        if (rows.length === 0) {
            state.points = [];
            ctx.fillStyle = 'rgba(160,168,200,0.9)';
            ctx.font = '500 13px Inter, sans-serif';
            ctx.textAlign = 'center';
            const msg = state.tick
                ? `No intraday ticks for ${state.code} on ${state.tick}`
                : 'No data for this selection';
            ctx.fillText(msg, cssW / 2, cssH / 2);
            return;
        }

        const values = rows.map((r) => r.close);
        const rawMin = Math.min(...values);
        const rawMax = Math.max(...values);
        const rawSpan = rawMax - rawMin || 1;
        const yPad = rawSpan * 0.08;
        const min = rawMin - yPad;
        const max = rawMax + yPad;
        const span = max - min;
        const up = values[values.length - 1] >= values[0];
        const lineColor = up ? 'rgba(34, 197, 94, 1)' : 'rgba(239, 68, 68, 1)';
        const fillColor = up ? 'rgba(34, 197, 94, 0.25)' : 'rgba(239, 68, 68, 0.25)';
        const pad = { top: 14, right: 62, bottom: 28, left: 8 };
        const chartW = cssW - pad.left - pad.right;
        const chartH = cssH - pad.top - pad.bottom;
        const hasVol = state.showVolume;
        const volH = hasVol ? Math.min(Math.floor(chartH * 0.22), 80) : 0;
        const gap = hasVol ? 8 : 0;
        const priceH = chartH - volH - gap;

        ctx.font = '10px "JetBrains Mono", monospace';
        ctx.textBaseline = 'middle';
        ctx.textAlign = 'left';
        for (let i = 0; i <= 4; i += 1) {
            const val = max - (span * i) / 4;
            const y = pad.top + (priceH * i) / 4;
            ctx.strokeStyle = 'rgba(255,255,255,0.06)';
            ctx.lineWidth = 1;
            ctx.beginPath();
            ctx.moveTo(pad.left, y);
            ctx.lineTo(pad.left + chartW, y);
            ctx.stroke();
            ctx.fillStyle = 'rgba(160,168,200,0.8)';
            ctx.fillText(fmt(val), pad.left + chartW + 6, y);
        }

        const xStep = rows.length === 1 ? 0 : chartW / (rows.length - 1);
        ctx.fillStyle = 'rgba(160,168,200,0.75)';
        ctx.textAlign = 'center';
        const labelEvery = Math.max(1, Math.floor(rows.length / 6));
        const xLabelY = pad.top + chartH + 16;
        for (let i = 0; i < rows.length; i += labelEvery) {
            const x = pad.left + xStep * i;
            const label = state.tick ? rows[i].x : String(rows[i].x).slice(0, 7);
            ctx.fillText(label, x, xLabelY);
        }

        const points = rows.map((r, i) => ({
            x: pad.left + xStep * i,
            y: pad.top + priceH - ((r.close - min) / span) * priceH
        }));
        state.points = points;

        if (hasVol) {
            const vols = rows.map((r) => (Number.isFinite(r.volume) ? r.volume : 0));
            const maxVol = Math.max(...vols, 0);
            if (maxVol > 0) {
                const bw = rows.length === 1 ? chartW : Math.max(1, (chartW / rows.length) * 0.65);
                const volTop = pad.top + priceH + gap;
                for (let i = 0; i < rows.length; i += 1) {
                    const v = vols[i];
                    if (v <= 0) continue;
                    const h = Math.max(1, (v / maxVol) * volH);
                    const prevClose = i > 0 ? rows[i - 1].close : rows[i].close;
                    ctx.fillStyle = rows[i].close >= prevClose
                        ? 'rgba(34,197,94,0.35)' : 'rgba(239,68,68,0.35)';
                    ctx.fillRect(points[i].x - bw / 2, volTop + volH - h, bw, h);
                }
                ctx.fillStyle = 'rgba(160,168,200,0.55)';
                ctx.font = '9px "JetBrains Mono", monospace';
                ctx.textAlign = 'left';
                ctx.fillText(`VOL ${fmtCompact(maxVol)}`, pad.left + 2, volTop + 10);
            }
        }

        const gradient = ctx.createLinearGradient(0, pad.top, 0, pad.top + priceH);
        gradient.addColorStop(0, fillColor);
        gradient.addColorStop(1, 'rgba(0,0,0,0)');
        ctx.beginPath();
        points.forEach((p, i) => {
            if (i === 0) ctx.moveTo(p.x, p.y);
            else ctx.lineTo(p.x, p.y);
        });
        ctx.strokeStyle = lineColor;
        ctx.lineWidth = 2;
        ctx.lineJoin = 'round';
        ctx.stroke();
        if (points.length > 1) {
            ctx.lineTo(points[points.length - 1].x, pad.top + priceH);
            ctx.lineTo(points[0].x, pad.top + priceH);
            ctx.closePath();
            ctx.fillStyle = gradient;
            ctx.fill();
        }

        const lastY = points[points.length - 1].y;
        ctx.save();
        ctx.strokeStyle = up ? 'rgba(34,197,94,0.4)' : 'rgba(239,197,94,0.4)';
        ctx.setLineDash([4, 4]);
        ctx.beginPath();
        ctx.moveTo(pad.left, lastY);
        ctx.lineTo(pad.left + chartW, lastY);
        ctx.stroke();
        ctx.restore();

        drawHover();
    }

    function drawHover() {
        const canvas = els.chart;
        const tooltip = els.tooltip;
        if (!canvas || !tooltip) return;
        const idx = state.hover;
        if (idx < 0 || !state.points[idx] || !state.series[idx]) {
            tooltip.classList.add('is-hidden');
            return;
        }
        const ctx = canvas.getContext('2d');
        const pt = state.points[idx];
        const row = state.series[idx];
        const h = state.cssHeight;

        ctx.save();
        ctx.strokeStyle = 'rgba(226,232,240,0.4)';
        ctx.setLineDash([3, 3]);
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(pt.x, 6);
        ctx.lineTo(pt.x, h - 28);
        ctx.stroke();
        ctx.restore();

        ctx.save();
        ctx.fillStyle = '#fff';
        ctx.strokeStyle = 'rgba(0,0,0,0.7)';
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.arc(pt.x, pt.y, 4, 0, Math.PI * 2);
        ctx.fill();
        ctx.stroke();
        ctx.restore();

        const chg = row.close - state.series[0].close;
        const ohl = Number.isFinite(row.high)
            ? `<small>O ${esc(fmt(row.open))}  H ${esc(fmt(row.high))}  L ${esc(fmt(row.low))}</small>`
            : '';
        const trades = Number.isFinite(row.trades) ? ` · Tx ${esc(fmt(row.trades, 0))}` : '';
        tooltip.innerHTML = `
            <span>${esc(state.tick ? `${state.tick} ${row.x}` : row.x)}</span>
            <strong>Rs. ${esc(fmt(row.close))}</strong>
            ${ohl}
            <small>Vol ${esc(fmtCompact(row.volume))} · Rs.${esc(fmtCompact(row.turnover))}${trades}</small>
            <small class="${chg >= 0 ? 'up' : 'down'}">${chg >= 0 ? '+' : ''}${esc(fmt(chg))} from start</small>
        `;
        const tw = 210;
        const left = Math.min(Math.max(pt.x - tw / 2, 6), Math.max(6, state.cssWidth - tw - 6));
        const top = pt.y > 120 ? pt.y - 112 : pt.y + 14;
        tooltip.style.left = `${left}px`;
        tooltip.style.top = `${top}px`;
        tooltip.classList.remove('is-hidden');
    }

    /* ── Interaction ─────────────────────────────────────── */

    function onMouseMove(event) {
        if (state.points.length === 0) return;
        const rect = els.chart.getBoundingClientRect();
        const x = event.clientX - rect.left;
        let best = 0, bestDist = Infinity;
        for (let i = 0; i < state.points.length; i += 1) {
            const dist = Math.abs(state.points[i].x - x);
            if (dist < bestDist) { bestDist = dist; best = i; }
        }
        if (best !== state.hover) {
            state.hover = best;
            drawChart();
        }
    }

    /* ── Status & controls ───────────────────────────────── */

    function describeSelection() {
        const code = state.code;
        if (state.tick) return `${code} · TICK ${state.tick}`;
        const label = isIndex(code) ? getIndexName(code) : getScripName(code);
        return `${code} — ${label} · ${state.range}`;
    }

    function syncControls() {
        document.querySelectorAll('[data-range]').forEach((b) => {
            b.classList.toggle('active', b.dataset.range === state.range);
        });
        els.tickbox.style.display = state.tick ? '' : 'none';
        els.ranges.style.display = state.tick ? 'none' : '';
        if (els.intervals.querySelector) {
            els.intervals.querySelector('select').value = state.interval;
            els.intervals.style.display = state.tick ? 'none' : '';
        }
        if (els.searchInput) els.searchInput.value = state.code;
        if (els.volBtn) {
            els.volBtn.classList.toggle('active', state.showVolume);
            els.volBtn.textContent = state.showVolume ? 'VOL ON' : 'VOL OFF';
        }
        if (els.tickdate && !els.tickdate.value && state.tick) els.tickdate.value = state.tick;
    }

    async function refresh() {
        els.status.textContent = `Loading ${describeSelection()}…`;
        syncControls();
        try {
            let raw;
            if (state.tick) {
                raw = await buildTickSeries();
            } else if (isIndex(state.code)) {
                raw = await buildIndexSeries();
            } else {
                raw = await buildLtpSeries();
            }
            state.series = aggregateSeries(raw, state.tick ? '1D' : state.interval);
            state.hover = -1;
            renderStats();
            renderDetails();
            drawChart();
            const src = state.tick ? 'ltp/daily' : isIndex(state.code) ? 'indices' : 'ltp';
            els.status.textContent = `${describeSelection()} · data/${src}`;
        } catch (err) {
            state.series = [];
            state.hover = -1;
            renderStats();
            renderDetails();
            drawChart();
            els.status.textContent = state.tick
                ? `No ticks for ${state.code} on ${state.tick} (${err.message})`
                : `Failed to load (${err.message})`;
        }
    }

    /* ── Tape ────────────────────────────────────────────── */

    async function buildTape() {
        try {
            const manifest = await ensureManifest('indices');
            const latestMonth = manifest.latestDate.slice(0, 7);
            const shard = await loadShard('indices', latestMonth);
            const dates = shard.dates || [];
            const lastIdx = dates.length - 1;
            const prevIdx = lastIdx - 1;
            const items = [];
            for (const meta of INDICES) {
                const series = (shard.series || {})[meta.code];
                if (!Array.isArray(series)) continue;
                const lastRow = series.find((r) => r[0] === lastIdx);
                if (!lastRow) continue;
                const prevRow = series.find((r) => r[0] === prevIdx);
                const last = Number(lastRow[1]);
                const prev = prevRow ? Number(prevRow[1]) : NaN;
                const chg = Number.isFinite(prev) ? last - prev : NaN;
                const pct = Number.isFinite(prev) && prev !== 0 ? (chg / prev) * 100 : NaN;
                items.push({ meta, last, chg, pct });
            }
            els.tape.innerHTML = items.map((it) => `
                <button class="tape-item${it.meta.code === state.code ? ' active' : ''}"
                        data-code="${esc(it.meta.code)}" title="${esc(it.meta.name)}">
                    <span class="tape-code">${esc(it.meta.code)}</span>
                    <span class="tape-last">${esc(fmt(it.last))}</span>
                    <span class="tape-chg ${it.chg >= 0 ? 'up' : 'down'}">${it.chg >= 0 ? '+' : ''}${esc(fmt(it.chg))} (${it.chg >= 0 ? '+' : ''}${esc(fmt(it.pct))}%)</span>
                </button>
            `).join('');
            els.tape.querySelectorAll('[data-code]').forEach((btn) => {
                btn.addEventListener('click', () => {
                    state.code = btn.dataset.code;
                    state.tick = null;
                    refresh();
                });
            });
        } catch {
            els.tape.innerHTML = '<span class="tape-empty">Index tape unavailable.</span>';
        }
    }

    /* ── Unified symbol search ────────────────────────────── */

    async function buildUnifiedList() {
        const indexEntries = INDICES.map((m) => ({
            code: m.code, name: m.name, type: 'index'
        }));

        let scripEntries = [];
        let nepseData = [];
        try {
            nepseData = await fetchJson('nepse_data.json');
        } catch { /* fallback to ltp shards */ }

        if (nepseData.length > 0) {
            const names = {};
            for (const item of nepseData) {
                const code = (item.symbol || '').toUpperCase();
                if (!code) continue;
                names[code] = item.name || code;
                scripEntries.push({
                    code,
                    name: item.name || code,
                    type: 'scrip',
                    ltp: item.ltp,
                    change: item.change,
                    percent_change: item.percent_change,
                    high: item.high,
                    low: item.low,
                    volume: item.volume,
                    turnover: item.turnover,
                    trades: item.trades,
                    market_cap: item.market_cap,
                    previous_close: item.previous_close,
                    last_updated: item.last_updated
                });
            }
            state.scripNames = names;
            state.nepseDataMap = {};
            for (const item of nepseData) {
                if (item.symbol) state.nepseDataMap[item.symbol.toUpperCase()] = item;
            }
            state.symbolList = Object.keys(names).sort();
        } else {
            try {
                const manifest = await ensureManifest('ltp');
                const months = manifest.availableMonths || [];
                const shard = await loadShard('ltp', months[months.length - 1]);
                const names = {};
                const codes = Object.keys(shard.series || {}).sort();
                for (const code of codes) {
                    names[code] = code;
                    scripEntries.push({ code, name: code, type: 'scrip' });
                }
                state.scripNames = names;
                state.symbolList = codes;
            } catch { /* indices-only fallback */ }
        }

        state.unifiedList = [...indexEntries, ...scripEntries];
        return state.unifiedList;
    }

    function populateDatalist() {
        const list = state.unifiedList;
        if (!els.symlist) return;
        els.symlist.innerHTML = list.map((item) => {
            const label = item.type === 'index'
                ? `${item.code} — ${item.name}`
                : `${item.code} — ${item.name}`;
            return `<option value="${esc(item.code)}" label="${esc(label)}">`;
        }).join('');
    }

    function fuzzyMatch(query, text) {
        const q = query.toLowerCase();
        const t = text.toLowerCase();
        if (t.includes(q)) return true;
        let qi = 0;
        for (let i = 0; i < t.length && qi < q.length; i++) {
            if (t[i] === q[qi]) qi++;
        }
        return qi === q.length;
    }

    function searchUnified(query) {
        const q = query.toUpperCase().trim();
        if (!q) return null;
        const list = state.unifiedList;
        const exact = list.find((item) => item.code === q);
        if (exact) return exact;
        const byName = list.find((item) =>
            item.name.toUpperCase().startsWith(q) || item.name.toUpperCase().includes(q)
        );
        if (byName) return byName;
        const fuzzy = list.find((item) => fuzzyMatch(q, item.code + ' ' + item.name));
        return fuzzy || null;
    }

    function selectCode(code) {
        const upper = code.toUpperCase().trim();
        if (!upper) return;
        const match = searchUnified(upper);
        if (match) {
            state.code = match.code;
        } else {
            state.code = upper;
        }
        state.tick = null;
        refresh();
        buildTape();
    }

    /* ── Controls wiring ─────────────────────────────────── */

    function buildControls() {
        els.intervals.innerHTML = `<select class="ctrl-select" aria-label="Interval">
            ${INTERVALS.map((iv) => `<option value="${esc(iv.key)}">${esc(iv.label)}</option>`).join('')}
        </select>`;
        els.intervals.querySelector('select').value = state.interval;
        els.ranges.innerHTML = RANGES.map((r) => `
            <button class="ctrl-btn" data-range="${esc(r.key)}">${esc(r.key)}</button>
        `).join('');

        els.intervals.querySelector('select').addEventListener('change', (e) => {
            state.tick = null;
            state.interval = e.target.value;
            refresh();
        });
        els.ranges.querySelectorAll('[data-range]').forEach((btn) => {
            btn.addEventListener('click', () => {
                state.tick = null;
                state.range = btn.dataset.range;
                refresh();
            });
        });
        if (els.volBtn) {
            els.volBtn.addEventListener('click', () => {
                state.showVolume = !state.showVolume;
                syncControls();
                drawChart();
            });
        }
        els.searchInput.addEventListener('change', () => {
            selectCode(els.searchInput.value);
        });
        els.searchInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                selectCode(els.searchInput.value);
                els.searchInput.blur();
            }
        });
        els.tickbtn.addEventListener('click', () => {
            const date = els.tickdate.value;
            if (!date) return;
            state.tick = date;
            refresh();
        });
        els.tickback.addEventListener('click', () => {
            state.tick = null;
            refresh();
        });
    }

    /* ── Init ────────────────────────────────────────────── */

    function init() {
        ['tape', 'ranges', 'intervals', 'chart', 'tooltip', 'status', 'searchInput', 'symlist',
            'tickbox', 'tickdate', 'tickbtn', 'tickback', 'volBtn', 'details',
            'stat-last', 'stat-chg', 'stat-chgpct', 'stat-high', 'stat-low', 'stat-vol', 'stat-count'
        ].forEach((id) => { els[id] = $(id); });
        if (!els.chart) return;
        const urlSymbol = new URLSearchParams(window.location.search).get('symbol');
        if (urlSymbol) {
            state.code = urlSymbol.toUpperCase();
            state.mode = INDICES.has(state.code) ? 'index' : 'scrip';
            if (els.searchInput) els.searchInput.value = state.code;
        }
        buildUnifiedList().then(() => {
            populateDatalist();
            if (!urlSymbol && els.searchInput) els.searchInput.value = state.code;
        });
        buildControls();
        buildTape();
        refresh();
        els.chart.addEventListener('mousemove', onMouseMove);
        els.chart.addEventListener('mouseleave', () => { state.hover = -1; drawChart(); });
        window.addEventListener('resize', () => drawChart());
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
