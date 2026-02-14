/**
 * WatchListTab - Underperforming properties flagged by configurable thresholds.
 * Shows occupancy, delinquency, renewal rate, and review rating flags.
 * Per WS6 design partner feedback.
 */
import { useState, useEffect, useRef } from 'react';
import { AlertTriangle, Building2, TrendingDown, DollarSign, Star, RefreshCw, ChevronDown, Settings, Check, RotateCcw } from 'lucide-react';
import { api } from '../api';

interface WatchFlag {
  metric: string;
  label: string;
  severity: string;
  value: number;
  threshold: number;
}

interface WatchProperty {
  id: string;
  name: string;
  owner_group: string;
  total_units: number;
  occupancy_pct: number;
  vacant: number;
  on_notice: number;
  preleased: number;
  delinquent_total: number;
  delinquent_units: number;
  renewal_rate_90d: number | null;
  google_rating: number | null;
  churn_score: number | null;
  at_risk_residents: number;
  flags: WatchFlag[];
  flag_count: number;
}

interface WatchlistData {
  total_properties: number;
  flagged_count: number;
  thresholds: {
    occupancy_pct: number;
    delinquent_total: number;
    renewal_rate_90d: number;
    google_rating: number;
  };
  watchlist: WatchProperty[];
}

interface Props {
  onPropertyClick?: (propertyId: string) => void;
  ownerGroup?: string;
  propertyIds?: string[];
}

// ---- Threshold persistence (localStorage) ----
interface Thresholds {
  occ_threshold?: number;
  delinq_threshold?: number;
  renewal_threshold?: number;
  review_threshold?: number;
}

const THRESHOLDS_KEY = 'watchlist_thresholds';

function loadThresholds(): Thresholds {
  try {
    const raw = localStorage.getItem(THRESHOLDS_KEY);
    return raw ? JSON.parse(raw) : {};
  } catch { return {}; }
}

function saveThresholds(t: Thresholds) {
  localStorage.setItem(THRESHOLDS_KEY, JSON.stringify(t));
}
// ---- End threshold helpers ----

const METRIC_ICONS: Record<string, typeof AlertTriangle> = {
  occupancy: TrendingDown,
  delinquency: DollarSign,
  renewal_rate: RefreshCw,
  review_rating: Star,
};

const METRIC_COLORS: Record<string, string> = {
  occupancy: 'text-red-600 bg-red-50 border-red-200',
  delinquency: 'text-amber-700 bg-amber-50 border-amber-200',
  renewal_rate: 'text-orange-600 bg-orange-50 border-orange-200',
  review_rating: 'text-purple-600 bg-purple-50 border-purple-200',
};

const PINNED_STORAGE_KEY = 'watchlist_pinned_properties';

function loadPinnedIds(): Set<string> {
  try {
    const raw = localStorage.getItem(PINNED_STORAGE_KEY);
    return raw ? new Set(JSON.parse(raw)) : new Set();
  } catch { return new Set(); }
}

function savePinnedIds(ids: Set<string>) {
  localStorage.setItem(PINNED_STORAGE_KEY, JSON.stringify([...ids]));
}

function FlagBadge({ flag }: { flag: WatchFlag }) {
  const Icon = METRIC_ICONS[flag.metric] || AlertTriangle;
  const colors = METRIC_COLORS[flag.metric] || 'text-slate-600 bg-slate-50 border-slate-200';
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium border ${colors}`}>
      <Icon className="w-3 h-3" />
      {flag.label}
    </span>
  );
}

export function WatchListTab({ onPropertyClick, ownerGroup, propertyIds }: Props) {
  const [data, setData] = useState<WatchlistData | null>(null);
  const [loading, setLoading] = useState(true);
  const [showAll, setShowAll] = useState(false);
  const [filterMetric, setFilterMetric] = useState<string>('all');
  const [pinnedIds, setPinnedIds] = useState<Set<string>>(loadPinnedIds);
  const [customThresholds, setCustomThresholds] = useState<Thresholds>(loadThresholds);
  const [showSettings, setShowSettings] = useState(false);
  const settingsRef = useRef<HTMLDivElement>(null);

  // Draft values for the settings editor (so changes only apply on Save)
  const [draftOcc, setDraftOcc] = useState<string>('');
  const [draftDelinq, setDraftDelinq] = useState<string>('');
  const [draftRenewal, setDraftRenewal] = useState<string>('');
  const [draftReview, setDraftReview] = useState<string>('');

  // Close settings on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (settingsRef.current && !settingsRef.current.contains(e.target as Node)) {
        setShowSettings(false);
      }
    };
    if (showSettings) document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [showSettings]);

  const fetchWatchlist = (thresholds: Thresholds) => {
    setLoading(true);
    const params: Parameters<typeof api.getWatchlist>[0] = {};
    if (ownerGroup) params.owner_group = ownerGroup;
    if (thresholds.occ_threshold != null) params.occ_threshold = thresholds.occ_threshold;
    if (thresholds.delinq_threshold != null) params.delinq_threshold = thresholds.delinq_threshold;
    if (thresholds.renewal_threshold != null) params.renewal_threshold = thresholds.renewal_threshold;
    if (thresholds.review_threshold != null) params.review_threshold = thresholds.review_threshold;
    api.getWatchlist(params)
      .then(d => setData(d))
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchWatchlist(customThresholds);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ownerGroup, customThresholds]);

  // Sync draft values when settings panel opens or data loads
  useEffect(() => {
    if (data) {
      setDraftOcc(String(customThresholds.occ_threshold ?? data.thresholds.occupancy_pct));
      setDraftDelinq(String(customThresholds.delinq_threshold ?? data.thresholds.delinquent_total));
      setDraftRenewal(String(customThresholds.renewal_threshold ?? data.thresholds.renewal_rate_90d));
      setDraftReview(String(customThresholds.review_threshold ?? data.thresholds.google_rating));
    }
  }, [showSettings, data, customThresholds]);

  const handleSaveThresholds = () => {
    const next: Thresholds = {};
    const occ = parseFloat(draftOcc);
    const delinq = parseFloat(draftDelinq);
    const renewal = parseFloat(draftRenewal);
    const review = parseFloat(draftReview);
    if (!isNaN(occ)) next.occ_threshold = occ;
    if (!isNaN(delinq)) next.delinq_threshold = delinq;
    if (!isNaN(renewal)) next.renewal_threshold = renewal;
    if (!isNaN(review)) next.review_threshold = review;
    setCustomThresholds(next);
    saveThresholds(next);
    setShowSettings(false);
  };

  const handleResetThresholds = () => {
    setCustomThresholds({});
    saveThresholds({});
    setShowSettings(false);
  };

  const togglePin = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    const next = new Set(pinnedIds);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    setPinnedIds(next);
    savePinnedIds(next);
  };

  if (loading) {
    return (
      <div className="space-y-4 animate-pulse">
        <div className="h-8 bg-slate-200 rounded w-64" />
        <div className="h-48 bg-slate-100 rounded" />
      </div>
    );
  }

  if (!data) {
    return <div className="text-center py-12 text-slate-500">Failed to load watchlist data</div>;
  }

  // Filter by selected property IDs (when multiple are selected in portfolio)
  const groupFiltered = (propertyIds && propertyIds.length > 1)
    ? data.watchlist.filter(p => propertyIds.includes(p.id))
    : data.watchlist;

  const flaggedOnly = groupFiltered.filter(p => p.flag_count > 0 || pinnedIds.has(p.id));
  const displayed = showAll ? groupFiltered : flaggedOnly;
  const filtered = filterMetric === 'all'
    ? displayed
    : displayed.filter(p => p.flags.some(f => f.metric === filterMetric) || pinnedIds.has(p.id));

  // Count matches per metric (among flagged/pinned properties) for badge display
  const metricCounts: Record<string, number> = {
    all: flaggedOnly.length,
    occupancy: flaggedOnly.filter(p => p.flags.some(f => f.metric === 'occupancy')).length,
    delinquency: flaggedOnly.filter(p => p.flags.some(f => f.metric === 'delinquency')).length,
    renewal_rate: flaggedOnly.filter(p => p.flags.some(f => f.metric === 'renewal_rate')).length,
    review_rating: flaggedOnly.filter(p => p.flags.some(f => f.metric === 'review_rating')).length,
  };

  const flaggedCount = flaggedOnly.length;
  const totalCount = groupFiltered.length;

  return (
    <div className="space-y-6">
      {/* Summary Bar */}
      <div className="flex flex-wrap items-center gap-4">
        <div className="flex items-center gap-2">
          <AlertTriangle className={`w-5 h-5 ${flaggedCount > 0 ? 'text-red-500' : 'text-emerald-500'}`} />
          <span className="text-lg font-bold text-slate-800">
            {flaggedCount} of {totalCount} properties flagged
          </span>
          {ownerGroup && (
            <span className="text-xs text-slate-400 ml-1">({ownerGroup})</span>
          )}
        </div>

        {/* Metric filter */}
        <div className="flex items-center gap-2 ml-auto">
          <span className="text-xs text-slate-500">Filter:</span>
          {[
            { key: 'all', label: 'All' },
            { key: 'occupancy', label: 'Occupancy' },
            { key: 'delinquency', label: 'Delinquency' },
            { key: 'renewal_rate', label: 'Renewals' },
            { key: 'review_rating', label: 'Reviews' },
          ].map(f => {
            const count = metricCounts[f.key] || 0;
            return (
              <button
                key={f.key}
                onClick={() => setFilterMetric(f.key)}
                className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${
                  filterMetric === f.key
                    ? 'bg-indigo-600 text-white'
                    : count === 0
                    ? 'bg-slate-50 text-slate-300 cursor-default'
                    : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                }`}
                disabled={count === 0 && f.key !== 'all'}
              >
                {f.label}{f.key !== 'all' && count > 0 ? ` (${count})` : ''}
              </button>
            );
          })}
        </div>

        {/* Toggle show all */}
        <button
          onClick={() => setShowAll(s => !s)}
          className="flex items-center gap-1 px-3 py-1 rounded-full text-xs font-medium bg-slate-100 text-slate-600 hover:bg-slate-200 transition-colors"
        >
          <ChevronDown className={`w-3 h-3 transition-transform ${showAll ? 'rotate-180' : ''}`} />
          {showAll ? 'Flagged Only' : 'Show All'}
        </button>
      </div>

      {/* Threshold Legend + Settings */}
      <div className="relative flex flex-wrap items-center gap-3 text-xs text-slate-500">
        <span>Thresholds:</span>
        <span>Occ &lt; {data.thresholds.occupancy_pct}%</span>
        <span>Delinq &gt; ${data.thresholds.delinquent_total.toLocaleString()}</span>
        <span>Renewal &lt; {data.thresholds.renewal_rate_90d}%</span>
        <span>Rating &lt; {data.thresholds.google_rating}</span>
        {pinnedIds.size > 0 && <span className="text-indigo-500">📌 {pinnedIds.size} pinned</span>}
        {Object.keys(customThresholds).length > 0 && (
          <span className="text-violet-500 font-medium">Custom</span>
        )}
        <button
          onClick={() => setShowSettings(s => !s)}
          className={`p-1 rounded transition-colors ${showSettings ? 'bg-slate-200 text-slate-700' : 'hover:bg-slate-100 text-slate-400 hover:text-slate-600'}`}
          title="Edit thresholds"
        >
          <Settings className="w-3.5 h-3.5" />
        </button>

        {/* Settings Popover */}
        {showSettings && (
          <div ref={settingsRef} className="absolute top-full left-0 mt-2 z-40 bg-white rounded-lg border border-slate-200 shadow-lg p-4 w-80">
            <h4 className="text-sm font-semibold text-slate-800 mb-3">Watchlist Thresholds</h4>
            <div className="grid grid-cols-2 gap-3">
              <label className="block">
                <span className="text-[11px] text-slate-500 mb-1 block">Occupancy below (%)</span>
                <input
                  type="number"
                  step="1"
                  value={draftOcc}
                  onChange={e => setDraftOcc(e.target.value)}
                  className="w-full px-2 py-1.5 border border-slate-200 rounded text-xs focus:outline-none focus:ring-2 focus:ring-indigo-300"
                />
              </label>
              <label className="block">
                <span className="text-[11px] text-slate-500 mb-1 block">Delinquent above ($)</span>
                <input
                  type="number"
                  step="1000"
                  value={draftDelinq}
                  onChange={e => setDraftDelinq(e.target.value)}
                  className="w-full px-2 py-1.5 border border-slate-200 rounded text-xs focus:outline-none focus:ring-2 focus:ring-indigo-300"
                />
              </label>
              <label className="block">
                <span className="text-[11px] text-slate-500 mb-1 block">Renewal below (%)</span>
                <input
                  type="number"
                  step="1"
                  value={draftRenewal}
                  onChange={e => setDraftRenewal(e.target.value)}
                  className="w-full px-2 py-1.5 border border-slate-200 rounded text-xs focus:outline-none focus:ring-2 focus:ring-indigo-300"
                />
              </label>
              <label className="block">
                <span className="text-[11px] text-slate-500 mb-1 block">Rating below (★)</span>
                <input
                  type="number"
                  step="0.1"
                  min="0"
                  max="5"
                  value={draftReview}
                  onChange={e => setDraftReview(e.target.value)}
                  className="w-full px-2 py-1.5 border border-slate-200 rounded text-xs focus:outline-none focus:ring-2 focus:ring-indigo-300"
                />
              </label>
            </div>
            <div className="flex items-center gap-2 mt-3 pt-3 border-t border-slate-100">
              <button
                onClick={handleSaveThresholds}
                className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-medium bg-indigo-600 text-white hover:bg-indigo-700 transition-colors"
              >
                <Check className="w-3 h-3" /> Save
              </button>
              <button
                onClick={handleResetThresholds}
                className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-medium bg-slate-100 text-slate-600 hover:bg-slate-200 transition-colors"
              >
                <RotateCcw className="w-3 h-3" /> Reset to Defaults
              </button>
              <button
                onClick={() => setShowSettings(false)}
                className="ml-auto px-3 py-1.5 rounded-lg text-xs font-medium text-slate-400 hover:text-slate-600 transition-colors"
              >
                Cancel
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Property Table */}
      {filtered.length === 0 ? (
        <div className="text-center py-12 text-slate-500">
          {showAll ? 'No properties match this filter' : 'No properties flagged — all metrics within thresholds'}
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-left text-xs font-medium text-slate-500 uppercase">
                <th className="pb-2 pr-1 w-8"></th>
                <th className="pb-2 pr-4">Property</th>
                <th className="pb-2 pr-4 text-right">Units</th>
                <th className="pb-2 pr-4 text-right">Occ%</th>
                <th className="pb-2 pr-4 text-right">Vacant</th>
                <th className="pb-2 pr-4 text-right">Delinquent</th>
                <th className="pb-2 pr-4 text-right">Renewal%</th>
                <th className="pb-2 pr-4 text-right">Rating</th>
                <th className="pb-2 pr-4 text-right">At-Risk</th>
                <th className="pb-2">Flags</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map(prop => {
                const isPinned = pinnedIds.has(prop.id);
                return (
                  <tr
                    key={prop.id}
                    className={`border-b border-slate-100 hover:bg-slate-50 ${prop.flag_count > 0 || isPinned ? '' : 'opacity-60'} ${onPropertyClick ? 'cursor-pointer' : ''}`}
                    onClick={() => onPropertyClick?.(prop.id)}
                  >
                    <td className="py-3 pr-1">
                      <button
                        onClick={(e) => togglePin(prop.id, e)}
                        className={`w-6 h-6 rounded-full flex items-center justify-center transition-colors ${
                          isPinned
                            ? 'bg-indigo-100 text-indigo-600 hover:bg-indigo-200'
                            : 'bg-transparent text-slate-300 hover:text-slate-500 hover:bg-slate-100'
                        }`}
                        title={isPinned ? 'Unpin from watchlist' : 'Pin to watchlist'}
                      >
                        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" className="w-3.5 h-3.5">
                          <path d="M10.97 2.22a.75.75 0 0 1 1.06 0l1.75 1.75a.75.75 0 0 1 0 1.06l-1.19 1.19 .47.47a.75.75 0 0 1-.53 1.28H9.81l-2.03 2.03 .22 2.19a.75.75 0 0 1-1.28.53L5 10.97l-2.72 2.72a.75.75 0 1 1-1.06-1.06L3.94 9.9l-.22-.22a.75.75 0 0 1 .53-1.28l2.19.22L8.47 6.6V3.87a.75.75 0 0 1 1.28-.53l.47.47 1.19-1.19Z" />
                        </svg>
                      </button>
                    </td>
                    <td className="py-3 pr-4">
                      <div className="flex items-center gap-2">
                        <Building2 className="w-4 h-4 text-slate-400" />
                        <div>
                          <div className="font-medium text-slate-800">{prop.name}</div>
                          <div className="text-xs text-slate-400">{prop.owner_group}</div>
                        </div>
                      </div>
                    </td>
                    <td className="py-3 pr-4 text-right text-slate-700">{prop.total_units}</td>
                    <td className={`py-3 pr-4 text-right font-medium ${prop.occupancy_pct < data.thresholds.occupancy_pct && prop.occupancy_pct > 0 ? 'text-red-600' : 'text-slate-700'}`}>
                      {prop.occupancy_pct > 0 ? `${prop.occupancy_pct.toFixed(1)}%` : '—'}
                    </td>
                    <td className="py-3 pr-4 text-right text-slate-700">{prop.vacant}</td>
                    <td className={`py-3 pr-4 text-right font-medium ${prop.delinquent_total > data.thresholds.delinquent_total ? 'text-amber-700' : 'text-slate-700'}`}>
                      {prop.delinquent_total > 0 ? `$${prop.delinquent_total.toLocaleString(undefined, { maximumFractionDigits: 0 })}` : '—'}
                    </td>
                    <td className={`py-3 pr-4 text-right font-medium ${prop.renewal_rate_90d != null && prop.renewal_rate_90d < data.thresholds.renewal_rate_90d ? 'text-orange-600' : 'text-slate-700'}`}>
                      {prop.renewal_rate_90d != null ? `${prop.renewal_rate_90d}%` : '—'}
                    </td>
                    <td className={`py-3 pr-4 text-right font-medium ${prop.google_rating != null && prop.google_rating < data.thresholds.google_rating ? 'text-purple-600' : 'text-slate-700'}`}>
                      {prop.google_rating != null ? prop.google_rating.toFixed(1) : '—'}
                    </td>
                    <td className="py-3 pr-4 text-right">
                      {prop.at_risk_residents > 0 ? (
                        <span className="text-red-600 font-medium">{prop.at_risk_residents}</span>
                      ) : '—'}
                    </td>
                    <td className="py-3">
                      <div className="flex flex-wrap gap-1">
                        {isPinned && prop.flag_count === 0 && (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium border text-indigo-600 bg-indigo-50 border-indigo-200">
                            Pinned
                          </span>
                        )}
                        {prop.flags.map((flag, i) => (
                          <FlagBadge key={i} flag={flag} />
                        ))}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
