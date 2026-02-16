/**
 * Maintenance Section - Make Ready Pipeline + Completed Turns
 * 
 * Displays data from RealPage Reports 4186 (Make Ready Summary) and 4189 (Closed Make Ready).
 * Shows units in the turnover pipeline and recently completed turns.
 */
import { useState, useEffect } from 'react';
import { Wrench, Clock, CheckCircle2, AlertTriangle } from 'lucide-react';
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

export default function MaintenanceSection({ propertyId, propertyIds }: Props) {
  const [data, setData] = useState<MaintenanceData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<'pipeline' | 'completed'>('pipeline');

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

  const { summary, pipeline, completed } = data;

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
                    <th className="px-4 py-2 text-slate-500 font-medium">Unit</th>
                    <th className="px-3 py-2 text-slate-500 font-medium">Unit Status</th>
                    <th className="px-3 py-2 text-slate-500 font-medium text-right">Sq Ft</th>
                    <th className="px-3 py-2 text-slate-500 font-medium text-right">Days Vacant</th>
                    <th className="px-3 py-2 text-slate-500 font-medium">Date Vacated</th>
                    <th className="px-3 py-2 text-slate-500 font-medium">Due Date</th>
                    <th className="px-3 py-2 text-slate-500 font-medium text-right">Work Orders</th>
                    <th className="px-4 py-2 text-slate-500 font-medium">Turn Status</th>
                  </tr>
                </thead>
                <tbody>
                  {pipeline.map((unit, i) => {
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
                    <th className="px-4 py-2 text-slate-500 font-medium">Unit</th>
                    <th className="px-3 py-2 text-slate-500 font-medium text-right">Work Orders</th>
                    <th className="px-3 py-2 text-slate-500 font-medium">Date Closed</th>
                    <th className="px-3 py-2 text-slate-500 font-medium text-right">Amount Charged</th>
                  </tr>
                </thead>
                <tbody>
                  {completed.map((unit, i) => (
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
