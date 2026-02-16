/**
 * BedroomConsolidatedView - Consolidated dashboard table grouped by bedroom type.
 * Combines occupancy, pricing, availability, and renewal data in one view.
 * Per WS5 design partner feedback.
 */
import { useState, useEffect } from 'react';
import { ChevronDown, Home } from 'lucide-react';
import { InfoTooltip } from './InfoTooltip';
import { api } from '../api';

interface BedroomRow {
  bedroom_type: string;
  bedrooms: number;
  floorplan_count: number;
  floorplans: string[];
  total_units: number;
  occupied: number;
  vacant: number;
  vacant_leased: number;
  vacant_not_leased: number;
  on_notice: number;
  occupancy_pct: number;
  avg_market_rent: number;
  avg_in_place_rent: number;
  rent_delta: number;
  expiring_90d: number;
  renewed_90d: number;
  renewal_pct_90d: number | null;
}

interface Totals {
  total_units: number;
  occupied: number;
  vacant: number;
  vacant_leased: number;
  on_notice: number;
  occupancy_pct: number;
  expiring_90d: number;
  renewed_90d: number;
  renewal_pct_90d: number | null;
}

interface Props {
  propertyId: string;
  propertyIds?: string[];
}

const fmt = (v: number) => v > 0 ? `$${v.toLocaleString(undefined, { maximumFractionDigits: 0 })}` : '—';
const pct = (v: number | null) => v != null ? `${v.toFixed(1)}%` : '—';

function OccBar({ occupied, total }: { occupied: number; vacant?: number; total: number }) {
  if (total === 0) return <span className="text-slate-400">—</span>;
  const occPct = (occupied / total) * 100;
  return (
    <div className="flex items-center gap-2">
      <div className="h-2 flex-1 bg-slate-200 rounded-full overflow-hidden min-w-[60px]">
        <div
          className={`h-full rounded-full transition-all duration-500 ${occPct >= 95 ? 'bg-emerald-400' : occPct >= 90 ? 'bg-blue-400' : occPct >= 80 ? 'bg-amber-400' : 'bg-red-400'}`}
          style={{ width: `${occPct}%` }}
        />
      </div>
      <span className="text-xs font-medium text-slate-600 w-12 text-right">{occPct.toFixed(1)}%</span>
    </div>
  );
}

export function BedroomConsolidatedView({ propertyId, propertyIds }: Props) {
  const [data, setData] = useState<{ bedrooms: BedroomRow[]; totals: Totals } | null>(null);
  const [loading, setLoading] = useState(true);
  const [collapsed, setCollapsed] = useState(false);

  const effectiveIds = propertyIds && propertyIds.length > 0 ? propertyIds : [propertyId];

  useEffect(() => {
    if (!effectiveIds.length || !effectiveIds[0]) return;
    setLoading(true);
    Promise.all(effectiveIds.map(id => api.getConsolidatedByBedroom(id).catch(() => null)))
      .then(results => {
        const valid = results.filter(r => r && r.bedrooms?.length > 0) as { bedrooms: BedroomRow[]; totals: Totals }[];
        if (valid.length === 0) { setData(null); return; }
        if (valid.length === 1) { setData(valid[0]); return; }
        // Merge bedroom rows by bedroom_type
        const rowMap: Record<string, BedroomRow> = {};
        for (const d of valid) {
          for (const b of d.bedrooms) {
            const key = b.bedroom_type;
            if (!rowMap[key]) {
              rowMap[key] = { ...b, floorplans: [...b.floorplans] };
            } else {
              const m = rowMap[key];
              m.floorplan_count += b.floorplan_count;
              m.floorplans = [...new Set([...m.floorplans, ...b.floorplans])];
              const totalUnitsNew = m.total_units + b.total_units;
              m.avg_market_rent = totalUnitsNew > 0 ? (m.avg_market_rent * m.total_units + b.avg_market_rent * b.total_units) / totalUnitsNew : 0;
              m.avg_in_place_rent = (m.occupied + b.occupied) > 0 ? (m.avg_in_place_rent * m.occupied + b.avg_in_place_rent * b.occupied) / (m.occupied + b.occupied) : 0;
              m.total_units = totalUnitsNew;
              m.occupied += b.occupied;
              m.vacant += b.vacant;
              m.vacant_leased += b.vacant_leased;
              m.vacant_not_leased += b.vacant_not_leased;
              m.on_notice += b.on_notice;
              m.expiring_90d += b.expiring_90d;
              m.renewed_90d += b.renewed_90d;
              m.occupancy_pct = m.total_units > 0 ? Math.round(m.occupied / m.total_units * 1000) / 10 : 0;
              m.rent_delta = m.avg_market_rent - m.avg_in_place_rent;
              m.renewal_pct_90d = m.expiring_90d > 0 ? Math.round(m.renewed_90d / m.expiring_90d * 100) : null;
            }
          }
        }
        const bedrooms = Object.values(rowMap).sort((a, b) => a.bedrooms - b.bedrooms);
        const totals: Totals = {
          total_units: bedrooms.reduce((s, b) => s + b.total_units, 0),
          occupied: bedrooms.reduce((s, b) => s + b.occupied, 0),
          vacant: bedrooms.reduce((s, b) => s + b.vacant, 0),
          vacant_leased: bedrooms.reduce((s, b) => s + b.vacant_leased, 0),
          on_notice: bedrooms.reduce((s, b) => s + b.on_notice, 0),
          occupancy_pct: 0, expiring_90d: bedrooms.reduce((s, b) => s + b.expiring_90d, 0),
          renewed_90d: bedrooms.reduce((s, b) => s + b.renewed_90d, 0),
          renewal_pct_90d: null,
        };
        totals.occupancy_pct = totals.total_units > 0 ? Math.round(totals.occupied / totals.total_units * 1000) / 10 : 0;
        totals.renewal_pct_90d = totals.expiring_90d > 0 ? Math.round(totals.renewed_90d / totals.expiring_90d * 100) : null;
        setData({ bedrooms, totals });
      })
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [effectiveIds.join(',')]);

  if (loading) {
    return (
      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden animate-pulse">
        <div className="px-4 py-3 bg-slate-50 border-b border-slate-200">
          <div className="h-4 bg-slate-200 rounded w-48" />
        </div>
        <div className="p-4 h-32 bg-slate-50" />
      </div>
    );
  }

  if (!data || data.bedrooms.length === 0) return null;

  const { bedrooms, totals } = data;

  return (
    <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
      <button
        onClick={() => setCollapsed(c => !c)}
        className="w-full px-4 py-3 border-b border-slate-200 bg-slate-50 flex items-center justify-between hover:bg-slate-100 transition-colors"
      >
        <h3 className="text-sm font-semibold text-slate-700 inline-flex items-center gap-2">
          <Home className="w-4 h-4 text-indigo-500" />
          Consolidated by Bedroom Type
          <InfoTooltip text="Aggregates all floorplans by bedroom count, showing occupancy, pricing, availability, and renewal metrics in one view. Source: RealPage Box Score + Leases." />
        </h3>
        <ChevronDown className={`w-4 h-4 text-slate-400 transition-transform ${collapsed ? '-rotate-90' : ''}`} />
      </button>

      {!collapsed && (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-left text-xs font-medium text-slate-500 uppercase bg-slate-50/50">
                <th className="px-4 py-2">Type</th>
                <th className="px-3 py-2 text-right">Units</th>
                <th className="px-3 py-2 text-right">Occ%</th>
                <th className="px-3 py-2 text-right">Vacant</th>
                <th className="px-3 py-2 text-right">
                  <span className="inline-flex items-center gap-0.5">NTV <InfoTooltip text="On Notice to Vacate" /></span>
                </th>
                <th className="px-3 py-2 text-right">
                  <span className="inline-flex items-center gap-0.5">V-Leased <InfoTooltip text="Vacant but leased (pending move-in)" /></span>
                </th>
                <th className="px-3 py-2 text-right">Market</th>
                <th className="px-3 py-2 text-right">In-Place</th>
                <th className="px-3 py-2 text-right">Delta</th>
                <th className="px-3 py-2 text-right">
                  <span className="inline-flex items-center gap-0.5">Exp 90d <InfoTooltip text="Leases expiring within 90 days" /></span>
                </th>
                <th className="px-3 py-2 text-right">
                  <span className="inline-flex items-center gap-0.5">Rnw% <InfoTooltip text="Renewal rate for 90-day expirations" /></span>
                </th>
              </tr>
            </thead>
            <tbody>
              {bedrooms.map(bed => (
                <tr key={bed.bedroom_type} className="border-b border-slate-100 hover:bg-slate-50">
                  <td className="px-4 py-2.5">
                    <div className="font-medium text-slate-800">{bed.bedroom_type}</div>
                    <div className="text-xs text-slate-400">{bed.floorplan_count} floorplan{bed.floorplan_count !== 1 ? 's' : ''}</div>
                  </td>
                  <td className="px-3 py-2.5 text-right text-slate-700">{bed.total_units}</td>
                  <td className="px-3 py-2.5">
                    <OccBar occupied={bed.occupied} vacant={bed.vacant} total={bed.total_units} />
                  </td>
                  <td className={`px-3 py-2.5 text-right font-medium ${bed.vacant > 0 ? 'text-red-600' : 'text-slate-700'}`}>
                    {bed.vacant}
                  </td>
                  <td className={`px-3 py-2.5 text-right ${bed.on_notice > 0 ? 'text-amber-600 font-medium' : 'text-slate-500'}`}>
                    {bed.on_notice || '—'}
                  </td>
                  <td className={`px-3 py-2.5 text-right ${bed.vacant_leased > 0 ? 'text-emerald-600 font-medium' : 'text-slate-500'}`}>
                    {bed.vacant_leased || '—'}
                  </td>
                  <td className="px-3 py-2.5 text-right text-slate-700">{fmt(bed.avg_market_rent)}</td>
                  <td className="px-3 py-2.5 text-right text-slate-700">{fmt(bed.avg_in_place_rent)}</td>
                  <td className={`px-3 py-2.5 text-right font-medium ${
                    bed.rent_delta > 0 ? 'text-emerald-600' : bed.rent_delta < 0 ? 'text-red-600' : 'text-slate-500'
                  }`}>
                    {bed.rent_delta > 0 ? `+${fmt(bed.rent_delta).replace('$', '$')}` : bed.rent_delta < 0 ? `-${fmt(Math.abs(bed.rent_delta))}` : '—'}
                  </td>
                  <td className="px-3 py-2.5 text-right text-slate-700">
                    {bed.expiring_90d > 0 ? bed.expiring_90d : '—'}
                  </td>
                  <td className={`px-3 py-2.5 text-right font-medium ${
                    bed.renewal_pct_90d != null && bed.renewal_pct_90d >= 50 ? 'text-emerald-600' :
                    bed.renewal_pct_90d != null ? 'text-amber-600' : 'text-slate-500'
                  }`}>
                    {pct(bed.renewal_pct_90d)}
                  </td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr className="bg-slate-50 border-t border-slate-300 font-semibold text-slate-800">
                <td className="px-4 py-2.5">Total</td>
                <td className="px-3 py-2.5 text-right">{totals.total_units}</td>
                <td className="px-3 py-2.5">
                  <OccBar occupied={totals.occupied} vacant={totals.vacant} total={totals.total_units} />
                </td>
                <td className="px-3 py-2.5 text-right">{totals.vacant}</td>
                <td className="px-3 py-2.5 text-right">{totals.on_notice || '—'}</td>
                <td className="px-3 py-2.5 text-right">{totals.vacant_leased || '—'}</td>
                <td className="px-3 py-2.5 text-right" colSpan={3}></td>
                <td className="px-3 py-2.5 text-right">{totals.expiring_90d > 0 ? totals.expiring_90d : '—'}</td>
                <td className="px-3 py-2.5 text-right">{pct(totals.renewal_pct_90d)}</td>
              </tr>
            </tfoot>
          </table>
        </div>
      )}
    </div>
  );
}
