import { useState, useEffect, useCallback } from 'react';
import { MapPin, Building, TrendingUp, Crosshair, Filter, ChevronDown, ChevronUp } from 'lucide-react';
import { MetricCard } from './MetricCard';
import { SectionHeader } from './SectionHeader';
import { api } from '../api';
import type { MarketCompsResponse } from '../types';

interface Submarket {
  id: string;
  name: string;
}

interface PropertyLocation {
  property_id: string;
  name: string;
  city: string;
  state: string;
}

interface Filters {
  minUnits?: number;
  maxUnits?: number;
  minYearBuilt?: number;
  maxYearBuilt?: number;
  amenities: string[];
}

const AMENITY_OPTIONS = [
  { id: 'pool', label: 'Pool' },
  { id: 'fitness', label: 'Fitness Center' },
  { id: 'clubhouse', label: 'Clubhouse' },
  { id: 'gated', label: 'Gated Access' },
  { id: 'parking', label: 'Covered Parking' },
  { id: 'washer_dryer', label: 'W/D Connections' },
  { id: 'pet_friendly', label: 'Pet Friendly' },
];

interface MarketCompsSectionProps {
  propertyId?: string;
  subjectProperty?: string;
}

export function MarketCompsSection({ propertyId, subjectProperty }: MarketCompsSectionProps) {
  const [data, setData] = useState<MarketCompsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedSubmarket, setSelectedSubmarket] = useState('');
  const [submarkets, setSubmarkets] = useState<Submarket[]>([]);
  const [loadingSubmarkets, setLoadingSubmarkets] = useState(true);
  const [propertyLocation, setPropertyLocation] = useState<PropertyLocation | null>(null);
  const [showFilters, setShowFilters] = useState(false);
  const [filters, setFilters] = useState<Filters>({
    minUnits: undefined,
    maxUnits: undefined,
    minYearBuilt: undefined,
    maxYearBuilt: undefined,
    amenities: [],
  });
  const [pendingFilters, setPendingFilters] = useState<Filters>({
    minUnits: undefined,
    maxUnits: undefined,
    minYearBuilt: undefined,
    maxYearBuilt: undefined,
    amenities: [],
  });

  // Load submarkets list
  useEffect(() => {
    api.getSubmarkets()
      .then(data => {
        setSubmarkets(data);
        setLoadingSubmarkets(false);
      })
      .catch(() => {
        // Fallback submarkets if API fails
        setSubmarkets([
          { id: 'South Asheville / Arden', name: 'South Asheville / Arden' },
          { id: 'Downtown', name: 'Downtown' },
          { id: 'Midtown', name: 'Midtown' },
        ]);
        setLoadingSubmarkets(false);
      });
  }, []);

  // Find matching submarket based on property location
  const findMatchingSubmarket = useCallback((location: PropertyLocation, submarketList: Submarket[]): string => {
    const cityState = `${location.city}, ${location.state}`.toLowerCase();
    const city = location.city.toLowerCase();
    
    for (const s of submarketList) {
      const name = s.name.toLowerCase();
      if (name.includes(cityState) || name.includes(city)) {
        return s.id;
      }
    }
    
    for (const s of submarketList) {
      if (s.name.toLowerCase().includes(location.state.toLowerCase())) {
        return s.id;
      }
    }
    
    return submarketList.length > 0 ? submarketList[0].id : '';
  }, []);

  // Load property location
  useEffect(() => {
    if (!propertyId) return;
    
    api.getPropertyLocation(propertyId)
      .then((loc) => {
        setPropertyLocation(loc);
        if (submarkets.length > 0 && !selectedSubmarket) {
          const matched = findMatchingSubmarket(loc, submarkets);
          setSelectedSubmarket(matched);
        }
      })
      .catch(() => {
        // Set default if property location fails
        if (submarkets.length > 0 && !selectedSubmarket) {
          setSelectedSubmarket(submarkets[0].id);
        }
      });
  }, [propertyId, submarkets, selectedSubmarket, findMatchingSubmarket]);

  // Zoom to property area button handler
  const zoomToPropertyArea = () => {
    if (propertyLocation && submarkets.length > 0) {
      const matched = findMatchingSubmarket(propertyLocation, submarkets);
      setSelectedSubmarket(matched);
    }
  };

  // Apply filters
  const applyFilters = () => {
    setFilters({ ...pendingFilters });
    setShowFilters(false);
  };

  const clearFilters = () => {
    const empty: Filters = { minUnits: undefined, maxUnits: undefined, minYearBuilt: undefined, maxYearBuilt: undefined, amenities: [] };
    setPendingFilters(empty);
    setFilters(empty);
  };

  const toggleAmenity = (amenityId: string) => {
    setPendingFilters(prev => ({
      ...prev,
      amenities: prev.amenities.includes(amenityId)
        ? prev.amenities.filter(a => a !== amenityId)
        : [...prev.amenities, amenityId]
    }));
  };

  const activeFilterCount = [
    filters.minUnits, filters.maxUnits, filters.minYearBuilt, filters.maxYearBuilt
  ].filter(Boolean).length + filters.amenities.length;

  // Fetch market comps when submarket or filters change
  useEffect(() => {
    async function fetchData() {
      if (!selectedSubmarket) return;
      setLoading(true);
      setError(null);
      try {
        const result = await api.getMarketComps(selectedSubmarket, subjectProperty, 20, {
          minUnits: filters.minUnits,
          maxUnits: filters.maxUnits,
          minYearBuilt: filters.minYearBuilt,
          maxYearBuilt: filters.maxYearBuilt,
          amenities: filters.amenities.length > 0 ? filters.amenities : undefined,
        });
        setData(result);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load market comps');
      } finally {
        setLoading(false);
      }
    }
    fetchData();
  }, [selectedSubmarket, subjectProperty, filters]);

  const formatCurrency = (val?: number) =>
    val ? new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(val) : '—';

  if (loading) {
    return (
      <div className="bg-white rounded-lg shadow p-6">
        <SectionHeader title="Market Comps" icon={MapPin} />
        <div className="animate-pulse space-y-4">
          <div className="grid grid-cols-3 gap-4">
            {[...Array(3)].map((_, i) => (
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
        <SectionHeader title="Market Comps" icon={MapPin} />
        <div className="text-red-600 p-4 bg-red-50 rounded">{error}</div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <SectionHeader
        title="Market Comps"
        icon={MapPin}
        description={`Comparable properties in ${selectedSubmarket}`}
      />

      <div className="space-y-6">
        {/* Submarket Selector and Filters */}
        <div className="mb-4 space-y-3">
          <div className="flex items-center gap-2 flex-wrap">
            <label className="text-sm font-medium text-gray-700">Submarket:</label>
            <select
              value={selectedSubmarket}
              onChange={(e) => setSelectedSubmarket(e.target.value)}
              className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 bg-white min-w-[250px]"
              disabled={loadingSubmarkets}
            >
              {loadingSubmarkets ? (
                <option>Loading submarkets...</option>
              ) : (
                submarkets.map(s => (
                  <option key={s.id} value={s.id}>{s.name}</option>
                ))
              )}
            </select>
            <button
              onClick={zoomToPropertyArea}
              className="flex items-center gap-1.5 px-3 py-2 text-sm font-medium text-blue-600 bg-blue-50 border border-blue-200 rounded-lg hover:bg-blue-100 transition-colors"
              title={propertyLocation ? `Zoom to ${propertyLocation.city}, ${propertyLocation.state}` : 'Zoom to property area'}
            >
              <Crosshair className="w-4 h-4" />
              Property Area
            </button>
            <button
              onClick={() => setShowFilters(!showFilters)}
              className={`flex items-center gap-1.5 px-3 py-2 text-sm font-medium rounded-lg border transition-colors ${
                activeFilterCount > 0
                  ? 'text-blue-700 bg-blue-100 border-blue-300'
                  : 'text-gray-600 bg-gray-50 border-gray-200 hover:bg-gray-100'
              }`}
            >
              <Filter className="w-4 h-4" />
              Filters
              {activeFilterCount > 0 && (
                <span className="ml-1 px-1.5 py-0.5 text-xs bg-blue-600 text-white rounded-full">
                  {activeFilterCount}
                </span>
              )}
              {showFilters ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
            </button>
          </div>

          {/* Filter Panel */}
          {showFilters && (
            <div className="p-4 bg-gray-50 rounded-lg border space-y-4">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                {/* Building Size */}
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">Min Units</label>
                  <input
                    type="number"
                    placeholder="e.g. 100"
                    value={pendingFilters.minUnits ?? ''}
                    onChange={(e) => setPendingFilters(prev => ({ ...prev, minUnits: e.target.value ? Number(e.target.value) : undefined }))}
                    className="w-full px-2 py-1.5 text-sm border rounded focus:ring-1 focus:ring-blue-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">Max Units</label>
                  <input
                    type="number"
                    placeholder="e.g. 500"
                    value={pendingFilters.maxUnits ?? ''}
                    onChange={(e) => setPendingFilters(prev => ({ ...prev, maxUnits: e.target.value ? Number(e.target.value) : undefined }))}
                    className="w-full px-2 py-1.5 text-sm border rounded focus:ring-1 focus:ring-blue-500"
                  />
                </div>
                {/* Year Built */}
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">Built After</label>
                  <input
                    type="number"
                    placeholder="e.g. 2010"
                    value={pendingFilters.minYearBuilt ?? ''}
                    onChange={(e) => setPendingFilters(prev => ({ ...prev, minYearBuilt: e.target.value ? Number(e.target.value) : undefined }))}
                    className="w-full px-2 py-1.5 text-sm border rounded focus:ring-1 focus:ring-blue-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">Built Before</label>
                  <input
                    type="number"
                    placeholder="e.g. 2020"
                    value={pendingFilters.maxYearBuilt ?? ''}
                    onChange={(e) => setPendingFilters(prev => ({ ...prev, maxYearBuilt: e.target.value ? Number(e.target.value) : undefined }))}
                    className="w-full px-2 py-1.5 text-sm border rounded focus:ring-1 focus:ring-blue-500"
                  />
                </div>
              </div>

              {/* Amenities */}
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-2">Amenities</label>
                <div className="flex flex-wrap gap-2">
                  {AMENITY_OPTIONS.map(amenity => (
                    <button
                      key={amenity.id}
                      onClick={() => toggleAmenity(amenity.id)}
                      className={`px-3 py-1 text-xs rounded-full border transition-colors ${
                        pendingFilters.amenities.includes(amenity.id)
                          ? 'bg-blue-100 text-blue-700 border-blue-300'
                          : 'bg-white text-gray-600 border-gray-200 hover:bg-gray-50'
                      }`}
                    >
                      {amenity.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* Filter Actions */}
              <div className="flex gap-2 pt-2 border-t">
                <button
                  onClick={applyFilters}
                  className="px-4 py-1.5 text-sm font-medium text-white bg-blue-600 rounded hover:bg-blue-700 transition-colors"
                >
                  Apply Filters
                </button>
                <button
                  onClick={clearFilters}
                  className="px-4 py-1.5 text-sm font-medium text-gray-600 bg-white border rounded hover:bg-gray-50 transition-colors"
                >
                  Clear All
                </button>
              </div>
            </div>
          )}

          {propertyLocation && (
            <p className="text-xs text-gray-500">
              Property location: {propertyLocation.city}, {propertyLocation.state}
            </p>
          )}
        </div>

        {/* Summary Metrics */}
        <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
          <MetricCard
            title="Avg Market Rent"
            value={formatCurrency(data?.avg_market_rent)}
            icon={TrendingUp}
          />
          <MetricCard
            title="Avg Occupancy"
            value={`${data?.avg_occupancy?.toFixed(1) ?? 0}%`}
            icon={Building}
          />
          <MetricCard
            title="Comps Found"
            value={data?.comps.length ?? 0}
            icon={MapPin}
          />
        </div>

        {/* Comps Table */}
        <div>
          <h3 className="text-sm font-semibold text-gray-700 mb-3">Comparable Properties</h3>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Property</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Location</th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Units</th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Year Built</th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Occupancy</th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Avg Rent</th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">1BR Rent</th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">2BR Rent</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {data?.comps.map((comp) => (
                  <tr key={comp.aln_id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 text-sm font-medium text-gray-900">
                      {comp.property_name}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-500">
                      {comp.city}, {comp.state}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-500 text-right">
                      {comp.num_units}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-500 text-right">
                      {comp.year_built ?? '—'}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-500 text-right">
                      {comp.occupancy ? `${comp.occupancy.toFixed(1)}%` : '—'}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-500 text-right">
                      {formatCurrency(comp.average_rent)}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-500 text-right">
                      {formatCurrency(comp.one_bed_rent)}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-500 text-right">
                      {formatCurrency(comp.two_bed_rent)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {(!data?.comps || data.comps.length === 0) && (
            <div className="text-center py-8 text-gray-500">
              No comparable properties found for this submarket
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
