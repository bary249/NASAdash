/**
 * Availability Section - ATR, availability buckets, and 7-week trend
 * Per PHH design partner feedback.
 */
import { useState, useEffect } from 'react';
import { Home, TrendingUp, TrendingDown, Minus, AlertTriangle } from 'lucide-react';
import { SectionHeader } from './SectionHeader';
import { api } from '../api';

interface AvailabilityData {
  property_id: string;
  total_units: number;
  occupied: number;
  vacant: number;
  on_notice: number;
  preleased: number;
  atr: number;
  atr_pct: number;
  availability_pct: number;
  buckets: {
    available_0_30: number;
    available_30_60: number;
    available_60_plus: number;
    total: number;
  };
  trend: {
    direction: string;
    weeks: {
      week_ending: string;
      atr: number;
      atr_pct: number;
      occupancy_pct: number;
      move_ins: number;
      move_outs: number;
    }[];
  };
  prior_month?: {
    atr: number;
    atr_pct: number;
    snapshot_date: string;
  } | null;
}

interface Props {
  propertyId: string;
  propertyIds?: string[];
  onDrillThrough?: (type: string, param?: string) => void;
}

function TrendIcon({ direction }: { direction: string }) {
  if (direction === 'increasing') return <TrendingUp className="w-4 h-4 text-red-500" />;
  if (direction === 'decreasing') return <TrendingDown className="w-4 h-4 text-emerald-500" />;
  return <Minus className="w-4 h-4 text-slate-400" />;
}

function TrendLabel({ direction }: { direction: string }) {
  if (direction === 'increasing') return <span className="text-xs text-red-600 font-medium">ATR Increasing ↑</span>;
  if (direction === 'decreasing') return <span className="text-xs text-emerald-600 font-medium">ATR Decreasing ↓</span>;
  return <span className="text-xs text-slate-500">ATR Stable</span>;
}

export function AvailabilitySection({ propertyId, propertyIds, onDrillThrough }: Props) {
  const [data, setData] = useState<AvailabilityData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [trendSortNewest, setTrendSortNewest] = useState(true);
  const effectiveIds = propertyIds && propertyIds.length > 0 ? propertyIds : [propertyId];

  useEffect(() => {
    setData(null);
    setError(null);
    setLoading(true);

    const fetchData = async () => {
      try {
        const results = await Promise.all(
          effectiveIds.map(id => api.getAvailability(id).catch(() => null))
        );
        const valid = results.filter(Boolean) as AvailabilityData[];
        if (valid.length === 0) { setData(null); return; }
        if (valid.length === 1) { setData(valid[0]); return; }

        // Merge multiple properties
        const merged: AvailabilityData = {
          property_id: `${valid.length} Properties`,
          total_units: valid.reduce((s, r) => s + r.total_units, 0),
          occupied: valid.reduce((s, r) => s + r.occupied, 0),
          vacant: valid.reduce((s, r) => s + r.vacant, 0),
          on_notice: valid.reduce((s, r) => s + r.on_notice, 0),
          preleased: valid.reduce((s, r) => s + r.preleased, 0),
          atr: valid.reduce((s, r) => s + r.atr, 0),
          atr_pct: 0,
          availability_pct: 0,
          buckets: {
            available_0_30: valid.reduce((s, r) => s + r.buckets.available_0_30, 0),
            available_30_60: valid.reduce((s, r) => s + r.buckets.available_30_60, 0),
            available_60_plus: valid.reduce((s, r) => s + (r.buckets.available_60_plus || 0), 0),
            total: valid.reduce((s, r) => s + r.buckets.total, 0),
          },
          trend: valid[0].trend, // Use first property's trend for portfolio
        };
        // Aggregate prior_month across all properties
        const priorProps = valid.filter(r => r.prior_month);
        if (priorProps.length > 0) {
          merged.prior_month = {
            atr: priorProps.reduce((s, r) => s + (r.prior_month?.atr || 0), 0),
            atr_pct: 0,
            snapshot_date: priorProps[0].prior_month!.snapshot_date,
          };
          merged.prior_month.atr_pct = merged.total_units > 0
            ? Math.round(merged.prior_month.atr / merged.total_units * 1000) / 10 : 0;
        }
        merged.atr_pct = merged.total_units > 0 ? Math.round(merged.atr / merged.total_units * 1000) / 10 : 0;
        merged.availability_pct = merged.atr_pct;
        setData(merged);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load');
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [effectiveIds.join(',')]);

  if (loading) {
    return (
      <div className="venn-section animate-pulse">
        <div className="h-8 bg-slate-200 rounded w-48 mb-4" />
        <div className="h-32 bg-slate-100 rounded" />
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="venn-section">
        <SectionHeader title="Availability & ATR" icon={Home} />
        <div className="text-center py-8 text-slate-500">
          {error || 'No availability data available'}
        </div>
      </div>
    );
  }

  const weeks = data?.trend?.weeks || [];
  const trendWeeks = trendSortNewest ? [...weeks].reverse() : [...weeks];
  const maxAtr = Math.max(...trendWeeks.map(w => w.atr), data?.atr || 0, 1);

  return (
    <div className="venn-section">
      <SectionHeader
        title="Availability & ATR"
        icon={Home}
        description="Actual-To-Rent = Vacant + On Notice − Pre-leased"
      />

      {/* ATR Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-6">
        <button onClick={() => onDrillThrough?.('atr')} className="bg-blue-50 border border-blue-100 rounded-xl p-4 text-left hover:border-blue-300 transition-colors cursor-pointer">
          <div className="text-xs font-medium text-blue-600 uppercase mb-1">ATR</div>
          <div className="text-2xl font-bold text-blue-700">{data.atr}</div>
          <div className="text-xs text-blue-500">{data.atr_pct}% of {data.total_units} units</div>
          {data.prior_month && (() => {
            const delta = data.atr - data.prior_month.atr;
            if (delta === 0) return <div className="text-[10px] text-slate-400 mt-1">No change vs prior month</div>;
            return (
              <div className={`text-[10px] mt-1 font-medium ${delta > 0 ? 'text-rose-500' : 'text-emerald-600'}`}>
                {delta > 0 ? '▲' : '▼'} {Math.abs(delta)} units vs prior mo ({data.prior_month.atr})
              </div>
            );
          })()}
        </button>

        <button onClick={() => onDrillThrough?.('availability_status', 'vacant')} className="bg-slate-50 border border-slate-100 rounded-xl p-4 text-left hover:border-slate-300 transition-colors cursor-pointer">
          <div className="text-xs font-medium text-slate-600 uppercase mb-1">Vacant</div>
          <div className="text-2xl font-bold text-slate-700">{data.vacant}</div>
          <div className="text-xs text-slate-500">units</div>
        </button>

        <button onClick={() => onDrillThrough?.('availability_status', 'notice')} className="bg-amber-50 border border-amber-100 rounded-xl p-4 text-left hover:border-amber-300 transition-colors cursor-pointer">
          <div className="text-xs font-medium text-amber-600 uppercase mb-1">On Notice</div>
          <div className="text-2xl font-bold text-amber-700">{data.on_notice}</div>
          <div className="text-xs text-amber-500">units</div>
        </button>

        <button onClick={() => onDrillThrough?.('availability_status', 'preleased')} className="bg-green-50 border border-green-100 rounded-xl p-4 text-left hover:border-green-300 transition-colors cursor-pointer">
          <div className="text-xs font-medium text-green-600 uppercase mb-1">Pre-leased</div>
          <div className="text-2xl font-bold text-green-700">{data.preleased}</div>
          <div className="text-xs text-green-500">units</div>
        </button>

        <div className="bg-slate-50 border border-slate-100 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-1">
            <TrendIcon direction={data.trend.direction} />
            <span className="text-xs font-medium text-slate-600 uppercase">Trend</span>
          </div>
          <TrendLabel direction={data.trend.direction} />
        </div>
      </div>

      {/* Availability Buckets */}
      <div className="grid md:grid-cols-2 gap-6 mb-6">
        <div className="bg-slate-50 rounded-xl p-4">
          <h4 className="text-sm font-semibold text-slate-700 mb-4">Availability Buckets</h4>
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-sm text-slate-600">0–30 Days</span>
              <span className="text-sm font-semibold text-slate-800">{data.buckets.available_0_30} units</span>
            </div>
            <div className="h-3 bg-slate-200 rounded-full overflow-hidden">
              <div
                className="h-full bg-blue-400 rounded-full transition-all duration-500"
                style={{ width: `${data.total_units > 0 ? (data.buckets.available_0_30 / data.total_units * 100) : 0}%` }}
              />
            </div>
            <div className="flex items-center justify-between mt-2">
              <span className="text-sm text-slate-600">30–60 Days</span>
              <span className="text-sm font-semibold text-slate-800">{data.buckets.available_30_60} units</span>
            </div>
            <div className="h-3 bg-slate-200 rounded-full overflow-hidden">
              <div
                className="h-full bg-orange-400 rounded-full transition-all duration-500"
                style={{ width: `${data.total_units > 0 ? (data.buckets.available_30_60 / data.total_units * 100) : 0}%` }}
              />
            </div>
            <div className="flex items-center justify-between mt-2">
              <span className="text-sm text-slate-600">60+ Days</span>
              <span className="text-sm font-semibold text-slate-800">{data.buckets.available_60_plus || 0} units</span>
            </div>
            <div className="h-3 bg-slate-200 rounded-full overflow-hidden">
              <div
                className="h-full bg-red-400 rounded-full transition-all duration-500"
                style={{ width: `${data.total_units > 0 ? ((data.buckets.available_60_plus || 0) / data.total_units * 100) : 0}%` }}
              />
            </div>
            <div className="flex items-center justify-between pt-2 border-t border-slate-200 mt-2">
              <span className="text-sm font-semibold text-slate-700">Total Availability</span>
              <span className="text-sm font-bold text-blue-700">{data.availability_pct}%</span>
            </div>
          </div>
        </div>

        {/* 7-Week ATR Trend */}
        <div className="bg-slate-50 rounded-xl p-4">
          <div className="flex items-center justify-between mb-4">
            <h4 className="text-sm font-semibold text-slate-700">7-Week ATR Trend</h4>
            <div className="flex items-center gap-3">
              <TrendLabel direction={data.trend.direction} />
              <button
                onClick={() => setTrendSortNewest(prev => !prev)}
                className="text-[10px] px-2 py-0.5 rounded border border-slate-300 text-slate-500 hover:bg-white hover:text-slate-700 transition-colors"
              >
                {trendSortNewest ? 'Newest ↓' : 'Oldest ↓'}
              </button>
            </div>
          </div>
          {trendWeeks.length > 0 ? (
            <div className="space-y-2">
              {trendWeeks.map((week, idx) => (
                <div key={idx} className="flex items-center gap-3">
                  <span className="text-xs text-slate-500 w-20 shrink-0">{week.week_ending}</span>
                  <div className="flex-1 h-4 bg-slate-200 rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all duration-500 ${
                        week.atr_pct > data.atr_pct + 2 ? 'bg-red-400' :
                        week.atr_pct < data.atr_pct - 2 ? 'bg-emerald-400' : 'bg-blue-400'
                      }`}
                      style={{ width: `${maxAtr > 0 ? (week.atr / maxAtr * 100) : 0}%` }}
                    />
                  </div>
                  <span className="text-xs font-medium text-slate-700 w-12 text-right">{week.atr} units</span>
                </div>
              ))}
            </div>
          ) : (
            <div className="flex items-center justify-center h-32 text-slate-400 text-sm">
              <AlertTriangle className="w-4 h-4 mr-2" />
              No projected occupancy data available
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
