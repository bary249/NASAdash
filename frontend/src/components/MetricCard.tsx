import { useState } from 'react';
import { LucideIcon, Info } from 'lucide-react';

export type HealthStatus = 'good' | 'warning' | 'critical' | 'neutral';

export interface MetricThreshold {
  good: number;      // >= this = green
  warning: number;   // >= this = yellow, < good
  // < warning = red
  higherIsBetter?: boolean; // default true
}

interface MetricCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  icon?: LucideIcon;
  trend?: 'up' | 'down' | 'neutral';
  onClick?: () => void;
  definition?: string;  // Tooltip explanation of what this metric means
  health?: HealthStatus; // Manual health status override
  threshold?: MetricThreshold; // Auto-calculate health from value
  rawValue?: number; // Numeric value for threshold calculation (if value is formatted string)
}

// Calculate health status from threshold
function calculateHealth(value: number, threshold: MetricThreshold): HealthStatus {
  const higherIsBetter = threshold.higherIsBetter !== false;
  
  if (higherIsBetter) {
    if (value >= threshold.good) return 'good';
    if (value >= threshold.warning) return 'warning';
    return 'critical';
  } else {
    // Lower is better (e.g., aged vacancy, exposure)
    if (value <= threshold.good) return 'good';
    if (value <= threshold.warning) return 'warning';
    return 'critical';
  }
}

export function MetricCard({ 
  title, 
  value, 
  subtitle, 
  icon: Icon, 
  trend, 
  onClick,
  definition,
  health,
  threshold,
  rawValue,
}: MetricCardProps) {
  const [showTooltip, setShowTooltip] = useState(false);

  // Determine health status
  let calculatedHealth: HealthStatus = 'neutral';
  if (health) {
    calculatedHealth = health;
  } else if (threshold) {
    const numValue = rawValue ?? (typeof value === 'number' ? value : parseFloat(String(value)));
    if (!isNaN(numValue)) {
      calculatedHealth = calculateHealth(numValue, threshold);
    }
  }

  const healthColors = {
    good: 'border-l-4 border-l-emerald-500 bg-gradient-to-br from-emerald-50/80 to-white',
    warning: 'border-l-4 border-l-amber-500 bg-gradient-to-br from-amber-50/80 to-white',
    critical: 'border-l-4 border-l-rose-500 bg-gradient-to-br from-rose-50/80 to-white',
    neutral: 'bg-white border border-venn-sand/60',
  };

  const healthTextColors = {
    good: 'text-emerald-700',
    warning: 'text-amber-700',
    critical: 'text-rose-700',
    neutral: 'text-slate-800',
  };

  const healthIndicator = {
    good: '●',
    warning: '●',
    critical: '●',
    neutral: '',
  };

  const indicatorColors = {
    good: 'text-emerald-500',
    warning: 'text-amber-500',
    critical: 'text-rose-500',
    neutral: '',
  };

  const trendColors = {
    up: 'text-emerald-600',
    down: 'text-rose-600',
    neutral: 'text-slate-600',
  };

  // Use health color for value, or fall back to trend color
  const valueColor = calculatedHealth !== 'neutral' 
    ? healthTextColors[calculatedHealth] 
    : (trend ? trendColors[trend] : 'text-gray-900');

  return (
    <div
      onClick={onClick}
      className={`rounded-venn-lg p-5 relative shadow-sm ${healthColors[calculatedHealth]} ${onClick ? 'cursor-pointer hover:shadow-venn hover:scale-[1.01] transition-all duration-300' : 'transition-all duration-300'}`}
    >
      {/* Definition tooltip trigger */}
      {definition && (
        <div 
          className="absolute top-4 right-4"
          onMouseEnter={() => setShowTooltip(true)}
          onMouseLeave={() => setShowTooltip(false)}
        >
          <Info className="w-4 h-4 text-slate-400 hover:text-venn-amber cursor-help transition-colors" />
          {showTooltip && (
            <div className="absolute right-0 top-6 z-50 w-64 p-4 bg-venn-navy text-white text-xs rounded-venn shadow-lg border border-venn-charcoal">
              <div className="font-semibold mb-1.5 text-venn-amber">{title}</div>
              <div className="text-slate-300 leading-relaxed">{definition}</div>
              <div className="absolute -top-1 right-3 w-2 h-2 bg-venn-navy rotate-45" />
            </div>
          )}
        </div>
      )}

      <div className="flex items-start justify-between">
        <div className="flex-1">
          <div className="flex items-center gap-1.5">
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">{title}</p>
            {calculatedHealth !== 'neutral' && (
              <span className={`text-xs ${indicatorColors[calculatedHealth]}`}>
                {healthIndicator[calculatedHealth]}
              </span>
            )}
          </div>
          <p className={`text-2xl font-bold mt-1.5 ${valueColor}`}>
            {value}
          </p>
          {subtitle && <p className="text-xs text-slate-500 mt-1">{subtitle}</p>}
        </div>
        {Icon && (
          <div className="ml-2 p-2 rounded-lg bg-white/60">
            <Icon className={`w-5 h-5 ${calculatedHealth !== 'neutral' ? indicatorColors[calculatedHealth] : (trend ? trendColors[trend] : 'text-slate-400')}`} />
          </div>
        )}
      </div>
    </div>
  );
}
