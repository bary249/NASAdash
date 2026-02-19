/**
 * Make Ready Status Section
 * 
 * Shows all vacant unrented units split into not-ready vs ready,
 * with estimated completion dates from the make-ready pipeline.
 */
import { useState, useEffect, useMemo, useCallback } from 'react';
import { Hammer, Clock, CheckCircle2, AlertTriangle, XCircle, DollarSign, ChevronUp, ChevronDown } from 'lucide-react';
import { SectionHeader } from './SectionHeader';
import { api } from '../api';

interface MakeReadyUnit {
  unit: string;
  floorplan: string;
  sqft: number;
  market_rent: number;
  days_vacant: number;
  date_vacated: string;
  date_due: string;
  days_until_ready: number | null;
  work_orders: number;
  in_pipeline: boolean;
  lost_rent: number;
  status?: string;
  made_ready_date?: string;
}

interface MakeReadySummary {
  total_vacant_unrented: number;
  ready_count: number;
  not_ready_count: number;
  in_progress: number;
  overdue: number;
  not_started: number;
  total_lost_rent: number;
}

interface MakeReadyData {
  property_id: string;
  not_ready: MakeReadyUnit[];
  ready: MakeReadyUnit[];
  summary: MakeReadySummary;
}

interface Props {
  propertyId: string;
  propertyIds?: string[];
}

type SortKey = 'unit' | 'floorplan' | 'sqft' | 'days_vacant' | 'date_due' | 'days_until_ready' | 'work_orders' | 'lost_rent' | 'market_rent' | 'status';
type SortDir = 'asc' | 'desc';

function SortableHeader({ label, active, dir, onClick, align = 'left' }: {
  label: string; active: boolean; dir: SortDir; onClick: () => void; align?: 'left' | 'right';
}) {
  return (
    <th
      className={`px-3 py-2 text-slate-500 font-medium cursor-pointer select-none hover:text-slate-700 transition-colors ${align === 'right' ? 'text-right' : ''}`}
      onClick={onClick}
    >
      <span className="inline-flex items-center gap-1">
        {label}
        {active ? (
          dir === 'asc' ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />
        ) : (
          <ChevronDown className="w-3 h-3 opacity-0" />
        )}
      </span>
    </th>
  );
}

function StatusBadge({ status }: { status: string }) {
  if (status === 'overdue') {
    return <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-700"><XCircle className="w-3 h-3" />Overdue</span>;
  }
  if (status === 'in_progress') {
    return <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-700"><Clock className="w-3 h-3" />In Progress</span>;
  }
  return <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-slate-100 text-slate-600"><AlertTriangle className="w-3 h-3" />Not Started</span>;
}

export default function MakeReadySection({ propertyId, propertyIds }: Props) {
  const [data, setData] = useState<MakeReadyData | null>(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<'not_ready' | 'ready'>('not_ready');
  const [sortKey, setSortKey] = useState<SortKey>('days_vacant');
  const [sortDir, setSortDir] = useState<SortDir>('desc');

  const effectiveIds = propertyIds && propertyIds.length > 0 ? propertyIds : [propertyId];

  const toggleSort = useCallback((key: SortKey) => {
    if (sortKey === key) setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    else { setSortKey(key); setSortDir(key === 'unit' || key === 'floorplan' ? 'asc' : 'desc'); }
  }, [sortKey]);

  useEffect(() => {
    if (!effectiveIds.length || !effectiveIds[0]) return;
    setLoading(true);
    Promise.all(effectiveIds.map(id => api.getMakeReadyStatus(id).catch(() => null)))
      .then(results => {
        const valid = results.filter(Boolean) as MakeReadyData[];
        if (valid.length === 0) { setData(null); return; }
        if (valid.length === 1) { setData(valid[0]); return; }
        // Merge for portfolio
        const notReady = valid.flatMap(d => d.not_ready || []);
        const ready = valid.flatMap(d => d.ready || []);
        setData({
          property_id: 'portfolio',
          not_ready: notReady,
          ready: ready,
          summary: {
            total_vacant_unrented: notReady.length + ready.length,
            ready_count: ready.length,
            not_ready_count: notReady.length,
            in_progress: valid.reduce((s, d) => s + (d.summary?.in_progress || 0), 0),
            overdue: valid.reduce((s, d) => s + (d.summary?.overdue || 0), 0),
            not_started: valid.reduce((s, d) => s + (d.summary?.not_started || 0), 0),
            total_lost_rent: valid.reduce((s, d) => s + (d.summary?.total_lost_rent || 0), 0),
          },
        });
      })
      .finally(() => setLoading(false));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [effectiveIds.join(',')]);

  const currentList = tab === 'not_ready' ? (data?.not_ready || []) : (data?.ready || []);

  const sorted = useMemo(() => {
    if (!currentList.length) return currentList;
    return [...currentList].sort((a, b) => {
      const av = a[sortKey as keyof MakeReadyUnit];
      const bv = b[sortKey as keyof MakeReadyUnit];
      if (av == null && bv == null) return 0;
      if (av == null) return 1;
      if (bv == null) return -1;
      let cmp = 0;
      if (typeof av === 'string' && typeof bv === 'string') cmp = av.localeCompare(bv);
      else cmp = (Number(av) || 0) - (Number(bv) || 0);
      return sortDir === 'asc' ? cmp : -cmp;
    });
  }, [currentList, sortKey, sortDir]);

  if (loading) {
    return (
      <div className="bg-white rounded-2xl border border-slate-200 p-8">
        <div className="animate-pulse space-y-4">
          <div className="h-6 bg-slate-200 rounded w-48" />
          <div className="grid grid-cols-4 gap-4">
            {[1,2,3,4].map(i => <div key={i} className="h-20 bg-slate-100 rounded-xl" />)}
          </div>
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="bg-white rounded-2xl border border-slate-200 p-8 text-center">
        <Hammer className="w-12 h-12 text-slate-300 mx-auto mb-3" />
        <p className="text-slate-500">No make-ready data available</p>
      </div>
    );
  }

  const { summary } = data;
  const readyPct = summary.total_vacant_unrented > 0
    ? Math.round(summary.ready_count / summary.total_vacant_unrented * 100)
    : 0;

  return (
    <div className="space-y-4">
      <SectionHeader
        icon={Hammer}
        title="Make Ready Status"
        subtitle="Vacant unrented units — ready vs not ready"
      />

      {/* Summary cards */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <div className="rounded-xl border bg-slate-50 border-slate-200 p-4">
          <div className="text-xs font-medium text-slate-500 mb-1">Vacant Unrented</div>
          <div className="text-2xl font-bold text-slate-800">{summary.total_vacant_unrented}</div>
        </div>
        <div className="rounded-xl border bg-emerald-50 border-emerald-200 p-4">
          <div className="flex items-center gap-1.5 mb-1">
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
            <span className="text-xs font-medium text-emerald-700">Ready</span>
          </div>
          <div className="text-2xl font-bold text-emerald-700">{summary.ready_count}</div>
          <div className="text-xs text-emerald-600 mt-0.5">{readyPct}% of vacant</div>
        </div>
        <div className="rounded-xl border bg-amber-50 border-amber-200 p-4">
          <div className="flex items-center gap-1.5 mb-1">
            <AlertTriangle className="w-3.5 h-3.5 text-amber-600" />
            <span className="text-xs font-medium text-amber-700">Not Ready</span>
          </div>
          <div className="text-2xl font-bold text-amber-700">{summary.not_ready_count}</div>
          <div className="text-xs text-amber-600 mt-0.5">
            {summary.in_progress > 0 && `${summary.in_progress} in progress`}
            {summary.overdue > 0 && ` · ${summary.overdue} overdue`}
            {summary.not_started > 0 && ` · ${summary.not_started} not started`}
          </div>
        </div>
        {summary.overdue > 0 && (
          <div className="rounded-xl border bg-red-50 border-red-200 p-4">
            <div className="flex items-center gap-1.5 mb-1">
              <XCircle className="w-3.5 h-3.5 text-red-600" />
              <span className="text-xs font-medium text-red-700">Overdue</span>
            </div>
            <div className="text-2xl font-bold text-red-700">{summary.overdue}</div>
            <div className="text-xs text-red-600 mt-0.5">past due date</div>
          </div>
        )}
        <div className="rounded-xl border bg-violet-50 border-violet-200 p-4">
          <div className="flex items-center gap-1.5 mb-1">
            <DollarSign className="w-3.5 h-3.5 text-violet-600" />
            <span className="text-xs font-medium text-violet-700">Lost Rent</span>
          </div>
          <div className="text-2xl font-bold text-violet-700">${summary.total_lost_rent.toLocaleString()}</div>
          <div className="text-xs text-violet-600 mt-0.5">vacancy cost to date</div>
        </div>
      </div>

      {/* Progress bar */}
      {summary.total_vacant_unrented > 0 && (
        <div className="bg-white rounded-xl border border-slate-200 p-4">
          <div className="flex justify-between text-xs text-slate-500 mb-2">
            <span>Make Ready Progress</span>
            <span>{readyPct}% complete</span>
          </div>
          <div className="h-3 bg-slate-100 rounded-full overflow-hidden flex">
            <div className="bg-emerald-500 rounded-l-full transition-all" style={{ width: `${readyPct}%` }} />
            {summary.in_progress > 0 && (
              <div className="bg-blue-400 transition-all" style={{ width: `${Math.round(summary.in_progress / summary.total_vacant_unrented * 100)}%` }} />
            )}
            {summary.overdue > 0 && (
              <div className="bg-red-400 transition-all" style={{ width: `${Math.round(summary.overdue / summary.total_vacant_unrented * 100)}%` }} />
            )}
          </div>
          <div className="flex gap-4 mt-2 text-xs">
            <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-emerald-500" />Ready ({summary.ready_count})</span>
            <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-blue-400" />In Progress ({summary.in_progress})</span>
            {summary.overdue > 0 && <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-red-400" />Overdue ({summary.overdue})</span>}
            {summary.not_started > 0 && <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-slate-300" />Not Started ({summary.not_started})</span>}
          </div>
        </div>
      )}

      {/* Tab toggle */}
      <div className="flex gap-2">
        <button
          onClick={() => setTab('not_ready')}
          className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${tab === 'not_ready' ? 'bg-amber-600 text-white' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'}`}
        >
          Not Ready ({data.not_ready.length})
        </button>
        <button
          onClick={() => setTab('ready')}
          className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${tab === 'ready' ? 'bg-emerald-600 text-white' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'}`}
        >
          Ready ({data.ready.length})
        </button>
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        {sorted.length === 0 ? (
          <div className="p-8 text-center text-slate-400">
            {tab === 'not_ready' ? 'All vacant units are ready — great job!' : 'No ready units'}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-slate-50 text-left text-xs uppercase">
                  <SortableHeader label="Unit" active={sortKey === 'unit'} dir={sortDir} onClick={() => toggleSort('unit')} />
                  <SortableHeader label="Floorplan" active={sortKey === 'floorplan'} dir={sortDir} onClick={() => toggleSort('floorplan')} />
                  <SortableHeader label="Sq Ft" active={sortKey === 'sqft'} dir={sortDir} onClick={() => toggleSort('sqft')} align="right" />
                  <SortableHeader label="Market Rent" active={sortKey === 'market_rent'} dir={sortDir} onClick={() => toggleSort('market_rent')} align="right" />
                  <SortableHeader label="Days Vacant" active={sortKey === 'days_vacant'} dir={sortDir} onClick={() => toggleSort('days_vacant')} align="right" />
                  {tab === 'not_ready' && (
                    <>
                      <SortableHeader label="Due Date" active={sortKey === 'date_due'} dir={sortDir} onClick={() => toggleSort('date_due')} />
                      <SortableHeader label="Days to Ready" active={sortKey === 'days_until_ready'} dir={sortDir} onClick={() => toggleSort('days_until_ready')} align="right" />
                      <SortableHeader label="Work Orders" active={sortKey === 'work_orders'} dir={sortDir} onClick={() => toggleSort('work_orders')} align="right" />
                      <th className="px-3 py-2 text-slate-500 font-medium">Status</th>
                    </>
                  )}
                  <SortableHeader label="Lost Rent" active={sortKey === 'lost_rent'} dir={sortDir} onClick={() => toggleSort('lost_rent')} align="right" />
                </tr>
              </thead>
              <tbody>
                {sorted.map((u, i) => (
                  <tr key={i} className={`border-t border-slate-50 ${u.status === 'overdue' ? 'bg-red-50/40' : u.status === 'not_started' ? 'bg-slate-50/40' : ''}`}>
                    <td className="px-3 py-2.5 font-medium text-slate-800">{u.unit}</td>
                    <td className="px-3 py-2.5 text-slate-600">{u.floorplan || '—'}</td>
                    <td className="px-3 py-2.5 text-right text-slate-600">{u.sqft > 0 ? u.sqft.toLocaleString() : '—'}</td>
                    <td className="px-3 py-2.5 text-right text-slate-700">${u.market_rent > 0 ? u.market_rent.toLocaleString() : '—'}</td>
                    <td className={`px-3 py-2.5 text-right font-medium ${u.days_vacant > 30 ? 'text-red-600' : u.days_vacant > 14 ? 'text-amber-600' : 'text-slate-700'}`}>
                      {u.days_vacant}d
                    </td>
                    {tab === 'not_ready' && (
                      <>
                        <td className="px-3 py-2.5 text-slate-600">{u.date_due || '—'}</td>
                        <td className={`px-3 py-2.5 text-right font-medium ${
                          u.days_until_ready === null ? 'text-slate-400' :
                          u.days_until_ready < 0 ? 'text-red-600' :
                          u.days_until_ready <= 3 ? 'text-amber-600' : 'text-emerald-600'
                        }`}>
                          {u.days_until_ready === null ? '—' :
                           u.days_until_ready < 0 ? `${Math.abs(u.days_until_ready)}d overdue` :
                           u.days_until_ready === 0 ? 'Today' :
                           `${u.days_until_ready}d`}
                        </td>
                        <td className="px-3 py-2.5 text-right text-slate-600">{u.work_orders || '—'}</td>
                        <td className="px-3 py-2.5">{u.status && <StatusBadge status={u.status} />}</td>
                      </>
                    )}
                    <td className="px-3 py-2.5 text-right text-slate-600">${u.lost_rent > 0 ? u.lost_rent.toLocaleString() : '0'}</td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr className="border-t-2 border-slate-200 bg-slate-50 font-semibold text-sm">
                  <td className="px-3 py-2.5 text-slate-700" colSpan={2}>Total ({sorted.length} units)</td>
                  <td className="px-3 py-2.5 text-right text-slate-600">{sorted.reduce((s, u) => s + (u.sqft || 0), 0).toLocaleString()}</td>
                  <td className="px-3 py-2.5 text-right text-slate-700">
                    ${sorted.length > 0 ? Math.round(sorted.reduce((s, u) => s + (u.market_rent || 0), 0) / sorted.length).toLocaleString() : '0'}
                    <span className="text-xs font-normal text-slate-400"> avg</span>
                  </td>
                  <td className="px-3 py-2.5 text-right text-slate-700">
                    {sorted.length > 0 ? Math.round(sorted.reduce((s, u) => s + (u.days_vacant || 0), 0) / sorted.length) : 0}d
                    <span className="text-xs font-normal text-slate-400"> avg</span>
                  </td>
                  {tab === 'not_ready' && (
                    <>
                      <td className="px-3 py-2.5" />
                      <td className="px-3 py-2.5" />
                      <td className="px-3 py-2.5 text-right text-slate-600">
                        {sorted.reduce((s, u) => s + (u.work_orders || 0), 0)}
                      </td>
                      <td className="px-3 py-2.5" />
                    </>
                  )}
                  <td className="px-3 py-2.5 text-right text-slate-700">${sorted.reduce((s, u) => s + (u.lost_rent || 0), 0).toLocaleString()}</td>
                </tr>
              </tfoot>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
