/**
 * AIResponseModal - Displays AI response with table data and suggested actions
 * Matches design: Modal overlay with natural language summary, data table, action buttons
 */
import { X, Sparkles } from 'lucide-react';

export type RiskLevel = 'HIGH' | 'MED' | 'LOW';

export interface AITableColumn {
  key: string;
  label: string;
  format?: (value: unknown) => string | React.ReactNode;
}

export interface AITableRow {
  [key: string]: unknown;
  riskLevel?: RiskLevel;
}

export interface SuggestedAction {
  label: string;
  onClick?: () => void;
}

interface AIResponseModalProps {
  isOpen: boolean;
  onClose: () => void;
  query: string;
  summary: string;
  columns: AITableColumn[];
  data: AITableRow[];
  suggestedActions?: SuggestedAction[];
  isLoading?: boolean;
}

// Format summary text - clean up markdown and emojis for display
function formatSummaryText(text: string): string {
  if (!text) return '';
  
  return text
    // Remove emoji headers and ## markers
    .replace(/[#🚨📍🏆⚠️💰📊🎯📈]+\s*/g, '')
    // Remove bold markdown
    .replace(/\*\*/g, '')
    // Clean up excessive newlines
    .replace(/\n{3,}/g, '\n\n')
    .trim();
}

export function AIResponseModal({
  isOpen,
  onClose,
  query,
  summary,
  columns,
  data,
  suggestedActions = [],
  isLoading = false,
}: AIResponseModalProps) {
  if (!isOpen) return null;

  const getRiskBadge = (level: RiskLevel) => {
    const styles: Record<RiskLevel, string> = {
      HIGH: 'bg-rose-100 text-rose-700 border-rose-200',
      MED: 'bg-amber-100 text-amber-700 border-amber-200',
      LOW: 'bg-emerald-100 text-emerald-700 border-emerald-200',
    };
    return (
      <span className={`px-2 py-0.5 text-xs font-semibold rounded border ${styles[level]}`}>
        {level}
      </span>
    );
  };

  const formatCellValue = (column: AITableColumn, value: unknown): React.ReactNode => {
    if (column.format) return column.format(value);
    if (value === null || value === undefined) return '—';
    if (typeof value === 'boolean') return value ? 'Yes' : 'No';
    return String(value);
  };

  return (
    <>
      {/* Backdrop */}
      <div 
        className="fixed inset-0 bg-black/50 backdrop-blur-sm z-40 transition-opacity"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="fixed inset-x-4 top-32 bottom-4 md:inset-x-auto md:left-1/2 md:-translate-x-1/2 md:w-[900px] md:max-h-[calc(100vh-180px)] z-50 flex flex-col">
        <div className="bg-white rounded-2xl shadow-2xl flex flex-col max-h-full overflow-hidden">
          {/* Header */}
          <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 bg-slate-50">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-lg bg-indigo-100 flex items-center justify-center">
                <Sparkles className="w-4 h-4 text-indigo-600" />
              </div>
              <div>
                <p className="text-sm text-slate-500">AI Response</p>
                <p className="text-xs text-slate-400 truncate max-w-md">{query}</p>
              </div>
            </div>
            <button
              onClick={onClose}
              className="p-2 hover:bg-slate-200 rounded-lg transition-colors"
            >
              <X className="w-5 h-5 text-slate-500" />
            </button>
          </div>

          {/* Content */}
          <div className="flex-1 overflow-y-auto p-6">
            {isLoading ? (
              <div className="flex flex-col items-center justify-center py-12">
                <div className="w-8 h-8 border-3 border-indigo-600 border-t-transparent rounded-full animate-spin" />
                <p className="mt-4 text-sm text-slate-500">Analyzing your data...</p>
              </div>
            ) : (
              <>
                {/* Summary - clean paragraph format */}
                <div className="mb-6">
                  <p className="text-slate-700 leading-relaxed text-[15px] whitespace-pre-line">
                    {formatSummaryText(summary)}
                  </p>
                </div>

                {/* Data Table - clean design without collapsible header */}
                {data.length > 0 && (
                  <div className="overflow-x-auto mb-6">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-slate-200">
                          {columns.map((col) => (
                            <th 
                              key={col.key}
                              className="px-3 py-3 text-left text-xs font-semibold text-slate-500"
                            >
                              {col.label}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100">
                        {data.map((row, rowIndex) => (
                          <tr key={rowIndex} className="hover:bg-slate-50 transition-colors">
                            {columns.map((col) => (
                              <td key={col.key} className="px-3 py-3 text-slate-700">
                                {col.key === 'riskLevel' && row.riskLevel ? (
                                  getRiskBadge(row.riskLevel as RiskLevel)
                                ) : (
                                  formatCellValue(col, row[col.key])
                                )}
                              </td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}

                {/* Suggested Actions */}
                {suggestedActions.length > 0 && (
                  <div>
                    <p className="text-sm font-medium text-slate-700 mb-3">Suggested actions:</p>
                    <div className="flex flex-wrap gap-2">
                      {suggestedActions.map((action, i) => (
                        <button
                          key={i}
                          onClick={action.onClick}
                          className="px-4 py-2 text-sm font-medium text-slate-700 bg-white border border-slate-300 rounded-full hover:bg-slate-50 hover:border-slate-400 transition-all flex items-center gap-2"
                        >
                          {action.label}
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      </div>
    </>
  );
}

/**
 * Helper function to format common cell values
 */
export const cellFormatters = {
  currency: (value: unknown) => {
    if (value === null || value === undefined) return '—';
    const num = typeof value === 'string' ? parseFloat(value) : Number(value);
    return `US$${num.toLocaleString()}`;
  },
  date: (value: unknown) => {
    if (!value) return '—';
    return String(value);
  },
  days: (value: unknown) => {
    if (!value) return '—';
    return `${value} days`;
  },
};
