/**
 * Amenities Section - Rentable items (parking, storage, etc.)
 * 
 * Shows inventory of rentable items with occupancy and revenue metrics.
 * Supports drill-through to see individual items.
 */
import { useState, useEffect } from 'react';
import { Car, Package, DollarSign, CheckCircle } from 'lucide-react';
import { useSortable } from '../hooks/useSortable';
import { SortHeader } from './SortHeader';
import { MetricCard } from './MetricCard';
import { api } from '../api';
import type { AmenitiesSummary, AmenityItem, AmenityTypeSummary } from '../types';

interface AmenitiesSectionProps {
  propertyId: string;
}

const AMENITY_COLUMNS = [
  { key: 'item_name', label: 'Name' },
  { key: 'item_type', label: 'Type' },
  { key: 'billing_amount', label: 'Rate', format: (v: unknown) => v ? `$${v}/mo` : '—' },
  { key: 'lease_id', label: 'Rented', format: (v: unknown) => v && String(v) !== '0' && String(v) !== '' ? '✓ Yes' : 'Available' },
  { key: 'date_available', label: 'Available Date', format: (v: unknown) => v ? String(v).split(' ')[0] : '—' },
];

function AmenityDrillTable({ items }: { items: AmenityItem[] }) {
  const { sorted, sortKey, sortDir, toggleSort } = useSortable(items);
  return (
    <div className="overflow-auto max-h-[60vh]">
      <table className="w-full text-sm">
        <thead className="bg-gray-50 sticky top-0">
          <tr>
            {AMENITY_COLUMNS.map(col => (
              <SortHeader
                key={col.key}
                label={col.label}
                column={col.key}
                sortKey={sortKey}
                sortDir={sortDir}
                onSort={toggleSort}
              />
            ))}
          </tr>
        </thead>
        <tbody>
          {sorted.map((item, idx) => (
            <tr key={(item as unknown as Record<string, unknown>).rid_id as string || idx} className="border-t hover:bg-gray-50">
              {AMENITY_COLUMNS.map(col => (
                <td key={col.key} className="px-4 py-2">
                  {col.format
                    ? col.format((item as unknown as Record<string, unknown>)[col.key])
                    : String((item as unknown as Record<string, unknown>)[col.key] ?? '—')
                  }
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function AmenitiesSection({ propertyId }: AmenitiesSectionProps) {
  const [summary, setSummary] = useState<AmenitiesSummary | null>(null);
  const [items, setItems] = useState<AmenityItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [drillOpen, setDrillOpen] = useState(false);
  const [drillTitle, setDrillTitle] = useState('');
  const [drillFilter, setDrillFilter] = useState<string | null>(null);

  useEffect(() => {
    if (!propertyId) return;
    
    setLoading(true);
    setError(null);
    
    Promise.all([
      api.getAmenitiesSummary(propertyId),
      api.getAmenities(propertyId)
    ])
      .then(([summaryData, itemsData]) => {
        setSummary(summaryData);
        setItems(itemsData);
      })
      .catch(err => {
        console.error('Error fetching amenities:', err);
        setError(err.message);
      })
      .finally(() => setLoading(false));
  }, [propertyId]);

  const openDrill = (title: string, filter?: string) => {
    setDrillTitle(title);
    setDrillFilter(filter || null);
    setDrillOpen(true);
  };

  const filteredItems = drillFilter
    ? items.filter(i => {
        if (drillFilter === 'available') return (i.status || '').toLowerCase().includes('available');
        if (drillFilter === 'rented') return !(i.status || '').toLowerCase().includes('available');
        return (i.item_type || '').toLowerCase().includes(drillFilter.toLowerCase());
      })
    : items;

  if (loading) {
    return (
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-lg font-semibold text-gray-800 mb-4 flex items-center gap-2">
          <Car className="w-5 h-5 text-blue-600" />
          Rentable Items
        </h2>
        <div className="text-center text-gray-500 py-8">Loading amenities...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-lg font-semibold text-gray-800 mb-4 flex items-center gap-2">
          <Car className="w-5 h-5 text-blue-600" />
          Rentable Items
        </h2>
        <div className="text-center text-red-500 py-8">{error}</div>
      </div>
    );
  }

  if (!summary || summary.total_items === 0) {
    return (
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-lg font-semibold text-gray-800 mb-4 flex items-center gap-2">
          <Car className="w-5 h-5 text-blue-600" />
          Rentable Items
        </h2>
        <div className="text-center text-gray-400 py-8">No rentable items available for this property</div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <h2 className="text-lg font-semibold text-gray-800 mb-4 flex items-center gap-2">
        <Car className="w-5 h-5 text-blue-600" />
        Rentable Items
        <span className="text-sm font-normal text-gray-500 ml-2">
          ({summary.total_items} items)
        </span>
      </h2>

      {/* Summary metrics */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <MetricCard
          title="Total Items"
          value={summary.total_items}
          icon={Package}
          onClick={() => openDrill('All Rentable Items')}
        />
        <MetricCard
          title="Available"
          value={summary.total_available}
          icon={CheckCircle}
          health={summary.total_available > 0 ? 'warning' : 'good'}
          onClick={() => openDrill('Available Items', 'available')}
        />
        <MetricCard
          title="Rented"
          value={summary.total_rented}
          icon={DollarSign}
          subtitle={`${summary.occupancy_rate}% occupied`}
          onClick={() => openDrill('Rented Items', 'rented')}
        />
        <MetricCard
          title="Monthly Revenue"
          value={`$${summary.monthly_actual.toLocaleString()}`}
          subtitle={`of $${summary.monthly_potential.toLocaleString()} potential`}
          icon={DollarSign}
        />
      </div>

      {/* By Type breakdown */}
      <div className="border-t pt-4">
        <h3 className="text-sm font-medium text-gray-700 mb-3">By Type</h3>
        <div className="space-y-2">
          {summary.by_type.map((type: AmenityTypeSummary) => (
            <div 
              key={type.type}
              className="flex items-center justify-between p-3 bg-gray-50 rounded-lg hover:bg-gray-100 cursor-pointer transition-colors"
              onClick={() => openDrill(type.type, type.type)}
            >
              <div className="flex items-center gap-3">
                {type.type.toLowerCase().includes('carport') || type.type.toLowerCase().includes('parking') ? (
                  <Car className="w-4 h-4 text-gray-500" />
                ) : (
                  <Package className="w-4 h-4 text-gray-500" />
                )}
                <span className="font-medium text-gray-800">{type.type}</span>
              </div>
              <div className="flex items-center gap-6 text-sm">
                <div className="text-gray-600">
                  <span className="font-medium text-green-600">{type.rented}</span>
                  <span className="text-gray-400"> / {type.total}</span>
                  <span className="text-gray-400 ml-1">rented</span>
                </div>
                <div className="text-gray-600">
                  <span className="font-medium">${type.monthly_rate}</span>
                  <span className="text-gray-400">/mo</span>
                </div>
                <div className="text-gray-600 w-24 text-right">
                  <span className="font-medium text-blue-600">${type.actual_revenue}</span>
                  <span className="text-gray-400">/mo</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Drill-through modal */}
      {drillOpen && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl w-full max-w-4xl max-h-[80vh] overflow-hidden">
            <div className="flex items-center justify-between p-4 border-b">
              <h3 className="text-lg font-semibold">{drillTitle} ({filteredItems.length})</h3>
              <button 
                onClick={() => setDrillOpen(false)}
                className="text-gray-500 hover:text-gray-700 text-xl"
              >
                ×
              </button>
            </div>
            <AmenityDrillTable items={filteredItems} />
          </div>
        </div>
      )}
    </div>
  );
}
