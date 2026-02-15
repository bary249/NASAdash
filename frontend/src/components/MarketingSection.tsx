/**
 * Marketing Section - Primary Advertising Source Evaluation
 * 
 * Embedded inside the Leasing tab. Shows lead sources breakdown table
 * from RealPage Report 4158 (Primary Advertising Source).
 * Supports sorting by any column and timeframe filtering.
 */
import { useState, useEffect, useMemo } from 'react';
import { Megaphone, ChevronDown, ChevronUp, ArrowUpDown, ArrowUp, ArrowDown } from 'lucide-react';
import { api } from '../api';

interface Source {
  source: string;
  new_prospects: number;
  phone_calls: number;
  visits: number;
  return_visits: number;
  leases: number;
  net_leases: number;
  cancelled_denied: number;
  prospect_to_lease_pct: number;
  visit_to_lease_pct: number;
}

interface MarketingData {
  property_id: string;
  date_range: string;
  timeframe: string;
  sources: Source[];
  totals: {
    total_prospects: number;
    total_calls: number;
    total_visits: number;
    total_leases: number;
    total_net_leases: number;
    overall_prospect_to_lease: number;
    overall_visit_to_lease: number;
  };
}

type SortKey = 'source' | 'new_prospects' | 'phone_calls' | 'visits' | 'leases' | 'net_leases' | 'prospect_to_lease_pct';
type SortDir = 'asc' | 'desc';

interface Props {
  propertyId: string;
  propertyIds?: string[];
  timeRange?: 'ytd' | 'mtd' | 'l30' | 'l7';
}

function SortIcon({ column, sortKey, sortDir }: { column: SortKey; sortKey: SortKey; sortDir: SortDir }) {
  if (column !== sortKey) return <ArrowUpDown className="w-3 h-3 text-slate-300 ml-1 inline" />;
  return sortDir === 'asc'
    ? <ArrowUp className="w-3 h-3 text-violet-500 ml-1 inline" />
    : <ArrowDown className="w-3 h-3 text-violet-500 ml-1 inline" />;
}

export default function MarketingSection({ propertyId, propertyIds, timeRange = 'ytd' }: Props) {
  const [data, setData] = useState<MarketingData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showAll, setShowAll] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const [sortKey, setSortKey] = useState<SortKey>('new_prospects');
  const [sortDir, setSortDir] = useState<SortDir>('desc');

  const effectiveIds = propertyIds && propertyIds.length > 0 ? propertyIds : [propertyId];

  // Map timeRange to API timeframe param
  const timeframe = timeRange === 'l30' ? 'l30' : timeRange === 'l7' ? 'l7' : timeRange === 'mtd' ? 'mtd' : 'ytd';

  useEffect(() => {
    if (!effectiveIds.length || !effectiveIds[0]) return;
    setLoading(true);
    setError(null);
    setData(null);

    const fetchAll = async () => {
      try {
        const results = await Promise.all(
          effectiveIds.map(id => api.getMarketing(id, timeframe).catch(() => null))
        );
        const valid = results.filter(Boolean) as MarketingData[];
        if (valid.length === 0) {
          setError('No marketing data available');
          return;
        }
        if (valid.length === 1) {
          setData(valid[0]);
          return;
        }
        // Merge sources by source name across properties
        const sourceMap = new Map<string, Source>();
        for (const d of valid) {
          for (const s of d.sources) {
            const key = s.source.toLowerCase().trim();
            const existing = sourceMap.get(key);
            if (existing) {
              existing.new_prospects += s.new_prospects;
              existing.phone_calls += s.phone_calls;
              existing.visits += s.visits;
              existing.return_visits += s.return_visits;
              existing.leases += s.leases;
              existing.net_leases += s.net_leases;
              existing.cancelled_denied += s.cancelled_denied;
            } else {
              sourceMap.set(key, { ...s });
            }
          }
        }
        // Recompute conversion percentages from merged totals
        const mergedSources = Array.from(sourceMap.values()).map(s => ({
          ...s,
          prospect_to_lease_pct: s.new_prospects > 0 ? Math.round((s.leases / s.new_prospects) * 100) : 0,
          visit_to_lease_pct: s.visits > 0 ? Math.round((s.leases / s.visits) * 100) : 0,
        }));
        // Merge totals
        const totalProspects = mergedSources.reduce((a, s) => a + s.new_prospects, 0);
        const totalCalls = mergedSources.reduce((a, s) => a + s.phone_calls, 0);
        const totalVisits = mergedSources.reduce((a, s) => a + s.visits, 0);
        const totalLeases = mergedSources.reduce((a, s) => a + s.leases, 0);
        const totalNetLeases = mergedSources.reduce((a, s) => a + s.net_leases, 0);

        const merged: MarketingData = {
          property_id: 'consolidated',
          date_range: valid[0].date_range,
          timeframe: valid[0].timeframe,
          sources: mergedSources,
          totals: {
            total_prospects: totalProspects,
            total_calls: totalCalls,
            total_visits: totalVisits,
            total_leases: totalLeases,
            total_net_leases: totalNetLeases,
            overall_prospect_to_lease: totalProspects > 0 ? Math.round((totalLeases / totalProspects) * 100) : 0,
            overall_visit_to_lease: totalVisits > 0 ? Math.round((totalLeases / totalVisits) * 100) : 0,
          },
        };
        setData(merged);
      } catch (err: any) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };
    fetchAll();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [effectiveIds.join(','), timeframe]);

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir(d => d === 'desc' ? 'asc' : 'desc');
    } else {
      setSortKey(key);
      setSortDir(key === 'source' ? 'asc' : 'desc');
    }
  };

  const sortedSources = useMemo(() => {
    if (!data) return [];
    const sorted = [...data.sources].sort((a, b) => {
      const av = a[sortKey];
      const bv = b[sortKey];
      if (typeof av === 'string' && typeof bv === 'string') {
        return sortDir === 'asc' ? av.localeCompare(bv) : bv.localeCompare(av);
      }
      const an = Number(av) || 0;
      const bn = Number(bv) || 0;
      return sortDir === 'asc' ? an - bn : bn - an;
    });
    return sorted;
  }, [data, sortKey, sortDir]);

  if (loading) {
    return (
      <div className="bg-white rounded-xl border border-slate-200 p-6">
        <div className="animate-pulse space-y-3">
          <div className="h-5 bg-slate-200 rounded w-56" />
          <div className="h-48 bg-slate-100 rounded" />
        </div>
      </div>
    );
  }

  if (error || !data || data.sources.length === 0) {
    return (
      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        <div className="flex items-center gap-2 px-4 py-3 border-b border-slate-100">
          <Megaphone className="w-4 h-4 text-violet-500" />
          <h3 className="text-sm font-semibold text-slate-700">Lead Sources by Advertising Channel</h3>
        </div>
        <div className="px-4 py-6 text-center text-sm text-slate-400">No advertising source data available for this property yet</div>
      </div>
    );
  }

  const topSources = showAll ? sortedSources : sortedSources.slice(0, 10);
  const thClass = "px-3 py-2 text-slate-500 font-medium text-right cursor-pointer hover:text-slate-700 select-none whitespace-nowrap";

  return (
    <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
      <button onClick={() => setCollapsed(c => !c)} className="flex items-center gap-2 w-full text-left px-4 py-3 border-b border-slate-100">
        <ChevronDown className={`w-4 h-4 text-slate-400 transition-transform ${collapsed ? '-rotate-90' : ''}`} />
        <Megaphone className="w-4 h-4 text-violet-500" />
        <h3 className="text-sm font-semibold text-slate-700">Lead Sources by Advertising Channel</h3>
        {data.date_range && <span className="text-xs text-slate-400 ml-auto">{data.date_range}</span>}
      </button>
      {!collapsed && (
        <>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-slate-50 text-left">
                  <th className="px-4 py-2 text-slate-500 font-medium cursor-pointer hover:text-slate-700 select-none" onClick={() => toggleSort('source')}>
                    Source <SortIcon column="source" sortKey={sortKey} sortDir={sortDir} />
                  </th>
                  <th className={thClass} onClick={() => toggleSort('new_prospects')}>
                    Prospects <SortIcon column="new_prospects" sortKey={sortKey} sortDir={sortDir} />
                  </th>
                  <th className={thClass} onClick={() => toggleSort('phone_calls')}>
                    Calls <SortIcon column="phone_calls" sortKey={sortKey} sortDir={sortDir} />
                  </th>
                  <th className={thClass} onClick={() => toggleSort('visits')}>
                    Visits <SortIcon column="visits" sortKey={sortKey} sortDir={sortDir} />
                  </th>
                  <th className={thClass} onClick={() => toggleSort('leases')}>
                    Leases <SortIcon column="leases" sortKey={sortKey} sortDir={sortDir} />
                  </th>
                  <th className={thClass} onClick={() => toggleSort('net_leases')}>
                    Net <SortIcon column="net_leases" sortKey={sortKey} sortDir={sortDir} />
                  </th>
                  <th className={thClass} onClick={() => toggleSort('prospect_to_lease_pct')}>
                    Conv% <SortIcon column="prospect_to_lease_pct" sortKey={sortKey} sortDir={sortDir} />
                  </th>
                </tr>
              </thead>
              <tbody>
                {topSources.map((src, i) => {
                  return (
                    <tr key={i} className="border-t border-slate-50 hover:bg-slate-50/50">
                      <td className="px-4 py-2 text-slate-800 font-medium truncate max-w-[200px]" title={src.source}>{src.source}</td>
                      <td className="px-3 py-2 text-right text-slate-700">{src.new_prospects}</td>
                      <td className="px-3 py-2 text-right text-slate-500">{src.phone_calls}</td>
                      <td className="px-3 py-2 text-right text-slate-700">{src.visits}</td>
                      <td className="px-3 py-2 text-right text-slate-700">{src.leases}</td>
                      <td className="px-3 py-2 text-right font-medium text-emerald-600">{src.net_leases}</td>
                      <td className="px-3 py-2 text-right text-slate-600">
                        {src.prospect_to_lease_pct > 0 ? `${src.prospect_to_lease_pct.toFixed(0)}%` : '—'}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          {sortedSources.length > 10 && (
            <button
              onClick={() => setShowAll(!showAll)}
              className="w-full px-4 py-2 text-sm text-violet-600 hover:bg-violet-50 border-t border-slate-100 flex items-center justify-center gap-1"
            >
              {showAll ? <><ChevronUp className="w-4 h-4" /> Show Top 10</> : <><ChevronDown className="w-4 h-4" /> Show All {sortedSources.length} Sources</>}
            </button>
          )}
        </>
      )}
    </div>
  );
}
