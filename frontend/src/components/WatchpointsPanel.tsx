/**
 * WatchpointsPanel - Portfolio-level metric watchpoints with live status.
 * Allows creating, viewing, and deleting custom metric thresholds.
 * Evaluates against aggregated portfolio metrics.
 */
import { useState, useEffect, useCallback } from 'react';
import { Target, Plus, Trash2, CheckCircle2, AlertTriangle, MinusCircle, X } from 'lucide-react';
import { api } from '../api';

interface Watchpoint {
  id: string;
  metric: string;
  operator: string;
  threshold: number;
  label: string;
  enabled: boolean;
  created_at: string;
  status: string;
  current_value: number | null;
}

interface MetricInfo {
  label: string;
  unit: string;
  direction: string;
}

const OPERATOR_LABELS: Record<string, string> = {
  lt: 'less than',
  gt: 'greater than',
  lte: '≤',
  gte: '≥',
  eq: 'equals',
};

const STATUS_CONFIG: Record<string, { icon: typeof CheckCircle2; color: string; bg: string; label: string }> = {
  triggered: { icon: AlertTriangle, color: 'text-red-600', bg: 'bg-red-50 border-red-200', label: 'Triggered' },
  ok: { icon: CheckCircle2, color: 'text-emerald-600', bg: 'bg-emerald-50 border-emerald-200', label: 'OK' },
  disabled: { icon: MinusCircle, color: 'text-slate-400', bg: 'bg-slate-50 border-slate-200', label: 'Disabled' },
  no_data: { icon: MinusCircle, color: 'text-slate-400', bg: 'bg-slate-50 border-slate-200', label: 'No Data' },
};

interface Props {
  ownerGroup?: string;
}

export function WatchpointsPanel({ ownerGroup }: Props) {
  const [watchpoints, setWatchpoints] = useState<Watchpoint[]>([]);
  const [availableMetrics, setAvailableMetrics] = useState<Record<string, MetricInfo>>({});
  const [currentMetrics, setCurrentMetrics] = useState<Record<string, number>>({});
  const [loading, setLoading] = useState(true);
  const [showAdd, setShowAdd] = useState(false);

  // Add form state
  const [newMetric, setNewMetric] = useState('');
  const [newOperator, setNewOperator] = useState('lt');
  const [newThreshold, setNewThreshold] = useState('');

  const refresh = useCallback(() => {
    setLoading(true);
    api.getWatchpoints(ownerGroup)
      .then(d => {
        setWatchpoints(d.watchpoints);
        setAvailableMetrics(d.available_metrics);
        setCurrentMetrics(d.current_metrics);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [ownerGroup]);

  useEffect(() => { refresh(); }, [refresh]);

  const handleAdd = async () => {
    if (!newMetric || !newThreshold) return;
    try {
      await api.createWatchpoint({
        metric: newMetric,
        operator: newOperator,
        threshold: parseFloat(newThreshold),
      }, ownerGroup);
      setShowAdd(false);
      setNewMetric('');
      setNewThreshold('');
      refresh();
    } catch (e) {
      console.error('Failed to create watchpoint:', e);
    }
  };

  const handleDelete = async (wpId: string) => {
    try {
      await api.deleteWatchpoint(wpId, ownerGroup);
      refresh();
    } catch (e) {
      console.error('Failed to delete watchpoint:', e);
    }
  };

  const triggeredCount = watchpoints.filter(w => w.status === 'triggered').length;

  if (loading) {
    return (
      <div className="bg-white rounded-xl border border-slate-200 p-6 animate-pulse">
        <div className="h-5 bg-slate-200 rounded w-48 mb-4" />
        <div className="h-24 bg-slate-100 rounded" />
      </div>
    );
  }

  return (
    <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
      {/* Header */}
      <div className="px-5 py-4 border-b border-slate-200 bg-slate-50 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Target className="w-5 h-5 text-indigo-500" />
          <div>
            <h3 className="text-sm font-semibold text-slate-800">Portfolio Watchpoints</h3>
            <p className="text-xs text-slate-500">Metric thresholds across all properties</p>
          </div>
          {triggeredCount > 0 && (
            <span className="px-2 py-0.5 rounded-full text-xs font-bold bg-red-100 text-red-700">
              {triggeredCount} triggered
            </span>
          )}
        </div>
        <button
          onClick={() => setShowAdd(!showAdd)}
          className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-medium bg-indigo-600 text-white hover:bg-indigo-700 transition-colors"
        >
          <Plus className="w-3 h-3" />
          Add
        </button>
      </div>

      {/* Add Form */}
      {showAdd && (
        <div className="px-5 py-4 border-b border-slate-200 bg-indigo-50/50">
          <div className="flex flex-wrap items-end gap-3">
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1">Metric</label>
              <select
                value={newMetric}
                onChange={e => setNewMetric(e.target.value)}
                className="rounded-lg border border-slate-300 text-sm px-3 py-1.5 bg-white"
              >
                <option value="">Select metric...</option>
                {Object.entries(availableMetrics).map(([key, info]) => (
                  <option key={key} value={key}>{info.label}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1">Condition</label>
              <select
                value={newOperator}
                onChange={e => setNewOperator(e.target.value)}
                className="rounded-lg border border-slate-300 text-sm px-3 py-1.5 bg-white"
              >
                <option value="lt">Less than</option>
                <option value="gt">Greater than</option>
                <option value="lte">≤</option>
                <option value="gte">≥</option>
                <option value="eq">Equals</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1">
                Threshold {newMetric && availableMetrics[newMetric] ? `(${availableMetrics[newMetric].unit})` : ''}
              </label>
              <input
                type="number"
                value={newThreshold}
                onChange={e => setNewThreshold(e.target.value)}
                placeholder="e.g. 90"
                className="rounded-lg border border-slate-300 text-sm px-3 py-1.5 w-28 bg-white"
              />
            </div>
            <button
              onClick={handleAdd}
              disabled={!newMetric || !newThreshold}
              className="px-4 py-1.5 rounded-lg text-sm font-medium bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              Create
            </button>
            <button
              onClick={() => setShowAdd(false)}
              className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
          {newMetric && currentMetrics[newMetric] !== undefined && (
            <div className="mt-2 text-xs text-slate-500">
              Current value: <span className="font-medium text-slate-700">{currentMetrics[newMetric]}{availableMetrics[newMetric]?.unit}</span>
            </div>
          )}
        </div>
      )}

      {/* Watchpoints List */}
      <div className="divide-y divide-slate-100">
        {watchpoints.length === 0 ? (
          <div className="px-5 py-8 text-center text-sm text-slate-500">
            No watchpoints defined. Click <strong>Add</strong> to create a portfolio-level metric threshold.
          </div>
        ) : (
          watchpoints.map(wp => {
            const cfg = STATUS_CONFIG[wp.status] || STATUS_CONFIG.no_data;
            const Icon = cfg.icon;
            const metaInfo = availableMetrics[wp.metric];
            return (
              <div key={wp.id} className={`px-5 py-3 flex items-center gap-3 ${wp.status === 'triggered' ? 'bg-red-50/30' : ''}`}>
                <Icon className={`w-5 h-5 flex-shrink-0 ${cfg.color}`} />
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium text-slate-800">{wp.label}</div>
                  <div className="text-xs text-slate-500">
                    {metaInfo?.label || wp.metric} {OPERATOR_LABELS[wp.operator] || wp.operator} {wp.threshold}{metaInfo?.unit || ''}
                    {wp.current_value !== null && (
                      <span className={`ml-2 ${wp.status === 'triggered' ? 'text-red-600 font-medium' : 'text-slate-600'}`}>
                        — Current: {wp.current_value}{metaInfo?.unit || ''}
                      </span>
                    )}
                  </div>
                </div>
                <span className={`px-2 py-0.5 rounded-full text-xs font-medium border ${cfg.bg} ${cfg.color}`}>
                  {cfg.label}
                </span>
                <button
                  onClick={() => handleDelete(wp.id)}
                  className="p-1 rounded text-slate-400 hover:text-red-500 hover:bg-red-50 transition-colors"
                  title="Delete watchpoint"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
