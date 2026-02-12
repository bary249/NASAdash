/**
 * ResidentRiskSection - Churn & Delinquency Prediction Dashboard
 *
 * Displays property-level risk scores from the Snowflake scoring engine.
 * Scores: 0 = high risk, 1 = healthy.
 * Risk tiers use portfolio-wide percentile thresholds on the at-risk group
 * (residents who have NOT given notice). HIGH = bottom 25%, MED = 25-75%, LOW = top 25%.
 */
import { useState, useEffect } from 'react';
import { ShieldAlert, TrendingDown, Users, Smartphone, Clock, Wrench, LogOut, AlertTriangle } from 'lucide-react';
import { SectionHeader } from './SectionHeader';
import { api } from '../api';

interface RiskDistribution {
  avg_score: number;
  median_score: number;
  high_risk: number;
  medium_risk: number;
  low_risk: number;
  threshold_high?: number;
  threshold_low?: number;
}

interface RiskInsights {
  pct_scheduled_moveout: number;
  pct_with_app: number;
  avg_tenure_months: number;
  avg_rent: number;
  avg_open_tickets: number;
}

interface RiskData {
  property_id: string;
  snapshot_date: string;
  total_scored: number;
  notice_count: number;
  at_risk_total: number;
  churn: RiskDistribution;
  delinquency: RiskDistribution;
  insights: RiskInsights;
}

interface Props {
  propertyId: string;
}

function ScoreGauge({ label, score, color }: { label: string; score: number; color: string }) {
  const pct = Math.round(score * 100);
  const circumference = 2 * Math.PI * 40;
  const offset = circumference - (score * circumference);

  return (
    <div className="flex flex-col items-center">
      <div className="relative w-24 h-24">
        <svg className="w-24 h-24 -rotate-90" viewBox="0 0 100 100">
          <circle cx="50" cy="50" r="40" fill="none" stroke="#e2e8f0" strokeWidth="8" />
          <circle
            cx="50" cy="50" r="40" fill="none"
            stroke={color}
            strokeWidth="8"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            strokeLinecap="round"
            className="transition-all duration-700"
          />
        </svg>
        <div className="absolute inset-0 flex items-center justify-center">
          <span className="text-xl font-bold text-slate-800">{pct}%</span>
        </div>
      </div>
      <span className="text-xs font-medium text-slate-500 mt-2">{label}</span>
    </div>
  );
}

function RiskBar({ high, medium, low, total }: { high: number; medium: number; low: number; total: number }) {
  if (total === 0) return null;
  const hPct = (high / total) * 100;
  const mPct = (medium / total) * 100;
  const lPct = (low / total) * 100;

  return (
    <div className="w-full">
      <div className="flex h-3 rounded-full overflow-hidden bg-slate-100">
        {hPct > 0 && (
          <div className="bg-red-500 transition-all duration-500" style={{ width: `${hPct}%` }} title={`High: ${high}`} />
        )}
        {mPct > 0 && (
          <div className="bg-amber-400 transition-all duration-500" style={{ width: `${mPct}%` }} title={`Medium: ${medium}`} />
        )}
        {lPct > 0 && (
          <div className="bg-emerald-500 transition-all duration-500" style={{ width: `${lPct}%` }} title={`Low: ${low}`} />
        )}
      </div>
      <div className="flex justify-between mt-1.5 text-xs text-slate-500">
        <span className="flex items-center gap-1">
          <span className="w-2 h-2 rounded-full bg-red-500 inline-block" />
          High {high}
        </span>
        <span className="flex items-center gap-1">
          <span className="w-2 h-2 rounded-full bg-amber-400 inline-block" />
          Medium {medium}
        </span>
        <span className="flex items-center gap-1">
          <span className="w-2 h-2 rounded-full bg-emerald-500 inline-block" />
          Low {low}
        </span>
      </div>
    </div>
  );
}

function InsightCard({ icon: Icon, label, value, subtitle, color }: {
  icon: typeof Users;
  label: string;
  value: string;
  subtitle?: string;
  color: string;
}) {
  return (
    <div className="bg-slate-50 rounded-xl p-4">
      <div className="flex items-center gap-2 mb-2">
        <Icon className={`w-4 h-4 ${color}`} />
        <span className="text-xs font-medium text-slate-500 uppercase">{label}</span>
      </div>
      <div className="text-lg font-bold text-slate-800">{value}</div>
      {subtitle && <div className="text-xs text-slate-400 mt-0.5">{subtitle}</div>}
    </div>
  );
}

export function ResidentRiskSection({ propertyId }: Props) {
  const [data, setData] = useState<RiskData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setData(null);
    setError(null);
    setLoading(true);

    api.getRiskScores(propertyId)
      .then(setData)
      .catch(err => {
        if (err.message?.includes('404')) {
          setData(null);
        } else {
          setError(err.message || 'Failed to load risk scores');
        }
      })
      .finally(() => setLoading(false));
  }, [propertyId]);

  if (loading) {
    return (
      <div className="venn-section animate-pulse">
        <div className="h-8 bg-slate-200 rounded w-48 mb-4" />
        <div className="h-48 bg-slate-100 rounded" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="venn-section">
        <SectionHeader title="Resident Risk Scores" icon={ShieldAlert} />
        <div className="text-center py-8 text-red-500">{error}</div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="venn-section">
        <SectionHeader title="Resident Risk Scores" icon={ShieldAlert} />
        <div className="text-center py-8 text-slate-500">
          No risk score data available for this property.
          <br />
          <span className="text-xs text-slate-400">Run the scoring engine sync to populate data.</span>
        </div>
      </div>
    );
  }

  const { churn, delinquency, insights } = data;
  const noticePct = data.total_scored > 0 ? Math.round((data.notice_count / data.total_scored) * 100) : 0;
  const atRiskPct = 100 - noticePct;

  return (
    <div className="space-y-6">
      <div className="bg-white rounded-xl border border-slate-200 p-6">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h3 className="text-lg font-semibold text-slate-800 flex items-center gap-2">
              <ShieldAlert className="w-5 h-5 text-indigo-600" />
              Resident Risk Scores
            </h3>
            <p className="text-xs text-slate-400 mt-1">
              AI-powered predictions · {data.total_scored} residents scored · {data.snapshot_date}
            </p>
          </div>
        </div>

        {/* Notice vs At-Risk Summary */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          <div className="bg-rose-50 border border-rose-100 rounded-xl p-4">
            <div className="flex items-center gap-2 mb-2">
              <LogOut className="w-4 h-4 text-rose-500" />
              <span className="text-xs font-medium text-rose-600 uppercase">Gave Notice</span>
            </div>
            <div className="text-2xl font-bold text-rose-700">{data.notice_count}</div>
            <div className="text-xs text-rose-500 mt-1">{noticePct}% of residents — already leaving</div>
          </div>

          <div className="bg-amber-50 border border-amber-100 rounded-xl p-4">
            <div className="flex items-center gap-2 mb-2">
              <AlertTriangle className="w-4 h-4 text-amber-500" />
              <span className="text-xs font-medium text-amber-600 uppercase">At Risk (No Notice)</span>
            </div>
            <div className="text-2xl font-bold text-amber-700">{data.at_risk_total}</div>
            <div className="text-xs text-amber-500 mt-1">{atRiskPct}% of residents — may not renew</div>
          </div>

          <div className="bg-red-50 border border-red-100 rounded-xl p-4">
            <div className="flex items-center gap-2 mb-2">
              <ShieldAlert className="w-4 h-4 text-red-500" />
              <span className="text-xs font-medium text-red-600 uppercase">High Churn Risk</span>
            </div>
            <div className="text-2xl font-bold text-red-700">{churn.high_risk}</div>
            <div className="text-xs text-red-500 mt-1">Bottom 25% — likely won't renew</div>
          </div>

          <div className="bg-blue-50 border border-blue-100 rounded-xl p-4">
            <div className="flex items-center gap-2 mb-2">
              <TrendingDown className="w-4 h-4 text-blue-500" />
              <span className="text-xs font-medium text-blue-600 uppercase">High Delinq Risk</span>
            </div>
            <div className="text-2xl font-bold text-blue-700">{delinquency.high_risk}</div>
            <div className="text-xs text-blue-500 mt-1">Bottom 25% — likely to owe</div>
          </div>
        </div>

        {/* Risk Distribution (At-Risk Group Only) */}
        {data.at_risk_total > 0 ? (
          <div className="grid md:grid-cols-2 gap-8 mb-8">
            {/* Churn */}
            <div className="bg-slate-50 rounded-xl p-5">
              <h4 className="text-sm font-semibold text-slate-700 mb-1">Churn Risk Distribution</h4>
              <p className="text-xs text-slate-400 mb-4">{data.at_risk_total} residents without notice · percentile-ranked</p>
              <div className="flex items-center gap-6">
                <ScoreGauge label="Avg Score" score={churn.avg_score} color={churn.avg_score >= 0.6 ? '#10b981' : churn.avg_score >= 0.4 ? '#f59e0b' : '#ef4444'} />
                <div className="flex-1">
                  <RiskBar
                    high={churn.high_risk}
                    medium={churn.medium_risk}
                    low={churn.low_risk}
                    total={data.at_risk_total}
                  />
                </div>
              </div>
            </div>

            {/* Delinquency */}
            <div className="bg-slate-50 rounded-xl p-5">
              <h4 className="text-sm font-semibold text-slate-700 mb-1">Delinquency Risk Distribution</h4>
              <p className="text-xs text-slate-400 mb-4">{data.at_risk_total} residents without notice · percentile-ranked</p>
              <div className="flex items-center gap-6">
                <ScoreGauge label="Avg Score" score={delinquency.avg_score} color={delinquency.avg_score >= 0.6 ? '#10b981' : delinquency.avg_score >= 0.4 ? '#f59e0b' : '#ef4444'} />
                <div className="flex-1">
                  <RiskBar
                    high={delinquency.high_risk}
                    medium={delinquency.medium_risk}
                    low={delinquency.low_risk}
                    total={data.at_risk_total}
                  />
                </div>
              </div>
            </div>
          </div>
        ) : (
          <div className="bg-rose-50 border border-rose-200 rounded-xl p-6 mb-8 text-center">
            <p className="text-sm text-rose-700 font-medium">All {data.total_scored} scored residents have given notice.</p>
            <p className="text-xs text-rose-500 mt-1">No at-risk residents to analyze — all are already scheduled to move out.</p>
          </div>
        )}

        {/* Contributing Factors */}
        <h4 className="text-sm font-semibold text-slate-700 mb-3">Contributing Factors</h4>
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          <InsightCard
            icon={TrendingDown}
            label="Gave Notice"
            value={`${noticePct}%`}
            subtitle={`${data.notice_count} of ${data.total_scored}`}
            color="text-rose-500"
          />
          <InsightCard
            icon={Smartphone}
            label="App Adoption"
            value={`${insights.pct_with_app.toFixed(0)}%`}
            subtitle="use the Venn app"
            color="text-indigo-500"
          />
          <InsightCard
            icon={Clock}
            label="Avg Tenure"
            value={`${insights.avg_tenure_months.toFixed(0)} mo`}
            subtitle="months in unit"
            color="text-sky-500"
          />
          <InsightCard
            icon={Users}
            label="Avg Rent"
            value={`$${Math.round(insights.avg_rent).toLocaleString()}`}
            subtitle="per month"
            color="text-emerald-500"
          />
          <InsightCard
            icon={Wrench}
            label="Open Tickets"
            value={insights.avg_open_tickets.toFixed(1)}
            subtitle="avg per resident"
            color="text-amber-500"
          />
        </div>
      </div>
    </div>
  );
}
