import { useState, useEffect } from 'react';
import { BarChart3, ChevronDown, ChevronRight, Info } from 'lucide-react';
import { api } from '../api';

interface StatusRow {
  label: string;
  count: number;
  pct: number;
}

interface Subtotal {
  label: string;
  count: number;
  pct: number;
  breakdown?: string;
  description?: string;
  formula?: string;
}

interface BreakdownData {
  property_id: string;
  total_units: number;
  statuses: StatusRow[];
  subtotals: {
    vacant: Subtotal;
    ready: Subtotal;
    not_ready: Subtotal;
    notice: Subtotal;
    preleased: Subtotal;
    atr: Subtotal;
  };
}

const STATUS_COLORS: Record<string, string> = {
  'Occupied': 'bg-emerald-500',
  'Vacant - Unrented': 'bg-red-400',
  'Vacant - Leased': 'bg-amber-400',
  'Notice - Unrented': 'bg-orange-400',
  'Notice - Rented': 'bg-yellow-400',
  'Model': 'bg-blue-400',
  'Admin/Down': 'bg-slate-400',
};

const STATUS_TEXT_COLORS: Record<string, string> = {
  'Occupied': 'text-emerald-700',
  'Vacant - Unrented': 'text-red-600',
  'Vacant - Leased': 'text-amber-600',
  'Notice - Unrented': 'text-orange-600',
  'Notice - Rented': 'text-yellow-600',
  'Model': 'text-blue-600',
  'Admin/Down': 'text-slate-500',
};

const STATUS_DRILL_MAP: Record<string, string> = {
  'Occupied': 'breakdown_occupied',
  'Vacant - Unrented': 'breakdown_vacant_unrented',
  'Vacant - Leased': 'breakdown_vacant_leased',
  'Notice - Unrented': 'breakdown_notice_unrented',
  'Notice - Rented': 'breakdown_notice_rented',
  'Model': 'breakdown_model',
  'Admin/Down': 'breakdown_down',
};

interface Props {
  propertyId: string;
  propertyIds?: string[];
  onDrillThrough?: (type: string, param?: string) => void;
}

export function UnitStatusBreakdown({ propertyId, propertyIds, onDrillThrough }: Props) {
  const [data, setData] = useState<BreakdownData | null>(null);
  const [loading, setLoading] = useState(true);
  const [collapsed, setCollapsed] = useState(false);

  useEffect(() => {
    if (!propertyId && (!propertyIds || propertyIds.length === 0)) return;
    setLoading(true);

    const ids = propertyIds && propertyIds.length > 0 ? propertyIds : [propertyId];

    Promise.all(ids.map(id => api.getUnitStatusBreakdown(id).catch(() => null)))
      .then(results => {
        const valid = results.filter(Boolean) as BreakdownData[];
        if (valid.length === 0) {
          setData(null);
          return;
        }

        if (valid.length === 1) {
          setData(valid[0]);
          return;
        }

        // Merge multiple properties
        const merged: BreakdownData = {
          property_id: 'portfolio',
          total_units: 0,
          statuses: [],
          subtotals: {
            vacant: { label: 'Total Vacant (incl. Leased)', count: 0, pct: 0 },
            ready: { label: 'Vacant & Ready', count: 0, pct: 0 },
            not_ready: { label: 'Vacant Not Ready', count: 0, pct: 0 },
            notice: { label: 'Total On Notice', count: 0, pct: 0 },
            preleased: { label: 'Pre-leased', count: 0, pct: 0 },
            atr: { label: 'Available to Rent (ATR)', count: 0, pct: 0 },
          },
        };

        const statusMap: Record<string, { count: number }> = {};

        for (const v of valid) {
          merged.total_units += v.total_units;
          for (const s of v.statuses) {
            if (!statusMap[s.label]) statusMap[s.label] = { count: 0 };
            statusMap[s.label].count += s.count;
          }
          merged.subtotals.vacant.count += v.subtotals.vacant.count;
          merged.subtotals.ready.count += v.subtotals.ready.count;
          merged.subtotals.not_ready.count += (v.subtotals.not_ready?.count || 0);
          merged.subtotals.notice.count += v.subtotals.notice.count;
          merged.subtotals.preleased.count += (v.subtotals.preleased?.count || 0);
          merged.subtotals.atr.count += v.subtotals.atr.count;
        }

        const total = merged.total_units;
        merged.statuses = Object.entries(statusMap).map(([label, { count }]) => ({
          label,
          count,
          pct: total > 0 ? Math.round(count / total * 1000) / 10 : 0,
        }));
        merged.subtotals.vacant.pct = total > 0 ? Math.round(merged.subtotals.vacant.count / total * 1000) / 10 : 0;
        merged.subtotals.ready.pct = total > 0 ? Math.round(merged.subtotals.ready.count / total * 1000) / 10 : 0;
        merged.subtotals.not_ready.pct = total > 0 ? Math.round(merged.subtotals.not_ready.count / total * 1000) / 10 : 0;
        merged.subtotals.notice.pct = total > 0 ? Math.round(merged.subtotals.notice.count / total * 1000) / 10 : 0;
        merged.subtotals.preleased.pct = total > 0 ? Math.round(merged.subtotals.preleased.count / total * 1000) / 10 : 0;
        merged.subtotals.atr.pct = total > 0 ? Math.round(merged.subtotals.atr.count / total * 1000) / 10 : 0;

        setData(merged);
      })
      .finally(() => setLoading(false));
  }, [propertyId, propertyIds]);

  if (loading) {
    return (
      <div className="bg-white rounded-xl border border-slate-200 p-6 mt-6 animate-pulse">
        <div className="h-6 bg-slate-200 rounded w-48 mb-4" />
        <div className="h-40 bg-slate-100 rounded" />
      </div>
    );
  }

  if (!data) return null;

  const { statuses, subtotals, total_units } = data;

  return (
    <div className="bg-white rounded-xl border border-slate-200 mt-6 overflow-hidden">
      {/* Header */}
      <button
        className="w-full flex items-center justify-between px-6 py-4 hover:bg-slate-50 transition-colors"
        onClick={() => setCollapsed(c => !c)}
      >
        <div className="flex items-center gap-2">
          <BarChart3 className="w-5 h-5 text-indigo-600" />
          <h3 className="text-base font-semibold text-slate-800">Unit Status Breakdown</h3>
          <span className="text-sm text-slate-400 ml-2">{total_units} units</span>
        </div>
        {collapsed ? <ChevronRight className="w-5 h-5 text-slate-400" /> : <ChevronDown className="w-5 h-5 text-slate-400" />}
      </button>

      {!collapsed && (
        <div className="px-6 pb-6">
          {/* Stacked bar visualization */}
          <div className="h-8 flex rounded-lg overflow-hidden mb-6">
            {statuses.filter(s => s.count > 0).map(s => (
              <div
                key={s.label}
                className={`${STATUS_COLORS[s.label] || 'bg-slate-300'} relative group transition-all`}
                style={{ width: `${s.pct}%`, minWidth: s.count > 0 ? '2px' : '0' }}
              >
                <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-2 py-1 bg-slate-800 text-white text-xs rounded whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-10">
                  {s.label}: {s.count} ({s.pct}%)
                </div>
              </div>
            ))}
          </div>

          {/* Status table */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Left: Individual statuses */}
            <div>
              <h4 className="text-xs font-medium text-slate-500 uppercase mb-3">Status Detail</h4>
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-200 text-xs text-slate-500 uppercase">
                    <th className="text-left py-2 pr-4">Status</th>
                    <th className="text-right py-2 px-3">Units</th>
                    <th className="text-right py-2 px-3">%</th>
                    <th className="py-2 pl-3 w-32"></th>
                  </tr>
                </thead>
                <tbody>
                  {statuses.map(s => {
                    const drillKey = STATUS_DRILL_MAP[s.label];
                    return (
                      <tr
                        key={s.label}
                        className={`border-b border-slate-100 ${drillKey && onDrillThrough ? 'cursor-pointer hover:bg-slate-50' : ''}`}
                        onClick={() => drillKey && onDrillThrough?.(drillKey)}
                      >
                        <td className="py-2.5 pr-4">
                          <div className="flex items-center gap-2">
                            <div className={`w-2.5 h-2.5 rounded-full ${STATUS_COLORS[s.label] || 'bg-slate-300'}`} />
                            <span className={`font-medium ${STATUS_TEXT_COLORS[s.label] || 'text-slate-600'}`}>{s.label}</span>
                          </div>
                        </td>
                        <td className="text-right py-2.5 px-3 font-semibold text-slate-700">{s.count}</td>
                        <td className="text-right py-2.5 px-3 text-slate-500">{s.pct}%</td>
                        <td className="py-2.5 pl-3">
                          <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
                            <div className={`h-full rounded-full ${STATUS_COLORS[s.label] || 'bg-slate-300'}`} style={{ width: `${s.pct}%` }} />
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                  {/* Total row */}
                  <tr className="border-t-2 border-slate-300 font-semibold">
                    <td className="py-2.5 pr-4 text-slate-800">Total</td>
                    <td className="text-right py-2.5 px-3 text-slate-800">{total_units}</td>
                    <td className="text-right py-2.5 px-3 text-slate-500">100%</td>
                    <td />
                  </tr>
                </tbody>
              </table>
            </div>

            {/* Right: Subtotals / KPI cards */}
            <div>
              <h4 className="text-xs font-medium text-slate-500 uppercase mb-3">Key Subtotals</h4>
              <div className="space-y-3">
                {/* Vacant subtotal */}
                <SubtotalCard
                  label={subtotals.vacant.label}
                  count={subtotals.vacant.count}
                  pct={subtotals.vacant.pct}
                  detail={subtotals.vacant.breakdown}
                  color="bg-red-50 border-red-200"
                  textColor="text-red-700"
                  onClick={() => onDrillThrough?.('breakdown_vacant')}
                />

                {/* Ready subtotal */}
                <SubtotalCard
                  label={subtotals.ready.label}
                  count={subtotals.ready.count}
                  pct={subtotals.ready.pct}
                  detail={subtotals.ready.description}
                  color="bg-emerald-50 border-emerald-200"
                  textColor="text-emerald-700"
                  onClick={() => onDrillThrough?.('breakdown_ready')}
                />

                {/* Vacant Not Ready subtotal */}
                {subtotals.not_ready && (
                  <SubtotalCard
                    label={subtotals.not_ready.label}
                    count={subtotals.not_ready.count}
                    pct={subtotals.not_ready.pct}
                    detail={subtotals.not_ready.description}
                    color="bg-amber-50 border-amber-200"
                    textColor="text-amber-700"
                    onClick={() => onDrillThrough?.('breakdown_not_ready')}
                  />
                )}

                {/* Notice subtotal */}
                <SubtotalCard
                  label={subtotals.notice.label}
                  count={subtotals.notice.count}
                  pct={subtotals.notice.pct}
                  detail={subtotals.notice.breakdown}
                  color="bg-orange-50 border-orange-200"
                  textColor="text-orange-700"
                  onClick={() => onDrillThrough?.('breakdown_notice')}
                />

                {/* Preleased subtotal */}
                {subtotals.preleased && (
                  <SubtotalCard
                    label={subtotals.preleased.label}
                    count={subtotals.preleased.count}
                    pct={subtotals.preleased.pct}
                    detail={subtotals.preleased.breakdown}
                    color="bg-green-50 border-green-200"
                    textColor="text-green-700"
                    onClick={() => onDrillThrough?.('breakdown_preleased')}
                  />
                )}

                {/* ATR subtotal */}
                <SubtotalCard
                  label={subtotals.atr.label}
                  count={subtotals.atr.count}
                  pct={subtotals.atr.pct}
                  detail={subtotals.atr.formula}
                  color="bg-indigo-50 border-indigo-200"
                  textColor="text-indigo-700"
                  highlight
                  onClick={() => onDrillThrough?.('breakdown_atr')}
                />
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function SubtotalCard({ label, count, pct, detail, color, textColor, highlight, onClick }: {
  label: string;
  count: number;
  pct: number;
  detail?: string;
  color: string;
  textColor: string;
  highlight?: boolean;
  onClick?: () => void;
}) {
  return (
    <div
      className={`rounded-lg border px-4 py-3 ${color} ${highlight ? 'ring-1 ring-indigo-300' : ''} ${onClick ? 'cursor-pointer hover:shadow-md transition-shadow' : ''}`}
      onClick={onClick}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className={`text-sm font-semibold ${textColor}`}>{label}</span>
          {detail && (
            <div className="relative group">
              <Info className="w-3.5 h-3.5 text-slate-400 cursor-help" />
              <div className="absolute bottom-full left-0 mb-1 px-2 py-1 bg-slate-800 text-white text-xs rounded whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-10 max-w-xs">
                {detail}
              </div>
            </div>
          )}
        </div>
        <div className="flex items-center gap-3">
          <span className={`text-lg font-bold ${textColor}`}>{count}</span>
          <span className="text-sm text-slate-500">({pct}%)</span>
        </div>
      </div>
    </div>
  );
}
