/**
 * AIInsightsPanel - AI-generated Red Flags & Alerts + Ask Me Anything
 * Replaces the old LeasingInsightPanel with real AI-driven insights
 */
import { useState, useEffect } from 'react';
import { AlertTriangle, MessageCircleQuestion, Sparkles, RefreshCw, ChevronDown, ChevronUp } from 'lucide-react';
import { api } from '../api';

interface Alert {
  severity: 'high' | 'medium' | 'low';
  title: string;
  fact: string;
  risk: string;
  action: string;
}

interface QnA {
  question: string;
  answer: string;
}

interface AIInsightsPanelProps {
  propertyId: string;
}

const SEVERITY_STYLES = {
  high: { bg: 'bg-rose-50', border: 'border-rose-200', icon: 'text-rose-500', badge: 'bg-rose-100 text-rose-700' },
  medium: { bg: 'bg-amber-50', border: 'border-amber-200', icon: 'text-amber-500', badge: 'bg-amber-100 text-amber-700' },
  low: { bg: 'bg-blue-50', border: 'border-blue-200', icon: 'text-blue-500', badge: 'bg-blue-100 text-blue-700' },
};

export function AIInsightsPanel({ propertyId }: AIInsightsPanelProps) {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [qna, setQna] = useState<QnA[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedAlert, setExpandedAlert] = useState<number | null>(0);
  const [expandedQna, setExpandedQna] = useState<number | null>(null);
  const [tab, setTab] = useState<'alerts' | 'qna'>('alerts');

  useEffect(() => {
    if (!propertyId) return;
    setLoading(true);
    setError(null);
    api.getAIInsights(propertyId)
      .then((data: { alerts?: { severity: string; title: string; fact: string; risk: string; action: string }[]; qna?: { question: string; answer: string }[]; error?: string }) => {
        setAlerts((data.alerts || []).map(a => ({ ...a, severity: a.severity as Alert['severity'] })));
        setQna(data.qna || []);
        if (data.error) setError(data.error);
        setExpandedAlert(0);
        setExpandedQna(null);
      })
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, [propertyId]);

  const handleRefresh = () => {
    setLoading(true);
    setError(null);
    // Add cache-bust param
    fetch(`/api/v2/properties/${propertyId}/ai-insights?refresh=1`)
      .then(r => r.json())
      .then((data) => {
        setAlerts(data.alerts || []);
        setQna(data.qna || []);
      })
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  };

  return (
    <div className="bg-white rounded-xl border border-slate-200 overflow-hidden h-fit">
      {/* Header */}
      <div className="px-4 py-3 border-b border-slate-200 bg-gradient-to-r from-violet-50 to-indigo-50">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-violet-500" />
            <h3 className="text-sm font-semibold text-slate-800">AI Insights</h3>
          </div>
          <button
            onClick={handleRefresh}
            disabled={loading}
            className="p-1 hover:bg-white/60 rounded transition-colors disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 text-slate-400 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Tab Toggle */}
      <div className="flex border-b border-slate-100">
        <button
          onClick={() => setTab('alerts')}
          className={`flex-1 px-3 py-2 text-xs font-medium transition-colors flex items-center justify-center gap-1.5
            ${tab === 'alerts' ? 'text-rose-600 border-b-2 border-rose-500 bg-rose-50/50' : 'text-slate-500 hover:text-slate-700'}`}
        >
          <AlertTriangle className="w-3.5 h-3.5" />
          Red Flags {alerts.length > 0 && <span className="px-1.5 py-0.5 text-[10px] bg-rose-100 text-rose-600 rounded-full">{alerts.length}</span>}
        </button>
        <button
          onClick={() => setTab('qna')}
          className={`flex-1 px-3 py-2 text-xs font-medium transition-colors flex items-center justify-center gap-1.5
            ${tab === 'qna' ? 'text-indigo-600 border-b-2 border-indigo-500 bg-indigo-50/50' : 'text-slate-500 hover:text-slate-700'}`}
        >
          <MessageCircleQuestion className="w-3.5 h-3.5" />
          Ask Me Anything
        </button>
      </div>

      {/* Content */}
      <div className="p-4">
        {loading && (
          <div className="flex items-center justify-center py-8">
            <div className="flex items-center gap-2 text-sm text-slate-400">
              <Sparkles className="w-4 h-4 animate-pulse text-violet-400" />
              Analyzing property data...
            </div>
          </div>
        )}

        {error && !loading && (
          <div className="text-xs text-slate-400 text-center py-4">{error}</div>
        )}

        {/* Alerts Tab */}
        {!loading && tab === 'alerts' && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {alerts.length === 0 && (
              <div className="text-xs text-slate-400 text-center py-4 col-span-full">No alerts generated</div>
            )}
            {alerts.map((alert, i) => {
              const styles = SEVERITY_STYLES[alert.severity] || SEVERITY_STYLES.medium;
              const isOpen = expandedAlert === i;
              return (
                <div key={i} className={`rounded-lg border ${styles.border} ${styles.bg} overflow-hidden`}>
                  <button
                    onClick={() => setExpandedAlert(isOpen ? null : i)}
                    className="w-full px-3 py-2.5 flex items-start gap-2 text-left"
                  >
                    <AlertTriangle className={`w-4 h-4 flex-shrink-0 mt-0.5 ${styles.icon}`} />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-1.5">
                        <span className={`px-1.5 py-0.5 text-[9px] font-semibold uppercase rounded ${styles.badge}`}>
                          {alert.severity}
                        </span>
                        <span className="text-xs font-semibold text-slate-800 truncate">{alert.title}</span>
                      </div>
                    </div>
                    {isOpen ? <ChevronUp className="w-3.5 h-3.5 text-slate-400 flex-shrink-0 mt-0.5" /> : <ChevronDown className="w-3.5 h-3.5 text-slate-400 flex-shrink-0 mt-0.5" />}
                  </button>
                  {isOpen && (
                    <div className="px-3 pb-3 space-y-1.5">
                      <p className="text-[11px] text-slate-700"><span className="font-semibold">Fact:</span> {alert.fact}</p>
                      <p className="text-[11px] text-slate-600"><span className="font-semibold">Risk:</span> {alert.risk}</p>
                      <p className="text-[11px] text-slate-800 font-medium"><span className="font-semibold">Action:</span> {alert.action}</p>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}

        {/* Q&A Tab */}
        {!loading && tab === 'qna' && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {qna.length === 0 && (
              <div className="text-xs text-slate-400 text-center py-4 col-span-full">No Q&A generated</div>
            )}
            {qna.map((item, i) => {
              const isOpen = expandedQna === i;
              return (
                <div key={i} className="rounded-lg border border-indigo-100 bg-indigo-50/50 overflow-hidden">
                  <button
                    onClick={() => setExpandedQna(isOpen ? null : i)}
                    className="w-full px-3 py-2.5 flex items-start gap-2 text-left"
                  >
                    <MessageCircleQuestion className="w-4 h-4 flex-shrink-0 mt-0.5 text-indigo-400" />
                    <span className="text-xs font-medium text-slate-800 flex-1">{item.question}</span>
                    {isOpen ? <ChevronUp className="w-3.5 h-3.5 text-slate-400 flex-shrink-0 mt-0.5" /> : <ChevronDown className="w-3.5 h-3.5 text-slate-400 flex-shrink-0 mt-0.5" />}
                  </button>
                  {isOpen && (
                    <div className="px-3 pb-3 ml-6">
                      <p className="text-[11px] text-slate-700 leading-relaxed">{item.answer}</p>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
