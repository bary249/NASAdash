import { useState, useEffect } from 'react';
import { DollarSign, TrendingUp, Home, ChevronDown, ChevronUp } from 'lucide-react';
import { useSortable } from '../hooks/useSortable';
import { SortHeader } from './SortHeader';
import { MetricCard } from './MetricCard';
import { SectionHeader } from './SectionHeader';
import { DrillThroughModal } from './DrillThroughModal';
import { api } from '../api';
import type { UnitPricingMetrics, UnitRaw } from '../types';

interface UnitPricingSectionProps {
  propertyId: string;
}

const UNIT_COLUMNS = [
  { key: 'unit_id', label: 'Unit' },
  { key: 'floorplan', label: 'Floorplan' },
  { key: 'bedrooms', label: 'BR' },
  { key: 'bathrooms', label: 'BA' },
  { key: 'square_feet', label: 'SqFt' },
  { key: 'market_rent', label: 'Market Rent', format: (v: unknown) => v ? `$${v}` : '—' },
  { key: 'status', label: 'Status' },
];

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function FloorplanTable({ floorplans, onDrill, formatCurrency }: { floorplans: any[]; onDrill: (title: string, fp?: string) => void; formatCurrency: (v: number) => string }) {
  const { sorted, sortKey, sortDir, toggleSort } = useSortable(floorplans);
  return (
    <div className="overflow-x-auto">
      <table className="min-w-full divide-y divide-gray-200">
        <thead className="bg-gray-50">
          <tr>
            <SortHeader label="Unit Type" column="name" sortKey={sortKey} sortDir={sortDir} onSort={toggleSort} />
            <SortHeader label="Units" column="unit_count" sortKey={sortKey} sortDir={sortDir} onSort={toggleSort} align="right" />
            <SortHeader label="SF" column="square_feet" sortKey={sortKey} sortDir={sortDir} onSort={toggleSort} align="right" />
            <SortHeader label="In-Place Rent" column="in_place_rent" sortKey={sortKey} sortDir={sortDir} onSort={toggleSort} align="right" />
            <SortHeader label="In-Place $/SF" column="in_place_rent_per_sf" sortKey={sortKey} sortDir={sortDir} onSort={toggleSort} align="right" />
            <SortHeader label="Asking Rent" column="asking_rent" sortKey={sortKey} sortDir={sortDir} onSort={toggleSort} align="right" />
            <SortHeader label="Asking $/SF" column="asking_rent_per_sf" sortKey={sortKey} sortDir={sortDir} onSort={toggleSort} align="right" />
            <SortHeader label="Growth" column="rent_growth" sortKey={sortKey} sortDir={sortDir} onSort={toggleSort} align="right" />
          </tr>
        </thead>
        <tbody className="bg-white divide-y divide-gray-200">
          {sorted.map((fp) => (
            <tr key={fp.floorplan_id} className="hover:bg-gray-50 cursor-pointer" onClick={() => onDrill(`${fp.name} Units`, fp.name)}>
              <td className="px-4 py-3 text-sm font-medium text-gray-900">
                {fp.name}
                {fp.bedrooms > 0 && <span className="text-gray-400 ml-1">({fp.bedrooms}BR)</span>}
              </td>
              <td className="px-4 py-3 text-sm text-gray-500 text-right">{fp.unit_count}</td>
              <td className="px-4 py-3 text-sm text-gray-500 text-right">{fp.square_feet}</td>
              <td className="px-4 py-3 text-sm text-gray-500 text-right">{formatCurrency(fp.in_place_rent)}</td>
              <td className="px-4 py-3 text-sm text-gray-500 text-right">${fp.in_place_rent_per_sf.toFixed(2)}</td>
              <td className="px-4 py-3 text-sm text-gray-500 text-right">{formatCurrency(fp.asking_rent)}</td>
              <td className="px-4 py-3 text-sm text-gray-500 text-right">${fp.asking_rent_per_sf.toFixed(2)}</td>
              <td className={`px-4 py-3 text-sm text-right font-medium ${fp.rent_growth >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                {fp.rent_growth >= 0 ? '+' : ''}{fp.rent_growth.toFixed(1)}%
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function UnitPricingSection({ propertyId }: UnitPricingSectionProps) {
  const [pricing, setPricing] = useState<UnitPricingMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  const [drillOpen, setDrillOpen] = useState(false);
  const [drillTitle, setDrillTitle] = useState('');
  const [drillData, setDrillData] = useState<UnitRaw[]>([]);
  const [drillLoading, setDrillLoading] = useState(false);
  const [unitTypeExpanded, setUnitTypeExpanded] = useState(false);

  useEffect(() => {
    async function fetchData() {
      if (!propertyId) return;
      setLoading(true);
      setError(null);
      try {
        const data = await api.getPricing(propertyId);
        setPricing(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load data');
      } finally {
        setLoading(false);
      }
    }
    fetchData();
  }, [propertyId]);

  const openDrill = async (title: string, floorplanFilter?: string) => {
    setDrillOpen(true);
    setDrillTitle(title);
    setDrillLoading(true);
    setDrillData([]);
    
    try {
      let data = await api.getRawUnits(propertyId);
      if (floorplanFilter) {
        data = data.filter((u) => u.floorplan === floorplanFilter);
      }
      setDrillData(data);
    } catch (e) {
      console.error('Drill-through error:', e);
    } finally {
      setDrillLoading(false);
    }
  };

  const closeDrill = () => {
    setDrillOpen(false);
    setDrillData([]);
  };

  const formatCurrency = (val: number) =>
    new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(val);

  if (loading) {
    return (
      <div className="bg-white rounded-lg shadow p-6">
        <SectionHeader title="Unit Pricing" icon={DollarSign} />
        <div className="animate-pulse space-y-4">
          <div className="grid grid-cols-4 gap-4">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="h-24 bg-gray-200 rounded" />
            ))}
          </div>
          <div className="h-48 bg-gray-200 rounded" />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-white rounded-lg shadow p-6">
        <SectionHeader title="Unit Pricing" icon={DollarSign} />
        <div className="text-red-600 p-4 bg-red-50 rounded">{error}</div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <SectionHeader
        title="Unit Pricing"
        icon={DollarSign}
        description={pricing?.property_name}
      />

      <div className="space-y-6">
        {/* Summary Metrics */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <MetricCard
            title="In-Place Rent"
            value={formatCurrency(pricing?.total_in_place_rent ?? 0)}
            subtitle="Weighted avg (current residents)"
            icon={Home}
            onClick={() => openDrill('All Units - In-Place Rent')}
          />
          <MetricCard
            title="In-Place $/SF"
            value={`$${pricing?.total_in_place_per_sf?.toFixed(2) ?? '0.00'}`}
            onClick={() => openDrill('All Units')}
          />
          <MetricCard
            title="Asking Rent"
            value={formatCurrency(pricing?.total_asking_rent ?? 0)}
            subtitle="Weighted avg (market)"
            icon={DollarSign}
            onClick={() => openDrill('All Units - Asking Rent')}
          />
          <MetricCard
            title="Asking $/SF"
            value={`$${pricing?.total_asking_per_sf?.toFixed(2) ?? '0.00'}`}
            onClick={() => openDrill('All Units')}
          />
        </div>

        {/* Rent Growth */}
        <div className="flex items-center gap-4 p-4 bg-gray-50 rounded-lg">
          <TrendingUp
            className={`w-8 h-8 ${
              (pricing?.total_rent_growth ?? 0) >= 0 ? 'text-green-600' : 'text-red-600'
            }`}
          />
          <div>
            <p className="text-sm text-gray-500">Rent Growth (Asking / In-Place) - 1</p>
            <p
              className={`text-2xl font-bold ${
                (pricing?.total_rent_growth ?? 0) >= 0 ? 'text-green-600' : 'text-red-600'
              }`}
            >
              {(pricing?.total_rent_growth ?? 0) >= 0 ? '+' : ''}
              {pricing?.total_rent_growth?.toFixed(1) ?? 0}%
            </p>
          </div>
        </div>

        {/* Floorplan Table - Collapsible */}
        <div>
          <button
            onClick={() => setUnitTypeExpanded(!unitTypeExpanded)}
            className="flex items-center justify-between w-full text-left mb-3 group"
          >
            <h3 className="text-sm font-semibold text-gray-700">By Unit Type</h3>
            <span className="text-gray-400 group-hover:text-gray-600">
              {unitTypeExpanded ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
            </span>
          </button>
          {unitTypeExpanded && <FloorplanTable floorplans={pricing?.floorplans || []} onDrill={openDrill} formatCurrency={formatCurrency} />}
        </div>
      </div>

      {/* Drill-Through Modal */}
      <DrillThroughModal
        isOpen={drillOpen}
        onClose={closeDrill}
        title={drillTitle}
        data={drillData}
        columns={UNIT_COLUMNS}
        loading={drillLoading}
      />
    </div>
  );
}
