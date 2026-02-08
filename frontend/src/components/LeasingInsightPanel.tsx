/**
 * LeasingInsightPanel - Right-side panel with dynamic insights
 * Matches design: Leasing Insight panel with DYNAMIC/PRE LEASE toggle
 */
import { useState } from 'react';
import { Heart, Plus, Sparkles } from 'lucide-react';

type InsightMode = 'DYNAMIC' | 'PRE_LEASE';

interface Insight {
  type: 'warning' | 'success' | 'info';
  title: string;
  description: string;
}

interface LeasingInsightPanelProps {
  insights?: Insight[];
  residentCount: number;
  propertyName?: string;
  isMock?: boolean;
}

// Smart insights for each mode
const DYNAMIC_INSIGHTS = {
  description: "Primary residents in good standing whose co-applicants (spouses, roommates, or partners) have",
  insight: "Most co-applicant delays start within the first day — a faster nudge may close the gap.",
  count: 34,
  label: "residents"
};

const PRE_LEASE_INSIGHTS = {
  description: "Prospects who toured in the last 7 days but haven't submitted an application yet",
  insight: "Tuesday and Wednesday tours convert 23% higher — consider prioritizing mid-week showings.",
  count: 12,
  label: "prospects"
};

export function LeasingInsightPanel({ residentCount, propertyName: _propertyName, isMock = true }: LeasingInsightPanelProps) {
  const [mode, setMode] = useState<InsightMode>('DYNAMIC');

  const currentInsight = mode === 'DYNAMIC' ? DYNAMIC_INSIGHTS : PRE_LEASE_INSIGHTS;
  const displayCount = mode === 'DYNAMIC' ? residentCount : PRE_LEASE_INSIGHTS.count;

  return (
    <div className="bg-white rounded-xl border border-slate-200 overflow-hidden h-fit">
      {/* Header */}
      <div className="px-4 py-3 border-b border-slate-200">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <h3 className="text-base font-semibold text-slate-800">Leasing Insight</h3>
            {isMock && (
              <span className="px-1 py-0.5 text-[8px] font-medium bg-amber-100 text-amber-700 rounded">
                mock
              </span>
            )}
          </div>
          <div className="flex items-center gap-2">
            <button className="p-1.5 hover:bg-slate-100 rounded-lg transition-colors">
              <Heart className="w-5 h-5 text-slate-400" />
            </button>
            <button className="p-1.5 hover:bg-slate-100 rounded-lg transition-colors">
              <Plus className="w-5 h-5 text-slate-400" />
            </button>
          </div>
        </div>
      </div>

      <div className="p-4">
        {/* Mode Toggle */}
        <div className="flex gap-2 mb-4">
          <button
            onClick={() => setMode('DYNAMIC')}
            className={`
              px-3 py-1.5 text-xs font-semibold rounded-lg transition-all
              ${mode === 'DYNAMIC' 
                ? 'bg-slate-800 text-white' 
                : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
              }
            `}
          >
            DYNAMIC
          </button>
          <button
            onClick={() => setMode('PRE_LEASE')}
            className={`
              px-3 py-1.5 text-xs font-semibold rounded-lg transition-all
              ${mode === 'PRE_LEASE' 
                ? 'bg-slate-800 text-white' 
                : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
              }
            `}
          >
            PRE LEASE
          </button>
        </div>

        {/* Description */}
        <p className="text-sm text-slate-600 mb-4 leading-relaxed">
          {currentInsight.description}
        </p>

        {/* Insight Card - Purple/Violet style */}
        <div className="bg-violet-50 border border-violet-100 rounded-xl p-4 mb-4">
          <div className="flex items-start gap-3">
            <Sparkles className="w-5 h-5 text-violet-500 flex-shrink-0 mt-0.5" />
            <p className="text-sm text-slate-700 leading-relaxed">
              {currentInsight.insight}
            </p>
          </div>
        </div>

        {/* Count */}
        <div className="flex items-baseline gap-2">
          <span className="text-2xl font-bold text-slate-800">{displayCount}</span>
          <span className="text-sm text-slate-500">{currentInsight.label}</span>
        </div>
      </div>
    </div>
  );
}
