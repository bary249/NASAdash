/**
 * Occupancy Trend Section - Week-over-week occupancy % from box score snapshots.
 * Shows a compact table of historical occupancy snapshots with direction indicators.
 */
import { useState, useEffect } from 'react';
import { TrendingUp, TrendingDown, Minus, BarChart3 } from 'lucide-react';
import { useSortable } from '../hooks/useSortable';
import { SortHeader } from './SortHeader';
import { SectionHeader } from './SectionHeader';
import { api } from '../api';

interface Snapshot {
  date: string;
  total_units: number;
  occupied: number;
  vacant: number;
  occupancy_pct: number;
  leased_pct: number;
  on_notice: number;
  preleased: number;
}

interface Props {
  propertyId: string;
  propertyIds?: string[];
}

function OccupancyTrendTable({ snaps, sortNewest }: { snaps: Snapshot[]; sortNewest: boolean }) {
  const { sorted, sortKey, sortDir, toggleSort } = useSortable(snaps);
  // When no explicit sort is active, use the original display order
  const displayData = sortKey ? sorted : snaps;
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="bg-slate-50 border-b border-slate-200">
          <tr>
            <SortHeader label="Date" column="date" sortKey={sortKey} sortDir={sortDir} onSort={toggleSort} />
            <SortHeader label="Units" column="total_units" sortKey={sortKey} sortDir={sortDir} onSort={toggleSort} align="right" />
            <SortHeader label="Occupied" column="occupied" sortKey={sortKey} sortDir={sortDir} onSort={toggleSort} align="right" />
            <SortHeader label="Vacant" column="vacant" sortKey={sortKey} sortDir={sortDir} onSort={toggleSort} align="right" />
            <SortHeader label="Occupancy" column="occupancy_pct" sortKey={sortKey} sortDir={sortDir} onSort={toggleSort} align="right" />
            <th className="px-4 py-2 text-center text-xs font-medium text-slate-500 uppercase">Δ</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {displayData.map((snap) => {
            const nextInTime = sortNewest ? snaps[snaps.indexOf(snap) + 1] : snaps[snaps.indexOf(snap) - 1];
            const delta = nextInTime ? snap.occupancy_pct - nextInTime.occupancy_pct : 0;
            const deltaRounded = Math.round(delta * 10) / 10;
            return (
              <tr key={snap.date} className="hover:bg-slate-50">
                <td className="px-4 py-2 text-slate-600 font-medium">{snap.date}</td>
                <td className="px-4 py-2 text-right text-slate-600">{snap.total_units}</td>
                <td className="px-4 py-2 text-right text-slate-600">{snap.occupied}</td>
                <td className="px-4 py-2 text-right text-slate-600">{snap.vacant}</td>
                <td className="px-4 py-2 text-right font-semibold">
                  <span className={snap.occupancy_pct >= 95 ? 'text-emerald-600' : snap.occupancy_pct >= 90 ? 'text-amber-600' : 'text-rose-600'}>
                    {snap.occupancy_pct}%
                  </span>
                </td>
                <td className="px-4 py-2 text-center">
                  {!nextInTime ? (
                    <span className="text-slate-300">—</span>
                  ) : deltaRounded > 0 ? (
                    <span className="inline-flex items-center gap-0.5 text-emerald-600 text-xs font-medium">
                      <TrendingUp className="w-3 h-3" /> +{deltaRounded}%
                    </span>
                  ) : deltaRounded < 0 ? (
                    <span className="inline-flex items-center gap-0.5 text-rose-500 text-xs font-medium">
                      <TrendingDown className="w-3 h-3" /> {deltaRounded}%
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-0.5 text-slate-400 text-xs">
                      <Minus className="w-3 h-3" /> 0
                    </span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export function OccupancyTrendSection({ propertyId, propertyIds }: Props) {
  const [snapshots, setSnapshots] = useState<Snapshot[]>([]);
  const [loading, setLoading] = useState(true);
  const [viewMode, setViewMode] = useState<'chart' | 'table'>('chart');
  const [sortNewest, setSortNewest] = useState(true);

  const effectiveIds = propertyIds && propertyIds.length > 0 ? propertyIds : [propertyId];

  useEffect(() => {
    setLoading(true);
    Promise.all(effectiveIds.map(id => api.getOccupancySnapshots(id).catch(() => ({ snapshots: [] }))))
      .then(results => {
        if (effectiveIds.length === 1) {
          // Single property: filter out bad snapshots (partial imports)
          const snaps = (results[0]?.snapshots || []).filter((s: Snapshot) => s.total_units >= 10);
          setSnapshots(snaps);
        } else {
          // Multi-property: only show dates where ALL properties have a real snapshot.
          // No carry-forward — every number is actual captured data.

          // 1. Per property: index snapshots by date, filtered
          const perProperty: Map<string, Snapshot>[] = results.map(r => {
            const map = new Map<string, Snapshot>();
            for (const s of (r?.snapshots || []) as Snapshot[]) {
              if (s.total_units >= 10) map.set(s.date, s);
            }
            return map;
          });

          // Skip properties with no snapshots at all
          const validProps = perProperty.filter(m => m.size > 0);
          if (validProps.length === 0) { setSnapshots([]); return; }

          // 2. Find dates where EVERY property has a real snapshot
          const firstPropDates = [...validProps[0].keys()];
          const commonDates = firstPropDates
            .filter(d => validProps.every(m => m.has(d)))
            .sort();

          // 3. Sum real snapshots on each common date
          const merged: Snapshot[] = [];
          for (const d of commonDates) {
            const agg: Snapshot = {
              date: d, total_units: 0, occupied: 0, vacant: 0,
              occupancy_pct: 0, leased_pct: 0, on_notice: 0, preleased: 0,
            };
            for (const m of validProps) {
              const s = m.get(d)!;
              agg.total_units += s.total_units;
              agg.occupied += s.occupied;
              agg.vacant += s.vacant;
              agg.on_notice += s.on_notice;
              agg.preleased += s.preleased;
            }
            if (agg.total_units > 0) {
              agg.occupancy_pct = Math.round(agg.occupied / agg.total_units * 1000) / 10;
              merged.push(agg);
            }
          }
          setSnapshots(merged);
        }
      })
      .finally(() => setLoading(false));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [effectiveIds.join(',')]);

  if (loading) {
    return (
      <div className="venn-section animate-pulse">
        <div className="h-8 bg-slate-200 rounded w-48 mb-4" />
        <div className="h-24 bg-slate-100 rounded" />
      </div>
    );
  }

  if (snapshots.length < 3) return null;

  // Show newest first
  const sorted = [...snapshots].reverse();
  const displaySnaps = sortNewest ? sorted : [...snapshots];

  // For bar chart: use occupancy_pct, scale bars relative to range for visual impact
  const allPcts = snapshots.map(s => s.occupancy_pct);
  const minPct = Math.min(...allPcts);
  const maxPct = Math.max(...allPcts);
  const rangeMin = Math.max(Math.floor(minPct) - 3, 0);
  const rangeMax = Math.min(Math.ceil(maxPct) + 2, 100);
  const latestOcc = sorted[0]?.occupancy_pct ?? 0;
  const prevOcc = sorted[1]?.occupancy_pct ?? 0;
  const overallDelta = sorted.length >= 2 ? Math.round((latestOcc - prevOcc) * 10) / 10 : 0;

  return (
    <div className="venn-section">
      <SectionHeader
        title="Occupancy Trend"
        icon={BarChart3}
        description="Historical box score snapshots"
      />

      <div className="flex items-center justify-end gap-2 mb-3">
        <div className="flex items-center gap-1 bg-slate-100 rounded-lg p-0.5">
          <button onClick={() => setViewMode('chart')} className={`px-2.5 py-1 rounded-md text-xs font-medium transition-all ${viewMode === 'chart' ? 'bg-white text-slate-800 shadow-sm' : 'text-slate-500 hover:text-slate-700'}`}>Chart</button>
          <button onClick={() => setViewMode('table')} className={`px-2.5 py-1 rounded-md text-xs font-medium transition-all ${viewMode === 'table' ? 'bg-white text-slate-800 shadow-sm' : 'text-slate-500 hover:text-slate-700'}`}>Table</button>
        </div>
        <button onClick={() => setSortNewest(prev => !prev)} className="text-[10px] px-2 py-0.5 rounded border border-slate-300 text-slate-500 hover:bg-white hover:text-slate-700 transition-colors">
          {sortNewest ? 'Newest ↓' : 'Oldest ↓'}
        </button>
      </div>

      {viewMode === 'chart' ? (
        <div className="bg-slate-50 rounded-xl p-4">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <span className="text-xl font-bold text-slate-800">{latestOcc}%</span>
              {overallDelta !== 0 && (
                <span className={`inline-flex items-center gap-0.5 text-xs font-medium ${overallDelta > 0 ? 'text-emerald-600' : 'text-rose-500'}`}>
                  {overallDelta > 0 ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
                  {overallDelta > 0 ? '+' : ''}{overallDelta}%
                </span>
              )}
            </div>
            <span className="text-[10px] text-slate-400">vs prior week</span>
          </div>
          <div className="space-y-2">
            {displaySnaps.map((snap) => {
              const barWidth = rangeMax > rangeMin ? ((snap.occupancy_pct - rangeMin) / (rangeMax - rangeMin)) * 100 : 50;
              const color = snap.occupancy_pct >= 95 ? 'bg-emerald-400' : snap.occupancy_pct >= 90 ? 'bg-blue-400' : 'bg-rose-400';
              return (
                <div key={snap.date} className="flex items-center gap-3">
                  <span className="text-xs text-slate-500 w-20 shrink-0">{snap.date}</span>
                  <div className="flex-1 h-4 bg-slate-200 rounded-full overflow-hidden">
                    <div className={`h-full rounded-full transition-all duration-500 ${color}`} style={{ width: `${Math.max(barWidth, 2)}%` }} />
                  </div>
                  <span className={`text-xs font-medium w-14 text-right ${snap.occupancy_pct >= 95 ? 'text-emerald-600' : snap.occupancy_pct >= 90 ? 'text-amber-600' : 'text-rose-600'}`}>
                    {snap.occupancy_pct}%
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      ) : (
        <OccupancyTrendTable snaps={displaySnaps} sortNewest={sortNewest} />
      )}
    </div>
  );
}
