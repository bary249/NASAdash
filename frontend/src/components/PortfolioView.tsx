/**
 * Portfolio View - Compare all properties at a glance
 * 
 * Shows a table/grid of all properties with key metrics and health indicators.
 * Supports two aggregation modes:
 * - Weighted Average: Per-property metrics averaged by unit count
 * - Row Metrics: Combined raw data, metrics calculated from combined dataset
 */
import { useState, useEffect } from 'react';
import { Building2, ChevronDown, ChevronUp, ChevronsUpDown, ExternalLink, Check, Calculator, Table2, Info, Filter } from 'lucide-react';
import { api } from '../api';
import type { PropertyInfo, OccupancyMetrics, ExposureMetrics, LeasingFunnelMetrics, AggregationMode } from '../types';
import { HealthStatus } from './MetricCard';
import { useScramble, useScrambleMode, scrambleName } from './DashboardV3';

interface ExpirationPeriod {
  label: string;
  expirations: number;
  renewals: number;
  signed: number;
  submitted: number;
  selected: number;
  renewal_pct: number;
}

interface PropertySummary {
  property: PropertyInfo;
  occupancy?: OccupancyMetrics;
  exposure?: ExposureMetrics;
  funnel?: LeasingFunnelMetrics;
  expirations?: { periods: ExpirationPeriod[] };
  atr?: { atr: number; atr_pct: number; vacant: number; on_notice: number; preleased: number };
  loading: boolean;
  error?: string;
  selected?: boolean;  // For multi-select
}

// Health calculation helpers
function getOccupancyHealth(value: number): HealthStatus {
  if (value >= 95) return 'good';
  if (value >= 90) return 'warning';
  return 'critical';
}


const healthDot: Record<HealthStatus, string> = {
  good: 'bg-emerald-500',
  warning: 'bg-amber-500',
  critical: 'bg-rose-500',
  neutral: 'bg-slate-300',
};

type SortKey = 'property' | 'units' | 'occupancy' | 'leased' | 'expiring90' | 'renewals90' | 'vacant' | 'atr';
type SortDir = 'asc' | 'desc';

function getSortValue(p: PropertySummary, key: SortKey): number | string {
  switch (key) {
    case 'property': return p.property.name?.toLowerCase() ?? '';
    case 'units': return p.occupancy?.total_units ?? -1;
    case 'occupancy': return p.occupancy?.physical_occupancy ?? -1;
    case 'leased': return p.occupancy?.leased_percentage ?? -1;
    case 'expiring90': return p.expirations?.periods?.find(pr => pr.label === '90d')?.expirations ?? -1;
    case 'renewals90': return p.expirations?.periods?.find(pr => pr.label === '90d')?.renewals ?? -1;
    case 'vacant': return p.occupancy?.vacant_units ?? -1;
    case 'atr': return p.atr?.atr ?? -1;
    default: return 0;
  }
}

interface PortfolioViewProps {
  onSelectProperty: (propertyId: string, propertyName?: string) => void;
  selectedPropertyId?: string;
  selectedPropertyIds?: Set<string>;
  onSelectedPropertyIdsChange?: (ids: Set<string>) => void;
  selectedOwnerGroup?: string;
  onOwnerGroupChange?: (group: string) => void;
}

export function PortfolioView({ onSelectProperty, selectedPropertyId, selectedPropertyIds: externalSelectedIds, onSelectedPropertyIdsChange, selectedOwnerGroup: externalOwnerGroup, onOwnerGroupChange }: PortfolioViewProps) {
  const [expanded, setExpanded] = useState(true);
  const [properties, setProperties] = useState<PropertySummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [aggregationMode, setAggregationMode] = useState<AggregationMode>('row_metrics');
  const [internalSelectedIds, setInternalSelectedIds] = useState<Set<string>>(new Set());
  
  // Use external state if provided, otherwise internal
  const selectedPropertyIds = externalSelectedIds ?? internalSelectedIds;
  const setSelectedPropertyIds = (ids: Set<string>) => {
    if (onSelectedPropertyIdsChange) {
      onSelectedPropertyIdsChange(ids);
    } else {
      setInternalSelectedIds(ids);
    }
  };
  const [showModeInfo, setShowModeInfo] = useState(false);
  const [sortKey, setSortKey] = useState<SortKey | null>(null);
  const [sortDir, setSortDir] = useState<SortDir>('asc');
  const [ownerGroups, setOwnerGroups] = useState<string[]>([]);
  const [internalOwnerGroup, setInternalOwnerGroup] = useState<string>('PHH');
  const selectedOwnerGroup = externalOwnerGroup ?? internalOwnerGroup;
  const setSelectedOwnerGroup = (g: string) => {
    if (onOwnerGroupChange) onOwnerGroupChange(g);
    else setInternalOwnerGroup(g);
  };
  const scramblePII = useScramble();
  const scrambleMode = useScrambleMode();

  // Load owner groups for filter dropdown
  useEffect(() => {
    api.getOwnerGroups().then(groups => {
      setOwnerGroups(groups);
    }).catch(() => {});
  }, []);

  useEffect(() => {
    async function loadPortfolio() {
      try {
        // Fetch from portfolio API to get all properties including RealPage
        const portfolioProps = await api.getPortfolioProperties(selectedOwnerGroup || undefined);
        
        // Map to PropertyInfo format
        const props = portfolioProps.map(p => ({
          id: p.id,
          name: p.name,
          pms_type: p.pms_type,
        }));
        
        // Initialize with loading state
        const summaries: PropertySummary[] = props.map(p => ({
          property: { id: p.id, name: p.name, address: '' },
          loading: true,
        }));
        setProperties(summaries);
        setLoading(false);

        // Auto-select all properties on load so multi-property view works immediately
        if (selectedPropertyIds.size === 0) {
          setSelectedPropertyIds(new Set(props.map(p => p.id)));
        }

        // Load metrics for each property using portfolio API
        await Promise.all(
          props.map(async (p, idx) => {
            try {
              // Fetch portfolio occupancy and per-property occupancy (for aged vacancy) in parallel
              const [occupancyResult, perPropertyOcc] = await Promise.all([
                api.getPortfolioOccupancy([p.id], aggregationMode),
                api.getOccupancy(p.id).catch(() => null),
              ]);
              const propertyOccupancy = occupancyResult.property_breakdown?.[0];
              const agedCount = (perPropertyOcc as any)?.aged_vacancy_90_plus || 0;
              
              const occupancy: Partial<OccupancyMetrics> = propertyOccupancy ? {
                total_units: propertyOccupancy.total_units,
                occupied_units: propertyOccupancy.occupied_units,
                vacant_units: propertyOccupancy.vacant_units,
                leased_units: propertyOccupancy.leased_units,
                physical_occupancy: propertyOccupancy.physical_occupancy,
                leased_percentage: propertyOccupancy.leased_percentage,
                aged_vacancy_90_plus: agedCount,
                preleased_vacant: propertyOccupancy.preleased_vacant || 0,
                vacant_ready: propertyOccupancy.vacant_ready || 0,
                vacant_not_ready: propertyOccupancy.vacant_not_ready || 0,
              } : {
                total_units: 0, occupied_units: 0, vacant_units: 0, leased_units: 0,
                physical_occupancy: 0, leased_percentage: 0, aged_vacancy_90_plus: 0, preleased_vacant: 0,
                vacant_ready: 0, vacant_not_ready: 0,
              };
              
              // Also fetch exposure metrics
              let exposure: Partial<ExposureMetrics> | undefined;
              try {
                exposure = await api.getExposure(p.id);
              } catch {
                // Exposure fetch failed, continue without it
              }

              // Fetch expirations/renewals
              let expirations: { periods: ExpirationPeriod[] } | undefined;
              try {
                expirations = await api.getExpirations(p.id);
              } catch {
                // Expirations fetch failed, continue without it
              }

              // Fetch leasing funnel (last 30 days)
              let funnel: LeasingFunnelMetrics | undefined;
              try {
                funnel = await api.getLeasingFunnel(p.id, 'l30');
              } catch {
                // Funnel fetch failed, continue without it
              }

              // Fetch ATR
              let atr: PropertySummary['atr'] | undefined;
              try {
                const avail = await api.getAvailability(p.id);
                if (avail) atr = { atr: avail.atr, atr_pct: avail.atr_pct, vacant: avail.vacant, on_notice: avail.on_notice, preleased: avail.preleased };
              } catch {
                // ATR fetch failed, continue without it
              }
              
              setProperties(prev => {
                const updated = [...prev];
                updated[idx] = {
                  ...updated[idx],
                  occupancy: occupancy as OccupancyMetrics,
                  exposure: exposure as ExposureMetrics,
                  expirations,
                  funnel,
                  atr,
                  loading: false,
                };
                return updated;
              });
            } catch (err) {
              console.error(`Failed to load ${p.name}:`, err);
              setProperties(prev => {
                const updated = [...prev];
                updated[idx] = {
                  ...updated[idx],
                  loading: false,
                  error: 'Failed to load',
                };
                return updated;
              });
            }
          })
        );
      } catch (err) {
        console.error('Failed to load portfolio:', err);
        setLoading(false);
      }
    }

    loadPortfolio();
  }, [aggregationMode, selectedOwnerGroup]);

  // Toggle property selection for multi-select
  const togglePropertySelection = (propertyId: string) => {
    const next = new Set(selectedPropertyIds);
    if (next.has(propertyId)) {
      next.delete(propertyId);
    } else {
      next.add(propertyId);
    }
    setSelectedPropertyIds(next);
  };

  // Select/deselect all
  const toggleSelectAll = () => {
    if (selectedPropertyIds.size === properties.length) {
      setSelectedPropertyIds(new Set());
    } else {
      setSelectedPropertyIds(new Set(properties.map(p => p.property.id)));
    }
  };

  // Filter properties for totals calculation based on selection
  const selectedProperties = selectedPropertyIds.size > 0 
    ? properties.filter(p => selectedPropertyIds.has(p.property.id))
    : properties;

  // Calculate portfolio totals based on aggregation mode
  const totals = selectedProperties.reduce(
    (acc, p) => {
      if (p.occupancy) {
        acc.totalUnits += p.occupancy.total_units;
        acc.occupiedUnits += p.occupancy.occupied_units;
        acc.vacantUnits += p.occupancy.vacant_units;
        acc.agedVacancy += p.occupancy.aged_vacancy_90_plus;
      }
      if (p.exposure) {
        acc.exposure30 += p.exposure.exposure_30_days;
        acc.notices30 += p.exposure.notices_30_days;
      }
      if (p.funnel) {
        acc.leads += p.funnel.leads;
        acc.tours += p.funnel.tours;
        acc.leaseSigns += p.funnel.lease_signs;
      }
      return acc;
    },
    { totalUnits: 0, occupiedUnits: 0, vacantUnits: 0, agedVacancy: 0, exposure30: 0, notices30: 0, leads: 0, tours: 0, leaseSigns: 0 }
  );

  // Sort properties
  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir(prev => prev === 'asc' ? 'desc' : 'asc');
    } else {
      setSortKey(key);
      setSortDir(key === 'property' ? 'asc' : 'desc');
    }
  };

  const sortedProperties = [...properties].sort((a, b) => {
    if (!sortKey) return 0;
    const aVal = getSortValue(a, sortKey);
    const bVal = getSortValue(b, sortKey);
    let cmp = 0;
    if (typeof aVal === 'string' && typeof bVal === 'string') {
      cmp = aVal.localeCompare(bVal);
    } else {
      cmp = (aVal as number) - (bVal as number);
    }
    return sortDir === 'asc' ? cmp : -cmp;
  });

  // Calculate occupancy based on aggregation mode
  let portfolioOccupancy: number;
  if (aggregationMode === 'row_metrics') {
    // Row Metrics: Calculate from combined raw data
    portfolioOccupancy = totals.totalUnits > 0 
      ? Math.round((totals.occupiedUnits / totals.totalUnits) * 100 * 10) / 10 
      : 0;
  } else {
    // Weighted Average: Simple average of per-property occupancy percentages
    const propsWithOcc = selectedProperties.filter(p => p.occupancy && p.occupancy.total_units > 0);
    const avgSum = propsWithOcc.reduce((sum, p) => sum + (p.occupancy!.physical_occupancy), 0);
    portfolioOccupancy = propsWithOcc.length > 0
      ? Math.round((avgSum / propsWithOcc.length) * 10) / 10
      : 0;
  }

  return (
    <div className="bg-white rounded-venn-lg shadow-venn-card border border-venn-sand/50 overflow-hidden">
      {/* Header */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full px-6 py-5 flex items-center justify-between hover:bg-venn-cream/30 transition-colors"
      >
        <div className="flex items-center gap-4">
          <div className="flex items-center justify-center w-11 h-11 rounded-venn-lg bg-gradient-to-br from-venn-amber to-venn-copper shadow-md shadow-venn-amber/10">
            <Building2 className="w-5 h-5 text-venn-navy" />
          </div>
          <div className="text-left">
            <h2 className="text-lg font-bold text-venn-navy">Portfolio Overview</h2>
            <span className="text-sm text-slate-500">
              {properties.length} properties • {totals.totalUnits} units
            </span>
          </div>
        </div>
        {expanded ? <ChevronUp className="w-5 h-5 text-venn-amber" /> : <ChevronDown className="w-5 h-5 text-venn-amber" />}
      </button>

      {/* Aggregation Mode Toggle */}
      {expanded && (
        <div className="px-6 py-3 border-b border-venn-sand/40 bg-gradient-to-r from-slate-50 to-venn-cream/20 flex items-center justify-between">
          <div className="flex items-center gap-4">
            {/* Owner Group Filter — hidden when user is authenticated (group locked by JWT) */}
            {ownerGroups.length > 1 && !externalOwnerGroup && (
              <div className="flex items-center gap-1.5">
                <Filter className="w-3.5 h-3.5 text-slate-500" />
                <select
                  value={selectedOwnerGroup}
                  onChange={(e) => { e.stopPropagation(); setSelectedOwnerGroup(e.target.value); setSelectedPropertyIds(new Set()); }}
                  onClick={(e) => e.stopPropagation()}
                  className="text-xs font-medium border border-venn-sand rounded-lg px-2 py-1.5 bg-white text-slate-700 focus:ring-venn-amber focus:border-venn-amber cursor-pointer"
                >
                  <option value="">All Groups</option>
                  {ownerGroups.map(g => (
                    <option key={g} value={g}>{g}</option>
                  ))}
                </select>
              </div>
            )}
            {/* Multi-select indicator */}
            {selectedPropertyIds.size > 0 && (
              <span className="text-sm text-venn-amber font-medium">
                {selectedPropertyIds.size} of {properties.length} selected
              </span>
            )}
            <button
              onClick={(e) => { e.stopPropagation(); toggleSelectAll(); }}
              className="text-sm text-slate-600 hover:text-venn-amber underline"
            >
              {selectedPropertyIds.size === properties.length ? 'Deselect All' : 'Select All'}
            </button>
          </div>
          
          {/* Aggregation Mode Toggle */}
          <div className="flex items-center gap-2">
            <span className="text-sm text-slate-600">Aggregation:</span>
            <div className="inline-flex rounded-lg shadow-sm">
              <button
                onClick={(e) => { e.stopPropagation(); setAggregationMode('weighted_avg'); }}
                className={`px-3 py-1.5 text-xs font-medium rounded-l-xl border transition-all ${
                  aggregationMode === 'weighted_avg'
                    ? 'bg-venn-amber text-venn-navy border-venn-amber'
                    : 'bg-white text-slate-700 border-venn-sand hover:bg-venn-cream/50'
                }`}
                title="Calculate per-property metrics, then weighted average by unit count"
              >
                <Calculator className="w-3 h-3 inline mr-1" />
                Weighted Avg
              </button>
              <button
                onClick={(e) => { e.stopPropagation(); setAggregationMode('row_metrics'); }}
                className={`px-3 py-1.5 text-xs font-medium rounded-r-xl border-t border-b border-r transition-all ${
                  aggregationMode === 'row_metrics'
                    ? 'bg-venn-amber text-venn-navy border-venn-amber'
                    : 'bg-white text-slate-700 border-venn-sand hover:bg-venn-cream/50'
                }`}
                title="Combine all raw data, calculate metrics from combined dataset"
              >
                <Table2 className="w-3 h-3 inline mr-1" />
                Row Metrics
              </button>
            </div>
            <button
              onClick={(e) => { e.stopPropagation(); setShowModeInfo(!showModeInfo); }}
              className="p-1 text-slate-400 hover:text-venn-amber transition-colors"
              title="What's the difference?"
            >
              <Info className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}
      
      {/* Mode Info Tooltip */}
      {expanded && showModeInfo && (
        <div className="px-6 py-3 bg-venn-amber/10 border-b border-venn-amber/20 text-sm text-slate-700">
          <strong>Weighted Average:</strong> Calculate metrics for each property, then average weighted by unit count.
          <br />
          <strong>Row Metrics:</strong> Combine all raw data from selected properties, then calculate metrics from the combined dataset.
        </div>
      )}

      {/* Table */}
      {expanded && (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gradient-to-r from-slate-50 to-venn-cream/30 border-y border-venn-sand/40">
              <tr>
                <th className="px-2 py-4 text-center font-semibold text-slate-500 w-10">
                  <input
                    type="checkbox"
                    checked={selectedPropertyIds.size === properties.length && properties.length > 0}
                    onChange={toggleSelectAll}
                    className="rounded border-venn-sand text-venn-amber focus:ring-venn-amber"
                    title="Select all"
                  />
                </th>
                {([
                  { key: 'property' as SortKey, label: 'Property', align: 'left' },
                  { key: 'units' as SortKey, label: 'Units', align: 'center' },
                  { key: 'occupancy' as SortKey, label: 'Occupancy', align: 'center' },
                  { key: 'leased' as SortKey, label: 'Leased %', align: 'center' },
                  { key: 'expiring90' as SortKey, label: 'Expiring 90d', align: 'center' },
                  { key: 'renewals90' as SortKey, label: 'Renewals 90d', align: 'center' },
                  { key: 'atr' as SortKey, label: 'ATR', align: 'center' },
                  { key: 'vacant' as SortKey, label: 'Vacant', align: 'center' },
                ]).map(col => (
                  <th
                    key={col.key}
                    className={`px-5 py-4 text-${col.align} font-bold text-slate-500 uppercase text-xs tracking-wider cursor-pointer select-none hover:text-venn-amber transition-colors group`}
                    onClick={() => handleSort(col.key)}
                  >
                    <span className="inline-flex items-center gap-1">
                      {col.label}
                      {sortKey === col.key ? (
                        sortDir === 'asc' ? <ChevronUp className="w-3.5 h-3.5 text-venn-amber" /> : <ChevronDown className="w-3.5 h-3.5 text-venn-amber" />
                      ) : (
                        <ChevronsUpDown className="w-3.5 h-3.5 text-slate-300 group-hover:text-venn-amber/50" />
                      )}
                    </span>
                  </th>
                ))}
                <th className="px-5 py-4 text-center font-bold text-slate-500"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-venn-sand/30">
              {loading ? (
                <tr>
                  <td colSpan={9} className="px-4 py-8 text-center text-slate-500">
                    <div className="flex items-center justify-center gap-2">
                      <div className="w-5 h-5 border-2 border-venn-amber border-t-transparent rounded-full animate-spin"></div>
                      Loading portfolio...
                    </div>
                  </td>
                </tr>
              ) : properties.length === 0 ? (
                <tr>
                  <td colSpan={9} className="px-4 py-8 text-center text-slate-500">
                    No properties found
                  </td>
                </tr>
              ) : (
                sortedProperties.map((p) => {
                  const isSelected = p.property.id === selectedPropertyId;
                  const isChecked = selectedPropertyIds.has(p.property.id);
                  const occHealth = p.occupancy ? getOccupancyHealth(p.occupancy.physical_occupancy) : 'neutral';
                  
                  return (
                    <tr 
                      key={p.property.id}
                      className={`hover:bg-venn-cream/40 cursor-pointer transition-all duration-200 ${isSelected ? 'bg-venn-amber/10' : ''} ${isChecked ? 'bg-venn-amber/5' : ''}`}
                      onClick={() => onSelectProperty(p.property.id, p.property.name)}
                    >
                      <td className="px-2 py-4 text-center" onClick={(e) => e.stopPropagation()}>
                        <input
                          type="checkbox"
                          checked={isChecked}
                          onChange={() => togglePropertySelection(p.property.id)}
                          className="rounded border-venn-sand text-venn-amber focus:ring-venn-amber"
                        />
                      </td>
                      <td className="px-5 py-4">
                        <div className="flex items-center gap-2">
                          {isChecked && <Check className="w-4 h-4 text-venn-amber" />}
                          <div className="font-semibold text-venn-navy">{scrambleName(p.property.name, scramblePII, scrambleMode)}</div>
                        </div>
                        {p.property.city && !scramblePII && (
                          <div className="text-xs text-slate-500">{p.property.city}, {p.property.state}</div>
                        )}
                      </td>
                      <td className="px-4 py-3 text-center text-slate-600">
                        {p.loading ? '...' : p.occupancy?.total_units ?? '—'}
                      </td>
                      <td className="px-4 py-3 text-center">
                        {p.loading ? '...' : p.occupancy ? (
                          <span className="inline-flex items-center gap-1.5">
                            <span className={`w-2 h-2 rounded-full ${healthDot[occHealth]}`} />
                            <span className={occHealth === 'good' ? 'text-emerald-700 font-semibold' : occHealth === 'warning' ? 'text-amber-700 font-semibold' : 'text-rose-700 font-semibold'}>
                              {p.occupancy.physical_occupancy}%
                            </span>
                          </span>
                        ) : '—'}
                      </td>
                      <td className="px-4 py-3 text-center text-slate-600">
                        {p.loading ? '...' : p.occupancy ? `${p.occupancy.leased_percentage}%` : '—'}
                      </td>
                      <td className="px-4 py-3 text-center">
                        {p.loading ? '...' : p.expirations?.periods?.find(pr => pr.label === '90d')?.expirations ?? '—'}
                      </td>
                      <td className="px-4 py-3 text-center">
                        {(() => {
                          if (p.loading) return '...';
                          const period = p.expirations?.periods?.find(pr => pr.label === '90d');
                          if (!period) return '—';
                          return (
                            <span className={`font-semibold ${period.renewal_pct >= 50 ? 'text-emerald-600' : period.renewal_pct >= 25 ? 'text-amber-600' : 'text-rose-500'}`}>
                              {period.renewals} <span className="text-xs font-normal text-slate-400">({period.renewal_pct}%)</span>
                            </span>
                          );
                        })()}
                      </td>
                      <td className="px-4 py-3 text-center">
                        {p.loading ? '...' : p.atr ? (
                          <span className={`font-semibold ${p.atr.atr > 5 ? 'text-rose-600' : p.atr.atr > 2 ? 'text-amber-600' : 'text-emerald-600'}`}>
                            {p.atr.atr} <span className="text-xs font-normal text-slate-400">({p.atr.atr_pct}%)</span>
                          </span>
                        ) : '—'}
                      </td>
                      <td className="px-4 py-3 text-center text-slate-600">
                        {p.loading ? '...' : p.occupancy?.vacant_units ?? '—'}
                      </td>
                      <td className="px-5 py-4 text-center">
                        <ExternalLink className="w-4 h-4 text-slate-400 hover:text-venn-amber transition-colors" />
                      </td>
                    </tr>
                  );
                })
              )}
              {/* Portfolio totals row */}
              {!loading && properties.length > 0 && (
                <tr className="bg-gradient-to-r from-venn-cream/60 to-slate-50 font-medium">
                  <td className="px-2 py-4"></td>
                  <td className="px-5 py-4 text-venn-navy">
                    <div className="flex items-center gap-2">
                      <span className="font-bold">{selectedPropertyIds.size > 0 ? 'Selected' : 'Portfolio'} Total</span>
                      <span className="text-xs font-normal text-slate-500 bg-white px-2 py-0.5 rounded-lg border border-venn-sand/50">
                        {aggregationMode === 'row_metrics' ? 'Row Metrics' : 'Weighted Avg'}
                      </span>
                    </div>
                  </td>
                  <td className="px-5 py-4 text-center text-venn-navy font-bold">{totals.totalUnits}</td>
                  <td className="px-5 py-4 text-center">
                    <span className="inline-flex items-center gap-1.5">
                      <span className={`w-2 h-2 rounded-full ${healthDot[getOccupancyHealth(portfolioOccupancy)]}`} />
                      <span className="font-semibold">{portfolioOccupancy}%</span>
                    </span>
                  </td>
                  <td className="px-5 py-4 text-center text-slate-500">—</td>
                  <td className="px-5 py-4 text-center text-venn-navy font-semibold">
                    {selectedProperties.reduce((sum, p) => sum + (p.expirations?.periods?.find(pr => pr.label === '90d')?.expirations ?? 0), 0)}
                  </td>
                  <td className="px-5 py-4 text-center text-venn-navy font-semibold">
                    {(() => {
                      const totalRenewals = selectedProperties.reduce((sum, p) => sum + (p.expirations?.periods?.find(pr => pr.label === '90d')?.renewals ?? 0), 0);
                      const totalExpirations = selectedProperties.reduce((sum, p) => sum + (p.expirations?.periods?.find(pr => pr.label === '90d')?.expirations ?? 0), 0);
                      const pct = totalExpirations > 0 ? Math.round(totalRenewals / totalExpirations * 100 * 10) / 10 : 0;
                      return <>{totalRenewals} <span className="text-xs font-normal text-slate-400">({pct}%)</span></>;
                    })()}
                  </td>
                  <td className="px-5 py-4 text-center text-venn-navy font-semibold">
                    {(() => {
                      const totalAtr = selectedProperties.reduce((sum, p) => sum + (p.atr?.atr ?? 0), 0);
                      const atrPct = totals.totalUnits > 0 ? Math.round(totalAtr / totals.totalUnits * 1000) / 10 : 0;
                      return <>{totalAtr} <span className="text-xs font-normal text-slate-400">({atrPct}%)</span></>;
                    })()}
                  </td>
                  <td className="px-5 py-4 text-center text-venn-navy font-semibold">{totals.vacantUnits}</td>
                  <td className="px-5 py-4"></td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
