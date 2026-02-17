/**
 * Occupancy Trend Section - Week-over-week occupancy % from box score snapshots.
 * Shows a compact table of historical occupancy snapshots with direction indicators.
 */
import { useState, useEffect } from 'react';
import { TrendingUp, TrendingDown, Minus, BarChart3 } from 'lucide-react';
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

export function OccupancyTrendSection({ propertyId, propertyIds }: Props) {
  const [snapshots, setSnapshots] = useState<Snapshot[]>([]);
  const [loading, setLoading] = useState(true);

  const effectiveIds = propertyIds && propertyIds.length > 0 ? propertyIds : [propertyId];

  useEffect(() => {
    setLoading(true);
    Promise.all(effectiveIds.map(id => api.getOccupancySnapshots(id).catch(() => ({ snapshots: [] }))))
      .then(results => {
        if (effectiveIds.length === 1) {
          setSnapshots(results[0]?.snapshots || []);
        } else {
          // Merge: group by date, sum units
          const byDate: Record<string, Snapshot> = {};
          for (const r of results) {
            for (const s of (r?.snapshots || [])) {
              if (!byDate[s.date]) {
                byDate[s.date] = { ...s };
              } else {
                byDate[s.date].total_units += s.total_units;
                byDate[s.date].occupied += s.occupied;
                byDate[s.date].vacant += s.vacant;
                byDate[s.date].on_notice += s.on_notice;
                byDate[s.date].preleased += s.preleased;
              }
            }
          }
          // Recalculate percentages
          const merged = Object.values(byDate).map(s => ({
            ...s,
            occupancy_pct: s.total_units > 0 ? Math.round(s.occupied / s.total_units * 1000) / 10 : 0,
          }));
          merged.sort((a, b) => a.date.localeCompare(b.date));
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

  if (snapshots.length === 0) return null;

  // Show newest first
  const sorted = [...snapshots].reverse();

  return (
    <div className="venn-section">
      <SectionHeader
        title="Occupancy Trend"
        icon={BarChart3}
        description="Historical box score snapshots"
      />

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 border-b border-slate-200">
            <tr>
              <th className="px-4 py-2 text-left text-xs font-medium text-slate-500 uppercase">Date</th>
              <th className="px-4 py-2 text-right text-xs font-medium text-slate-500 uppercase">Units</th>
              <th className="px-4 py-2 text-right text-xs font-medium text-slate-500 uppercase">Occupied</th>
              <th className="px-4 py-2 text-right text-xs font-medium text-slate-500 uppercase">Vacant</th>
              <th className="px-4 py-2 text-right text-xs font-medium text-slate-500 uppercase">Occupancy</th>
              <th className="px-4 py-2 text-center text-xs font-medium text-slate-500 uppercase">Δ</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {sorted.map((snap, idx) => {
              const prev = sorted[idx + 1]; // previous in time (one row below = older)
              const delta = prev ? snap.occupancy_pct - prev.occupancy_pct : 0;
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
                    {!prev ? (
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
    </div>
  );
}
