/**
 * DashboardV3 - Main redesigned dashboard matching the new design mockups
 * Features:
 * - Top search bar with Classic Search / AI Assist toggle
 * - Property selector with timeframe and filters
 * - Tab navigation: Overview, Renewals, Leasing, Delinquencies
 * - Property card with image
 * - KPI grid with metrics
 * - Unit Mix & Pricing section
 * - Market Comps table
 * - Leasing Insight panel
 * - AI Response modal for AI queries
 */
import { useState, useEffect, useCallback } from 'react';
import { 
  RefreshCw, Eye, EyeOff, LogOut,
  Building2, DollarSign, TrendingUp, TrendingDown, Home, ChevronDown
} from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';

import { SearchBar } from './SearchBar';
import { PropertyCard } from './PropertyCard';
import { KPICard, FunnelKPICard, VacantKPICard } from './KPICard';
import { TabNavigation, TabId } from './TabNavigation';
import { UnitMixPricing } from './UnitMixPricing';
import { MarketCompsTable } from './MarketCompsTable';
import { AIInsightsPanel, saveQuestion } from './AIInsightsPanel';
import { GoogleReviewsSection } from './GoogleReviewsSection';
import { ReputationOverview } from './ReputationOverview';
import { RentableItemsSection } from './RentableItemsSection';
import { DelinquencySection } from './DelinquencySection';
import { AvailabilitySection } from './AvailabilitySection';
import { BedroomConsolidatedView } from './BedroomConsolidatedView';
import { WatchpointsPanel } from './WatchpointsPanel';
import { ResidentRiskSection } from './ResidentRiskSection';
import FinancialsSection from './FinancialsSection';
import MarketingSection from './MarketingSection';
import MaintenanceSection from './MaintenanceSection';
import { WatchListTab } from './WatchListTab';
import { DrillThroughModal } from './DrillThroughModal';
import { AIResponseModal, AITableColumn, AITableRow, SuggestedAction } from './AIResponseModal';
import { PortfolioView } from './PortfolioView';
import { InfoTooltip } from './InfoTooltip';


import { api } from '../api';
import { PropertyDataProvider, usePropertyData } from '../data/PropertyDataContext';
import type { MarketComp, UnitPricingMetrics, PropertyInfo } from '../types';

// Context for PII scrambling
import { createContext, useContext } from 'react';

// Two modes: full PII scramble (all properties) and demo mode (only Ridian/Northern)
type ScrambleMode = 'off' | 'full' | 'demo';
const ScrambleContext = createContext<ScrambleMode>('off');
export const useScramble = () => useContext(ScrambleContext) !== 'off';
export const useScrambleMode = () => useContext(ScrambleContext);

// Demo mode mapping for specific properties
const DEMO_NAMES: Record<string, string> = {
  'Ridian': 'XXXX',
  'The Northern': 'YYYY',
};

const SCRAMBLED_NAMES: Record<string, string> = {};
let nameCounter = 1;
export function scrambleName(name: string, enabled: boolean, mode: ScrambleMode = 'full'): string {
  if (!enabled || !name) return name;
  
  // Demo mode: only scramble Ridian and The Northern
  if (mode === 'demo') {
    for (const [key, replacement] of Object.entries(DEMO_NAMES)) {
      if (name.toLowerCase().includes(key.toLowerCase())) {
        return replacement;
      }
    }
    return name; // Don't scramble other properties in demo mode
  }
  
  // Full scramble mode
  if (!SCRAMBLED_NAMES[name]) {
    SCRAMBLED_NAMES[name] = `Property ${String.fromCharCode(64 + nameCounter++)}`;
  }
  return SCRAMBLED_NAMES[name];
}


interface DashboardV3Props {
  initialPropertyId?: string;
}

export function DashboardV3({ initialPropertyId }: DashboardV3Props) {
  const { user, logout } = useAuth();
  
  // Core state
  const [propertyId, setPropertyId] = useState(initialPropertyId || '');
  const [propertyName, setPropertyName] = useState('');
  const [scrambleMode, setScrambleMode] = useState<ScrambleMode>('off');
  const [activeTab, setActiveTab] = useState<TabId>('overview');
  const [timeRange, setTimeRange] = useState<'ytd' | 'mtd' | 'l30' | 'l7'>('mtd');
  const [selectedPropertyIds, setSelectedPropertyIds] = useState<Set<string>>(new Set());
  // Lock owner group to the authenticated user's group — no manual switching
  const [selectedOwnerGroup, setSelectedOwnerGroup] = useState<string>(user?.owner_group || 'PHH');

  // Active property IDs: use checked properties if any, otherwise fall back to single clicked property
  const activePropertyIds = selectedPropertyIds.size > 0
    ? Array.from(selectedPropertyIds)
    : propertyId ? [propertyId] : [];

  // Effective property ID: single clicked property, or first checked property as fallback
  const effectivePropertyId = propertyId || (selectedPropertyIds.size > 0 ? Array.from(selectedPropertyIds)[0] : '');
  
  // AI state
  const [aiLoading, setAILoading] = useState(false);
  const [aiModalOpen, setAIModalOpen] = useState(false);
  const [aiQuery, setAIQuery] = useState('');
  const [aiResponse, setAIResponse] = useState<{
    summary: string;
    columns: AITableColumn[];
    data: AITableRow[];
    actions: SuggestedAction[];
  } | null>(null);

  // Data state
  const [marketComps, setMarketComps] = useState<MarketComp[]>([]);
  const [pricing, setPricing] = useState<UnitPricingMetrics | null>(null);
  const [propertiesMap, setPropertiesMap] = useState<Record<string, PropertyInfo>>({});
  const [selectedPropertyInfo, setSelectedPropertyInfo] = useState<PropertyInfo | null>(null);
  const [groupPropertyIds, setGroupPropertyIds] = useState<string[]>([]);

  // Fetch properties list once on mount for floor_count / google_rating
  useEffect(() => {
    api.getProperties().then(list => {
      const map: Record<string, PropertyInfo> = {};
      for (const p of list) map[p.id] = p;
      setPropertiesMap(map);
    }).catch(() => {});
  }, []);

  // Fetch all property IDs for the selected owner group (for AI Insights fallback)
  useEffect(() => {
    api.getPortfolioProperties(selectedOwnerGroup || undefined)
      .then(list => setGroupPropertyIds(list.map(p => p.id)))
      .catch(() => setGroupPropertyIds([]));
  }, [selectedOwnerGroup]);

  // Property IDs for AI Insights: active selection > group fallback
  const aiPropertyIds = activePropertyIds.length > 0 ? activePropertyIds : groupPropertyIds;

  // Property selection handler (single click on row)
  const handleSelectProperty = useCallback((id: string, name?: string) => {
    setPropertyId(id);
    setPropertyName(name || id);
  }, []);

  // Multi-select handler (checkboxes)
  const handleSelectedPropertyIdsChange = useCallback((ids: Set<string>) => {
    setSelectedPropertyIds(ids);
  }, []);

  // Update selectedPropertyInfo when property or propertiesMap changes
  useEffect(() => {
    if (propertyId && propertiesMap[propertyId]) {
      setSelectedPropertyInfo(propertiesMap[propertyId]);
    }
  }, [propertyId, propertiesMap]);

  // Fetch market comps when property changes
  useEffect(() => {
    if (!propertyId) return;
    
    // Get property location first, then fetch comps
    api.getPropertyLocation(propertyId)
      .then(loc => {
        const submarket = `${loc.city}, ${loc.state}`;
        return api.getMarketComps(submarket, loc.name, 5);
      })
      .then(result => setMarketComps(result.comps))
      .catch(err => console.warn('Failed to fetch market comps:', err));
    
    // Fetch pricing
    api.getPricing(propertyId)
      .then(setPricing)
      .catch(err => console.warn('Failed to fetch pricing:', err));
  }, [propertyId]);

  // AI search handler
  const handleAISearch = async (query: string, isAI: boolean) => {
    if (!isAI) return;
    
    saveQuestion(query);
    setAIQuery(query);
    setAILoading(true);
    setAIModalOpen(true);
    
    try {
      // Detect portfolio-level questions
      const queryLower = query.toLowerCase();
      const isMultiProperty = activePropertyIds.length > 1;
      const isPortfolioQuery = 
        isMultiProperty ||
        queryLower.includes('portfolio') ||
        queryLower.includes('all properties') ||
        queryLower.includes('across properties') ||
        queryLower.includes('highlight') ||
        queryLower.includes('overview') ||
        queryLower.includes('summary of my') ||
        queryLower.includes('how are we doing') ||
        queryLower.includes('performance across') ||
        !propertyId; // If no property selected, treat as portfolio query
      
      let result;
      if (isPortfolioQuery) {
        // Use portfolio chat endpoint for portfolio-level or multi-property questions
        result = await api.sendPortfolioChatMessage(query, []);
      } else {
        // Use property-specific chat endpoint
        result = await api.sendChatMessage(propertyId, query, []);
      }
      
      // Parse AI response - the backend now returns structured data
      const response = result.response;
      const columns = result.columns || [];
      const data = result.data || [];
      const actions = result.actions || [];
      
      setAIResponse({
        summary: response,
        columns: columns,
        data: data,
        actions: actions,
      });
    } catch (err) {
      console.error('AI search failed:', err);
      setAIResponse({
        summary: 'Sorry, I encountered an error processing your request. Please try again.',
        columns: [],
        data: [],
        actions: [],
      });
    } finally {
      setAILoading(false);
    }
  };

  // Helper to check if scrambling is active
  const isScrambleActive = scrambleMode !== 'off';

  return (
    <ScrambleContext.Provider value={scrambleMode}>
      <div className={`min-h-screen bg-slate-100 transition-all duration-300 ${aiModalOpen ? 'overflow-hidden' : ''}`}>
        {/* Header */}
        <header className="bg-white border-b border-gray-200 text-gray-900">
          <div className="max-w-7xl mx-auto px-4 py-3">
            {/* Top row: Logo and actions */}
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-3">
                <p className="text-xl font-light tracking-widest text-gray-400" style={{ fontFamily: 'Georgia, serif' }}>
                  venn
                </p>
                <span className="text-gray-300">|</span>
                <p className="text-sm font-medium text-gray-600">Owner Dashboard</p>
              </div>
              
              <div className="flex items-center gap-2">
                {/* Hide PII Toggle - Full scramble */}
                <button
                  onClick={() => setScrambleMode(scrambleMode === 'full' ? 'off' : 'full')}
                  className={`
                    flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium transition-all
                    ${scrambleMode === 'full' 
                      ? 'bg-amber-500 text-white' 
                      : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                    }
                  `}
                >
                  {scrambleMode === 'full' ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  <span>Hide PII</span>
                </button>

                <button 
                  onClick={() => window.location.reload()}
                  className="p-2 bg-gray-100 hover:bg-gray-200 rounded-lg transition-colors text-gray-500"
                >
                  <RefreshCw className="w-4 h-4" />
                </button>

                {/* User info + Logout */}
                {user && (
                  <div className="flex items-center gap-2 ml-2 pl-2 border-l border-gray-200">
                    <span className="text-xs text-gray-500">{user.display_name}</span>
                    <button
                      onClick={logout}
                      className="p-2 bg-gray-100 hover:bg-red-50 hover:text-red-600 rounded-lg transition-colors text-gray-500"
                      title="Sign out"
                    >
                      <LogOut className="w-4 h-4" />
                    </button>
                  </div>
                )}
              </div>
            </div>

            {/* Search Bar */}
            <div className="py-1">
              <SearchBar
                onSearch={handleAISearch}
                isLoading={aiLoading}
              />
            </div>
          </div>
        </header>

        {/* AI Insights - Full width, above portfolio and tabs */}
        {aiPropertyIds.length > 0 && (
          <div className="max-w-7xl mx-auto px-4 pt-2 pb-1">
            <AIInsightsPanel propertyId={aiPropertyIds[0]} propertyIds={aiPropertyIds} />
          </div>
        )}

        {/* Sub-header: Property selector, timeframe, tabs */}
        <div className="bg-white border-b border-slate-200 sticky top-0 z-30">
          <div className="max-w-7xl mx-auto px-4 py-3">
            <div className="flex items-center justify-center">
              <TabNavigation activeTab={activeTab} onTabChange={setActiveTab} />
            </div>
          </div>
        </div>

        {/* Main Content */}
        <main className="max-w-7xl mx-auto px-4 py-6">
          {/* Watchpoints — shown when watchpoints tab active */}
          {activeTab === 'watchpoints' && (
            <div className="mb-6">
              {propertyId ? (
                <WatchpointsPanel propertyId={propertyId} />
              ) : (
                <div className="bg-white rounded-xl border border-slate-200 p-8 text-center text-sm text-slate-500">
                  Select a property from the portfolio table below to view and manage watchpoints.
                </div>
              )}
            </div>
          )}

          {/* Watchlist — portfolio-level, shown when watchlist tab active */}
          {activeTab === 'watchlist' && (
            <div className="mb-6">
              <WatchListTab
                onPropertyClick={(id) => {
                  const info = propertiesMap[id];
                  setPropertyId(id);
                  setPropertyName(info?.name || id);
                  setActiveTab('overview');
                }}
                ownerGroup={selectedOwnerGroup}
                propertyIds={activePropertyIds}
              />
            </div>
          )}

          {/* Portfolio Overview (collapsible) */}
          <div className="mb-6">
            <PortfolioView 
              onSelectProperty={handleSelectProperty}
              selectedPropertyId={propertyId}
              selectedPropertyIds={selectedPropertyIds}
              onSelectedPropertyIdsChange={handleSelectedPropertyIdsChange}
              selectedOwnerGroup={selectedOwnerGroup}
              onOwnerGroupChange={setSelectedOwnerGroup}
            />
          </div>

          {/* Time Selection Strip */}
          <div className="mb-4 flex items-center gap-2">
            <span className="text-xs font-medium text-slate-500 uppercase tracking-wide mr-2">Period</span>
            {([
              { key: 'ytd' as const, label: 'YTD' },
              { key: 'mtd' as const, label: 'MTD' },
              { key: 'l30' as const, label: 'Last 30d' },
              { key: 'l7' as const, label: 'Last 7d' },
            ]).map(t => (
              <button
                key={t.key}
                onClick={() => setTimeRange(t.key)}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                  timeRange === t.key
                    ? 'bg-slate-800 text-white shadow-sm'
                    : 'bg-white text-slate-600 border border-slate-200 hover:bg-slate-50'
                }`}
              >
                {t.label}
              </button>
            ))}
          </div>

          {/* Property Dashboard */}
          {effectivePropertyId ? (
            <PropertyDataProvider propertyId={effectivePropertyId} propertyIds={activePropertyIds} timeframe={timeRange === 'mtd' ? 'cm' : timeRange === 'ytd' ? 'ytd' : timeRange === 'l30' ? 'l30' : 'l7'}>
              <PropertyDashboard
                propertyId={effectivePropertyId}
                propertyIds={activePropertyIds}
                propertyName={activePropertyIds.length > 1
                  ? `${activePropertyIds.length} Properties Selected`
                  : scrambleName(propertyName || propertiesMap[effectivePropertyId]?.name || effectivePropertyId, isScrambleActive, scrambleMode)}
                originalPropertyName={propertyName || propertiesMap[effectivePropertyId]?.name || effectivePropertyId}
                pricing={pricing}
                marketComps={marketComps}
                activeTab={activeTab}
                propertyInfo={selectedPropertyInfo || propertiesMap[effectivePropertyId] || null}
                timeRange={timeRange}
              />
            </PropertyDataProvider>
          ) : activeTab !== 'watchlist' && activeTab !== 'watchpoints' ? (
            <div className="bg-white rounded-2xl border border-slate-200 p-12 text-center">
              <div className="w-16 h-16 rounded-2xl bg-indigo-100 flex items-center justify-center mx-auto mb-4">
                <Building2 className="w-8 h-8 text-indigo-600" />
              </div>
              <h3 className="text-lg font-semibold text-slate-700 mb-2">Select a Property</h3>
              <p className="text-slate-500">Choose a property from the portfolio above to view detailed metrics</p>
            </div>
          ) : null}
        </main>

        {/* AI Response Modal */}
        <AIResponseModal
          isOpen={aiModalOpen}
          onClose={() => setAIModalOpen(false)}
          query={aiQuery}
          summary={aiResponse?.summary || ''}
          columns={aiResponse?.columns || []}
          data={aiResponse?.data || []}
          suggestedActions={aiResponse?.actions || []}
          isLoading={aiLoading}
        />
      </div>
    </ScrambleContext.Provider>
  );
}

/**
 * PropertyDashboard - Inner component that uses PropertyDataContext
 */
interface PropertyDashboardProps {
  propertyId: string;
  propertyIds: string[];
  propertyName: string;
  originalPropertyName: string;
  pricing: UnitPricingMetrics | null;
  marketComps: MarketComp[];
  activeTab: TabId;
  propertyInfo?: PropertyInfo | null;
  timeRange?: 'ytd' | 'mtd' | 'l30' | 'l7';
}

// Property image mapping
const propertyImages: Record<string, string> = {
  'Nexus East': '/NexusEast.jpg',
  'Parkside at Round Rock': '/Parkside.jpg',
  'The Northern': '/Northern.jpg',
  'Ridian': '/Ridian.jpg',
  // Fallbacks for demo mode scrambled names
  'YYYY': '/Northern.jpg',
  'XXXX': '/Ridian.jpg',
};

function getPropertyImage(name: string): string | undefined {
  if (!name) return undefined;
  // Check for exact match first
  if (propertyImages[name]) return propertyImages[name];
  // Check for partial match (case insensitive)
  const nameLower = name.toLowerCase();
  for (const [key, url] of Object.entries(propertyImages)) {
    if (nameLower.includes(key.toLowerCase()) || key.toLowerCase().includes(nameLower)) {
      return url;
    }
  }
  return undefined;
}

const statusCellClass = (v: unknown) => {
  const s = String(v);
  if (s === 'Renewal Signed') return 'text-emerald-600 font-semibold';
  if (s === 'Notice Given') return 'text-rose-600 font-semibold';
  return 'text-gray-900';
};

const EXPIRATION_DRILL_COLUMNS = [
  { key: 'unit', label: 'Unit' },
  { key: 'floorplan', label: 'Floorplan' },
  { key: 'sqft', label: 'Sq Ft', format: (v: unknown) => Number(v) > 0 ? Number(v).toLocaleString() : '—' },
  { key: 'market_rent', label: 'Market Rent', format: (v: unknown) => Number(v) > 0 ? `$${Number(v).toLocaleString()}` : '—' },
  { key: 'lease_end', label: 'Lease End' },
  { key: 'status', label: 'Status', cellClassName: statusCellClass },
  { key: 'move_in', label: 'Move In' },
];

const RENEWAL_DRILL_COLUMNS = [
  { key: 'unit', label: 'Unit' },
  { key: 'floorplan', label: 'Floorplan' },
  { key: 'sqft', label: 'Sq Ft', format: (v: unknown) => Number(v) > 0 ? Number(v).toLocaleString() : '—' },
  { key: 'market_rent', label: 'Market Rent', format: (v: unknown) => Number(v) > 0 ? `$${Number(v).toLocaleString()}` : '—' },
  { key: 'lease_end', label: 'Current Lease End' },
  { key: 'status', label: 'Status', cellClassName: statusCellClass },
  { key: 'renewal_type', label: 'Renewal Type' },
  { key: 'move_in', label: 'Move In' },
];

function PropertyDashboard({ propertyId, propertyIds, propertyName, originalPropertyName, pricing, marketComps, activeTab, propertyInfo, timeRange = 'mtd' }: PropertyDashboardProps) {
  const { occupancy, funnel, expirations, loading, error, periodEnd } = usePropertyData();

  const periodLabel = timeRange === 'ytd' ? 'YTD' : timeRange === 'mtd' ? 'MTD' : timeRange === 'l30' ? 'Last 30 days' : 'Last 7 days';

  // New KPI data
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const [atrData, setAtrData] = useState<any>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const [showsL7, setShowsL7] = useState<any>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const [tradeoutData, setTradeoutData] = useState<any>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const [availByFp, setAvailByFp] = useState<any>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const [forecast, setForecast] = useState<any>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const [renewalData, setRenewalData] = useState<any>(null);
  const [availCollapsed, setAvailCollapsed] = useState(false);
  const [forecastCollapsed, setForecastCollapsed] = useState(false);
  const [renewalViewMode, setRenewalViewMode] = useState<'rolling' | 'monthly'>('rolling');

  // KPI drill-down state
  const [kpiDrillOpen, setKpiDrillOpen] = useState(false);
  const [kpiDrillTitle, setKpiDrillTitle] = useState('');
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const [kpiDrillData, setKpiDrillData] = useState<any[]>([]);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const [kpiDrillColumns, setKpiDrillColumns] = useState<any[]>([]);
  const [kpiDrillLoading, setKpiDrillLoading] = useState(false);

  useEffect(() => {
    if (!propertyIds.length) return;
    const ids = propertyIds;

    // ATR: sum across properties
    Promise.all(ids.map(id => api.getAvailability(id).catch(() => null)))
      .then(results => {
        const valid = results.filter((r: any) => r != null);
        if (valid.length === 0) { setAtrData(null); return; }
        const merged = {
          atr: valid.reduce((s: number, r: any) => s + (r.atr || 0), 0),
          total_units: valid.reduce((s: number, r: any) => s + (r.total_units || 0), 0),
          vacant: valid.reduce((s: number, r: any) => s + (r.vacant || 0), 0),
          on_notice: valid.reduce((s: number, r: any) => s + (r.on_notice || 0), 0),
          preleased: valid.reduce((s: number, r: any) => s + (r.preleased || 0), 0),
          atr_pct: 0,
        };
        merged.atr_pct = merged.total_units > 0 ? Math.round(merged.atr / merged.total_units * 1000) / 10 : 0;
        setAtrData(merged);
      }).catch(() => {});

    // Shows: sum across properties, merge details + by_date for drill-through
    Promise.all(ids.map(id => api.getShows(id, 7).catch(() => ({ total_shows: 0, details: [], by_date: [] }))))
      .then(results => {
        const allDetails = results.flatMap((r: any) => r?.details || []);
        // Merge by_date across properties, summing counts per unique date
        const dateMap: Record<string, number> = {};
        for (const r of results as any[]) {
          for (const d of (r?.by_date || [])) {
            dateMap[d.date] = (dateMap[d.date] || 0) + d.count;
          }
        }
        const mergedByDate = Object.entries(dateMap).map(([date, count]) => ({ date, count })).sort((a, b) => a.date.localeCompare(b.date));
        setShowsL7({
          total_shows: results.reduce((s: number, r: any) => s + (r?.total_shows || 0), 0),
          details: allDetails,
          by_date: mergedByDate,
        });
      }).catch(() => {});

    // Tradeouts: concat arrays, recalculate summary
    Promise.all(ids.map(id => api.getTradeouts(id, 30).catch(() => ({ tradeouts: [], summary: {} }))))
      .then(results => {
        const allTradeouts = results.flatMap((r: any) => r?.tradeouts || []);
        const totalPrior = allTradeouts.reduce((s: number, t: any) => s + (t.prior_rent || 0), 0);
        const totalNew = allTradeouts.reduce((s: number, t: any) => s + (t.new_rent || 0), 0);
        const count = allTradeouts.length;
        setTradeoutData({
          tradeouts: allTradeouts,
          summary: {
            count,
            avg_prior_rent: count > 0 ? Math.round(totalPrior / count) : 0,
            avg_new_rent: count > 0 ? Math.round(totalNew / count) : 0,
            avg_dollar_change: count > 0 ? Math.round((totalNew - totalPrior) / count) : 0,
            avg_pct_change: totalPrior > 0 ? Math.round((totalNew - totalPrior) / totalPrior * 1000) / 10 : 0,
          },
        });
      }).catch(() => {});

    // Availability by floorplan: merge across properties
    Promise.all(ids.map(id => api.getAvailabilityByFloorplan(id).catch(() => ({ floorplans: [], totals: {} }))))
      .then(results => {
        const allFps = results.flatMap((r: any) => r?.floorplans || []);
        const totals = { total: 0, vacant: 0, notice: 0, vacant_leased: 0, vacant_not_leased: 0, occupied: 0, model: 0, down: 0 };
        for (const r of results) {
          const rt = (r as any)?.totals;
          if (rt) {
            for (const k of Object.keys(totals) as (keyof typeof totals)[]) {
              totals[k] += rt[k] || 0;
            }
          }
        }
        setAvailByFp({ floorplans: allFps, totals });
      }).catch(() => {});

    // Forecast: merge across properties by week index
    Promise.all(ids.map(id => api.getOccupancyForecast(id, 12).catch(() => null)))
      .then(results => {
        const valid = results.filter((r: any) => r && r.forecast && r.forecast.length > 0);
        if (valid.length === 0) { setForecast(null); return; }
        if (valid.length === 1) { setForecast(valid[0]); return; }
        // Merge by week index: sum numerics, concat unit arrays
        const maxWeeks = Math.max(...valid.map((r: any) => r.forecast.length));
        const merged: any[] = [];
        for (let w = 0; w < maxWeeks; w++) {
          const base: any = { week: w + 1, week_start: '', week_end: '', projected_occupied: 0, projected_occupancy_pct: 0, scheduled_move_ins: 0, scheduled_move_outs: 0, notice_move_outs: 0, lease_expirations: 0, renewals: 0, net_expirations: 0, net_change: 0 };
          let totalUnits = 0;
          for (const r of valid as any[]) {
            const fw = r.forecast[w];
            if (!fw) continue;
            if (w === 0 || !base.week_start) { base.week_start = fw.week_start; base.week_end = fw.week_end; }
            base.projected_occupied += fw.projected_occupied || 0;
            base.scheduled_move_ins += fw.scheduled_move_ins || 0;
            base.scheduled_move_outs += fw.scheduled_move_outs || 0;
            base.notice_move_outs += fw.notice_move_outs || 0;
            base.lease_expirations += fw.lease_expirations || 0;
            base.renewals += fw.renewals || 0;
            base.net_expirations += fw.net_expirations || 0;
            base.net_change += fw.net_change || 0;
            totalUnits += r.total_units || 0;
          }
          base.projected_occupancy_pct = totalUnits > 0 ? Math.round(base.projected_occupied / totalUnits * 1000) / 10 : 0;
          merged.push(base);
        }
        setForecast({
          forecast: merged,
          current_occupied: valid.reduce((s: number, r: any) => s + (r.current_occupied || 0), 0),
          total_units: valid.reduce((s: number, r: any) => s + (r.total_units || 0), 0),
          current_notice: valid.reduce((s: number, r: any) => s + (r.current_notice || 0), 0),
          vacant_leased: valid.reduce((s: number, r: any) => s + (r.vacant_leased || 0), 0),
          undated_move_ins: valid.reduce((s: number, r: any) => s + (r.undated_move_ins || 0), 0),
          notice_units: valid.flatMap((r: any) => r.notice_units || []),
          move_in_units: valid.flatMap((r: any) => r.move_in_units || []),
          expiration_units: valid.flatMap((r: any) => r.expiration_units || []),
        });
      }).catch(() => {});

    // Renewals: merge across properties
    Promise.all(ids.map(id => api.getRenewals(id, 30).catch(() => ({ renewals: [], summary: {} }))))
      .then(results => {
        const allRenewals = results.flatMap((r: any) => r?.renewals || []);
        const totalRent = allRenewals.reduce((s: number, r: any) => s + (r.renewal_rent || 0), 0);
        const totalPrior = allRenewals.reduce((s: number, r: any) => s + (r.prior_rent || 0), 0);
        const count = allRenewals.length;
        setRenewalData({
          renewals: allRenewals,
          summary: {
            count,
            avg_renewal_rent: count > 0 ? Math.round(totalRent / count) : 0,
            avg_prior_rent: count > 0 ? Math.round(totalPrior / count) : 0,
            avg_vs_prior: count > 0 ? Math.round((totalRent - totalPrior) / count) : 0,
            avg_vs_prior_pct: totalPrior > 0 ? Math.round((totalRent - totalPrior) / totalPrior * 1000) / 10 : 0,
          },
        });
      }).catch(() => {});
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [propertyIds.join(',')]);

  // Drill-through state for renewals
  const [drillOpen, setDrillOpen] = useState(false);
  const [drillTitle, setDrillTitle] = useState('');
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const [drillData, setDrillData] = useState<any[]>([]);
  const [drillLoading, setDrillLoading] = useState(false);
  const [drillFilter, setDrillFilter] = useState<'renewed' | 'expiring' | 'vacating' | 'pending' | 'mtm' | 'moved_out' | undefined>(undefined);

  const UNIT_COLUMNS = [
    { key: 'unit', label: 'Unit' },
    { key: 'floorplan', label: 'Floorplan' },
    { key: 'status', label: 'Status' },
    { key: 'sqft', label: 'SqFt', format: (v: unknown) => v ? String(v) : '—' },
    { key: 'market_rent', label: 'Market Rent', format: (v: unknown) => v ? `$${Number(v).toLocaleString()}` : '—' },
    { key: 'actual_rent', label: 'Actual Rent', format: (v: unknown) => v ? `$${Number(v).toLocaleString()}` : '—' },
    { key: 'lease_end', label: 'Lease End' },
    { key: 'days_vacant', label: 'Days Vacant', format: (v: unknown) => v != null ? `${v}d` : '—' },
  ];

  const FORECAST_UNIT_COLUMNS = [
    { key: 'unit', label: 'Unit' },
    { key: 'floorplan', label: 'Floorplan' },
    { key: 'type', label: 'Category', format: (v: unknown) => {
      const m: Record<string, string> = {
        notice_move_out: 'Notice Move-Out',
        scheduled_move_in: 'Scheduled Move-In',
        scheduled_move_in_undated: 'Pre-Leased (date TBD)',
        lease_expiration: 'Expiring',
        lease_expiration_renewed: 'Renewed',
      };
      return m[String(v)] || String(v);
    }, cellClassName: (v: unknown) => v === 'lease_expiration_renewed' ? 'text-emerald-600 font-medium' : v === 'lease_expiration' ? 'text-amber-600' : 'text-gray-900' },
    { key: 'date', label: 'Date' },
    { key: 'rent', label: 'Rent', format: (v: unknown) => v ? `$${Number(v).toLocaleString()}` : '—' },
  ];

  const TRADEOUT_COLUMNS = [
    { key: 'unit_id', label: 'Unit' },
    { key: 'unit_type', label: 'Type' },
    { key: 'prior_rent', label: 'Prior Rent', format: (v: unknown) => `$${Number(v).toLocaleString()}` },
    { key: 'new_rent', label: 'New Rent', format: (v: unknown) => `$${Number(v).toLocaleString()}` },
    { key: 'dollar_change', label: '$ Change', format: (v: unknown) => { const n = Number(v); return `${n >= 0 ? '+' : ''}$${n.toLocaleString()}`; } },
    { key: 'pct_change', label: '% Change', format: (v: unknown) => { const n = Number(v); return `${n >= 0 ? '+' : ''}${n.toFixed(1)}%`; } },
    { key: 'move_in_date', label: 'Move In' },
  ];

  const RENEWAL_COLUMNS = [
    { key: 'unit_id', label: 'Unit' },
    { key: 'floorplan', label: 'Floorplan' },
    { key: 'renewal_rent', label: 'Renewal Rent', format: (v: unknown) => `$${Number(v).toLocaleString()}` },
    { key: 'prior_rent', label: 'Prior Rent', format: (v: unknown) => `$${Number(v).toLocaleString()}` },
    { key: 'vs_prior', label: 'vs Prior', format: (v: unknown) => { const n = Number(v); return `${n >= 0 ? '+' : ''}$${n.toLocaleString()}`; } },
    { key: 'vs_prior_pct', label: '% Change', format: (v: unknown) => { const n = Number(v); return `${n >= 0 ? '+' : ''}${n.toFixed(1)}%`; } },
    { key: 'lease_start', label: 'Start Date' },
    { key: 'lease_term', label: 'Term' },
  ];

  const filterUnitsByWeek = useCallback((units: { date?: string | null }[], weekStart?: string, weekEnd?: string) => {
    if (!weekStart || !weekEnd) return units;
    const ws = new Date(weekStart + 'T00:00:00');
    const we = new Date(weekEnd + 'T23:59:59');
    return units.filter(u => {
      if (!u.date) return false;
      // Parse MM/DD/YYYY format
      const parts = u.date.split('/');
      if (parts.length !== 3) return false;
      const d = new Date(Number(parts[2]), Number(parts[0]) - 1, Number(parts[1]));
      return d >= ws && d <= we;
    });
  }, []);

  const openKpiDrill = useCallback(async (type: string, param?: string, weekStart?: string, weekEnd?: string) => {
    setKpiDrillLoading(true);
    setKpiDrillOpen(true);
    const weekLabel = weekStart ? ` (${weekStart.slice(5)} – ${weekEnd?.slice(5)})` : '';

    try {
      if (type === 'availability') {
        setKpiDrillTitle(`Units — ${param || 'All'}`);
        setKpiDrillColumns(UNIT_COLUMNS);
        const result = await api.getAvailabilityUnits(propertyId, param || undefined);
        setKpiDrillData(result.units);
      } else if (type === 'availability_status') {
        const label = param === 'notice' ? 'Notice Units' : param === 'vacant' ? 'Vacant Units' : `${param} Units`;
        setKpiDrillTitle(label);
        setKpiDrillColumns(UNIT_COLUMNS);
        const result = await api.getAvailabilityUnits(propertyId, undefined, param);
        setKpiDrillData(result.units);
      } else if (type === 'forecast_notice') {
        setKpiDrillTitle(`Notice Move-Out Units${weekLabel}`);
        setKpiDrillColumns(FORECAST_UNIT_COLUMNS);
        setKpiDrillData(filterUnitsByWeek(forecast?.notice_units || [], weekStart, weekEnd));
      } else if (type === 'forecast_moveins') {
        const allMoveIns = forecast?.move_in_units || [];
        const filtered = filterUnitsByWeek(allMoveIns, weekStart, weekEnd);
        const weekRange = weekStart && weekEnd
          ? `${weekStart.slice(5).replace('-','/')} – ${weekEnd.slice(5).replace('-','/')}`
          : null;
        let units;
        if (filtered.length > 0) {
          units = filtered;
        } else if (weekStart && forecast?.forecast) {
          // Distribute undated units across weeks by report count
          const weeks = forecast.forecast as { week_start: string; scheduled_move_ins: number }[];
          let offset = 0;
          let sliceCount = 0;
          for (const fw of weeks) {
            if (fw.week_start === weekStart) {
              sliceCount = fw.scheduled_move_ins;
              break;
            }
            offset += fw.scheduled_move_ins;
          }
          units = allMoveIns.slice(offset, offset + sliceCount)
            .map((u: Record<string, unknown>) => ({ ...u, date: weekRange }));
        } else {
          units = allMoveIns.map((u: Record<string, unknown>) => ({ ...u, date: (u.date as string) || weekRange }));
        }
        setKpiDrillTitle(`Scheduled Move-In Units${weekLabel}`);
        setKpiDrillData(units);
        setKpiDrillColumns(FORECAST_UNIT_COLUMNS);
      } else if (type === 'forecast_expirations') {
        setKpiDrillTitle(`Lease Expirations${weekLabel}`);
        setKpiDrillColumns(FORECAST_UNIT_COLUMNS);
        setKpiDrillData(filterUnitsByWeek(forecast?.expiration_units || [], weekStart, weekEnd));
      } else if (type === 'tradeouts') {
        setKpiDrillTitle('Lease Trade-Outs — Unit Detail');
        setKpiDrillColumns(TRADEOUT_COLUMNS);
        setKpiDrillData(tradeoutData?.tradeouts || []);
      } else if (type === 'atr') {
        setKpiDrillTitle('ATR Units — Vacant + On Notice');
        setKpiDrillColumns(UNIT_COLUMNS);
        const results = await Promise.all(
          propertyIds.map(id => api.getAvailabilityUnits(id).catch(() => ({ units: [], count: 0 })))
        );
        const allUnits = results.flatMap((r: any) => r.units || []);
        // Show Vacant + On Notice + Admin/Down (NOT Vacant-Leased — those are pre-leased and subtracted)
        // Admin/Down included because box_score counts them within vacant_units (down=0)
        const atrUnits = allUnits.filter((u: any) =>
          ['Vacant', 'Occupied-NTV', 'Occupied-NTVL', 'Admin/Down'].includes(u.status)
        );
        setKpiDrillData(atrUnits);
      } else if (type === 'renewals') {
        setKpiDrillTitle('Renewal Leases — Rent vs Prior');
        setKpiDrillColumns(RENEWAL_COLUMNS);
        setKpiDrillData(renewalData?.renewals || []);
      }
    } catch {
      setKpiDrillData([]);
    } finally {
      setKpiDrillLoading(false);
    }
  }, [propertyId, forecast, tradeoutData, showsL7, renewalData, filterUnitsByWeek]);

  const openDrill = useCallback(async (days: number, filter?: 'renewed' | 'expiring' | 'vacating' | 'pending' | 'mtm' | 'moved_out') => {
    setDrillFilter(filter);
    const labels: Record<string, string> = {
      renewed: 'Renewed Leases',
      expiring: 'Expiring (not renewed)',
      vacating: 'Vacating Leases',
      pending: 'Pending Decision',
      mtm: 'Month-to-Month Leases',
      moved_out: 'Moved Out',
    };
    const label = filter ? labels[filter] || 'All Leases' : 'All Expiring Leases';
    setDrillTitle(`${label} — Next ${days} Days`);
    setDrillOpen(true);
    setDrillLoading(true);
    try {
      const result = await api.getExpirationDetails(propertyId, days, filter);
      setDrillData(result.leases);
    } catch {
      setDrillData([]);
    } finally {
      setDrillLoading(false);
    }
  }, [propertyId]);

  if (loading) {
    return (
      <div className="grid grid-cols-12 gap-6 animate-pulse">
        <div className="col-span-3 h-72 bg-slate-200 rounded-2xl" />
        <div className="col-span-9 grid grid-cols-4 gap-4">
          {[...Array(8)].map((_, i) => (
            <div key={i} className="h-28 bg-slate-200 rounded-xl" />
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-rose-50 border border-rose-200 rounded-2xl p-6 text-rose-700">
        {error}
      </div>
    );
  }

  // Prepare unit mix data from pricing
  const floorplans = pricing?.floorplans?.map(fp => ({
    name: fp.name,
    unitCount: fp.unit_count,
    inPlaceRent: fp.in_place_rent,
    askingRent: fp.asking_rent,
  })) || [];

  // Prepare market comps data
  const compsData = marketComps.map(c => ({
    name: c.property_name,
    studioRent: c.studio_rent,
    oneBedRent: c.one_bed_rent,
    twoBedRent: c.two_bed_rent,
    threeBedRent: c.three_bed_rent,
    isSubject: c.property_name === propertyName,
  }));

  // Calculate renewal trend from expirations data
  const exp90 = expirations?.periods?.find(p => p.label === '90d');
  const renewalTrend = exp90?.renewal_pct ?? 0;
  
  // Calculate lease trade-out values (use real data if available)
  const tradeoutSummary = tradeoutData?.summary;
  const avgTradeOut = tradeoutSummary?.count ? tradeoutSummary.avg_new_rent : (pricing?.total_asking_rent || 0);
  const prevTradeOut = tradeoutSummary?.count ? tradeoutSummary.avg_prior_rent : (pricing?.total_in_place_rent || 0);
  const tradeoutPct = tradeoutSummary?.count ? tradeoutSummary.avg_pct_change : 0;
  const renewalSummary = renewalData?.summary;
  const renewalCount = renewalSummary?.count ?? 0;
  const avgRenewalRent = renewalSummary?.avg_renewal_rent ?? 0;
  const renewalVsPriorPct = renewalSummary?.avg_vs_prior_pct ?? 0;

  // Format "as of" date for KPI labels (from context periodEnd)
  const asOfLabel = periodEnd
    ? `as of ${periodEnd.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}`
    : '';

  return (
    <div className="space-y-6">
      {/* Main Grid: Property Card + KPIs */}
      <div className="grid grid-cols-12 gap-6">
        {/* Property Card - Left */}
        <div className="col-span-12 lg:col-span-3">
          <PropertyCard
            name={propertyName}
            units={occupancy?.totalUnits || 0}
            floors={propertyInfo?.floor_count}
            rating={propertyInfo?.google_rating}
            reviewCount={propertyInfo?.google_review_count}
            vacantReady={occupancy?.vacantReady || 0}
            agedVacancy={occupancy?.agedVacancy90Plus || 0}
            imageUrl={getPropertyImage(originalPropertyName)}
          />
        </div>

        {/* KPIs Grid - Right */}
        <div className="col-span-12 lg:col-span-9">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {/* Row 1 */}
            <KPICard
              title="Occupancy"
              value={`${occupancy?.physicalOccupancy || 0}%`}
              timeLabel={asOfLabel}
              icon={<Home className="w-4 h-4" />}
              tooltip="Physical occupancy = Occupied Units ÷ Total Units × 100. Source: RealPage Box Score."
            />
            
            <KPICard
              title="In-Place"
              value={`$${pricing?.total_in_place_rent?.toLocaleString() || '—'}`}
              subtitle={`Asking $${pricing?.total_asking_rent?.toLocaleString() || '—'}`}
              timeLabel={asOfLabel}
              icon={<DollarSign className="w-4 h-4" />}
              tooltip="Weighted avg actual rent across occupied units (In-Place). Asking = avg market rent across all units. Source: RealPage Rent Roll."
            />
            
            <KPICard
              title="Renewal Rate (90d)"
              value={`${renewalTrend}%`}
              subtitle={`${exp90?.renewals ?? 0} of ${exp90?.expirations ?? 0} renewed`}
              icon={<TrendingUp className="w-4 h-4" />}
              tooltip="Leases with status 'Current - Future' ÷ All leases expiring within 90 days × 100. Source: RealPage Leases."
            />
            
            <div role="button" tabIndex={0} onClick={() => openKpiDrill('tradeouts')} onKeyDown={e => e.key === 'Enter' && openKpiDrill('tradeouts')} className="text-left w-full">
              <KPICard
                title={`Trade Outs${tradeoutSummary?.count ? ` (${tradeoutSummary.count})` : ''}`}
                value={avgTradeOut ? `$${Math.round(avgTradeOut).toLocaleString()}` : '—'}
                subtitle={prevTradeOut ? `Prior $${Math.round(prevTradeOut).toLocaleString()} (${tradeoutPct >= 0 ? '+' : ''}${tradeoutPct.toFixed(1)}%)` : 'No trade-out data'}
                timeLabel={periodLabel}
                icon={<DollarSign className="w-4 h-4" />}
                tooltip="Avg new rent for recent move-ins vs prior tenant's rent on the same unit. % Change = (New − Prior) ÷ Prior × 100. Source: RealPage Rent Roll."
              />
            </div>

            {/* Row 2 */}
            <VacantKPICard
              total={availByFp?.totals?.vacant ?? occupancy?.vacantUnits ?? 0}
              ready={occupancy?.vacantReady || 0}
              agedCount={occupancy?.agedVacancy90Plus}
              timeLabel={asOfLabel}
              tooltip="Total vacant units from Box Score. Ready = units with made-ready date. Aged = vacant > 90 days. Source: RealPage Box Score."
            />
            
            <div role="button" tabIndex={0} onClick={() => openKpiDrill('atr')} onKeyDown={e => e.key === 'Enter' && openKpiDrill('atr')} className="text-left w-full">
              <KPICard
                title="ATR"
                value={atrData ? String(atrData.atr) : '—'}
                subtitle={atrData ? `${atrData.atr_pct}% of ${atrData.total_units} units` : ''}
                icon={<Home className="w-4 h-4" />}
                tooltip="Actual-To-Rent = Vacant + On Notice − Pre-leased. Represents the true number of units that need to be filled. Source: RealPage Box Score."
              />
            </div>

            <FunnelKPICard
              leads={funnel?.leads || 0}
              tours={funnel?.tours || 0}
              applications={funnel?.applications || 0}
              leasesSigned={funnel?.leaseSigns || 0}
              sightUnseen={funnel?.sightUnseen || 0}
              tourToApp={funnel?.tourToApp || 0}
              timeLabel={periodLabel}
            />
            
            <div role="button" tabIndex={0} onClick={() => openKpiDrill('renewals')} onKeyDown={e => e.key === 'Enter' && openKpiDrill('renewals')} className="text-left w-full">
              <KPICard
                title={`Renewals${renewalCount ? ` (${renewalCount})` : ''}`}
                value={avgRenewalRent ? `$${Math.round(avgRenewalRent).toLocaleString()}` : '—'}
                subtitle={renewalCount ? `vs Prior ${renewalVsPriorPct >= 0 ? '+' : ''}${renewalVsPriorPct.toFixed(1)}%` : 'No data'}
                timeLabel={periodLabel}
                icon={<TrendingDown className="w-4 h-4" />}
                tooltip={`Renewal leases: avg rent $${Math.round(avgRenewalRent).toLocaleString()} vs prior rent $${Math.round(renewalSummary?.avg_prior_rent || 0).toLocaleString()}. ${renewalCount} total renewals. Source: RealPage Leases.`}
              />
            </div>
          </div>
        </div>
      </div>

      {/* Tab-specific content */}
      {activeTab === 'overview' && (
        <>
          <MarketCompsTable comps={compsData} subjectProperty={propertyName} propertyId={propertyId} />

          {/* Consolidated by Bedroom Type */}
          <BedroomConsolidatedView propertyId={propertyId} propertyIds={propertyIds} />

          {/* ATR & Availability Section */}
          <AvailabilitySection propertyId={propertyId} propertyIds={propertyIds} onDrillThrough={openKpiDrill} />

          {/* Unit Mix & Pricing */}
          <UnitMixPricing floorplans={floorplans} />
        </>
      )}

      {activeTab === 'renewals' && (
        <div className="bg-white rounded-xl border border-slate-200 p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-slate-800">Lease Renewals</h3>
            <div className="flex items-center gap-1 bg-slate-100 rounded-lg p-0.5">
              <button
                onClick={() => setRenewalViewMode('rolling')}
                className={`px-3 py-1 rounded-md text-xs font-medium transition-all ${
                  renewalViewMode === 'rolling' ? 'bg-white text-slate-800 shadow-sm' : 'text-slate-500 hover:text-slate-700'
                }`}
              >Rolling</button>
              <button
                onClick={() => setRenewalViewMode('monthly')}
                className={`px-3 py-1 rounded-md text-xs font-medium transition-all ${
                  renewalViewMode === 'monthly' ? 'bg-white text-slate-800 shadow-sm' : 'text-slate-500 hover:text-slate-700'
                }`}
              >Monthly</button>
            </div>
          </div>
          <div className={`grid gap-4 mb-6 ${renewalViewMode === 'monthly' ? 'grid-cols-4' : 'grid-cols-3'}`}>
            {expirations?.periods
              ?.filter(p => renewalViewMode === 'rolling' ? p.label.endsWith('d') : !p.label.endsWith('d'))
              .map(p => {
              const days = p.label === '30d' ? 30 : p.label === '60d' ? 60 : 90;
              return (
                <div key={p.label} className="bg-slate-50 rounded-lg p-4 relative">
                  <div className="text-xs font-medium text-slate-500 uppercase mb-3">{p.label.endsWith('d') ? (p.label === '30d' ? 'Next 30 Days' : p.label === '60d' ? 'Next 60 Days' : 'Next 90 Days') : p.label}</div>
                  <button onClick={() => openDrill(days)} className="flex items-baseline gap-2 mb-1 hover:opacity-70 transition-opacity cursor-pointer">
                    <span className="text-2xl font-bold text-slate-800">{p.expirations}</span>
                    <span className="text-sm text-slate-500 underline decoration-dotted">expiring</span>
                    <InfoTooltip text="Total leases with end dates in this period. Click to see all units." />
                  </button>
                  <button onClick={() => openDrill(days, 'renewed')} className="flex items-baseline gap-2 mb-1 hover:opacity-70 transition-opacity cursor-pointer">
                    <span className="text-2xl font-bold text-emerald-600">{p.renewals}</span>
                    <span className="text-sm text-slate-500 underline decoration-dotted">renewed</span>
                    <InfoTooltip text="Resident has signed a renewal lease. The unit is secured for another term." />
                  </button>
                  {(p.vacating ?? 0) > 0 && (
                    <button onClick={() => openDrill(days, 'vacating')} className="flex items-baseline gap-2 mb-1 hover:opacity-70 transition-opacity cursor-pointer">
                      <span className="text-lg font-bold text-rose-500">{p.vacating}</span>
                      <span className="text-xs text-slate-400 underline decoration-dotted">vacating</span>
                      <InfoTooltip text="Resident has given notice to vacate. Unit will need to be turned and re-leased." />
                    </button>
                  )}
                  {(p.unknown ?? 0) > 0 && (
                    <button onClick={() => openDrill(days, 'pending')} className="flex items-baseline gap-2 mb-1 hover:opacity-70 transition-opacity cursor-pointer">
                      <span className="text-lg font-bold text-amber-500">{p.unknown}</span>
                      <span className="text-xs text-slate-400 underline decoration-dotted">pending</span>
                      <InfoTooltip text="No decision recorded yet. Resident has not renewed or given notice — follow up needed." />
                    </button>
                  )}
                  {(p.mtm ?? 0) > 0 && (
                    <button onClick={() => openDrill(days, 'mtm')} className="flex items-baseline gap-2 mb-1 hover:opacity-70 transition-opacity cursor-pointer">
                      <span className="text-lg font-bold text-slate-400">{p.mtm}</span>
                      <span className="text-xs text-slate-400 underline decoration-dotted">MTM</span>
                      <InfoTooltip text="Lease converted to month-to-month. Resident stays without a fixed-term renewal." />
                    </button>
                  )}
                  {(p.moved_out ?? 0) > 0 && (
                    <button onClick={() => openDrill(days, 'moved_out')} className="flex items-baseline gap-2 mb-1 hover:opacity-70 transition-opacity cursor-pointer">
                      <span className="text-lg font-bold text-slate-500">{p.moved_out}</span>
                      <span className="text-xs text-slate-400 underline decoration-dotted">moved out</span>
                      <InfoTooltip text="Resident has already moved out. Unit is vacant or in turnover." />
                    </button>
                  )}
                  <div className={`text-sm font-semibold inline-flex items-center gap-1 mt-1 ${p.renewal_pct >= 50 ? 'text-emerald-600' : p.renewal_pct >= 25 ? 'text-amber-600' : 'text-rose-500'}`}>
                    {p.renewal_pct}% renewal rate
                    <InfoTooltip text="Renewed ÷ Total expiring × 100. Higher is better — means more residents are staying." />
                  </div>
                </div>
              );
            })}
          </div>
          <p className="text-sm text-slate-500">Renewal rate: <strong className={`${(exp90?.renewal_pct ?? 0) >= 50 ? 'text-emerald-600' : (exp90?.renewal_pct ?? 0) >= 25 ? 'text-amber-600' : 'text-rose-500'}`}>{exp90?.renewal_pct ?? 0}%</strong> of leases expiring in 90 days have been renewed</p>
        </div>
      )}

      {/* Renewal drill-through modal */}
      <DrillThroughModal
        isOpen={drillOpen}
        onClose={() => setDrillOpen(false)}
        title={drillTitle}
        data={drillData}
        columns={drillFilter === 'renewed' ? RENEWAL_DRILL_COLUMNS : EXPIRATION_DRILL_COLUMNS}
        loading={drillLoading}
      />

      {/* KPI drill-through modal */}
      <DrillThroughModal
        isOpen={kpiDrillOpen}
        onClose={() => setKpiDrillOpen(false)}
        title={kpiDrillTitle}
        data={kpiDrillData}
        columns={kpiDrillColumns}
        loading={kpiDrillLoading}
      />

      {activeTab === 'leasing' && (
        <>
        <div className="bg-white rounded-xl border border-slate-200 p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-slate-800">Leasing Activity</h3>
            <span className="text-xs text-slate-400 bg-slate-50 px-2 py-1 rounded">{periodLabel}</span>
          </div>
          <div className="grid grid-cols-4 gap-4 mb-6">
            <div className="bg-indigo-50 rounded-lg p-4">
              <div className="text-2xl font-bold text-indigo-700">{funnel?.leads || 0}</div>
              <div className="text-sm text-indigo-600 inline-flex items-center gap-0.5">Total Leads <InfoTooltip text="Unique prospects who made first contact via email, phone call, text, walk-in, guest card, or internet inquiry. Deduplicated by prospect name. Source: RealPage Activity Report." /></div>
            </div>
            <div className="bg-violet-50 rounded-lg p-4">
              <div className="text-2xl font-bold text-violet-700">{funnel?.tours || 0}</div>
              <div className="text-sm text-violet-600 inline-flex items-center gap-0.5">Tours <InfoTooltip text="Unique prospects who had a Visit or Visit (return) event recorded. Deduplicated by prospect name. Source: RealPage Activity Report." /></div>
            </div>
            <div className="bg-fuchsia-50 rounded-lg p-4">
              <div className="text-2xl font-bold text-fuchsia-700">{funnel?.applications || 0}</div>
              <div className="text-sm text-fuchsia-600 inline-flex items-center gap-0.5">Applications <InfoTooltip text="Unique prospects who reached the application stage (pre-qualify, identity verification, agreement, or quote). Deduplicated by prospect name. Source: RealPage Activity Report." /></div>
            </div>
            <div className="bg-emerald-50 rounded-lg p-4">
              <div className="text-2xl font-bold text-emerald-700">{funnel?.leaseSigns || 0}</div>
              <div className="text-sm text-emerald-600 inline-flex items-center gap-0.5">Leases Signed <InfoTooltip text="Unique prospects who reached 'Leased' status. Deduplicated by prospect name. Source: RealPage Activity Report." /></div>
            </div>
          </div>
          <div className="grid grid-cols-3 gap-4 mb-6">
            <div className="bg-amber-50 rounded-lg p-4">
              <div className="text-2xl font-bold text-amber-700">{funnel?.tourToApp || 0}<span className="text-sm font-normal text-amber-500 ml-1">({funnel?.tours ? Math.round((funnel.tourToApp || 0) / funnel.tours * 100) : 0}%)</span></div>
              <div className="text-sm text-amber-600 inline-flex items-center gap-0.5">Tour → Application <InfoTooltip text="Prospects who had a tour AND subsequently submitted an application. Percentage is of total tours." /></div>
            </div>
            <div className="bg-violet-50 rounded-lg p-4">
              <div className="text-2xl font-bold text-violet-700">{funnel?.sightUnseen || 0}<span className="text-sm font-normal text-violet-500 ml-1">({funnel?.applications ? Math.round((funnel.sightUnseen || 0) / funnel.applications * 100) : 0}%)</span></div>
              <div className="text-sm text-violet-600 inline-flex items-center gap-0.5">Apps w/o Tour <InfoTooltip text="Prospects who applied without ever touring the property in person. Percentage is of total applications." /></div>
            </div>
            <div className="bg-sky-50 rounded-lg p-4">
              <div className="text-2xl font-bold text-sky-700">{funnel?.leads ? ((funnel.leaseSigns / funnel.leads) * 100).toFixed(1) : 0}%</div>
              <div className="text-sm text-sky-600 inline-flex items-center gap-0.5">Lead → Lease <InfoTooltip text="Conversion Rate = Leases Signed ÷ Total Leads × 100. Source: RealPage Leasing Activity (last 30 days)." /></div>
            </div>
          </div>
        </div>

        {/* Lead Sources by Advertising Channel (merged from Marketing) */}
        <MarketingSection propertyId={propertyId} propertyIds={propertyIds} timeRange={timeRange as 'ytd' | 'mtd' | 'l30' | 'l7'} />

        {/* Availability by Floorplan (moved from overview) */}
        {availByFp && availByFp.floorplans.length > 0 && (
          <div className="bg-white rounded-xl border border-slate-200 p-6">
            <button onClick={() => setAvailCollapsed(c => !c)} className="flex items-center gap-2 w-full text-left">
              <ChevronDown className={`w-4 h-4 text-slate-400 transition-transform ${availCollapsed ? '-rotate-90' : ''}`} />
              <h3 className="text-lg font-semibold text-slate-800">Available Units by Floorplan</h3>
            </button>
            {!availCollapsed && <div className="overflow-x-auto mt-4">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-200 text-left text-xs font-medium text-slate-500 uppercase">
                    <th className="pb-2 pr-4">Floorplan</th>
                    <th className="pb-2 pr-4">Type</th>
                    <th className="pb-2 pr-4 text-right">Total</th>
                    <th className="pb-2 pr-4 text-right"><span className="inline-flex items-center gap-0.5">Vacant <InfoTooltip text="Units with no current occupant. Source: RealPage Box Score." /></span></th>
                    <th className="pb-2 pr-4 text-right"><span className="inline-flex items-center gap-0.5">Notice <InfoTooltip text="Occupied units with a Notice-to-Vacate filed. Source: RealPage Box Score." /></span></th>
                    <th className="pb-2 pr-4 text-right"><span className="inline-flex items-center gap-0.5">Vac Leased <InfoTooltip text="Vacant units with a signed lease (pending move-in). Source: RealPage Box Score." /></span></th>
                    <th className="pb-2 pr-4 text-right"><span className="inline-flex items-center gap-0.5">Vac Not Leased <InfoTooltip text="Vacant units without a signed lease. Source: RealPage Box Score." /></span></th>
                    <th className="pb-2 pr-4 text-right"><span className="inline-flex items-center gap-0.5">Mkt Rent <InfoTooltip text="Average market rent for this floorplan. Source: RealPage Box Score." /></span></th>
                    <th className="pb-2 text-right"><span className="inline-flex items-center gap-0.5">Occ% <InfoTooltip text="Occupancy % for this floorplan. Source: RealPage Box Score." /></span></th>
                  </tr>
                </thead>
                <tbody>
                  {availByFp.floorplans.map((fp: { floorplan: string; group: string; total_units: number; vacant_units: number; on_notice: number; vacant_leased: number; vacant_not_leased: number; avg_market_rent: number; occupancy_pct: number }) => (
                    <tr key={fp.floorplan} className="border-b border-slate-100 hover:bg-slate-50 cursor-pointer" onClick={() => openKpiDrill('availability', fp.floorplan)}>
                      <td className="py-2 pr-4 font-medium text-indigo-600 underline decoration-dotted">{fp.floorplan}</td>
                      <td className="py-2 pr-4 text-slate-500">{fp.group}</td>
                      <td className="py-2 pr-4 text-right">{fp.total_units}</td>
                      <td className={`py-2 pr-4 text-right font-medium ${fp.vacant_units > 0 ? 'text-amber-600' : 'text-slate-400'}`}>{fp.vacant_units}</td>
                      <td className={`py-2 pr-4 text-right ${fp.on_notice > 0 ? 'text-rose-500 font-medium' : 'text-slate-400'}`}>{fp.on_notice}</td>
                      <td className="py-2 pr-4 text-right text-emerald-600">{fp.vacant_leased}</td>
                      <td className="py-2 pr-4 text-right text-amber-600">{fp.vacant_not_leased}</td>
                      <td className="py-2 pr-4 text-right">${fp.avg_market_rent.toLocaleString(undefined, { maximumFractionDigits: 0 })}</td>
                      <td className="py-2 text-right">{fp.occupancy_pct.toFixed(1)}%</td>
                    </tr>
                  ))}
                </tbody>
                <tfoot>
                  <tr className="border-t-2 border-slate-300 font-semibold text-slate-800">
                    <td className="pt-2" colSpan={2}>Total</td>
                    <td className="pt-2 text-right">{availByFp.totals.total}</td>
                    <td className="pt-2 text-right text-amber-600 cursor-pointer underline decoration-dotted" onClick={() => openKpiDrill('availability_status', 'vacant')}>{availByFp.totals.vacant}</td>
                    <td className="pt-2 text-right text-rose-500 cursor-pointer underline decoration-dotted" onClick={() => openKpiDrill('availability_status', 'notice')}>{availByFp.totals.notice}</td>
                    <td className="pt-2 text-right" colSpan={4}></td>
                  </tr>
                </tfoot>
              </table>
            </div>}
          </div>
        )}

        {/* Occupancy Forecast (moved from overview) */}
        {forecast && forecast.forecast.length > 0 && (
          <div className="bg-white rounded-xl border border-slate-200 p-6">
            <button onClick={() => setForecastCollapsed(c => !c)} className="flex items-center gap-2 w-full text-left">
              <ChevronDown className={`w-4 h-4 text-slate-400 transition-transform ${forecastCollapsed ? '-rotate-90' : ''}`} />
              <h3 className="text-lg font-semibold text-slate-800">Occupancy Forecast</h3>
            </button>
            {!forecastCollapsed && <><div className="flex items-center gap-4 mb-4 mt-1">
              <p className="text-xs text-slate-500">{forecast.current_occupied}/{forecast.total_units} currently occupied · 12-week projection</p>
              {(forecast.vacant_leased > 0 || forecast.current_notice > 0) && (
                <div className="flex gap-3">
                  {forecast.vacant_leased > 0 && (
                    <button onClick={() => openKpiDrill('forecast_moveins')} className="text-xs bg-emerald-50 text-emerald-700 px-2 py-0.5 rounded cursor-pointer hover:bg-emerald-100 transition">
                      {forecast.vacant_leased} pre-leased{forecast.undated_move_ins > 0 ? ' (dates TBD)' : ''}
                    </button>
                  )}
                  {forecast.current_notice > 0 && (
                    <button onClick={() => openKpiDrill('forecast_notice')} className="text-xs bg-rose-50 text-rose-600 px-2 py-0.5 rounded cursor-pointer hover:bg-rose-100 transition">
                      {forecast.current_notice} on notice
                    </button>
                  )}
                </div>
              )}
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-200 text-left text-xs font-medium text-slate-500 uppercase">
                    <th className="pb-2 pr-4">Week</th>
                    <th className="pb-2 pr-4 text-right"><span className="inline-flex items-center gap-0.5">Projected Occ <InfoTooltip text="Projected occupied units at week end. Source: RealPage Projected Occupancy Report." /></span></th>
                    <th className="pb-2 pr-4 text-right"><span className="inline-flex items-center gap-0.5">Occ% <InfoTooltip text="Projected Occupied ÷ Total Units × 100." /></span></th>
                    <th className="pb-2 pr-4 text-right"><span className="inline-flex items-center gap-0.5">Move Ins <InfoTooltip text="Scheduled move-ins for this week." /></span></th>
                    <th className="pb-2 pr-4 text-right"><span className="inline-flex items-center gap-0.5">Notice Outs <InfoTooltip text="Units on notice-to-vacate with move-out date in this week." /></span></th>
                    <th className="pb-2 pr-4 text-right"><span className="inline-flex items-center gap-0.5">Net <InfoTooltip text="Net = Move Ins − Move Outs." /></span></th>
                    <th className="pb-2 pr-4 text-right"><span className="inline-flex items-center gap-0.5">Expirations <InfoTooltip text="Leases expiring this week." /></span></th>
                    <th className="pb-2 pr-4 text-right"><span className="inline-flex items-center gap-0.5">Renewals <InfoTooltip text="Already renewed leases expiring this week." /></span></th>
                    <th className="pb-2 text-right"><span className="inline-flex items-center gap-0.5">Net Exp <InfoTooltip text="Expirations − Renewals." /></span></th>
                  </tr>
                </thead>
                <tbody>
                  {(forecast.forecast as { week: number; week_start: string; week_end: string; projected_occupied: number; projected_occupancy_pct: number; scheduled_move_ins: number; notice_move_outs: number; net_change: number; lease_expirations: number; renewals: number; net_expirations: number }[]).map((w) => (
                    <tr key={w.week} className="border-b border-slate-100 hover:bg-slate-50">
                      <td className="py-2 pr-4 text-slate-600">Wk {w.week} <span className="text-slate-400 text-xs">({w.week_start.slice(5)})</span></td>
                      <td className="py-2 pr-4 text-right font-medium">{w.projected_occupied}</td>
                      <td className="py-2 pr-4 text-right">{w.projected_occupancy_pct}%</td>
                      <td className={`py-2 pr-4 text-right ${w.scheduled_move_ins > 0 ? 'text-emerald-600 font-medium cursor-pointer underline decoration-dotted' : 'text-slate-400'}`} onClick={w.scheduled_move_ins > 0 ? () => openKpiDrill('forecast_moveins', undefined, w.week_start, w.week_end) : undefined}>{w.scheduled_move_ins || '—'}</td>
                      <td className={`py-2 pr-4 text-right ${w.notice_move_outs > 0 ? 'text-rose-500 font-medium cursor-pointer underline decoration-dotted' : 'text-slate-400'}`} onClick={w.notice_move_outs > 0 ? () => openKpiDrill('forecast_notice', undefined, w.week_start, w.week_end) : undefined}>{w.notice_move_outs || '—'}</td>
                      <td className={`py-2 pr-4 text-right font-medium ${w.net_change > 0 ? 'text-emerald-600' : w.net_change < 0 ? 'text-rose-500' : 'text-slate-400'}`}>{w.net_change > 0 ? `+${w.net_change}` : w.net_change || '—'}</td>
                      <td className={`py-2 pr-4 text-right ${w.lease_expirations > 0 ? 'text-amber-600 cursor-pointer underline decoration-dotted' : 'text-slate-400'}`} onClick={w.lease_expirations > 0 ? () => openKpiDrill('forecast_expirations', undefined, w.week_start, w.week_end) : undefined}>{w.lease_expirations || '—'}</td>
                      <td className={`py-2 pr-4 text-right ${w.renewals > 0 ? 'text-emerald-600 font-medium' : 'text-slate-400'}`}>{w.renewals || '—'}</td>
                      <td className={`py-2 text-right font-medium ${w.net_expirations > 0 ? 'text-amber-600' : w.net_expirations < 0 ? 'text-emerald-600' : 'text-slate-400'}`}>{w.net_expirations > 0 ? w.net_expirations : w.net_expirations < 0 ? w.net_expirations : '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>}
          </div>
        )}
        </>
      )}

      {activeTab === 'delinquencies' && (
        <DelinquencySection propertyId={propertyId} propertyIds={propertyIds} />
      )}

      {activeTab === 'financials' && (
        <FinancialsSection propertyId={propertyId} propertyIds={propertyIds} />
      )}

      {activeTab === 'maintenance' && (
        <MaintenanceSection propertyId={propertyId} propertyIds={propertyIds} />
      )}

      {activeTab === 'rentable' && (
        <RentableItemsSection propertyId={propertyId} propertyIds={propertyIds} />
      )}

      {activeTab === 'risk' && (
        <ResidentRiskSection propertyId={propertyId} propertyIds={propertyIds} />
      )}

      {activeTab === 'reviews' && (
        <>
          <ReputationOverview propertyId={propertyId} propertyIds={propertyIds} />
          <GoogleReviewsSection propertyId={propertyId} propertyIds={propertyIds} propertyName={propertyName} />
        </>
      )}

      {/* Watchlist is rendered at the top level in DashboardV3, above portfolio */}
    </div>
  );
}

export default DashboardV3;
