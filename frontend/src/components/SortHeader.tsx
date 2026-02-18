import { ChevronUp, ChevronDown, ChevronsUpDown } from 'lucide-react';
import type { SortDir } from '../hooks/useSortable';

interface SortHeaderProps {
  label: string;
  column: string;
  sortKey: string | null;
  sortDir: SortDir;
  onSort: (key: string) => void;
  align?: 'left' | 'right' | 'center';
  className?: string;
}

export function SortHeader({ label, column, sortKey, sortDir, onSort, align = 'left', className = '' }: SortHeaderProps) {
  const isActive = sortKey === column;
  const alignClass = align === 'right' ? 'text-right justify-end' : align === 'center' ? 'text-center justify-center' : 'text-left';
  return (
    <th
      className={`px-4 py-2 text-xs font-medium text-slate-500 uppercase tracking-wider cursor-pointer select-none hover:text-slate-700 transition-colors ${alignClass} ${className}`}
      onClick={() => onSort(column)}
    >
      <span className={`inline-flex items-center gap-0.5 ${align === 'right' ? 'flex-row-reverse' : ''}`}>
        {label}
        {isActive ? (
          sortDir === 'asc' ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />
        ) : (
          <ChevronsUpDown className="w-3 h-3 opacity-30" />
        )}
      </span>
    </th>
  );
}
