/**
 * Maintenance Section - Make Ready Pipeline + Completed Turns
 * 
 * Displays data from RealPage Reports 4186 (Make Ready Summary) and 4189 (Closed Make Ready).
 * Shows units in the turnover pipeline and recently completed turns.
 */
import { useState, useEffect, useMemo, useCallback } from 'react';
import { Wrench, Clock, CheckCircle2, AlertTriangle, ChevronUp, ChevronDown } from 'lucide-react';
import { SectionHeader } from './SectionHeader';
import { api } from '../api';

interface PipelineUnit {
  unit: string;
  sqft: number;
  days_vacant: number;
  date_vacated: string;
  date_due: string;
  num_work_orders: number;
  unit_status: string;
  lease_status: string;
}

interface CompletedUnit {
  unit: string;
  num_work_orders: number;
  date_closed: string;
  amount_charged: number;
}

interface MaintenanceSummary {
  units_in_pipeline: number;
  avg_days_vacant: number;
  overdue_count: number;
  completed_this_period: number;
}

interface MaintenanceData {
  property_id: string;
  pipeline: PipelineUnit[];
  completed: CompletedUnit[];
  summary: MaintenanceSummary;
}

interface Props {
  propertyId: string;
  propertyIds?: string[];
}

function StatCard({ icon: Icon, label, value, subtext, variant = 'default' }: { icon: typeof Clock; label: string; value: string | number; subtext?: string; variant?: 'default' | 'warning' | 'success' }) {
  const colors = {
    default: 'bg-slate-50 border-slate-200',
    warning: 'bg-amber-50 border-amber-200',
    success: 'bg-emerald-50 border-emerald-200',
  };
  const iconColors = {
    default: 'text-slate-500',
    warning: 'text-amber-600',
    success: 'text-emerald-600',
  };
  return (
    <div className={`rounded-xl border p-4 ${colors[variant]}`}>
      <div className="flex items-center gap-2 mb-2">
        <Icon className={`w-4 h-4 ${iconColors[variant]}`} />
        <span className="text-xs font-medium text-slate-500">{label}</span>
      </div>
      <div className="text-2xl font-bold text-slate-800">{value}</div>
      {subtext && <div className="text-xs text-slate-500 mt-1">{subtext}</div>}
    </div>
  );
}

type PipelineSortKey = keyof PipelineUnit;
type CompletedSortKey = keyof CompletedUnit;
type SortDir = 'asc' | 'desc';

function SortableHeader({ label, active, dir, onClick, align = 'left' }: {
  label: string; active: boolean; dir: SortDir; onClick: () => void; align?: 'left' | 'right';
}) {
  return (
    <th
      className={`group px-3 py-2 text-slate-500 font-medium cursor-pointer select-none hover:text-slate-700 hover:bg-slate-100/50 transition-colors ${align === 'right' ? 'text-right' : ''} ${label === 'Unit' || label === 'Turn Status' ? 'px-4' : ''}`}
      onClick={onClick}
    >
      <span className="inline-flex items-center gap-1">
        {label}
        {active ? (
          dir === 'asc' ? <ChevronUp className="w-3 h-3 text-slate-700" /> : <ChevronDown className="w-3 h-3 text-slate-700" />
        ) : (
          <ChevronDown className="w-3 h-3 opacity-20 group-hover:opacity-50" />
        )}
      </span>
    </th>
  );
}

export default function MaintenanceSection({ propertyId, propertyIds }: Props) {
  const [data, setData] = useState<MaintenanceData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<'pipeline' | 'completed'>('pipeline');

  // Sorting state
  const [pipeSortKey, setPipeSortKey] = useState<PipelineSortKey>('days_vacant');
  const [pipeSortDir, setPipeSortDir] = useState<SortDir>('desc');
  const [compSortKey, setCompSortKey] = useState<CompletedSortKey>('date_closed');
  const [compSortDir, setCompSortDir] = useState<SortDir>('desc');

  const togglePipeSort = useCallback((key: PipelineSortKey) => {
    if (pipeSortKey === key) setPipeSortDir(d => d === 'asc' ? 'desc' : 'asc');
    else { setPipeSortKey(key); setPipeSortDir(key === 'unit' ? 'asc' : 'desc'); }
  }, [pipeSortKey]);

  const toggleCompSort = useCallback((key: CompletedSortKey) => {
    if (compSortKey === key) setCompSortDir(d => d === 'asc' ? 'desc' : 'asc');
    else { setCompSortKey(key); setCompSortDir(key === 'unit' ? 'asc' : 'desc'); }
  }, [compSortKey]);

  const effectiveIds = propertyIds && propertyIds.length > 0 ? propertyIds : [propertyId];

  useEffect(() => {
    if (!effectiveIds.length || !effectiveIds[0]) return;
    setLoading(true);
    setError(null);
    Promise.all(effectiveIds.map(id => api.getMaintenance(id).catch(() => null)))
      .then(results => {
        const valid = results.filter(Boolean) as MaintenanceData[];
        if (valid.length === 0) { setData(null); return; }
        if (valid.length === 1) { setData(valid[0]); return; }
        const pipeline = valid.flatMap(d => d.pipeline || []);
        const completed = valid.flatMap(d => d.completed || []);
        const avgDaysVacant = pipeline.length > 0 ? Math.round(pipeline.reduce((s, u) => s + (u.days_vacant || 0), 0) / pipeline.length) : 0;
        setData({
          property_id: 'multi',
          pipeline,
          completed,
          summary: {
            units_in_pipeline: pipeline.length,
            avg_days_vacant: avgDaysVacant,
            overdue_count: valid.reduce((s, d) => s + (d.summary?.overdue_count || 0), 0),
            completed_this_period: valid.reduce((s, d) => s + (d.summary?.completed_this_period || 0), 0),
          },
        });
      })
      .catch(err => setError(err instanceof Error ? err.message : 'Failed'))
      .finally(() => setLoading(false));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [effectiveIds.join(',')]);

  // Sorted data — hooks must be called before any early returns
  const pipeline = data?.pipeline || [];
  const completed = data?.completed || [];

  const parseDate = (s: string): number => {
    if (!s) return 0;
    const parts = s.split('/');
    if (parts.length === 3) {
      const [m, d, y] = parts.map(Number);
      const year = y < 100 ? 2000 + y : y;
      return new Date(year, m - 1, d).getTime();
    }
    const t = Date.parse(s);
    return isNaN(t) ? 0 : t;
  };

  const DATE_KEYS = new Set(['date_vacated', 'date_due', 'date_closed']);

  const sortedPipeline = useMemo(() => {
    if (!pipeline.length) return pipeline;
    return [...pipeline].sort((a, b) => {
      const av = a[pipeSortKey];
      const bv = b[pipeSortKey];
      let cmp = 0;
      if (DATE_KEYS.has(pipeSortKey)) {
        cmp = parseDate(String(av || '')) - parseDate(String(bv || ''));
      } else if (typeof av === 'string' && typeof bv === 'string') {
        cmp = av.localeCompare(bv);
      } else {
        cmp = (Number(av) || 0) - (Number(bv) || 0);
      }
      return pipeSortDir === 'asc' ? cmp : -cmp;
    });
  }, [pipeline, pipeSortKey, pipeSortDir]);

  const sortedCompleted = useMemo(() => {
    if (!completed.length) return completed;
    return [...completed].sort((a, b) => {
      const av = a[compSortKey];
      const bv = b[compSortKey];
      let cmp = 0;
      if (DATE_KEYS.has(compSortKey)) {
        cmp = parseDate(String(av || '')) - parseDate(String(bv || ''));
      } else if (typeof av === 'string' && typeof bv === 'string') {
        cmp = av.localeCompare(bv);
      } else {
        cmp = (Number(av) || 0) - (Number(bv) || 0);
      }
      return compSortDir === 'asc' ? cmp : -cmp;
    });
  }, [completed, compSortKey, compSortDir]);

  if (loading) {
    return (
      <div className="bg-white rounded-2xl border border-slate-200 p-8">
        <div className="animate-pulse space-y-4">
          <div className="h-6 bg-slate-200 rounded w-48" />
          <div className="grid grid-cols-4 gap-4">
            {[1,2,3,4].map(i => <div key={i} className="h-24 bg-slate-100 rounded-xl" />)}
          </div>
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="bg-white rounded-2xl border border-slate-200 p-8 text-center">
        <Wrench className="w-12 h-12 text-slate-300 mx-auto mb-3" />
        <p className="text-slate-500">No maintenance data available for this property</p>
      </div>
    );
  }

  const { summary } = data;

  return (
    <div className="space-y-4">
      <SectionHeader
        icon={Wrench}
        title="Maintenance & Turns"
        subtitle="Make-ready pipeline and completed unit turns"
      />

      {/* Summary KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatCard icon={Wrench} label="In Pipeline" value={summary.units_in_pipeline} subtext="units being turned" />
        <StatCard icon={Clock} label="Avg Days Vacant" value={summary.avg_days_vacant} subtext="days in pipeline" variant={summary.avg_days_vacant > 14 ? 'warning' : 'default'} />
        <StatCard icon={AlertTriangle} label="Overdue (>14d)" value={summary.overdue_count} variant={summary.overdue_count > 0 ? 'warning' : 'default'} />
        <StatCard icon={CheckCircle2} label="Completed" value={summary.completed_this_period} subtext="this period" variant="success" />
      </div>

      {/* Tab Toggle */}
      <div className="flex gap-2">
        <button
          onClick={() => setTab('pipeline')}
          className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${tab === 'pipeline' ? 'bg-slate-800 text-white' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'}`}
        >
          Pipeline ({pipeline.length})
        </button>
        <button
          onClick={() => setTab('completed')}
          className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${tab === 'completed' ? 'bg-slate-800 text-white' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'}`}
        >
          Completed ({completed.length})
        </button>
      </div>

      {/* Pipeline Table */}
      {tab === 'pipeline' && (
        <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
          {pipeline.length === 0 ? (
            <div className="p-8 text-center text-slate-400">No units currently in make-ready pipeline</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-slate-50 text-left">
                    <SortableHeader label="Unit" active={pipeSortKey === 'unit'} dir={pipeSortDir} onClick={() => togglePipeSort('unit')} />
                    <SortableHeader label="Unit Status" active={pipeSortKey === 'unit_status'} dir={pipeSortDir} onClick={() => togglePipeSort('unit_status')} />
                    <SortableHeader label="Sq Ft" active={pipeSortKey === 'sqft'} dir={pipeSortDir} onClick={() => togglePipeSort('sqft')} align="right" />
                    <SortableHeader label="Days Vacant" active={pipeSortKey === 'days_vacant'} dir={pipeSortDir} onClick={() => togglePipeSort('days_vacant')} align="right" />
                    <SortableHeader label="Date Vacated" active={pipeSortKey === 'date_vacated'} dir={pipeSortDir} onClick={() => togglePipeSort('date_vacated')} />
                    <SortableHeader label="Due Date" active={pipeSortKey === 'date_due'} dir={pipeSortDir} onClick={() => togglePipeSort('date_due')} />
                    <SortableHeader label="Work Orders" active={pipeSortKey === 'num_work_orders'} dir={pipeSortDir} onClick={() => togglePipeSort('num_work_orders')} align="right" />
                    <SortableHeader label="Turn Status" active={pipeSortKey === 'lease_status'} dir={pipeSortDir} onClick={() => togglePipeSort('lease_status')} />
                  </tr>
                </thead>
                <tbody>
                  {sortedPipeline.map((unit, i) => {
                    const isOverdue = unit.days_vacant > 14;
                    const isFuture = unit.days_vacant < 0;
                    const status = unit.unit_status?.toLowerCase() || '';
                    const isVacant = status === 'vacant';
                    const isOccupied = status === 'occupied';
                    const isNotice = status.includes('notice');
                    return (
                      <tr key={i} className={`border-t border-slate-50 ${isOverdue ? 'bg-amber-50/30' : ''}`}>
                        <td className="px-4 py-2 font-medium text-slate-800">{unit.unit}</td>
                        <td className="px-3 py-2">
                          {isVacant ? (
                            <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-amber-100 text-amber-700">Vacant</span>
                          ) : isNotice ? (
                            <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-rose-100 text-rose-700">Notice</span>
                          ) : isOccupied ? (
                            <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-emerald-100 text-emerald-700">Occupied</span>
                          ) : unit.unit_status ? (
                            <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-slate-100 text-slate-600">{unit.unit_status}</span>
                          ) : (
                            <span className="text-slate-400">—</span>
                          )}
                        </td>
                        <td className="px-3 py-2 text-right text-slate-600">{unit.sqft > 0 ? unit.sqft.toLocaleString() : '—'}</td>
                        <td className={`px-3 py-2 text-right font-medium ${isOverdue ? 'text-amber-600' : isFuture ? 'text-blue-600' : 'text-slate-700'}`}>
                          {isFuture ? `in ${Math.abs(unit.days_vacant)}d` : `${unit.days_vacant}d`}
                        </td>
                        <td className="px-3 py-2 text-slate-600">{unit.date_vacated || '—'}</td>
                        <td className="px-3 py-2 text-slate-600">{unit.date_due || '—'}</td>
                        <td className="px-3 py-2 text-right text-slate-600">{unit.num_work_orders}</td>
                        <td className="px-4 py-2">
                          {isFuture ? (
                            <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-700">Pre-Turn</span>
                          ) : isOverdue ? (
                            <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-amber-100 text-amber-700">Overdue</span>
                          ) : (
                            <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-slate-100 text-slate-600">In Progress</span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Completed Table */}
      {tab === 'completed' && (
        <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
          {completed.length === 0 ? (
            <div className="p-8 text-center text-slate-400">No completed turns this period</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-slate-50 text-left">
                    <SortableHeader label="Unit" active={compSortKey === 'unit'} dir={compSortDir} onClick={() => toggleCompSort('unit')} />
                    <SortableHeader label="Work Orders" active={compSortKey === 'num_work_orders'} dir={compSortDir} onClick={() => toggleCompSort('num_work_orders')} align="right" />
                    <SortableHeader label="Date Closed" active={compSortKey === 'date_closed'} dir={compSortDir} onClick={() => toggleCompSort('date_closed')} />
                    <SortableHeader label="Amount Charged" active={compSortKey === 'amount_charged'} dir={compSortDir} onClick={() => toggleCompSort('amount_charged')} align="right" />
                  </tr>
                </thead>
                <tbody>
                  {sortedCompleted.map((unit, i) => (
                    <tr key={i} className="border-t border-slate-50">
                      <td className="px-4 py-2 font-medium text-slate-800">{unit.unit}</td>
                      <td className="px-3 py-2 text-right text-slate-600">{unit.num_work_orders}</td>
                      <td className="px-3 py-2 text-slate-600">{unit.date_closed}</td>
                      <td className="px-3 py-2 text-right text-slate-700">
                        {unit.amount_charged > 0 ? `$${unit.amount_charged.toLocaleString()}` : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
