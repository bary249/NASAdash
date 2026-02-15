/**
 * AIInsightsPanel - AI-generated Red Flags & Alerts + Ask Me Anything
 * Replaces the old LeasingInsightPanel with real AI-driven insights.
 * User questions from AI chat / search bar are saved and re-answered on each load.
 */
import { useState, useEffect, useCallback } from 'react';
import { AlertTriangle, MessageCircleQuestion, Sparkles, RefreshCw, ChevronDown, ChevronUp, X, Loader2 } from 'lucide-react';
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
  saved?: boolean;        // true = user-saved question
  loading?: boolean;      // true = answer being recalculated
}

interface AIInsightsPanelProps {
  propertyId: string;
  propertyIds?: string[];
}

// ---- Saved-questions helpers (localStorage) ----
const SAVED_Q_KEY = 'ai_saved_questions';

export function loadSavedQuestions(): string[] {
  try {
    const raw = localStorage.getItem(SAVED_Q_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch { return []; }
}

export function saveQuestion(q: string) {
  const qs = loadSavedQuestions();
  const trimmed = q.trim();
  if (!trimmed || qs.includes(trimmed)) return;
  qs.push(trimmed);
  localStorage.setItem(SAVED_Q_KEY, JSON.stringify(qs));
  window.dispatchEvent(new Event('saved-questions-changed'));
}

export function removeSavedQuestion(q: string) {
  const qs = loadSavedQuestions().filter(x => x !== q);
  localStorage.setItem(SAVED_Q_KEY, JSON.stringify(qs));
  window.dispatchEvent(new Event('saved-questions-changed'));
}
// ---- End helpers ----

const SEVERITY_STYLES = {
  high: { bg: 'bg-rose-50', border: 'border-rose-200', icon: 'text-rose-500', badge: 'bg-rose-100 text-rose-700' },
  medium: { bg: 'bg-amber-50', border: 'border-amber-200', icon: 'text-amber-500', badge: 'bg-amber-100 text-amber-700' },
  low: { bg: 'bg-blue-50', border: 'border-blue-200', icon: 'text-blue-500', badge: 'bg-blue-100 text-blue-700' },
};

export function AIInsightsPanel({ propertyId, propertyIds }: AIInsightsPanelProps) {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [qna, setQna] = useState<QnA[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedAlert, setExpandedAlert] = useState<number | null>(0);
  const [expandedQna, setExpandedQna] = useState<number | null>(null);
  const [tab, setTab] = useState<'alerts' | 'qna'>('alerts');
  const [collapsed, setCollapsed] = useState(() => {
    try { return localStorage.getItem('ai_panel_collapsed') === 'true'; } catch { return false; }
  });

  const toggleCollapsed = () => {
    setCollapsed(prev => {
      const next = !prev;
      try { localStorage.setItem('ai_panel_collapsed', String(next)); } catch {}
      return next;
    });
  };

  const effectiveIds = propertyIds && propertyIds.length > 0 ? propertyIds : [propertyId];

  // Recalculate answer for a single saved question
  const recalcSavedAnswer = useCallback(async (question: string, pid: string): Promise<string> => {
    try {
      const result = await api.sendChatMessage(pid, question, []);
      return result.response || 'No answer available.';
    } catch {
      return 'Failed to recalculate answer.';
    }
  }, []);

  // Load AI-generated insights + recalculate saved questions
  const loadInsights = useCallback(async (refresh = false) => {
    if (!effectiveIds.length || !effectiveIds[0]) return;
    setLoading(true);
    setError(null);
    const isMulti = effectiveIds.length > 1;

    try {
      // Fetch AI-generated alerts + qna
      const results = await Promise.all(effectiveIds.map(id =>
        refresh
          ? fetch(`/api/v2/properties/${id}/ai-insights?refresh=1`).then(r => r.json()).catch(() => null)
          : api.getAIInsights(id).catch(() => null)
      ));
      const valid = results.filter(Boolean) as Array<{ property_name?: string; alerts?: { severity: string; title: string; fact: string; risk: string; action: string }[]; qna?: { question: string; answer: string }[]; error?: string }>;
      const allAlerts = valid.flatMap(d => {
        const propName = d.property_name || '';
        return (d.alerts || []).map(a => ({
          ...a,
          severity: a.severity as Alert['severity'],
          title: isMulti && propName ? `[${propName}] ${a.title}` : a.title,
        }));
      });
      const aiQna: QnA[] = valid.flatMap(d => {
        const propName = d.property_name || '';
        return (d.qna || []).map(q => ({
          ...q,
          question: isMulti && propName ? `[${propName}] ${q.question}` : q.question,
          saved: false,
        }));
      });
      const severityOrder = { high: 0, medium: 1, low: 2 };
      allAlerts.sort((a, b) => (severityOrder[a.severity] ?? 1) - (severityOrder[b.severity] ?? 1));
      setAlerts(allAlerts);

      const errors = valid.filter(d => d.error).map(d => d.error);
      if (errors.length) setError(errors[0] || null);
      setExpandedAlert(0);

      // Load saved questions — show them immediately with "loading" answers
      const savedQs = loadSavedQuestions();
      const savedQna: QnA[] = savedQs.map(q => ({ question: q, answer: '', saved: true, loading: true }));
      setQna([...savedQna, ...aiQna]);
      setLoading(false);

      // Recalculate answers for saved questions in parallel
      if (savedQs.length > 0) {
        const primaryId = effectiveIds[0];
        const answers = await Promise.all(savedQs.map(q => recalcSavedAnswer(q, primaryId)));
        setQna(prev => prev.map(item => {
          if (!item.saved) return item;
          const idx = savedQs.indexOf(item.question);
          if (idx >= 0) return { ...item, answer: answers[idx], loading: false };
          return item;
        }));
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load');
      setLoading(false);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [effectiveIds.join(','), recalcSavedAnswer]);

  useEffect(() => { loadInsights(); }, [loadInsights]);

  // Listen for saved-questions changes from other components
  useEffect(() => {
    const handler = () => loadInsights();
    window.addEventListener('saved-questions-changed', handler);
    return () => window.removeEventListener('saved-questions-changed', handler);
  }, [loadInsights]);

  const handleRemoveSaved = (question: string, e: React.MouseEvent) => {
    e.stopPropagation();
    removeSavedQuestion(question);
  };

  const savedCount = qna.length;

  return (
    <div className="bg-white rounded-xl border border-slate-200 overflow-hidden h-fit">
      {/* Header */}
      <div
        className="px-4 py-2 border-b border-slate-200 bg-gradient-to-r from-violet-50 to-indigo-50 cursor-pointer select-none"
        onClick={toggleCollapsed}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Sparkles className="w-3.5 h-3.5 text-violet-500" />
            <h3 className="text-xs font-semibold text-slate-800">AI Insights</h3>
          </div>
          <div className="flex items-center gap-1">
            <button
              onClick={(e) => { e.stopPropagation(); loadInsights(true); }}
              disabled={loading}
              className="p-1 hover:bg-white/60 rounded transition-colors disabled:opacity-50"
            >
              <RefreshCw className={`w-3.5 h-3.5 text-slate-400 ${loading ? 'animate-spin' : ''}`} />
            </button>
            <ChevronDown className={`w-4 h-4 text-slate-400 transition-transform duration-200 ${collapsed ? '-rotate-90' : ''}`} />
          </div>
        </div>
      </div>

      <div className={`overflow-hidden transition-all duration-300 ease-in-out ${collapsed ? 'max-h-0' : 'max-h-[2000px]'}`}>
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
          {savedCount > 0 && <span className="px-1.5 py-0.5 text-[10px] bg-indigo-100 text-indigo-600 rounded-full">{savedCount}</span>}
        </button>
      </div>

      {/* Content */}
      <div className="p-3">
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
              <div className="text-xs text-slate-400 text-center py-4 col-span-full">No Q&A generated — ask a question via the search bar or AI chat to save it here</div>
            )}
            {qna.map((item, i) => {
              const isOpen = expandedQna === i;
              const isSaved = item.saved;
              return (
                <div key={i} className={`rounded-lg border overflow-hidden ${isSaved ? 'border-violet-200 bg-violet-50/50' : 'border-indigo-100 bg-indigo-50/50'}`}>
                  <button
                    onClick={() => setExpandedQna(isOpen ? null : i)}
                    className="w-full px-3 py-2.5 flex items-start gap-2 text-left"
                  >
                    <MessageCircleQuestion className={`w-4 h-4 flex-shrink-0 mt-0.5 ${isSaved ? 'text-violet-400' : 'text-indigo-400'}`} />
                    <span className="text-xs font-medium text-slate-800 flex-1">{item.question}</span>
                    <div className="flex items-center gap-1 flex-shrink-0">
                      {isSaved && (
                        <span
                          onClick={(e) => handleRemoveSaved(item.question, e)}
                          className="p-0.5 rounded hover:bg-red-100 text-slate-300 hover:text-red-500 transition-colors"
                          title="Remove saved question"
                        >
                          <X className="w-3.5 h-3.5" />
                        </span>
                      )}
                      {isOpen ? <ChevronUp className="w-3.5 h-3.5 text-slate-400" /> : <ChevronDown className="w-3.5 h-3.5 text-slate-400" />}
                    </div>
                  </button>
                  {isOpen && (
                    <div className="px-3 pb-3 ml-6">
                      {item.loading ? (
                        <div className="flex items-center gap-2 text-[11px] text-slate-400">
                          <Loader2 className="w-3 h-3 animate-spin" />
                          Recalculating answer...
                        </div>
                      ) : (
                        <p className="text-[11px] text-slate-700 leading-relaxed whitespace-pre-wrap">{item.answer}</p>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
      </div>
    </div>
  );
}
