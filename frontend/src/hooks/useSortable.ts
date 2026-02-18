import { useState, useMemo } from 'react';

export type SortDir = 'asc' | 'desc';

/**
 * Generic hook for sortable tables.
 * Returns sorted data + state + toggle function.
 * Handles numbers, strings, nulls/blanks (sorted last).
 */
export function useSortable<T>(
  data: T[],
  defaultKey: string | null = null,
  defaultDir: SortDir = 'desc',
) {
  const [sortKey, setSortKey] = useState<string | null>(defaultKey);
  const [sortDir, setSortDir] = useState<SortDir>(defaultDir);

  const toggleSort = (key: string) => {
    if (sortKey === key) {
      if (sortDir === 'desc') setSortDir('asc');
      else { setSortKey(null); setSortDir('desc'); }
    } else {
      setSortKey(key);
      setSortDir('desc');
    }
  };

  const sorted = useMemo(() => {
    if (!sortKey) return data;
    return [...data].sort((a, b) => {
      const av = (a as Record<string, unknown>)[sortKey];
      const bv = (b as Record<string, unknown>)[sortKey];
      const aNull = av == null || av === '' || av === '—' || av === '-';
      const bNull = bv == null || bv === '' || bv === '—' || bv === '-';
      if (aNull && bNull) return 0;
      if (aNull) return 1;
      if (bNull) return -1;
      const an = Number(av);
      const bn = Number(bv);
      if (!isNaN(an) && !isNaN(bn)) {
        return sortDir === 'asc' ? an - bn : bn - an;
      }
      const as = String(av).toLowerCase();
      const bs = String(bv).toLowerCase();
      if (as < bs) return sortDir === 'asc' ? -1 : 1;
      if (as > bs) return sortDir === 'asc' ? 1 : -1;
      return 0;
    });
  }, [data, sortKey, sortDir]);

  return { sorted, sortKey, sortDir, toggleSort };
}
