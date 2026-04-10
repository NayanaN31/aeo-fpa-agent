import React, { useEffect, useRef, useState } from 'react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

/**
 * FastAPI base URL. Empty string = static / GitHub Pages mode (no chat API).
 * - Production build: set VITE_STATIC_ONLY=true for github.io, or VITE_API_BASE_URL for a hosted API.
 * - Local dev: defaults to http://127.0.0.1:8000 (or same host:8000 on LAN).
 */
function getApiBase() {
  if (import.meta.env.VITE_STATIC_ONLY === 'true') return '';
  const envUrl = import.meta.env.VITE_API_BASE_URL;
  if (envUrl != null && String(envUrl).trim() !== '') {
    return String(envUrl).replace(/\/$/, '');
  }
  if (typeof window === 'undefined') return 'http://127.0.0.1:8000';
  const { protocol, hostname } = window.location;
  if (hostname !== 'localhost' && hostname !== '127.0.0.1') {
    return `${protocol}//${hostname}:8000`;
  }
  return 'http://127.0.0.1:8000';
}

/** JSON shipped with the static build (briefing + backtest for GitHub Pages). */
function staticDemoUrl() {
  const b = import.meta.env.BASE_URL || '/';
  const path = b.endsWith('/') ? `${b}static-demo.json` : `${b}/static-demo.json`;
  return path.replace(/([^:]\/)\/+/g, '$1');
}

function isStaticDemo() {
  return getApiBase() === '';
}

// ─────────────────────────────────────────────────────────────────────────────
// AEO Financial Data
// ─────────────────────────────────────────────────────────────────────────────

const FINANCIALS = [
  { label: 'FY2015', fy: 2015, revenue: 3521.8, grossMargin: 36.99, opMargin:  9.08 },
  { label: 'FY2016', fy: 2016, revenue: 3609.9, grossMargin: 37.87, opMargin:  9.18 },
  { label: 'FY2017', fy: 2017, revenue: 3795.5, grossMargin: 36.11, opMargin:  7.98 },
  { label: 'FY2018', fy: 2018, revenue: 4035.7, grossMargin: 36.86, opMargin:  8.35 },
  { label: 'FY2019', fy: 2019, revenue: 4308.2, grossMargin: 35.33, opMargin:  5.42 },
  { label: 'FY2020', fy: 2020, revenue: 3759.1, grossMargin: 30.54, opMargin: -7.22, isCovid: true },
  { label: 'FY2021', fy: 2021, revenue: 5010.8, grossMargin: 39.75, opMargin: 11.80 },
  { label: 'FY2022', fy: 2022, revenue: 4989.8, grossMargin: 34.98, opMargin:  4.95 },
  { label: 'FY2023', fy: 2023, revenue: 5261.8, grossMargin: 38.48, opMargin:  4.23 },
  { label: 'FY2024', fy: 2024, revenue: 5328.7, grossMargin: 39.20, opMargin:  8.02 },
];

// ─────────────────────────────────────────────────────────────────────────────
// Competitor Data — sourced from SEC EDGAR 10-K filings
// Labels aligned to AEO's fiscal year convention (year ending Jan/Feb = FY{year-1})
// ─────────────────────────────────────────────────────────────────────────────

const PEERS = {
  ANF: {
    name: 'Abercrombie & Fitch', color: '#60A5FA', segment: 'Teen/Young Adult',
    data: [
      { label: 'FY2020', gm: 59.37, om:  1.93, rev: 3623 },
      { label: 'FY2021', gm: 60.51, om: -0.65, rev: 3125 },
      { label: 'FY2022', gm: 62.27, om:  9.24, rev: 3713 },
      { label: 'FY2023', gm: 56.91, om:  2.51, rev: 3698 },
      { label: 'FY2024', gm: 62.92, om: 11.32, rev: 4281 },
    ],
  },
  URBN: {
    name: 'Urban Outfitters', color: '#10b981', segment: 'Teen/Young Adult',
    data: [
      { label: 'FY2020', gm: 31.12, om:  5.82, rev: 3984 },
      { label: 'FY2021', gm: 24.98, om:  0.12, rev: 3450 },
      { label: 'FY2022', gm: 32.84, om:  8.98, rev: 4549 },
      { label: 'FY2023', gm: 29.76, om:  4.73, rev: 4795 },
      { label: 'FY2024', gm: 33.29, om:  7.18, rev: 5153 },
    ],
  },
  BKE: {
    name: 'Buckle', color: '#f97316', segment: 'Teen/Young Adult',
    data: [
      { label: 'FY2021', gm: 44.46, om: 18.64, rev:  901 },
      { label: 'FY2022', gm: 50.44, om: 25.92, rev: 1295 },
      { label: 'FY2023', gm: 50.25, om: 24.39, rev: 1345 },
      { label: 'FY2024', gm: 49.09, om: 21.49, rev: 1261 },
    ],
  },
  LULU: {
    name: 'lululemon', color: '#f472b6', segment: 'Activewear (Aerie comp)',
    data: [
      { label: 'FY2021', gm: 55.98, om: 18.63, rev:  4402 },
      { label: 'FY2022', gm: 57.68, om: 21.31, rev:  6257 },
      { label: 'FY2023', gm: 55.39, om: 16.38, rev:  8111 },
      { label: 'FY2024', gm: 58.31, om: 22.17, rev:  9619 },
    ],
  },
  VSCO: {
    name: "Victoria's Secret", color: '#fb7185', segment: 'Intimates (Aerie comp)',
    data: [
      { label: 'FY2022', gm: 35.59, om:  7.53, rev: 6344 },
      { label: 'FY2023', gm: 36.27, om:  3.98, rev: 6182 },
      { label: 'FY2024', gm: 36.66, om:  4.98, rev: 6230 },
    ],
  },
  GPS: {
    name: 'Gap Inc.', color: '#fbbf24', segment: 'Multi-brand Specialty',
    data: [
      { label: 'FY2020', gm: 34.09, om: -6.25, rev: 13800 },
      { label: 'FY2021', gm: 39.81, om:  4.86, rev: 16670 },
      { label: 'FY2022', gm: 34.32, om: -0.44, rev: 15616 },
      { label: 'FY2023', gm: 38.79, om:  3.76, rev: 14889 },
      { label: 'FY2024', gm: 41.28, om:  7.37, rev: 15086 },
    ],
  },
};

// FY2024 snapshot for quick comparison (approx. same period ending Jan–Feb 2025)
const FY2024_SNAPSHOT = [
  { ticker: 'AEO',  name: 'American Eagle',    color: '#3B82F6', gm: 39.20, om:  8.02, rev: 5329,  revB: 5.33 },
  { ticker: 'ANF',  name: 'Abercrombie',       color: '#60A5FA', gm: 62.92, om: 11.32, rev: 4281,  revB: 4.28 },
  { ticker: 'URBN', name: 'Urban Outfitters',  color: '#34D399', gm: 33.29, om:  7.18, rev: 5153,  revB: 5.15 },
  { ticker: 'BKE',  name: 'Buckle',            color: '#F59E0B', gm: 49.09, om: 21.49, rev: 1261,  revB: 1.26 },
  { ticker: 'LULU', name: 'lululemon',         color: '#E879F9', gm: 58.31, om: 22.17, rev: 9619,  revB: 9.62 },
  { ticker: 'VSCO', name: "Victoria's Secret", color: '#FB7185', gm: 36.27, om:  3.98, rev: 6182,  revB: 6.18 },
  { ticker: 'GPS',  name: 'Gap Inc.',          color: '#94A3B8', gm: 38.79, om:  3.76, rev: 14889, revB: 14.89 },
];

// ─────────────────────────────────────────────────────────────────────────────
// Waterfall bridge data
// ─────────────────────────────────────────────────────────────────────────────

const WATERFALL_DATA = [
  { label: 'FY2019',  base: 0,      height: 4308.2, isAnchor: true,  rawDelta: 4308.2  },
  { label: 'FY2020',  base: 3759.1, height:  549.1, isNeg: true,     rawDelta: -549.1  },
  { label: 'FY2021',  base: 3759.1, height: 1251.7, isPos: true,     rawDelta: 1251.7  },
  { label: 'FY2022',  base: 4989.8, height:   21.0, isNeg: true,     rawDelta:  -21.0  },
  { label: 'FY2023',  base: 4989.8, height:  272.0, isPos: true,     rawDelta:  272.0  },
  { label: 'FY2024',  base: 5261.8, height:   66.9, isPos: true,     rawDelta:   66.9  },
  { label: "'24 End", base: 0,      height: 5328.7, isAnchor: true,  rawDelta: 5328.7  },
];

// ─────────────────────────────────────────────────────────────────────────────
// Brand Segment Data — AE vs Aerie revenue by fiscal year ($M)
// Source: SEC EDGAR iXBRL — aeo:AerieBrandMember / aeo:AmericanEagleBrandMember
// ─────────────────────────────────────────────────────────────────────────────

const SEGMENTS = [
  { label: 'FY2018', aerie:  627.8, ae: 3387.8, aerieShare: 15.6 },
  { label: 'FY2019', aerie:  801.0, ae: 3479.6, aerieShare: 18.7 },
  { label: 'FY2020', aerie:  990.0, ae: 2733.8, aerieShare: 26.6, isCovid: true },
  { label: 'FY2021', aerie: 1376.3, ae: 3555.7, aerieShare: 27.9 },
  { label: 'FY2022', aerie: 1506.8, ae: 3262.9, aerieShare: 31.6, aerie_oi_m: 10.8, ae_oi_m: 16.6 },
  { label: 'FY2023', aerie: 1670.0, ae: 3361.6, aerieShare: 33.2, aerie_oi_m: 16.2, ae_oi_m: 17.8 },
  { label: 'FY2024', aerie: 1738.4, ae: 3385.2, aerieShare: 33.9, aerie_oi_m: 18.2, ae_oi_m: 17.9 },
];

// ─────────────────────────────────────────────────────────────────────────────
// Hardcoded demo conversations
// ─────────────────────────────────────────────────────────────────────────────

const MESSAGES = [
  { id: 1, role: 'user', text: 'Forecast revenue for the next 2 years' },
  {
    id: 2, role: 'agent', type: 'forecast',
    summary: 'Based on historical trend analysis with FY2020 excluded as a structural COVID outlier (avg. growth 5.3%), here are three scenarios through FY2026.',
    rows: [
      { scenario: 'Base', fy25: '$5.44B', fy26: '$5.55B', growth: '+2.1%', color: '#818cf8' },
      { scenario: 'Bull', fy25: '$5.52B', fy26: '$5.72B', growth: '+3.6%', color: '#34d399' },
      { scenario: 'Bear', fy25: '$5.33B', fy26: '$5.34B', growth: '+0.1%', color: '#fbbf24' },
    ],
    insight: 'Aerie brand growth and digital channel expansion are the primary upside levers. Watch comparable sales guidance in Q1.',
  },
  { id: 3, role: 'user', text: 'What if comp sales decline 3%? Show a budget scenario.' },
  {
    id: 4, role: 'agent', type: 'budget',
    summary: 'Scenario: Revenue −3.0% · COGS flat · SG&A flat — Base year: FY2024',
    rows: [
      { metric: 'Net Revenue',      actual: '$5,329M', projected: '$5,169M', delta: '−$160M',  neg: true  },
      { metric: 'Gross Profit',     actual: '$2,089M', projected: '$2,026M', delta: '−$63M',   neg: true  },
      { metric: 'Gross Margin',     actual: '39.2%',   projected: '39.2%',   delta: 'flat',    neg: false },
      { metric: 'SG&A',             actual: '$1,432M', projected: '$1,432M', delta: 'flat',    neg: false },
      { metric: 'Operating Income', actual: '$427M',   projected: '$365M',   delta: '−$62M',   neg: true  },
      { metric: 'Operating Margin', actual: '8.0%',    projected: '7.1%',    delta: '−0.9pp',  neg: true  },
    ],
    insight: 'A 3% comp sales decline would reduce operating income by ~$62M (−14.5%). SG&A deleveraging is the primary risk.',
  },
  { id: 5, role: 'user', text: 'How does AEO compare against all its competitors?' },
  {
    id: 6, role: 'agent', type: 'peer_snapshot',
    summary: 'FY2024 Competitive Landscape — AEO vs. 6 peers (most recent fiscal year ending Jan–Feb 2025)',
    note: "AEO occupies the mid-tier on gross margin. Buckle and lululemon lead on profitability. AEO's scale is comparable to ANF and URBN.",
    insight: "AEO's 8.0% operating margin is closing in on ANF's 11.3%, a meaningful reversal from FY2023 (4.2% vs 2.5%). The Aerie brand's premium positioning strategy is the key margin driver. LULU and BKE demonstrate that higher GM is achievable at this scale — target benchmarks for the medium term.",
  },
];

// ─────────────────────────────────────────────────────────────────────────────
// Design tokens
// ─────────────────────────────────────────────────────────────────────────────

// AEO Brand Palette — American Eagle Outfitters × Apple-style design
const C = {
  bg:          '#05080F',          // near-black navy canvas
  panel:       '#070B18',          // left panel — deepest navy
  card:        '#0B1427',          // card surface — dark navy blue
  cardHover:   '#0E1A30',
  border:      'rgba(255,255,255,0.07)',
  borderMid:   'rgba(255,255,255,0.12)',
  borderBlue:  'rgba(37,99,235,0.18)',
  textPrimary: '#EEF2FF',          // near-white with cool blue tint
  textSub:     '#6B7FA0',          // desaturated AEO blue-gray
  textMuted:   '#2E3F5A',
  // AEO brand blue spectrum
  blue:        '#1D4ED8',          // AEO corporate blue
  blueLight:   '#3B82F6',          // chart / accent blue
  blueFaint:   'rgba(37,99,235,0.08)',
  // AEO eagle red
  red:         '#DC2626',
  redFaint:    'rgba(220,38,38,0.08)',
  // Keep alias so existing components using C.indigo still work
  indigo:      '#2563EB',
  cyan:        '#06B6D4',
  green:       '#22C55E',
  greenFaint:  'rgba(34,197,94,0.08)',
  amber:       '#F59E0B',
};

const FALLBACK_CHIPS = [
  { label: 'Forecast next 2 years',              query: 'Forecast revenue for the next 2 years with base, bull, and bear scenarios', icon: '📈' },
  { label: 'Benchmark AEO vs all competitors',   query: 'Benchmark AEO vs all competitors', icon: '🔍' },
  { label: 'What if comp sales decline 3%?',     query: 'What if comparable sales decline 3%? Show a budget scenario.', icon: '📊' },
  { label: 'Calculate FY2024 financial ratios',   query: 'Calculate FY2024 financial ratios', icon: '🧮' },
];

// ─────────────────────────────────────────────────────────────────────────────
// Shared sub-components
// ─────────────────────────────────────────────────────────────────────────────

function SectionLabel({ children }) {
  return (
    <p style={{ color: C.textSub, fontSize: 10, letterSpacing: '0.12em', fontWeight: 600 }}
       className="uppercase mb-3">
      {children}
    </p>
  );
}

function LegendDot({ color, opacity = 1, label, dashed }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
      {dashed ? (
        <svg width="14" height="8" viewBox="0 0 14 8">
          <line x1="0" y1="4" x2="14" y2="4" stroke={color} strokeWidth="2"
            strokeDasharray="3 2" strokeOpacity={opacity} />
        </svg>
      ) : (
        <div style={{ width: 10, height: 10, borderRadius: 2, background: color, opacity }} />
      )}
      <span style={{ color: C.textSub, fontSize: 11 }}>{label}</span>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Stat cards
// ─────────────────────────────────────────────────────────────────────────────

function StatCard({ label, value, delta, deltaLabel, icon }) {
  const positive = delta && !delta.startsWith('−') && delta !== 'flat';
  const deltaColor = !delta ? C.textSub : delta === 'flat' ? C.textSub : positive ? C.green : C.red;
  return (
    <div style={{
      background: `linear-gradient(145deg, ${C.card} 0%, rgba(13,26,52,0.9) 100%)`,
      border: `1px solid ${C.border}`,
      borderTop: `1px solid rgba(255,255,255,0.09)`,
      borderRadius: 16, padding: '20px 22px', flex: 1, minWidth: 0,
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 14 }}>
        <p style={{ color: C.textSub, fontSize: 10, fontWeight: 600, letterSpacing: '0.10em', lineHeight: 1.3 }}
           className="uppercase">{label}</p>
        <div style={{
          width: 28, height: 28, borderRadius: 8,
          background: C.blueFaint, border: `1px solid ${C.borderBlue}`,
          display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 13, flexShrink: 0,
        }}>{icon}</div>
      </div>
      <p style={{ color: C.textPrimary, fontSize: 28, fontWeight: 700, lineHeight: 1, marginBottom: 8, letterSpacing: '-0.5px' }}>
        {value}
      </p>
      {delta && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
          <span style={{
            color: deltaColor, fontSize: 11, fontWeight: 600,
            background: positive ? C.greenFaint : delta === 'flat' ? 'transparent' : C.redFaint,
            borderRadius: 4, padding: '1px 5px',
          }}>{delta}</span>
          <span style={{ color: C.textMuted, fontSize: 10 }}>{deltaLabel}</span>
        </div>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Header “as of” date (updates daily while the app is open)
// ─────────────────────────────────────────────────────────────────────────────

function LiveHeaderDate() {
  const [label, setLabel] = useState(() =>
    new Date().toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }),
  );
  useEffect(() => {
    const tick = () =>
      setLabel(new Date().toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }));
    const id = setInterval(tick, 60_000);
    return () => clearInterval(id);
  }, []);
  return (
    <div style={{ fontSize:10,color:C.textMuted,background:'rgba(255,255,255,0.03)',
      border:`1px solid ${C.border}`,borderRadius:7,padding:'5px 10px' }}>
      As of {label}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Executive Summary — CFO briefing from /summary
// ─────────────────────────────────────────────────────────────────────────────

function ExecutiveSummary({ refreshKey, onSuggestionsLoaded }) {
  const [text, setText] = useState('');
  const [insights, setInsights] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    const ac = new AbortController();
    const timer = setTimeout(() => ac.abort(), isStaticDemo() ? 15000 : 35000);

    const loadStatic = () =>
      fetch(staticDemoUrl(), { signal: ac.signal })
        .then(r => (r.ok ? r.json() : Promise.reject()))
        .then(d => {
          setText(d.summary || '');
          setInsights(d.insights || []);
          if (d.suggestions && onSuggestionsLoaded) onSuggestionsLoaded(d.suggestions);
          setLoading(false);
        });

    const loadApi = () =>
      fetch(`${getApiBase()}/summary`, { signal: ac.signal })
        .then(r => (r.ok ? r.json() : Promise.reject()))
        .then(d => {
          setText(d.summary || '');
          setInsights(d.insights || []);
          if (d.suggestions && onSuggestionsLoaded) onSuggestionsLoaded(d.suggestions);
          setLoading(false);
        });

    (isStaticDemo() ? loadStatic() : loadApi()).catch(() => {
      setText(
        isStaticDemo()
          ? 'Static demo file missing. Run: python3 scripts/export_static_demo.py then rebuild.'
          : 'Live briefing unavailable. Start the API: python3 src/04_api_server.py (then refresh). Charts still use local data.',
      );
      setInsights([]);
      setLoading(false);
    }).finally(() => clearTimeout(timer));
  }, [refreshKey]);

  if (!loading && !text) return null;

  const signalColors = [
    { bg: 'rgba(34,197,94,0.08)',  border: 'rgba(34,197,94,0.20)',  dot: C.green },
    { bg: 'rgba(245,158,11,0.08)', border: 'rgba(245,158,11,0.20)', dot: C.amber },
    { bg: 'rgba(37,99,235,0.08)',  border: 'rgba(37,99,235,0.20)',  dot: C.blueLight },
    { bg: 'rgba(6,182,212,0.08)',  border: 'rgba(6,182,212,0.20)',  dot: C.cyan },
    { bg: 'rgba(239,68,68,0.08)',  border: 'rgba(239,68,68,0.20)',  dot: C.red },
  ];

  return (
    <div>
      <div style={{
        background: 'linear-gradient(135deg, rgba(29,78,216,0.09) 0%, rgba(6,182,212,0.05) 100%)',
        border: `1px solid rgba(37,99,235,0.20)`,
        borderRadius: 16, padding: '20px 24px',
        display: 'flex', gap: 16, alignItems: 'flex-start',
      }}>
        {/* Brand badge */}
        <div style={{
          width: 36, height: 36, borderRadius: 10, flexShrink: 0,
          background: 'linear-gradient(135deg, #1D4ED8, #0EA5E9)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 16, boxShadow: '0 4px 12px rgba(29,78,216,0.25)',
        }}>
          ✦
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
            <span style={{
              color: C.blueLight, fontSize: 10, fontWeight: 700, letterSpacing: '0.1em',
              background: 'rgba(37,99,235,0.12)', border: `1px solid rgba(37,99,235,0.22)`,
              borderRadius: 5, padding: '2px 8px',
            }} className="uppercase">{isStaticDemo() ? 'Executive briefing' : 'AI Executive Briefing'}</span>
            <span style={{ color: C.textMuted, fontSize: 10 }}>· FY2024 actuals · SEC 10-K</span>
          </div>
          {loading ? (
            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              {[0.6, 0.45, 0.55].map((w, i) => (
                <div key={i} style={{
                  height: 11, borderRadius: 4,
                  width: `${w * 100}%`,
                  background: 'rgba(255,255,255,0.07)',
                  animation: `pulse 1.4s ease-in-out ${i * 0.15}s infinite`,
                }} />
              ))}
              <style>{`@keyframes pulse{0%,100%{opacity:0.4}50%{opacity:0.9}}`}</style>
            </div>
          ) : (
            <p style={{ color: C.textPrimary, fontSize: 12.5, lineHeight: 1.7, margin: 0 }}>
              {text}
            </p>
          )}
        </div>
      </div>

      {/* Key Signals — data-driven insights rendered as callout pills */}
      {insights.length > 0 && (
        <div style={{ marginTop: 12, display: 'flex', flexWrap: 'wrap', gap: 8 }}>
          <span style={{
            color: C.textMuted, fontSize: 9, fontWeight: 700, letterSpacing: '0.1em',
            alignSelf: 'center', marginRight: 4,
          }} className="uppercase">Key Signals</span>
          {insights.map((ins, i) => {
            const sc = signalColors[i % signalColors.length];
            return (
              <div key={i} style={{
                background: sc.bg, border: `1px solid ${sc.border}`,
                borderRadius: 8, padding: '6px 10px',
                display: 'flex', alignItems: 'center', gap: 6,
                maxWidth: '100%',
              }}>
                <div style={{
                  width: 6, height: 6, borderRadius: '50%',
                  background: sc.dot, flexShrink: 0,
                }} />
                <span style={{ color: C.textSub, fontSize: 11, lineHeight: 1.4 }}>
                  {ins}
                </span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Backtest accuracy card (metrics from API — recomputed per forecast question)
// ─────────────────────────────────────────────────────────────────────────────

function BacktestCard({ backtest }) {
  const [showTip, setShowTip] = useState(false);
  const hasData = Boolean(
    backtest && typeof backtest.revenue_mape === 'number' && !Number.isNaN(backtest.revenue_mape),
  );
  const fmt = (v, u) => (hasData && v != null ? `${v}${u}` : '—');
  const metrics = [
    { label: 'Revenue MAPE',   value: fmt(backtest?.revenue_mape, '%'),     raw: backtest?.revenue_mape,     unit: '%', color: C.green,     bg: C.greenFaint,  border: 'rgba(34,197,94,0.16)' },
    { label: 'OI MAPE (avg)',  value: fmt(backtest?.oi_mape, '%'),          raw: backtest?.oi_mape,          unit: '%', color: C.amber,     bg: 'rgba(245,158,11,0.08)', border: 'rgba(245,158,11,0.16)' },
    { label: 'GM Error',       value: fmt(backtest?.gm_error_pp, 'pp'),     raw: backtest?.gm_error_pp,      unit: 'pp', color: C.blueLight, bg: C.blueFaint,   border: C.borderBlue },
    { label: 'Directional',    value: fmt(backtest?.directional_accuracy, '%'), raw: backtest?.directional_accuracy, unit: '%', color: C.blueLight, bg: C.blueFaint, border: C.borderBlue },
  ];

  return (
    <div style={{
      background: `linear-gradient(145deg, ${C.card} 0%, rgba(13,26,52,0.9) 100%)`,
      border: `1px solid ${C.border}`,
      borderRadius: 16, padding: '18px 20px',
    }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div style={{
            width: 26, height: 26, borderRadius: 7,
            background: C.blueFaint, border: `1px solid ${C.borderBlue}`,
            display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 13,
          }}>🎯</div>
          <span style={{
            color: C.textSub, fontSize: 10, fontWeight: 700, letterSpacing: '0.1em',
          }} className="uppercase">Forecast Backtest</span>
        </div>
        <div
          style={{ position: 'relative', cursor: 'default' }}
          onMouseEnter={() => setShowTip(true)}
          onMouseLeave={() => setShowTip(false)}
        >
          <span style={{
            color: C.textMuted, fontSize: 10, background: 'rgba(255,255,255,0.05)',
            border: `1px solid ${C.border}`, borderRadius: 4, padding: '2px 7px', cursor: 'help',
          }}>?</span>
          {showTip && (
            <div style={{
              position: 'absolute', right: 0, top: 22, width: 260, zIndex: 50,
              background: '#1e1e2e', border: `1px solid ${C.border}`,
              borderRadius: 8, padding: '10px 12px',
              color: C.textSub, fontSize: 11, lineHeight: 1.6,
              boxShadow: '0 8px 24px rgba(0,0,0,0.5)',
            }}>
              <strong style={{ color: C.textPrimary }}>How this was measured:</strong><br/>
              {hasData ? (
                <>
                  {backtest.windows} expanding windows; train through FY t, score base-case revenue vs
                  the next {backtest.horizon_years} fiscal year(s) of AEO 10-K actuals. Same α and COVID
                  treatment as your forecast chart.
                </>
              ) : (
                <>Ask a revenue forecast in chat — holdout metrics align to that horizon and settings.</>
              )}
            </div>
          )}
        </div>
      </div>

      {/* 4-cell metric grid */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 12 }}>
        {metrics.map(m => (
          <div key={m.label} style={{
            background: m.bg, border: `1px solid ${m.border}`,
            borderRadius: 10, padding: '10px 12px',
          }}>
            <p style={{ color: C.textMuted, fontSize: 9, marginBottom: 4, letterSpacing: '0.05em' }} className="uppercase">
              {m.label}
            </p>
            <p style={{ color: m.raw != null ? m.color : C.textMuted, fontSize: 20, fontWeight: 700, letterSpacing: '-0.5px', margin: 0 }}>
              {m.value}
            </p>
          </div>
        ))}
      </div>

      {/* Latest window callout */}
      <div style={{
        background: 'rgba(34,197,94,0.06)', border: '1px solid rgba(34,197,94,0.12)',
        borderRadius: 8, padding: '8px 10px', marginBottom: 10,
        display: 'flex', alignItems: 'center', gap: 8,
      }}>
        <span style={{ color: C.green, fontSize: 11, fontWeight: 600 }}>
          Latest window{hasData ? ':' : ''}
        </span>
        <span style={{ color: C.textSub, fontSize: 11 }}>
          {hasData && backtest.latest_window
            ? `${backtest.latest_window.label} · Rev MAPE ${backtest.latest_window.rev_mape}% · OI MAPE ${backtest.latest_window.oi_mape}%`
            : '—'}
        </span>
      </div>

      {/* Footnote */}
      <p style={{ color: C.textMuted, fontSize: 10, lineHeight: 1.5, margin: 0 }}>
        {hasData ? backtest.model : 'Component P&L engine · expanding-window holdout on filed AEO actuals'}
      </p>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Segment stacked bar chart — AE brand vs Aerie brand revenue
// ─────────────────────────────────────────────────────────────────────────────

const SegmentTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  const d = payload[0]?.payload;
  if (!d) return null;
  const total = d.aerie + d.ae;
  return (
    <div style={{
      background: '#1e293b', border: `1px solid ${C.borderMid}`,
      borderRadius: 8, padding: '10px 14px', boxShadow: '0 8px 32px rgba(0,0,0,0.6)', minWidth: 180,
    }}>
      <p style={{ color: C.textSub, fontSize: 11, marginBottom: 6 }}>{label}</p>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 3 }}>
        <div style={{ width: 8, height: 8, borderRadius: 2, background: '#22d3ee' }} />
        <span style={{ color: C.textSub, fontSize: 11 }}>Aerie:</span>
        <span style={{ color: C.textPrimary, fontSize: 13, fontWeight: 600 }}>${d.aerie.toFixed(0)}M</span>
        <span style={{ color: C.textSub, fontSize: 10 }}>({d.aerieShare.toFixed(1)}%)</span>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
        <div style={{ width: 8, height: 8, borderRadius: 2, background: C.indigo }} />
        <span style={{ color: C.textSub, fontSize: 11 }}>AE Brand:</span>
        <span style={{ color: C.textPrimary, fontSize: 13, fontWeight: 600 }}>${d.ae.toFixed(0)}M</span>
        <span style={{ color: C.textSub, fontSize: 10 }}>({(100 - d.aerieShare).toFixed(1)}%)</span>
      </div>
      <div style={{ borderTop: `1px solid ${C.border}`, paddingTop: 5 }}>
        <span style={{ color: C.textSub, fontSize: 11 }}>Total: </span>
        <span style={{ color: C.textPrimary, fontSize: 12, fontWeight: 600 }}>${(total / 1000).toFixed(2)}B</span>
      </div>
      {d.aerie_oi_m && (
        <div style={{ marginTop: 5 }}>
          <span style={{ color: C.textSub, fontSize: 10 }}>Seg. OI Margin — </span>
          <span style={{ color: '#22d3ee', fontSize: 10 }}>Aerie {d.aerie_oi_m}%</span>
          <span style={{ color: C.textSub, fontSize: 10 }}> · </span>
          <span style={{ color: C.indigo, fontSize: 10 }}>AE {d.ae_oi_m}%</span>
        </div>
      )}
      {d.isCovid && <p style={{ color: C.red, fontSize: 10, marginTop: 4 }}>⚠ COVID-19 impact year</p>}
    </div>
  );
};

function SegmentChart() {
  return (
    <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 16, padding: '22px 22px 16px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 10 }}>
        <SectionLabel>AE vs Aerie · FY2018–FY2024 ($M)</SectionLabel>
        <div style={{ display: 'flex', gap: 14, alignItems: 'center' }}>
          <LegendDot color={C.cyan} label="Aerie" />
          <LegendDot color={C.blue} label="AE Brand" />
        </div>
      </div>
      <ResponsiveContainer width="100%" height={220}>
        <BarChart data={SEGMENTS} barSize={26} margin={{ top: 4, right: 8, left: -12, bottom: 0 }}>
          <CartesianGrid vertical={false} stroke="rgba(255,255,255,0.04)" />
          <XAxis dataKey="label" tick={{ fill: C.textSub, fontSize: 10 }} axisLine={false} tickLine={false}
            tickFormatter={v => v.replace('FY', "'")} />
          <YAxis tick={{ fill: C.textSub, fontSize: 10 }} axisLine={false} tickLine={false}
            tickFormatter={v => `$${(v / 1000).toFixed(1)}B`} domain={[0, 5500]} />
          <Tooltip content={<SegmentTooltip />} cursor={{ fill: 'rgba(255,255,255,0.03)' }} />
          <Bar dataKey="ae" name="AE Brand" stackId="a" fill={C.blue} fillOpacity={0.70} />
          <Bar dataKey="aerie" name="Aerie" stackId="a" fill={C.cyan} fillOpacity={0.85} radius={[5, 5, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
      <div style={{
        marginTop: 10, padding: '10px 14px',
        background: 'rgba(6,182,212,0.06)', border: `1px solid rgba(6,182,212,0.15)`,
        borderRadius: 10, display: 'flex', alignItems: 'center', gap: 10,
      }}>
        <span style={{ fontSize: 16 }}>↗</span>
        <div>
          <span style={{ color: C.cyan, fontSize: 12, fontWeight: 600 }}>Aerie: 15.6% → 33.9% of revenue</span>
          <span style={{ color: C.textSub, fontSize: 11 }}> · FY2018–FY2024 · ~13% CAGR · AEO's primary growth engine</span>
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// FY2024 Gross Margin Snapshot Bar Chart (horizontal)
// ─────────────────────────────────────────────────────────────────────────────

const SnapshotTooltip = ({ active, payload }) => {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div style={{
      background: '#1e293b', border: `1px solid ${C.borderMid}`,
      borderRadius: 8, padding: '10px 14px', boxShadow: '0 8px 32px rgba(0,0,0,0.6)',
    }}>
      <p style={{ color: C.textSub, fontSize: 11, marginBottom: 4 }}>
        <strong style={{ color: d.color }}>{d.ticker}</strong> · {d.name}
      </p>
      <p style={{ color: C.textPrimary, fontSize: 13, fontWeight: 700 }}>GM: {d.gm.toFixed(1)}%</p>
      <p style={{ color: C.cyan, fontSize: 12 }}>Op Margin: {d.om.toFixed(1)}%</p>
      <p style={{ color: C.textSub, fontSize: 11 }}>Revenue: ${d.revB.toFixed(2)}B</p>
      <p style={{ color: C.textSub, fontSize: 10, marginTop: 3, fontStyle: 'italic' }}>{d.ticker === 'AEO' ? 'Fiscal 2024' : 'Most recent fiscal year'}</p>
    </div>
  );
};

function MarginSnapshotChart() {
  // Sort by gross margin descending
  const sorted = [...FY2024_SNAPSHOT].sort((a, b) => b.gm - a.gm);
  return (
    <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 16, padding: '22px 22px 16px' }}>
      <SectionLabel>Gross Margin · FY2024 Peers (%)</SectionLabel>
      <ResponsiveContainer width="100%" height={220}>
        <BarChart data={sorted} layout="vertical" barSize={16} margin={{ top: 0, right: 40, left: 30, bottom: 0 }}>
          <CartesianGrid horizontal={false} stroke="rgba(255,255,255,0.04)" />
          <XAxis type="number" tick={{ fill: C.textSub, fontSize: 10 }} axisLine={false} tickLine={false}
            tickFormatter={v => `${v}%`} domain={[0, 70]} />
          <YAxis type="category" dataKey="ticker" tick={{ fill: C.textSub, fontSize: 11, fontWeight: 600 }}
            axisLine={false} tickLine={false} width={40} />
          <Tooltip content={<SnapshotTooltip />} cursor={{ fill: 'rgba(255,255,255,0.03)' }} />
          <Bar dataKey="gm" radius={[0, 4, 4, 0]}>
            {sorted.map(entry => (
              <Cell key={entry.ticker} fill={entry.color} fillOpacity={entry.ticker === 'AEO' ? 1 : 0.7} />
            ))}
          </Bar>
          {/* AEO reference line */}
          <ReferenceLine x={39.20} stroke={C.indigo} strokeDasharray="3 3" strokeWidth={1.5}
            label={{ value: 'AEO', fill: C.indigo, fontSize: 9, position: 'right' }} />
        </BarChart>
      </ResponsiveContainer>
      <p style={{ color: C.textMuted, fontSize: 10, marginTop: 8, textAlign: 'center' }}>
        AEO reference line · All figures from most recent 10-K filings
      </p>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Revenue bar chart
// ─────────────────────────────────────────────────────────────────────────────

const BarTooltip = ({ active, payload }) => {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div style={{
      background: '#1e293b', border: `1px solid ${C.borderMid}`,
      borderRadius: 8, padding: '10px 14px', boxShadow: '0 8px 32px rgba(0,0,0,0.6)', minWidth: 160,
    }}>
      <p style={{ color: C.textSub, fontSize: 11, marginBottom: 4 }}>{d.label}</p>
      {d.isBudget ? (
        <>
          <p style={{ color: C.amber, fontSize: 15, fontWeight: 700 }}>${d.revenue.toFixed(1)}M</p>
          <p style={{ color: C.amber, fontSize: 11, marginTop: 3 }}>What-if scenario</p>
        </>
      ) : d.isProjected ? (
        <>
          <p style={{ color: C.indigo, fontSize: 15, fontWeight: 700 }}>${d.revenue.toFixed(1)}M <span style={{ color: C.textSub, fontSize: 11 }}>base</span></p>
          <p style={{ color: C.green,  fontSize: 12, marginTop: 3 }}>Bull: ${d.bull?.toFixed(1)}M</p>
          <p style={{ color: C.amber,  fontSize: 12 }}>Bear: ${d.bear?.toFixed(1)}M</p>
        </>
      ) : (
        <>
          <p style={{ color: d.isCovid ? C.red : C.textPrimary, fontSize: 15, fontWeight: 700 }}>
            ${d.revenue.toFixed(1)}M
          </p>
          {d.isCovid && <p style={{ color: C.red, fontSize: 11, marginTop: 3 }}>⚠ COVID-19 outlier</p>}
        </>
      )}
    </div>
  );
};

function forecastChartEndYear(cu) {
  if (cu?.type !== 'forecast' || !cu?.data?.length) return '2024';
  const lab = cu.data[cu.data.length - 1].label || '';
  const m = lab.match(/FY(\d{4})/);
  return m ? m[1] : '2024';
}

function RevenueBarChart({ chartUpdate, onDismiss }) {
  const allData = [...FINANCIALS];
  if (chartUpdate?.type === 'forecast' && chartUpdate.data?.length) {
    chartUpdate.data.forEach(d => allData.push({ label: d.label, revenue: d.base, bull: d.bull, bear: d.bear, isProjected: true }));
  }
  if (chartUpdate?.type === 'budget') {
    allData.push({ label: chartUpdate.label, revenue: chartUpdate.revenue, isBudget: true, revChange: chartUpdate.rev_change });
  }
  const anomalyYears = chartUpdate?.type === 'anomaly' ? new Set(chartUpdate.flagged_years) : new Set();
  const domainMax = Math.max(...allData.map(d => d.revenue), 5800);

  return (
    <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 16, padding: '22px 22px 16px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
        <SectionLabel>Revenue · FY2015–{chartUpdate?.type === 'forecast' ? forecastChartEndYear(chartUpdate) : '2024'}</SectionLabel>
        {chartUpdate && chartUpdate.type !== 'peer_comparison' && (
          <button onClick={onDismiss} style={{
            background: 'rgba(255,255,255,0.05)', border: `1px solid ${C.border}`,
            borderRadius: 20, padding: '3px 10px', cursor: 'pointer', color: C.textSub,
            fontSize: 11, display: 'flex', alignItems: 'center', gap: 5,
          }}>
            <span style={{ color: chartUpdate.type === 'forecast' ? C.blueLight : chartUpdate.type === 'budget' ? C.amber : C.red }}>●</span>
            {chartUpdate.type === 'forecast' ? 'Showing Forecast' : chartUpdate.type === 'budget' ? `Showing ${chartUpdate.label}` : 'Showing Anomalies'}
            <span style={{ opacity: 0.5 }}>✕</span>
          </button>
        )}
      </div>
      <ResponsiveContainer width="100%" height={220}>
        <BarChart data={allData} barSize={18} margin={{ top: 4, right: 8, left: -12, bottom: 0 }}>
          <CartesianGrid vertical={false} stroke="rgba(255,255,255,0.03)" />
          <XAxis dataKey="label" tick={{ fill: C.textSub, fontSize: 10 }} axisLine={false} tickLine={false}
            tickFormatter={v => v.replace('FY', "'")} />
          <YAxis tick={{ fill: C.textSub, fontSize: 10 }} axisLine={false} tickLine={false}
            tickFormatter={v => `$${(v/1000).toFixed(1)}B`}
            domain={[2500, Math.ceil(domainMax/500)*500+200]} />
          <Tooltip content={<BarTooltip />} cursor={{ fill: 'rgba(255,255,255,0.02)' }} />
          {chartUpdate?.type === 'forecast' && (
            <ReferenceLine x="FY2024" stroke="rgba(255,255,255,0.10)" strokeDasharray="4 3" />
          )}
          <Bar dataKey="revenue" radius={[5,5,0,0]}>
            {allData.map(entry => {
              let fill = C.blue, opacity = 0.72;
              if (entry.isCovid)          { fill = C.red;      opacity = 0.85; }
              else if (entry.isProjected) { fill = C.blueLight; opacity = 0.35; }
              else if (entry.isBudget)    { fill = C.amber;     opacity = 0.85; }
              else if (anomalyYears.has(entry.fy)) { fill = C.amber; opacity = 0.85; }
              return <Cell key={entry.label} fill={fill} fillOpacity={opacity} />;
            })}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
      <div style={{ display: 'flex', gap: 16, marginTop: 10, flexWrap: 'wrap' }}>
        <LegendDot color={C.blue}     opacity={0.72} label="Historical" />
        <LegendDot color={C.red}      opacity={0.85} label="COVID outlier (FY2020)" />
        {chartUpdate?.type === 'forecast' && <LegendDot color={C.blueLight} opacity={0.35} label="Projected (base)" />}
        {chartUpdate?.type === 'budget'   && <LegendDot color={C.amber}     opacity={0.85} label="What-if" />}
        {chartUpdate?.type === 'anomaly'  && <LegendDot color={C.amber}     opacity={0.85} label="Flagged" />}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Margin line chart + interactive peer selector
// ─────────────────────────────────────────────────────────────────────────────

const MarginTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div style={{
      background: '#1e293b', border: `1px solid ${C.borderMid}`,
      borderRadius: 8, padding: '10px 14px', boxShadow: '0 8px 32px rgba(0,0,0,0.6)',
    }}>
      <p style={{ color: C.textSub, fontSize: 11, marginBottom: 6 }}>{label}</p>
      {payload.map(p => p.value != null && (
        <div key={p.dataKey} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 3 }}>
          <div style={{ width: 8, height: 8, borderRadius: '50%', background: p.color }} />
          <span style={{ color: C.textSub, fontSize: 11 }}>{p.name}:</span>
          <span style={{ color: p.value < 0 ? C.red : C.textPrimary, fontSize: 13, fontWeight: 600 }}>
            {p.value.toFixed(1)}%
          </span>
        </div>
      ))}
    </div>
  );
};

function MarginLineChart({ activePeers, onTogglePeer }) {
  // Merge active peer data into FINANCIALS array
  const peerKeys = Object.keys(PEERS);
  const chartData = FINANCIALS.map(d => {
    const row = { ...d };
    peerKeys.forEach(ticker => {
      if (!activePeers.has(ticker)) return;
      const match = PEERS[ticker].data.find(p => p.label === d.label);
      row[`${ticker}_gm`] = match?.gm ?? null;
      row[`${ticker}_om`] = match?.om ?? null;
    });
    return row;
  });

  // Calculate dynamic Y-axis domain
  let yMax = 45;
  activePeers.forEach(ticker => {
    const maxGm = Math.max(...PEERS[ticker].data.map(p => p.gm || 0));
    if (maxGm > yMax) yMax = maxGm + 5;
  });

  const [hoveredPeer, setHoveredPeer] = useState(null);

  return (
    <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 16, padding: '22px 22px 16px' }}>
      {/* Header + peer selector */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 10 }}>
        <SectionLabel>Margins · FY2015–2024</SectionLabel>
        {activePeers.size > 0 && (
          <button onClick={() => activePeers.forEach(t => onTogglePeer(t))} style={{
            background: 'none', border: 'none', cursor: 'pointer',
            color: C.textSub, fontSize: 10, marginBottom: 12,
          }}>
            Clear all
          </button>
        )}
      </div>

      {/* Peer selector chips */}
      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 14 }}>
        {peerKeys.map(ticker => {
          const peer = PEERS[ticker];
          const active = activePeers.has(ticker);
          const hovered = hoveredPeer === ticker;
          return (
            <button
              key={ticker}
              onClick={() => onTogglePeer(ticker)}
              onMouseEnter={() => setHoveredPeer(ticker)}
              onMouseLeave={() => setHoveredPeer(null)}
              title={`${peer.name} · ${peer.segment}`}
              style={{
                background: active ? `${peer.color}1A` : hovered ? 'rgba(255,255,255,0.05)' : 'rgba(255,255,255,0.02)',
                border: `1px solid ${active ? peer.color + '55' : 'rgba(255,255,255,0.07)'}`,
                borderRadius: 20, padding: '4px 12px', cursor: 'pointer',
                color: active ? peer.color : C.textSub,
                fontSize: 11, fontWeight: active ? 600 : 400,
                transition: 'all 0.15s',
                display: 'flex', alignItems: 'center', gap: 5,
              }}
            >
              {active && <span style={{ width: 6, height: 6, borderRadius: '50%', background: peer.color, flexShrink: 0 }} />}
              {ticker}
            </button>
          );
        })}
        <span style={{ color: C.textMuted, fontSize: 10, alignSelf: 'center', marginLeft: 2 }}>
          {activePeers.size === 0 ? 'tap to compare' : `${activePeers.size} active`}
        </span>
      </div>

      <ResponsiveContainer width="100%" height={220}>
        <LineChart data={chartData} margin={{ top: 4, right: 8, left: -12, bottom: 0 }}>
          <CartesianGrid stroke="rgba(255,255,255,0.04)" />
          <XAxis dataKey="label" tick={{ fill: C.textSub, fontSize: 10 }} axisLine={false} tickLine={false}
            tickFormatter={v => v.replace('FY', "'")} />
          <YAxis tick={{ fill: C.textSub, fontSize: 10 }} axisLine={false} tickLine={false}
            tickFormatter={v => `${v}%`} domain={[-15, Math.ceil(yMax/10)*10]} />
          <Tooltip content={<MarginTooltip />} />
          <ReferenceLine y={0} stroke="rgba(255,255,255,0.12)" strokeDasharray="4 3" />

          {/* AEO lines */}
          <Line type="monotone" dataKey="grossMargin" name="AEO Gross Margin"
            stroke={C.blueLight} strokeWidth={2}
            dot={{ r: 3, fill: C.blueLight, strokeWidth: 0 }} activeDot={{ r: 5 }} />
          <Line type="monotone" dataKey="opMargin" name="AEO Op. Margin"
            stroke={C.cyan} strokeWidth={2}
            dot={(props) => {
              const { cx, cy, payload } = props;
              return <circle key={payload.label} cx={cx} cy={cy}
                r={payload.isCovid ? 5 : 3} fill={payload.isCovid ? C.red : C.cyan} strokeWidth={0} />;
            }}
            activeDot={{ r: 5 }} />

          {/* Peer overlay lines */}
          {[...activePeers].map(ticker => {
            const color = PEERS[ticker].color;
            const name  = PEERS[ticker].name;
            return (
              <React.Fragment key={ticker}>
                <Line type="monotone" dataKey={`${ticker}_gm`} name={`${name} GM`}
                  stroke={color} strokeWidth={1.5} strokeDasharray="5 3"
                  dot={{ r: 2.5, fill: color, strokeWidth: 0 }}
                  activeDot={{ r: 4 }} connectNulls={false} />
                <Line type="monotone" dataKey={`${ticker}_om`} name={`${name} OM`}
                  stroke={color} strokeWidth={1.5} strokeDasharray="2 3" strokeOpacity={0.7}
                  dot={false} activeDot={{ r: 3 }} connectNulls={false} />
              </React.Fragment>
            );
          })}

          <Legend wrapperStyle={{ paddingTop: 10 }}
            formatter={v => <span style={{ color: C.textSub, fontSize: 10 }}>{v}</span>} />
        </LineChart>
      </ResponsiveContainer>

      {activePeers.size > 0 && (
        <div style={{ display: 'flex', gap: 12, marginTop: 8, flexWrap: 'wrap' }}>
          {[...activePeers].map(ticker => (
            <LegendDot key={ticker} color={PEERS[ticker].color} dashed label={`${ticker} (dashed)`} />
          ))}
        </div>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Waterfall chart
// ─────────────────────────────────────────────────────────────────────────────

const WaterfallTooltip = ({ active, payload }) => {
  if (!active || !payload?.length) return null;
  const d = payload[1]?.payload ?? payload[0]?.payload;
  if (!d) return null;
  return (
    <div style={{ background: '#1e293b', border: `1px solid ${C.borderMid}`, borderRadius: 8, padding: '10px 14px' }}>
      <p style={{ color: C.textSub, fontSize: 11, marginBottom: 4 }}>{d.label}</p>
      {d.isAnchor ? (
        <p style={{ color: C.indigo, fontSize: 15, fontWeight: 700 }}>${d.height.toFixed(1)}M</p>
      ) : (
        <p style={{ color: d.isPos ? C.green : C.red, fontSize: 15, fontWeight: 700 }}>
          {d.isPos ? '+' : '−'}${Math.abs(d.rawDelta).toFixed(1)}M
        </p>
      )}
      {d.label === 'FY2020' && <p style={{ color: C.red, fontSize: 11, marginTop: 3 }}>COVID-19 impact</p>}
      {d.label === 'FY2021' && <p style={{ color: C.green, fontSize: 11, marginTop: 3 }}>Post-COVID recovery</p>}
    </div>
  );
};

function WaterfallChart() {
  return (
    <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 16, padding: '22px 22px 16px' }}>
      <SectionLabel>Revenue Bridge · FY2019 → FY2024 ($M)</SectionLabel>
      <ResponsiveContainer width="100%" height={220}>
        <BarChart data={WATERFALL_DATA} barSize={24} margin={{ top: 4, right: 8, left: -12, bottom: 0 }}>
          <CartesianGrid vertical={false} stroke="rgba(255,255,255,0.04)" />
          <XAxis dataKey="label" tick={{ fill: C.textSub, fontSize: 10 }} axisLine={false} tickLine={false} />
          <YAxis tick={{ fill: C.textSub, fontSize: 10 }} axisLine={false} tickLine={false}
            tickFormatter={v => `$${(v/1000).toFixed(1)}B`} domain={[2800, 5900]} />
          <Tooltip content={<WaterfallTooltip />} cursor={{ fill: 'rgba(255,255,255,0.03)' }} />
          <Bar dataKey="base" stackId="wf" fill="transparent" />
          <Bar dataKey="height" stackId="wf" radius={[5,5,0,0]}>
            {WATERFALL_DATA.map(entry => (
              <Cell key={entry.label}
                fill={entry.isAnchor ? C.blue : entry.isPos ? C.green : C.red}
                fillOpacity={entry.isAnchor ? 0.80 : 0.88} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
      <div style={{ display: 'flex', gap: 16, marginTop: 10 }}>
        <LegendDot color={C.blue}  opacity={0.80} label="Anchor" />
        <LegendDot color={C.green} opacity={0.88} label="YoY Growth" />
        <LegendDot color={C.red}   opacity={0.88} label="YoY Decline" />
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// ROI modal
// ─────────────────────────────────────────────────────────────────────────────

function RoiModal({ onClose }) {
  const rows = [
    { item: 'Budget cycle labor (manual)',       assumption: '2 cycles/yr × 40 hrs × 50 analysts × 60% automate', impact: '~$110K/yr' },
    { item: 'Ad-hoc query automation',           assumption: '20 min/query × 500 queries × $45/hr avg cost',      impact: '~$7.5K/yr' },
    { item: 'Reconciliation error reduction',    assumption: 'Est. 3 material corrections/yr @ $30K each',        impact: '~$90K/yr'  },
    { item: 'External consultants displaced',    assumption: '1–2 FP&A engagements/yr @ $50K each',              impact: '~$50K/yr'  },
    { item: 'Faster time-to-insight',            assumption: '70% reduction in time-to-answer',                   impact: 'Strategic'  },
    { item: 'Tool cost estimate',                assumption: 'LLM API + infra + maintenance',                     impact: '~$50K/yr'  },
  ];
  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.75)',
      display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}
      onClick={onClose}>
      <div style={{
        background: '#0f1829', border: `1px solid ${C.borderMid}`,
        borderRadius: 16, padding: '28px 32px', maxWidth: 560, width: '90%',
        boxShadow: '0 24px 80px rgba(0,0,0,0.8)',
      }} onClick={e => e.stopPropagation()}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 20 }}>
          <div>
            <p style={{ color: C.textPrimary, fontWeight: 700, fontSize: 16, marginBottom: 3 }}>ROI Calculator</p>
            <p style={{ color: C.textSub, fontSize: 12 }}>Estimated annual value of FP&A automation at AEO scale (~50 analysts)</p>
          </div>
          <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', color: C.textSub, fontSize: 20, padding: 4 }}>✕</button>
        </div>
        <div style={{ borderRadius: 10, overflow: 'hidden', border: `1px solid ${C.border}` }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
            <thead>
              <tr style={{ background: 'rgba(255,255,255,0.03)' }}>
                {['Value Driver', 'Assumption', 'Est. Impact'].map(h => (
                  <th key={h} style={{ padding: '9px 12px', textAlign: 'left', color: C.textSub,
                    fontWeight: 500, fontSize: 10, letterSpacing: '0.06em', borderBottom: `1px solid ${C.border}` }}
                    className="uppercase">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={i} style={{ borderTop: i === 0 ? 'none' : `1px solid ${C.border}` }}>
                  <td style={{ padding: '8px 12px', color: C.textPrimary, fontSize: 11, fontWeight: 500 }}>{r.item}</td>
                  <td style={{ padding: '8px 12px', color: C.textSub, fontSize: 10 }}>{r.assumption}</td>
                  <td style={{ padding: '8px 12px', fontWeight: 600, fontSize: 12,
                    color: r.impact.startsWith('~$') ? C.green : r.item.includes('cost') ? C.amber : C.cyan }}>{r.impact}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div style={{ marginTop: 16, padding: '14px 16px', borderRadius: 10,
          background: 'rgba(52,211,153,0.08)', border: `1px solid rgba(52,211,153,0.2)` }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
            <div>
              <p style={{ color: C.textSub, fontSize: 11 }}>Estimated annual value</p>
              <p style={{ color: C.green, fontSize: 24, fontWeight: 700 }}>≈ $207K – $350K/yr</p>
            </div>
            <div style={{ textAlign: 'right' }}>
              <p style={{ color: C.textSub, fontSize: 11 }}>Tool cost</p>
              <p style={{ color: C.amber, fontSize: 18, fontWeight: 600 }}>~$50K/yr</p>
            </div>
          </div>
          <p style={{ color: C.textSub, fontSize: 10, lineHeight: 1.4 }}>
            4–7× estimated ROI. Excludes strategic upside from faster planning cycles and reduced consultant spend.
          </p>
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Chat message renderers
// ─────────────────────────────────────────────────────────────────────────────

function AgentBubble({ children }) {
  return (
    <div style={{ background: C.card, border: `1px solid ${C.border}`,
      borderRadius: '4px 12px 12px 12px', padding: '14px 16px', maxWidth: '92%' }}>
      {children}
    </div>
  );
}

function ForecastMessage({ msg }) {
  return (
    <AgentBubble>
      <p style={{ color: C.textSub, fontSize: 12, marginBottom: 10, lineHeight: 1.5 }}>{msg.summary}</p>
      <div style={{ borderRadius: 8, overflow: 'hidden', border: `1px solid ${C.border}`, marginBottom: 10 }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
          <thead>
            <tr style={{ background: 'rgba(255,255,255,0.03)' }}>
              {['Scenario','FY2025','FY2026','Growth Rate'].map(h => (
                <th key={h} style={{ padding: '8px 12px', textAlign: 'left', color: C.textSub,
                  fontWeight: 500, fontSize: 10, letterSpacing: '0.06em' }} className="uppercase">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {msg.rows.map((r,i) => (
              <tr key={r.scenario} style={{ borderTop: i===0?'none':`1px solid ${C.border}` }}>
                <td style={{ padding: '9px 12px' }}>
                  <span style={{ display:'inline-flex',alignItems:'center',gap:6,color:r.color,fontWeight:600,fontSize:12 }}>
                    <span style={{ width:6,height:6,borderRadius:'50%',background:r.color,flexShrink:0 }}/>
                    {r.scenario}
                  </span>
                </td>
                <td style={{ padding:'9px 12px',color:C.textPrimary,fontWeight:600 }}>{r.fy25}</td>
                <td style={{ padding:'9px 12px',color:C.textPrimary,fontWeight:600 }}>{r.fy26}</td>
                <td style={{ padding:'9px 12px',color:C.green,fontWeight:500 }}>{r.growth}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p style={{ color:C.textSub,fontSize:11,lineHeight:1.5,borderLeft:`2px solid ${C.indigo}`,paddingLeft:10,marginLeft:2 }}>
        💡 {msg.insight}
      </p>
    </AgentBubble>
  );
}

function BudgetMessage({ msg }) {
  return (
    <AgentBubble>
      <p style={{ color:C.amber,fontSize:11,fontWeight:600,marginBottom:8,letterSpacing:'0.04em' }}>BUDGET SCENARIO</p>
      <p style={{ color:C.textSub,fontSize:11,marginBottom:10 }}>{msg.summary}</p>
      <div style={{ borderRadius:8,overflow:'hidden',border:`1px solid ${C.border}`,marginBottom:10 }}>
        <table style={{ width:'100%',borderCollapse:'collapse',fontSize:12 }}>
          <thead>
            <tr style={{ background:'rgba(255,255,255,0.03)' }}>
              {['Metric','FY2024 Actual','Projected','Impact'].map(h=>(
                <th key={h} style={{ padding:'7px 12px',textAlign:'left',color:C.textSub,fontWeight:500,fontSize:10,letterSpacing:'0.06em' }} className="uppercase">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {msg.rows.map((r,i)=>(
              <tr key={r.metric} style={{ borderTop:i===0?'none':`1px solid ${C.border}` }}>
                <td style={{ padding:'8px 12px',color:C.textSub,fontSize:11 }}>{r.metric}</td>
                <td style={{ padding:'8px 12px',color:C.textPrimary,fontWeight:500 }}>{r.actual}</td>
                <td style={{ padding:'8px 12px',color:C.textPrimary,fontWeight:600 }}>{r.projected}</td>
                <td style={{ padding:'8px 12px',color:r.delta==='flat'?C.textSub:r.neg?C.red:C.green,fontWeight:500,fontSize:11 }}>{r.delta}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p style={{ color:C.textSub,fontSize:11,lineHeight:1.5,borderLeft:`2px solid ${C.amber}`,paddingLeft:10,marginLeft:2 }}>
        💡 {msg.insight}
      </p>
    </AgentBubble>
  );
}

function PeerSnapshotMessage({ msg }) {
  const sorted = [...FY2024_SNAPSHOT].sort((a,b) => b.gm - a.gm);
  return (
    <AgentBubble>
      <p style={{ color:'#10b981',fontSize:11,fontWeight:600,marginBottom:4,letterSpacing:'0.04em' }}>
        COMPETITIVE BENCHMARK · FY2024
      </p>
      <p style={{ color:C.textSub,fontSize:11,marginBottom:10,lineHeight:1.5 }}>{msg.summary}</p>
      <div style={{ borderRadius:8,overflow:'hidden',border:`1px solid ${C.border}`,marginBottom:10 }}>
        <table style={{ width:'100%',borderCollapse:'collapse',fontSize:12 }}>
          <thead>
            <tr style={{ background:'rgba(255,255,255,0.03)' }}>
              {['Company','Revenue','Gross Margin','Op Margin','Segment'].map(h=>(
                <th key={h} style={{ padding:'7px 10px',textAlign:'left',color:C.textSub,fontWeight:500,fontSize:9,letterSpacing:'0.06em' }} className="uppercase">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sorted.map((r,i)=>{
              const isAeo = r.ticker === 'AEO';
              const seg = isAeo ? 'Teen/YA + Intimates' : Object.values(PEERS).find(p=>p.name===r.name)?.segment ?? '';
              return (
                <tr key={r.ticker} style={{
                  borderTop:i===0?'none':`1px solid ${C.border}`,
                  background:isAeo?'rgba(129,140,248,0.06)':'transparent',
                }}>
                  <td style={{ padding:'8px 10px' }}>
                    <span style={{ display:'inline-flex',alignItems:'center',gap:6 }}>
                      <span style={{ width:8,height:8,borderRadius:2,background:r.color,flexShrink:0 }}/>
                      <span style={{ color:isAeo?C.textPrimary:C.textSub,fontWeight:isAeo?700:500,fontSize:12 }}>
                        {r.ticker}
                      </span>
                    </span>
                  </td>
                  <td style={{ padding:'8px 10px',color:C.textSub,fontSize:11 }}>${r.revB.toFixed(1)}B</td>
                  <td style={{ padding:'8px 10px',color:r.color,fontWeight:700,fontSize:13 }}>{r.gm.toFixed(1)}%</td>
                  <td style={{ padding:'8px 10px',color:r.om<0?C.red:C.textPrimary,fontWeight:600,fontSize:12 }}>{r.om.toFixed(1)}%</td>
                  <td style={{ padding:'8px 10px',color:C.textMuted,fontSize:10 }}>{seg}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p style={{ color:C.textSub,fontSize:11,lineHeight:1.5,marginBottom:6 }}>{msg.note}</p>
      <p style={{ color:C.textSub,fontSize:11,lineHeight:1.5,borderLeft:`2px solid #10b981`,paddingLeft:10,marginLeft:2 }}>
        💡 {msg.insight}
      </p>
    </AgentBubble>
  );
}

function ChatMessage({ msg }) {
  if (msg.role === 'user') {
    return (
      <div style={{ display:'flex',justifyContent:'flex-end',marginBottom:12 }}>
        <div style={{
          background:'rgba(129,140,248,0.12)',border:`1px solid rgba(129,140,248,0.2)`,
          borderRadius:'12px 4px 12px 12px',padding:'10px 14px',
          maxWidth:'80%',color:C.textPrimary,fontSize:13,lineHeight:1.5,
        }}>{msg.text}</div>
      </div>
    );
  }
  return (
    <div style={{ display:'flex',gap:10,marginBottom:16,alignItems:'flex-start' }}>
      <div style={{
        width:28,height:28,borderRadius:8,flexShrink:0,marginTop:2,
        background:'linear-gradient(135deg, #6366f1, #06b6d4)',
        display:'flex',alignItems:'center',justifyContent:'center',
        fontSize:12,fontWeight:700,color:'#fff',
      }}>A</div>
      <div style={{ flex:1,minWidth:0 }}>
        {msg.type === 'forecast'       && <ForecastMessage msg={msg} />}
        {msg.type === 'budget'         && <BudgetMessage msg={msg} />}
        {msg.type === 'peer_snapshot'  && <PeerSnapshotMessage msg={msg} />}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Markdown renderer
// ─────────────────────────────────────────────────────────────────────────────

function renderInline(text) {
  return text.split(/(\*\*[^*]+\*\*)/g).map((part, i) =>
    part.startsWith('**') && part.endsWith('**')
      ? <strong key={i} style={{ color: C.textPrimary, fontWeight: 600 }}>{part.slice(2,-2)}</strong>
      : part
  );
}

/** Collapse ugly model output so "Suggested next steps" can be detected on its own line */
function normalizeSuggestedStepsMarkdown(raw) {
  if (!raw) return raw;
  let s = raw.replace(/\r\n/g, '\n');
  s = s.replace(/\\(\*{1,2})/g, '$1');
  s = s.replace(/\*{3,}/g, '**');
  s = s.replace(/\s*\*{1,2}\s*Suggested next steps:\s*\*{1,2}\s*/gi, '\n**Suggested next steps:**\n');
  return s.trim();
}

function isSuggestedHeadingLine(line) {
  const t = line.trim();
  return /^\*{0,2}\s*Suggested next steps:\s*\*{0,2}$/i.test(t);
}

function MarkdownBlock({ text }) {
  const lines = normalizeSuggestedStepsMarkdown(text).split('\n');
  const elements = [];
  let bulletBuffer = [];
  const flushBullets = () => {
    if (!bulletBuffer.length) return;
    elements.push(
      <ul key={`ul-${elements.length}`} style={{ margin:'6px 0 6px 4px',paddingLeft:16,listStyle:'none' }}>
        {bulletBuffer.map((item,i)=>(
          <li key={i} style={{ display:'flex',gap:8,marginBottom:4,alignItems:'flex-start' }}>
            <span style={{ color:C.indigo,fontSize:10,marginTop:4,flexShrink:0 }}>▸</span>
            <span style={{ color:C.textPrimary,fontSize:13,lineHeight:1.55 }}>{renderInline(item)}</span>
          </li>
        ))}
      </ul>
    );
    bulletBuffer = [];
  };
  lines.forEach((line,i)=>{
    if (line.startsWith('### ')) { flushBullets(); elements.push(<p key={i} style={{ color:C.textPrimary,fontWeight:700,fontSize:13,marginTop:elements.length>0?12:0,marginBottom:4 }}>{renderInline(line.slice(4))}</p>); }
    else if (line.startsWith('## ')) { flushBullets(); elements.push(<p key={i} style={{ color:C.textPrimary,fontWeight:700,fontSize:14,marginTop:elements.length>0?14:0,marginBottom:4 }}>{renderInline(line.slice(3))}</p>); }
    else if (/^[-*] /.test(line)) { bulletBuffer.push(line.slice(2)); }
    else if (line.trim()==='') { flushBullets(); if (elements.length>0) elements.push(<div key={`sp-${i}`} style={{ height:6 }}/>); }
    else if (isSuggestedHeadingLine(line)) {
      flushBullets();
      elements.push(
        <p key={i} style={{ color:C.textPrimary,fontSize:13,fontWeight:700,margin:'10px 0 6px',letterSpacing:'0.02em' }}>
          Suggested next steps
        </p>,
      );
    }
    else { flushBullets(); elements.push(<p key={i} style={{ color:C.textPrimary,fontSize:13,lineHeight:1.65,margin:'2px 0' }}>{renderInline(line)}</p>); }
  });
  flushBullets();
  return <>{elements}</>;
}

function LiveAgentMessage({ text }) {
  return (
    <div style={{ display:'flex',gap:10,marginBottom:16,alignItems:'flex-start' }}>
      <div style={{
        width:28,height:28,borderRadius:8,flexShrink:0,marginTop:2,
        background:'linear-gradient(135deg, #6366f1, #06b6d4)',
        display:'flex',alignItems:'center',justifyContent:'center',
        fontSize:12,fontWeight:700,color:'#fff',
      }}>A</div>
      <div style={{ background:C.card,border:`1px solid ${C.border}`,borderRadius:'4px 12px 12px 12px',padding:'14px 16px',maxWidth:'92%' }}>
        <MarkdownBlock text={text} />
      </div>
    </div>
  );
}

function TypingIndicator() {
  return (
    <div style={{ display:'flex',gap:10,marginBottom:16,alignItems:'flex-start' }}>
      <div style={{ width:28,height:28,borderRadius:8,flexShrink:0,background:'linear-gradient(135deg, #6366f1, #06b6d4)',display:'flex',alignItems:'center',justifyContent:'center',fontSize:12,fontWeight:700,color:'#fff' }}>A</div>
      <div style={{ background:C.card,border:`1px solid ${C.border}`,borderRadius:'4px 12px 12px 12px',padding:'14px 16px',display:'flex',gap:5,alignItems:'center' }}>
        {[0,1,2].map(i=>(
          <div key={i} style={{ width:6,height:6,borderRadius:'50%',background:C.indigo,animation:`pulse 1.2s ease-in-out ${i*0.2}s infinite`,opacity:0.7 }}/>
        ))}
        <style>{`@keyframes pulse{0%,80%,100%{transform:scale(0.7);opacity:0.4}40%{transform:scale(1);opacity:1}}`}</style>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Inline suggestion chips (shown below the last agent message)
// ─────────────────────────────────────────────────────────────────────────────

function InlineSuggestionChips({ suggestions, onSelect, disabled }) {
  const [hovered, setHovered] = useState(null);
  if (!suggestions || suggestions.length === 0) return null;
  return (
    <div style={{ marginLeft: 38, marginBottom: 14, marginTop: -4 }}>
      <p style={{ color: C.textPrimary, fontSize: 11, marginBottom: 6, fontWeight: 700 }}>
        Suggested next steps
      </p>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
        {suggestions.map((s, i) => (
          <button
            key={i}
            onClick={() => !disabled && onSelect(s)}
            onMouseEnter={() => setHovered(i)}
            onMouseLeave={() => setHovered(null)}
            disabled={disabled}
            style={{
              background: hovered === i ? 'rgba(37,99,235,0.12)' : 'rgba(37,99,235,0.05)',
              border: `1px solid ${hovered === i ? 'rgba(37,99,235,0.28)' : 'rgba(37,99,235,0.12)'}`,
              borderRadius: 10, padding: '7px 13px', cursor: disabled ? 'not-allowed' : 'pointer',
              color: hovered === i ? C.textPrimary : C.textSub, fontSize: 11, textAlign: 'left',
              display: 'flex', alignItems: 'center', gap: 8,
              opacity: disabled ? 0.4 : 1, transition: 'all 0.15s',
            }}
          >
            <span style={{ color: C.blueLight, fontSize: 10, flexShrink: 0 }}>→</span>
            <span style={{ lineHeight: 1.4 }}>{s}</span>
          </button>
        ))}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Prompt chips
// ─────────────────────────────────────────────────────────────────────────────

function PromptChips({ onSelect, disabled, dynamicChips }) {
  const [hovered, setHovered] = useState(null);
  const chips = (dynamicChips && dynamicChips.length > 0)
    ? dynamicChips.map(c => ({ label: c.label, query: c.query, icon: '⚡' }))
    : FALLBACK_CHIPS;
  return (
    <div style={{ display:'flex',flexWrap:'wrap',gap:6,padding:'10px 18px 4px' }}>
      {chips.map((chip,i)=>(
        <button key={chip.label}
          onClick={()=>!disabled&&onSelect(chip.query)}
          onMouseEnter={()=>setHovered(i)} onMouseLeave={()=>setHovered(null)}
          style={{
            background:hovered===i?'rgba(37,99,235,0.14)':'rgba(37,99,235,0.06)',
            border:`1px solid ${hovered===i?'rgba(37,99,235,0.32)':'rgba(37,99,235,0.14)'}`,
            borderRadius:20,padding:'5px 13px',cursor:disabled?'not-allowed':'pointer',
            color:hovered===i?C.textPrimary:C.textSub,fontSize:11,
            display:'flex',alignItems:'center',gap:5,
            opacity:disabled?0.4:1,transition:'all 0.15s',whiteSpace:'nowrap',
          }}
        >
          <span style={{ fontSize:12 }}>{chip.icon}</span>
          <span>{chip.label}</span>
        </button>
      ))}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Chat panel
// ─────────────────────────────────────────────────────────────────────────────

function ChatPanel({ onChartUpdate, onPeerUpdate, onTimeSaved, onSummaryRefresh, dynamicChips }) {
  const scrollRef = useRef(null);
  const inputRef  = useRef(null);
  const [input, setInput]             = useState('');
  const [liveMessages, setLiveMessages] = useState([]);
  const [loading, setLoading]         = useState(false);
  const [apiError, setApiError]       = useState(null);
  const staticDemo = isStaticDemo();

  const scrollToBottom = () => setTimeout(()=>{ if(scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight; },50);
  useEffect(()=>{ scrollToBottom(); },[liveMessages,loading]);

  // Restore session history on mount
  useEffect(() => {
    if (staticDemo) return;
    fetch(`${getApiBase()}/history`)
      .then(r => r.ok ? r.json() : Promise.reject())
      .then(d => {
        if (d.messages && d.messages.length > 0) {
          const restored = d.messages.map(m => ({
            role: m.role === 'user' ? 'user' : 'agent',
            text: m.content,
          }));
          setLiveMessages(restored);
        }
      })
      .catch(() => {});
  }, []);

  const sendMessage = async (text) => {
    if (staticDemo || !text.trim() || loading) return;
    setInput(''); setApiError(null);
    setLiveMessages(prev=>[...prev,{ role:'user',text }]);
    setLoading(true);
    onTimeSaved(prev => prev + 45);

    try {
      const res = await fetch(`${getApiBase()}/chat`,{
        method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({message:text}),
      });
      if (!res.ok) throw new Error(`Server error ${res.status}`);
      const data = await res.json();
      setLiveMessages(prev=>[...prev,{role:'agent',text:data.response,suggestions:data.suggestions||[]}]);
      onSummaryRefresh?.();
      if (data.chart_update && !data.chart_update.error) {
        if (data.chart_update.type === 'peer_comparison') {
          // Auto-activate all known peers on comparison queries
          onPeerUpdate(new Set(Object.keys(PEERS)));
        } else {
          onChartUpdate(data.chart_update);
        }
      }
    } catch(err) {
      const base = getApiBase();
      setApiError(err.message.includes('Failed to fetch')
        ? `Cannot reach the API at ${base}. In the project folder run: python3 src/04_api_server.py`
        : err.message);
    } finally {
      setLoading(false);
      inputRef.current?.focus();
    }
  };

  const handleKey = (e)=>{ if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();sendMessage(input.trim());} };

  return (
    <div style={{ display:'flex',flexDirection:'column',height:'100%' }}>
      {/* Header */}
      <div style={{ padding:'22px 24px 18px',borderBottom:`1px solid ${C.border}`,flexShrink:0 }}>
        {staticDemo && (
          <div style={{
            background:'rgba(245,158,11,0.08)',border:'1px solid rgba(245,158,11,0.22)',
            borderRadius:8,padding:'8px 12px',marginBottom:12,color:C.textSub,fontSize:11,lineHeight:1.5,
          }}>
            <strong style={{ color:C.amber }}>GitHub Pages (static).</strong>{' '}
            Charts and briefing load from embedded data. For live FP&A chat, run{' '}
            <code style={{ fontSize:10,opacity:0.9 }}>npm run start:app</code> locally or deploy the FastAPI API and rebuild with{' '}
            <code style={{ fontSize:10,opacity:0.9 }}>VITE_API_BASE_URL</code> set to your API URL.
          </div>
        )}
        <div style={{ display:'flex',alignItems:'center',justifyContent:'space-between',marginBottom:4 }}>
          <div style={{ display:'flex',alignItems:'center',gap:10 }}>
            {/* AEO Eagle mark */}
            <div style={{
              width:32,height:32,borderRadius:9,flexShrink:0,
              background:'linear-gradient(135deg, #1D4ED8 0%, #1E40AF 100%)',
              display:'flex',alignItems:'center',justifyContent:'center',
              fontSize:14,fontWeight:700,color:'#fff',letterSpacing:'-0.5px',
              boxShadow:'0 3px 10px rgba(29,78,216,0.30)',
            }}>A</div>
            <div>
              <p style={{ color:C.textPrimary,fontWeight:600,fontSize:14,marginBottom:1 }}>FP&A Intelligence</p>
              <p style={{ color:C.textSub,fontSize:10 }}>American Eagle Outfitters · FY2015–2024</p>
            </div>
          </div>
          <div style={{ display:'flex',gap:5,alignItems:'center' }}>
            <div style={{ width:6,height:6,borderRadius:'50%',background:C.green }}/>
            <span style={{
              color:C.textSub,fontSize:10,letterSpacing:'0.06em',
              background:'rgba(255,255,255,0.04)',border:`1px solid ${C.border}`,
              borderRadius:6,padding:'3px 8px',
            }} className="uppercase">AEO 10-K</span>
          </div>
        </div>
      </div>

      {/* Messages */}
      <div ref={scrollRef} style={{ flex:1,overflowY:'auto',padding:'16px 16px 8px' }}>
        {MESSAGES.map(msg=><ChatMessage key={msg.id} msg={msg}/>)}
        {liveMessages.length>0&&(
          <div style={{ display:'flex',alignItems:'center',gap:10,margin:'8px 0 16px' }}>
            <div style={{ flex:1,height:1,background:C.border }}/>
            <span style={{ color:C.textMuted,fontSize:10,letterSpacing:'0.08em' }} className="uppercase">Live session</span>
            <div style={{ flex:1,height:1,background:C.border }}/>
          </div>
        )}
        {liveMessages.map((msg,i)=>{
          const isLastAgent = msg.role==='agent' && liveMessages.slice(i+1).every(m=>m.role!=='agent');
          return msg.role==='user' ? (
            <div key={i} style={{ display:'flex',justifyContent:'flex-end',marginBottom:12 }}>
              <div style={{
                background:'linear-gradient(135deg, rgba(29,78,216,0.18), rgba(30,64,175,0.12))',
                border:`1px solid rgba(37,99,235,0.24)`,
                borderRadius:'14px 4px 14px 14px',padding:'10px 15px',
                maxWidth:'80%',color:C.textPrimary,fontSize:13,lineHeight:1.6,
              }}>{msg.text}</div>
            </div>
          ) : (
            <div key={i}>
              <LiveAgentMessage text={msg.text}/>
              {isLastAgent && msg.suggestions && msg.suggestions.length > 0 && (
                <InlineSuggestionChips
                  suggestions={msg.suggestions}
                  onSelect={sendMessage}
                  disabled={loading || staticDemo}
                />
              )}
            </div>
          );
        })}
        {loading&&<TypingIndicator/>}
        {apiError&&(
          <div style={{ background:C.redFaint,border:`1px solid rgba(220,38,38,0.28)`,
            borderRadius:10,padding:'10px 14px',marginBottom:12,color:C.red,fontSize:12,lineHeight:1.5 }}>
            ⚠ {apiError}
          </div>
        )}
      </div>

      <PromptChips onSelect={sendMessage} disabled={loading || staticDemo} dynamicChips={dynamicChips}/>

      {/* Input */}
      <div style={{ padding:'12px 18px 16px',borderTop:`1px solid ${C.border}`,flexShrink:0 }}>
        <div style={{ display:'flex',gap:10,alignItems:'center',
          background:C.card,
          border:`1px solid ${loading&&!staticDemo?'rgba(37,99,235,0.45)':C.borderMid}`,
          borderRadius:12,padding:'11px 14px',transition:'border-color 0.2s',
          boxShadow: loading&&!staticDemo?'0 0 0 2px rgba(37,99,235,0.08)':'none',
        }}>
          <input ref={inputRef} value={input} onChange={e=>setInput(e.target.value)} onKeyDown={handleKey}
            placeholder={staticDemo ? 'Live chat disabled on static hosting' : 'Ask a financial question… (Enter to send)'}
            disabled={loading || staticDemo}
            style={{ flex:1,background:'none',border:'none',outline:'none',
              color:loading||staticDemo?C.textSub:C.textPrimary,fontSize:13,cursor:loading||staticDemo?'not-allowed':'text' }}/>
          <button onClick={()=>sendMessage(input.trim())} disabled={staticDemo||!input.trim()||loading}
            style={{
              background:'linear-gradient(135deg, #1D4ED8, #1E40AF)',
              border:'none',borderRadius:8,cursor:!staticDemo&&input.trim()&&!loading?'pointer':'not-allowed',
              width:32,height:32,display:'flex',alignItems:'center',justifyContent:'center',
              opacity:!staticDemo&&input.trim()&&!loading?1:0.30,transition:'opacity 0.15s',flexShrink:0,
              boxShadow:!staticDemo&&input.trim()&&!loading?'0 2px 8px rgba(29,78,216,0.35)':'none',
            }}>
            {loading
              ? <div style={{ width:12,height:12,border:'2px solid rgba(255,255,255,0.3)',borderTopColor:'#fff',borderRadius:'50%',animation:'spin 0.6s linear infinite' }}/>
              : <svg width="14" height="14" viewBox="0 0 24 24" fill="none"><path d="M5 12h14M12 5l7 7-7 7" stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"/></svg>
            }
          </button>
        </div>
        <style>{`@keyframes spin{to{transform:rotate(360deg)}}`}</style>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Main dashboard
// ─────────────────────────────────────────────────────────────────────────────

// ─────────────────────────────────────────────────────────────────────────────
// Tab bar
// ─────────────────────────────────────────────────────────────────────────────

const TABS = [
  { id: 'overview',    label: 'Overview',    icon: '◎' },
  { id: 'competitors', label: 'Competitors', icon: '⇄' },
  { id: 'deepdive',    label: 'Deep Dive',   icon: '◈' },
];

function TabBar({ active, onChange }) {
  const [hovered, setHovered] = useState(null);
  return (
    <div style={{
      display: 'flex', gap: 4, padding: '3px',
      background: 'rgba(255,255,255,0.03)', borderRadius: 12,
      border: `1px solid ${C.border}`, alignSelf: 'flex-start',
    }}>
      {TABS.map(tab => {
        const isActive  = active === tab.id;
        const isHovered = hovered === tab.id && !isActive;
        return (
          <button
            key={tab.id}
            onClick={() => onChange(tab.id)}
            onMouseEnter={() => setHovered(tab.id)}
            onMouseLeave={() => setHovered(null)}
            style={{
              background: isActive
                ? 'linear-gradient(135deg, rgba(29,78,216,0.22), rgba(37,99,235,0.14))'
                : isHovered ? 'rgba(255,255,255,0.04)' : 'transparent',
              border: isActive
                ? `1px solid rgba(37,99,235,0.30)`
                : '1px solid transparent',
              borderRadius: 9, padding: '7px 18px', cursor: 'pointer',
              color: isActive ? C.blueLight : isHovered ? C.textPrimary : C.textSub,
              fontSize: 11.5, fontWeight: isActive ? 600 : 450,
              display: 'flex', alignItems: 'center', gap: 6,
              transition: 'all 0.15s', letterSpacing: '-0.01em',
            }}
          >
            <span style={{ fontSize: 11, opacity: isActive ? 1 : 0.5 }}>{tab.icon}</span>
            {tab.label}
          </button>
        );
      })}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Main dashboard
// ─────────────────────────────────────────────────────────────────────────────

export default function Dashboard() {
  const [chartUpdate, setChartUpdate]   = useState(null);
  const [activePeers, setActivePeers]   = useState(new Set());
  const [minutesSaved, setMinutesSaved] = useState(0);
  const [showRoi, setShowRoi]           = useState(false);
  const [summaryKey, setSummaryKey]     = useState(0);
  const [activeTab, setActiveTab]       = useState('overview');
  const [dynamicChips, setDynamicChips] = useState([]);
  const [defaultForecastBacktest, setDefaultForecastBacktest] = useState(null);

  useEffect(() => {
    const url = isStaticDemo() ? staticDemoUrl() : `${getApiBase()}/forecast-backtest`;
    fetch(url)
      .then(r => (r.ok ? r.json() : Promise.reject()))
      .then(d => {
        const bt = d.backtest;
        if (bt && typeof bt.revenue_mape === 'number') {
          setDefaultForecastBacktest(bt);
        }
      })
      .catch(() => {});
  }, []);

  const forecastData = chartUpdate?.type === 'forecast' && chartUpdate.data?.length ? chartUpdate.data[0] : null;
  const forecastFyLabel = forecastData?.label || 'FY2025';
  const hoursSaved   = (minutesSaved / 60).toFixed(1);

  const handleTogglePeer = (ticker) => {
    setActivePeers(prev => {
      const next = new Set(prev);
      if (next.has(ticker)) next.delete(ticker);
      else next.add(ticker);
      return next;
    });
  };

  // When switching to Competitors tab, auto-activate all peers
  const handleTabChange = (tabId) => {
    setActiveTab(tabId);
    if (tabId === 'competitors') {
      setActivePeers(new Set(Object.keys(PEERS)));
    }
  };

  return (
    <div style={{ background:C.bg,height:'100vh',width:'100vw',display:'flex',
      fontFamily:'-apple-system, BlinkMacSystemFont, "Inter", system-ui, sans-serif',
      overflow:'hidden', letterSpacing:'-0.01em' }}>

      {showRoi && <RoiModal onClose={()=>setShowRoi(false)}/>}

      {/* Left: Chat */}
      <div style={{ width:'38%',borderRight:`1px solid ${C.border}`,display:'flex',flexDirection:'column',background:C.panel }} data-chat-panel>
        <ChatPanel
          onChartUpdate={setChartUpdate}
          onPeerUpdate={setActivePeers}
          onTimeSaved={setMinutesSaved}
          onSummaryRefresh={() => setSummaryKey(k => k + 1)}
          dynamicChips={dynamicChips}
        />
      </div>

      {/* Right: Dashboard */}
      <div style={{ width:'62%',display:'flex',flexDirection:'column',overflow:'hidden' }}>

        {/* Header */}
        <div style={{
          padding:'16px 32px 14px',borderBottom:`1px solid ${C.border}`,flexShrink:0,
          display:'flex',alignItems:'center',justifyContent:'space-between',
          background:'rgba(5,8,15,0.60)', backdropFilter:'blur(12px)',
        }}>
          <div>
            <div style={{ display:'flex',alignItems:'center',gap:10,marginBottom:2 }}>
              <p style={{ color:C.textPrimary,fontWeight:700,fontSize:15,letterSpacing:'-0.3px' }}>
                AEO Financial Intelligence
              </p>
              <span style={{
                background: 'linear-gradient(90deg,#1D4ED8,#0EA5E9)',
                WebkitBackgroundClip:'text',WebkitTextFillColor:'transparent',
                fontSize:10,fontWeight:700,
              }}>LIVE</span>
            </div>
            <p style={{ color:C.textSub,fontSize:10.5 }}>
              American Eagle Outfitters · SEC 10-K · FY2015–2024 · 6 Competitors
            </p>
          </div>
          <div style={{ display:'flex',gap:6,alignItems:'center' }}>
            {minutesSaved > 0 && (
              <div style={{ display:'flex',alignItems:'center',gap:5,
                background:C.greenFaint,border:`1px solid rgba(34,197,94,0.20)`,
                borderRadius:7,padding:'5px 10px' }}>
                <span style={{ fontSize:11 }}>⏱</span>
                <span style={{ color:C.green,fontSize:10,fontWeight:600 }}>~{hoursSaved}h saved</span>
              </div>
            )}
            <button onClick={()=>setShowRoi(true)} style={{
              background:C.blueFaint,border:`1px solid ${C.borderBlue}`,
              borderRadius:7,padding:'5px 12px',cursor:'pointer',color:C.blueLight,fontSize:10,fontWeight:600 }}>
              ROI
            </button>
            <button onClick={()=>window.print()} style={{
              background:'rgba(255,255,255,0.04)',border:`1px solid ${C.border}`,
              borderRadius:7,padding:'5px 12px',cursor:'pointer',color:C.textSub,fontSize:10,
              display:'flex',alignItems:'center',gap:4 }}>
              <svg width="11" height="11" viewBox="0 0 24 24" fill="none">
                <path d="M12 3v13M7 11l5 5 5-5M3 18h18" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
              Export
            </button>
            <LiveHeaderDate />
          </div>
        </div>

        {/* Content */}
        <div style={{ flex:1,overflowY:'auto',padding:'24px 28px',display:'flex',flexDirection:'column',gap:18 }}>

          {/* Row 1: Executive Briefing + Backtest */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 280px', gap: 14, alignItems: 'start' }}>
            <ExecutiveSummary refreshKey={summaryKey} onSuggestionsLoaded={setDynamicChips} />
            <BacktestCard
              backtest={
                chartUpdate?.type === 'forecast' && chartUpdate.backtest
                  ? chartUpdate.backtest
                  : defaultForecastBacktest
              }
            />
          </div>

          {/* Row 2: KPI Scorecard */}
          <div style={{ display:'grid',gridTemplateColumns:'repeat(4,1fr)',gap:12 }}>
            <StatCard
              label={forecastData ? `${forecastFyLabel} base (rev $M)` : 'Net Revenue'}
              value={forecastData ? `$${forecastData.base.toFixed(0)}M` : '$5.33B'}
              delta={forecastData ? `Bull $${forecastData.bull.toFixed(0)}M` : '+1.3%'}
              deltaLabel={forecastData ? `Bear $${forecastData.bear.toFixed(0)}M` : 'vs FY2023'}
              icon="📈"
            />
            <StatCard label="Gross Margin" value="39.2%" delta="+0.72pp" deltaLabel="vs FY2023" icon="📊"/>
            <StatCard
              label={chartUpdate?.type==='budget'?'Budget Scenario':'Operating Income'}
              value={chartUpdate?.type==='budget'?`$${chartUpdate.revenue?.toFixed(0)}M`:'$427M'}
              delta={chartUpdate?.type==='budget'?`${(chartUpdate.rev_change>0?'+':'')}${chartUpdate.rev_change}% rev`:'+91.8%'}
              deltaLabel={chartUpdate?.type==='budget'?'vs FY2024':'vs FY2023'}
              icon="💰"
            />
            <StatCard
              label={activePeers.size>0?`vs ${[...activePeers].join(', ')}`:'Forecast Accuracy'}
              value={activePeers.size>0?`${activePeers.size} peers`:'100%'}
              delta={activePeers.size>0?'Overlay active':'Directional'}
              deltaLabel={activePeers.size>0?'on margin chart':'post-COVID excl.'}
              icon={activePeers.size>0?'🔍':'🎯'}
            />
          </div>

          {/* Tab navigation */}
          <TabBar active={activeTab} onChange={handleTabChange} />

          {/* Tab content — 2-column grid */}
          {activeTab === 'overview' && (
            <div style={{ display:'grid',gridTemplateColumns:'1fr 1fr',gap:14 }}>
              <RevenueBarChart chartUpdate={chartUpdate} onDismiss={()=>setChartUpdate(null)}/>
              <MarginLineChart activePeers={activePeers} onTogglePeer={handleTogglePeer}/>
            </div>
          )}

          {activeTab === 'competitors' && (
            <div style={{ display:'grid',gridTemplateColumns:'1fr 1fr',gap:14 }}>
              <MarginSnapshotChart/>
              <MarginLineChart activePeers={activePeers} onTogglePeer={handleTogglePeer}/>
            </div>
          )}

          {activeTab === 'deepdive' && (
            <div style={{ display:'grid',gridTemplateColumns:'1fr 1fr',gap:14 }}>
              <SegmentChart/>
              <WaterfallChart/>
            </div>
          )}

          <p style={{ color:C.textMuted,fontSize:9,textAlign:'center',paddingBottom:4,opacity:0.5 }}>
            SEC EDGAR 10-K iXBRL · AEO, ANF, URBN, BKE, LULU, VSCO, GPS · CIK verified
          </p>
        </div>
      </div>

      <style>{`@media print{[data-chat-panel]{display:none!important}}@keyframes spin{to{transform:rotate(360deg)}}`}</style>
    </div>
  );
}
