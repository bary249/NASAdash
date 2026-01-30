import { Calendar } from 'lucide-react';
import type { Timeframe } from '../types';

interface TimeframeSelectorProps {
  value: Timeframe;
  onChange: (timeframe: Timeframe) => void;
  periodStart?: string;
  periodEnd?: string;
}

const TIMEFRAME_OPTIONS: { value: Timeframe; label: string; description: string }[] = [
  { value: 'cm', label: 'Current Month', description: '1st of month to today' },
  { value: 'pm', label: 'Previous Month', description: 'Full previous month' },
  { value: 'ytd', label: 'Year-to-Date', description: 'Jan 1st to today' },
];

export function TimeframeSelector({ value, onChange, periodStart, periodEnd }: TimeframeSelectorProps) {
  return (
    <div className="flex flex-wrap items-center gap-3 p-3 bg-gray-50 rounded-lg border">
      <div className="flex items-center gap-2">
        <Calendar className="w-4 h-4 text-gray-500" />
        <span className="text-sm font-medium text-gray-600">Timeframe:</span>
      </div>
      <div className="flex gap-1">
        {TIMEFRAME_OPTIONS.map((opt) => (
          <button
            key={opt.value}
            onClick={() => onChange(opt.value)}
            title={opt.description}
            className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
              value === opt.value
                ? 'bg-blue-600 text-white'
                : 'bg-white text-gray-600 border hover:bg-gray-100'
            }`}
          >
            {opt.label}
          </button>
        ))}
      </div>
      {periodStart && periodEnd && (
        <span className="text-xs text-gray-500 ml-auto">
          {periodStart} → {periodEnd}
        </span>
      )}
    </div>
  );
}
