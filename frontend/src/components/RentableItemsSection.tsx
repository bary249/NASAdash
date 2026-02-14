/**
 * RentableItemsSection - Rentable items from real API data
 * Shows parking, storage, pet fees, and other ancillary revenue items
 */
import { useEffect, useState } from 'react';
import { api } from '../api';
import { AmenityTypeSummary } from '../types';

interface RentableItemsSectionProps {
  propertyId: string;
  propertyIds?: string[];
}

export function RentableItemsSection({ propertyId, propertyIds }: RentableItemsSectionProps) {
  const [items, setItems] = useState<AmenityTypeSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [totals, setTotals] = useState({
    totalRented: 0,
    totalAvailable: 0,
    totalRevenue: 0,
  });

  const effectiveIds = propertyIds && propertyIds.length > 0 ? propertyIds : [propertyId];

  useEffect(() => {
    if (!effectiveIds.length) return;
    
    setLoading(true);
    Promise.all(effectiveIds.map(id => api.getAmenitiesSummary(id).catch(() => null)))
      .then(results => {
        const valid = results.filter(Boolean) as Array<{ by_type: AmenityTypeSummary[]; total_rented: number; total_available: number; monthly_actual: number }>;
        if (valid.length === 0) { setItems([]); return; }
        if (valid.length === 1) {
          setItems(valid[0].by_type || []);
          setTotals({ totalRented: valid[0].total_rented, totalAvailable: valid[0].total_available, totalRevenue: valid[0].monthly_actual });
          return;
        }
        // Merge by type name
        const byType = new Map<string, AmenityTypeSummary>();
        for (const summary of valid) {
          for (const item of (summary.by_type || [])) {
            const existing = byType.get(item.type);
            if (existing) {
              existing.total += item.total;
              existing.available += item.available;
              existing.rented += item.rented;
              existing.actual_revenue += item.actual_revenue;
              // weighted average for monthly_rate
              existing.monthly_rate = existing.total > 0
                ? Math.round(existing.actual_revenue / Math.max(existing.rented, 1))
                : item.monthly_rate;
            } else {
              byType.set(item.type, { ...item });
            }
          }
        }
        const merged = Array.from(byType.values());
        setItems(merged);
        setTotals({
          totalRented: valid.reduce((s, r) => s + r.total_rented, 0),
          totalAvailable: valid.reduce((s, r) => s + r.total_available, 0),
          totalRevenue: valid.reduce((s, r) => s + r.monthly_actual, 0),
        });
      })
      .catch(err => {
        console.error('Failed to fetch amenities:', err);
        setItems([]);
      })
      .finally(() => setLoading(false));
  }, [effectiveIds.join(',')]);

  if (loading) {
    return (
      <div className="bg-white rounded-xl border border-slate-200 p-6">
        <div className="animate-pulse">
          <div className="h-6 bg-slate-200 rounded w-40 mb-4" />
          <div className="space-y-3">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="h-10 bg-slate-100 rounded" />
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <div className="bg-white rounded-xl border border-slate-200 p-6">
        <h3 className="text-lg font-semibold text-slate-800 mb-4">Rentable Items</h3>
        <p className="text-slate-500 text-sm">No rentable items found for this property.</p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-xl border border-slate-200 p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-slate-800">Rentable Items</h3>
        <div className="flex items-center gap-4 text-sm">
          <span className="text-slate-500">
            <span className="font-medium text-emerald-600">{totals.totalRented}</span> rented
          </span>
          <span className="text-slate-500">
            <span className="font-medium text-slate-600">{totals.totalAvailable}</span> available
          </span>
        </div>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-200">
              <th className="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase">Type</th>
              <th className="px-4 py-3 text-right text-xs font-medium text-slate-500 uppercase">Total</th>
              <th className="px-4 py-3 text-right text-xs font-medium text-slate-500 uppercase">Monthly Rate</th>
              <th className="px-4 py-3 text-right text-xs font-medium text-slate-500 uppercase">Available</th>
              <th className="px-4 py-3 text-right text-xs font-medium text-slate-500 uppercase">Rented</th>
              <th className="px-4 py-3 text-right text-xs font-medium text-slate-500 uppercase">Revenue</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {items.map((item, idx) => (
              <tr key={idx} className="hover:bg-slate-50">
                <td className="px-4 py-3 font-medium text-slate-800">{item.type}</td>
                <td className="px-4 py-3 text-right text-slate-600">{item.total}</td>
                <td className="px-4 py-3 text-right text-slate-700">${item.monthly_rate.toLocaleString()}</td>
                <td className="px-4 py-3 text-right text-slate-600">{item.available}</td>
                <td className="px-4 py-3 text-right text-emerald-600 font-medium">{item.rented}</td>
                <td className="px-4 py-3 text-right text-slate-800 font-medium">
                  ${item.actual_revenue.toLocaleString()}
                </td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr className="bg-slate-50 font-medium">
              <td className="px-4 py-3 text-slate-800" colSpan={5}>Total Ancillary Revenue</td>
              <td className="px-4 py-3 text-right text-emerald-700 font-bold">
                ${totals.totalRevenue.toLocaleString()}
              </td>
            </tr>
          </tfoot>
        </table>
      </div>
    </div>
  );
}
