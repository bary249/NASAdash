/**
 * KPICard - Metric card matching the new design
 * Shows value, comparison, and trend indicator
 */
import { ReactNode } from 'react';
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';
import { InfoTooltip } from './InfoTooltip';

type TrendDirection = 'up' | 'down' | 'flat';
type CardVariant = 'default' | 'highlight' | 'warning' | 'success';

interface KPICardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  timeLabel?: string;
  comparison?: {
    label: string;
    value: string | number;
  };
  trend?: {
    value: number;
    direction: TrendDirection;
    isPositive?: boolean; // true = green for up, false = green for down
  };
  variant?: CardVariant;
  onClick?: () => void;
  icon?: ReactNode;
  tooltip?: string;
  children?: ReactNode;
  isMock?: boolean; // Show "mock" tag for hardcoded values
  isCalc?: boolean; // Show "calc" tag for calculated values
}

export function KPICard({
  title,
  value,
  subtitle,
  timeLabel,
  comparison,
  trend,
  variant = 'default',
  onClick,
  icon,
  tooltip,
  children,
  isMock = false,
  isCalc = false,
}: KPICardProps) {
  const variantStyles: Record<CardVariant, string> = {
    default: 'bg-white border-slate-200 hover:border-slate-300',
    highlight: 'bg-indigo-50 border-indigo-200 hover:border-indigo-300',
    warning: 'bg-amber-50 border-amber-200 hover:border-amber-300',
    success: 'bg-emerald-50 border-emerald-200 hover:border-emerald-300',
  };

  const getTrendColor = () => {
    if (!trend) return '';
    const isGood = trend.isPositive !== undefined 
      ? (trend.direction === 'up') === trend.isPositive
      : trend.direction === 'up';
    return isGood ? 'text-emerald-600' : 'text-rose-600';
  };

  const TrendIcon = trend?.direction === 'up' ? TrendingUp : trend?.direction === 'down' ? TrendingDown : Minus;

  return (
    <div
      onClick={onClick}
      className={`
        rounded-xl border p-4 transition-all duration-200
        ${variantStyles[variant]}
        ${onClick ? 'cursor-pointer hover:shadow-md' : ''}
      `}
    >
      {/* Header with title and icon */}
      <div className="flex items-start justify-between mb-2">
        <div className="flex items-center gap-1">
          <span className="text-xs font-medium text-slate-500 uppercase tracking-wide">
            {title}
          </span>
          {timeLabel && (
            <span className="text-[9px] text-slate-400 font-normal normal-case tracking-normal">
              {timeLabel}
            </span>
          )}
          {isMock && (
            <span className="px-1 py-0.5 text-[8px] font-medium bg-amber-100 text-amber-700 rounded">
              mock
            </span>
          )}
          {isCalc && (
            <span className="px-1 py-0.5 text-[8px] font-medium bg-sky-100 text-sky-700 rounded">
              calc
            </span>
          )}
        </div>
        <div className="flex items-center gap-1.5">
          {icon && <div className="text-slate-400">{icon}</div>}
          {tooltip && <InfoTooltip text={tooltip} />}
        </div>
      </div>

      {/* Main Value */}
      <div className="flex items-baseline gap-2 min-w-0">
        <span className="text-2xl font-bold text-slate-900 truncate">{value}</span>
        {trend && (
          <div className={`flex items-center gap-0.5 text-xs font-medium whitespace-nowrap ${getTrendColor()}`}>
            <TrendIcon className="w-3 h-3 flex-shrink-0" />
            <span>{trend.value > 0 ? '+' : ''}{trend.value}%</span>
          </div>
        )}
      </div>

      {/* Subtitle */}
      {subtitle && (
        <p className="text-xs text-slate-500 mt-1">{subtitle}</p>
      )}

      {/* Comparison */}
      {comparison && (
        <p className="text-xs text-slate-400 mt-1">
          {comparison.label} <span className="font-medium text-slate-600">{comparison.value}</span>
        </p>
      )}

      {/* Custom children (for funnel, etc.) */}
      {children}
    </div>
  );
}

/**
 * FunnelKPICard - Special variant for leasing funnel visualization
 */
interface FunnelKPICardProps {
  leads: number;
  tours: number;
  applications: number;
  leasesSigned: number;
  sightUnseen?: number;
  tourToApp?: number;
  timeLabel?: string;
  onClick?: () => void;
  priorLeads?: number;
  priorTours?: number;
  priorApplications?: number;
  priorLeasesSigned?: number;
  priorPeriodLabel?: string;
}

function PeriodDelta({ current, prior, noData }: { current: number; prior?: number; noData?: boolean }) {
  if (prior == null || prior === 0) return null;
  // Don't show misleading delta when current period has no data at all
  if (noData) return <div className="text-[10px] text-slate-400 mt-0.5">prev: {prior}</div>;
  const diff = current - prior;
  const pct = Math.round((diff / prior) * 100);
  if (pct === 0) return (
    <div className="text-[10px] text-slate-400 mt-0.5">vs {prior}</div>
  );
  return (
    <div className={`text-[10px] font-medium mt-0.5 ${pct > 0 ? 'text-emerald-600' : 'text-rose-500'}`}>
      {pct > 0 ? '▲' : '▼'} {Math.abs(pct)}% <span className="font-normal text-slate-400">vs {prior}</span>
    </div>
  );
}

export function FunnelKPICard({ leads, tours, applications, leasesSigned, sightUnseen: _sightUnseen = 0, tourToApp: _tourToApp = 0, timeLabel, onClick, priorLeads, priorTours, priorApplications, priorLeasesSigned, priorPeriodLabel }: FunnelKPICardProps) {
  const noCurrentData = leads === 0 && tours === 0 && applications === 0 && leasesSigned === 0;
  const stages = [
    { label: 'Leads', value: leads, prior: priorLeads },
    { label: 'Tours', value: tours, prior: priorTours },
    { label: 'Apps', value: applications, prior: priorApplications },
    { label: 'Signed', value: leasesSigned, prior: priorLeasesSigned },
  ];

  return (
    <div
      onClick={onClick}
      className={`
        rounded-xl border border-slate-200 p-4 bg-white transition-all duration-200 overflow-hidden
        ${onClick ? 'cursor-pointer hover:shadow-md hover:border-slate-300' : ''}
      `}
    >
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-1">
          <span className="text-xs font-medium text-slate-500 uppercase tracking-wide">Leasing Funnel</span>
          <InfoTooltip text="Leads = new prospects whose first-ever activity falls within this period (e.g. guest card, first email, first call). Tours = unique prospects who visited the property. Apps = unique prospects who applied, pre-qualified, or received a quote. Signed = unique prospects who reached 'Leased' status. All counts are deduplicated by prospect name. Comparison shows the equivalent prior period (e.g. Last 7d compares to the 7 days before that). Source: RealPage Activity Report." />
        </div>
        <span className="text-[10px] text-slate-400">{timeLabel || 'MTD'}</span>
      </div>

      <div className="grid grid-cols-4 gap-2">
        {stages.map((stage) => (
          <div key={stage.label} className="text-center">
            <div className="text-2xl font-bold text-slate-900">{stage.value}</div>
            <div className="text-[11px] text-slate-500 mt-0.5">{stage.label}</div>
            <PeriodDelta current={stage.value} prior={stage.prior} noData={noCurrentData} />
          </div>
        ))}
      </div>
      {priorPeriodLabel && (priorLeads != null || priorTours != null) && (
        <div className="text-[10px] text-slate-400 text-right mt-2">vs {priorPeriodLabel}</div>
      )}
    </div>
  );
}

/**
 * VacantKPICard - Special variant for vacant units with status badges
 */
interface VacantKPICardProps {
  total: number;
  ready: number;
  agedCount?: number;
  timeLabel?: string;
  tooltip?: string;
  onClick?: () => void;
}

export function VacantKPICard({ total, ready, agedCount, timeLabel, tooltip, onClick }: VacantKPICardProps) {
  return (
    <div
      onClick={onClick}
      className={`
        rounded-xl border border-slate-200 p-4 bg-white transition-all duration-200
        ${onClick ? 'cursor-pointer hover:shadow-md hover:border-slate-300' : ''}
      `}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1">
          <span className="text-xs font-medium text-slate-500 uppercase tracking-wide">
            Vacant
          </span>
          {timeLabel && (
            <span className="text-[9px] text-slate-400 font-normal normal-case tracking-normal">
              {timeLabel}
            </span>
          )}
        </div>
        {tooltip && <InfoTooltip text={tooltip} />}
      </div>

      <div className="text-3xl font-bold text-slate-900 mt-2">{total}</div>

      <div className="flex items-center gap-2 mt-2">
        <span className="px-2 py-0.5 bg-emerald-100 text-emerald-700 text-xs font-medium rounded-full">
          {ready} Ready
        </span>
        {agedCount !== undefined && agedCount > 0 && (
          <span className="px-2 py-0.5 bg-rose-100 text-rose-700 text-xs font-medium rounded-full">
            {agedCount} unit &gt;90 days
          </span>
        )}
      </div>
    </div>
  );
}
