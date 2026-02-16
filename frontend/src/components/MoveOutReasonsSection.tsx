/**
 * MoveOutReasonsSection - Reasons for Move Out (Report 3879)
 * Shows category/reason breakdown for former residents and residents on notice.
 * Placed at the bottom of the Renewals tab.
 */
import { useState, useEffect } from 'react';
import { LogOut, ChevronDown, ChevronUp, Users, AlertTriangle } from 'lucide-react';
import { SectionHeader } from './SectionHeader';
import { api } from '../api';

interface Reason {
  reason: string;
  count: number;
  pct: number;
}

interface Category {
  category: string;
  count: number;
  pct: number;
  reasons: Reason[];
}

interface MoveOutData {
  property_id: string;
  date_range: string;
  former: Category[];
  notice: Category[];
  totals: { former: number; notice: number; total: number };
}

interface Props {
  propertyId: string;
  propertyIds?: string[];
}

const CATEGORY_COLORS: Record<string, string> = {
  'Lifestyle change': 'bg-sky-500',
  'Forced move (eviction)': 'bg-rose-500',
  'Transfer': 'bg-amber-500',
  'Dissatisfied': 'bg-orange-500',
  'Skip / eviction': 'bg-red-700',
  'Other': 'bg-slate-400',
};

function getCategoryColor(cat: string): string {
  return CATEGORY_COLORS[cat] || 'bg-indigo-500';
}

function CategoryBar({ categories, total }: { categories: Category[]; total: number }) {
  if (total === 0) return null;
  return (
    <div className="flex h-3 rounded-full overflow-hidden gap-0.5">
      {categories.map((cat, i) => (
        <div
          key={i}
          className={`${getCategoryColor(cat.category)} transition-all duration-300`}
          style={{ width: `${Math.max((cat.count / total) * 100, 2)}%` }}
          title={`${cat.category}: ${cat.count} (${cat.pct}%)`}
        />
      ))}
    </div>
  );
}

function CategoryCard({ cat, total, defaultOpen = false }: { cat: Category; total: number; defaultOpen?: boolean }) {
  const [open, setOpen] = useState(defaultOpen);
  const barColor = getCategoryColor(cat.category);

  return (
    <div className="border border-slate-100 rounded-lg overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-4 py-3 hover:bg-slate-50 transition-colors"
      >
        <div className="flex items-center gap-3">
          <div className={`w-3 h-3 rounded-full ${barColor}`} />
          <span className="text-sm font-medium text-slate-700">{cat.category}</span>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-sm font-bold text-slate-800 tabular-nums">{cat.count}</span>
          <span className="text-xs text-slate-400 tabular-nums w-12 text-right">{cat.pct}%</span>
          {open ? <ChevronUp size={14} className="text-slate-400" /> : <ChevronDown size={14} className="text-slate-400" />}
        </div>
      </button>
      {open && cat.reasons.length > 0 && (
        <div className="border-t border-slate-100 px-4 py-2 space-y-1.5">
          {cat.reasons.map((r, i) => (
            <div key={i} className="flex items-center justify-between">
              <div className="flex items-center gap-2 flex-1 min-w-0">
                <div className="w-full max-w-[200px] bg-slate-100 rounded-full h-1.5 overflow-hidden">
                  <div
                    className={`h-full rounded-full ${barColor} opacity-60`}
                    style={{ width: `${Math.max((r.count / total) * 100, 3)}%` }}
                  />
                </div>
                <span className="text-xs text-slate-600 truncate">{r.reason}</span>
              </div>
              <div className="flex items-center gap-2 shrink-0 ml-2">
                <span className="text-xs font-semibold text-slate-700 tabular-nums">{r.count}</span>
                <span className="text-[10px] text-slate-400 tabular-nums w-10 text-right">{r.pct}%</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function MoveOutReasonsSection({ propertyId, propertyIds }: Props) {
  const [data, setData] = useState<MoveOutData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'former' | 'notice'>('former');

  const effectiveIds = propertyIds && propertyIds.length > 0 ? propertyIds : [propertyId];

  useEffect(() => {
    if (!effectiveIds.length || !effectiveIds[0]) {
      setLoading(false);
      setError('No property selected');
      return;
    }
    setLoading(true);
    setError(null);
    setData(null);

    const fetchAll = async () => {
      try {
        const results = await Promise.all(
          effectiveIds.map(id => api.getMoveOutReasons(id).catch(() => null))
        );
        const valid = results.filter(Boolean) as MoveOutData[];
        if (valid.length === 0) {
          setError('No move-out reasons data available');
          return;
        }
        if (valid.length === 1) {
          setData(valid[0]);
          return;
        }
        // Merge multi-property data
        const mergeCategories = (arrays: Category[][]): Category[] => {
          const catMap = new Map<string, { count: number; pct: number; reasonMap: Map<string, number> }>();
          let grandTotal = 0;
          for (const cats of arrays) {
            for (const c of cats) {
              grandTotal += c.count;
              const existing = catMap.get(c.category);
              if (existing) {
                existing.count += c.count;
                for (const r of c.reasons) {
                  existing.reasonMap.set(r.reason, (existing.reasonMap.get(r.reason) || 0) + r.count);
                }
              } else {
                const rm = new Map<string, number>();
                for (const r of c.reasons) rm.set(r.reason, r.count);
                catMap.set(c.category, { count: c.count, pct: 0, reasonMap: rm });
              }
            }
          }
          return Array.from(catMap.entries())
            .map(([category, v]) => ({
              category,
              count: v.count,
              pct: grandTotal > 0 ? Math.round((v.count / grandTotal) * 10000) / 100 : 0,
              reasons: Array.from(v.reasonMap.entries())
                .map(([reason, count]) => ({
                  reason,
                  count,
                  pct: grandTotal > 0 ? Math.round((count / grandTotal) * 10000) / 100 : 0,
                }))
                .sort((a, b) => b.count - a.count),
            }))
            .sort((a, b) => b.count - a.count);
        };

        const merged: MoveOutData = {
          property_id: 'consolidated',
          date_range: valid[0].date_range,
          former: mergeCategories(valid.map(d => d.former)),
          notice: mergeCategories(valid.map(d => d.notice)),
          totals: {
            former: valid.reduce((a, d) => a + d.totals.former, 0),
            notice: valid.reduce((a, d) => a + d.totals.notice, 0),
            total: valid.reduce((a, d) => a + d.totals.total, 0),
          },
        };
        setData(merged);
      } catch (err: any) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };
    fetchAll();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [effectiveIds.join(',')]);

  if (loading) {
    return (
      <div className="space-y-4">
        <SectionHeader title="Move-Out Reasons" icon={LogOut} />
        <div className="flex items-center justify-center py-12 text-slate-400 text-sm">
          <div className="animate-spin mr-2 h-4 w-4 border-2 border-slate-300 border-t-transparent rounded-full" />
          Loading move-out data...
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="space-y-4">
        <SectionHeader title="Move-Out Reasons" icon={LogOut} />
        <div className="bg-white border border-slate-200 rounded-xl p-6 text-center text-slate-400 text-sm">
          {error?.includes('404') ? 'No move-out reasons data available for this property yet.' : `Failed to load: ${error}`}
        </div>
      </div>
    );
  }

  const categories = activeTab === 'former' ? data.former : data.notice;
  const total = activeTab === 'former' ? data.totals.former : data.totals.notice;

  return (
    <div className="space-y-4">
      <SectionHeader
        title="Move-Out Reasons"
        icon={LogOut}
        subtitle={data.date_range || undefined}
      />

      {/* Summary KPIs */}
      <div className="grid grid-cols-3 gap-3">
        <div className="bg-white border border-slate-200 rounded-xl p-4">
          <div className="text-[10px] text-slate-400 uppercase tracking-wider font-medium mb-1">Former Residents</div>
          <div className="text-2xl font-bold text-slate-900 tabular-nums">{data.totals.former}</div>
          <div className="text-[10px] text-slate-400">moved out</div>
        </div>
        <div className="bg-white border border-slate-200 rounded-xl p-4">
          <div className="text-[10px] text-slate-400 uppercase tracking-wider font-medium mb-1">On Notice</div>
          <div className="text-2xl font-bold text-amber-600 tabular-nums">{data.totals.notice}</div>
          <div className="text-[10px] text-slate-400">gave notice</div>
        </div>
        <div className="bg-white border border-slate-200 rounded-xl p-4">
          <div className="text-[10px] text-slate-400 uppercase tracking-wider font-medium mb-1">Total</div>
          <div className="text-2xl font-bold text-slate-900 tabular-nums">{data.totals.total}</div>
          <div className="text-[10px] text-slate-400">all move-outs</div>
        </div>
      </div>

      {/* Tab toggle */}
      <div className="bg-white border border-slate-200 rounded-xl overflow-hidden">
        <div className="flex border-b border-slate-100">
          <button
            onClick={() => setActiveTab('former')}
            className={`flex-1 flex items-center justify-center gap-2 px-4 py-2.5 text-sm font-medium transition-colors ${
              activeTab === 'former'
                ? 'text-slate-800 bg-slate-50 border-b-2 border-indigo-500'
                : 'text-slate-400 hover:text-slate-600'
            }`}
          >
            <Users size={14} />
            Former Residents ({data.totals.former})
          </button>
          <button
            onClick={() => setActiveTab('notice')}
            className={`flex-1 flex items-center justify-center gap-2 px-4 py-2.5 text-sm font-medium transition-colors ${
              activeTab === 'notice'
                ? 'text-slate-800 bg-slate-50 border-b-2 border-amber-500'
                : 'text-slate-400 hover:text-slate-600'
            }`}
          >
            <AlertTriangle size={14} />
            On Notice ({data.totals.notice})
          </button>
        </div>

        <div className="p-4 space-y-3">
          {/* Stacked bar */}
          <CategoryBar categories={categories} total={total} />

          {/* Legend */}
          <div className="flex flex-wrap gap-3 mb-2">
            {categories.map((cat, i) => (
              <div key={i} className="flex items-center gap-1.5">
                <div className={`w-2.5 h-2.5 rounded-full ${getCategoryColor(cat.category)}`} />
                <span className="text-[11px] text-slate-500">{cat.category}</span>
              </div>
            ))}
          </div>

          {/* Category cards */}
          {categories.length === 0 ? (
            <div className="text-center text-slate-400 text-sm py-8">No data for this category.</div>
          ) : (
            <div className="space-y-2">
              {categories.map((cat, i) => (
                <CategoryCard key={cat.category} cat={cat} total={total} defaultOpen={i === 0} />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
