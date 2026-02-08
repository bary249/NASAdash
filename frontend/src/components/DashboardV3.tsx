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
  Filter, RefreshCw, Settings, Eye, EyeOff, 
  Building2, DollarSign, TrendingUp, Home
} from 'lucide-react';

import { SearchBar } from './SearchBar';
import { PropertyCard } from './PropertyCard';
import { KPICard, FunnelKPICard, VacantKPICard } from './KPICard';
import { TabNavigation, TabId } from './TabNavigation';
import { UnitMixPricing } from './UnitMixPricing';
import { MarketCompsTable } from './MarketCompsTable';
import { LeasingInsightPanel } from './LeasingInsightPanel';
import { RentableItemsSection } from './RentableItemsSection';
import { DelinquencySection } from './DelinquencySection';
import { AIResponseModal, AITableColumn, AITableRow, SuggestedAction } from './AIResponseModal';
import { PortfolioView } from './PortfolioView';


import { api } from '../api';
import { PropertyDataProvider, usePropertyData } from '../data/PropertyDataContext';
import type { MarketComp, UnitPricingMetrics } from '../types';

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
  // Core state
  const [propertyId, setPropertyId] = useState(initialPropertyId || '');
  const [propertyName, setPropertyName] = useState('');
  const [scrambleMode, setScrambleMode] = useState<ScrambleMode>('off');
  const [activeTab, setActiveTab] = useState<TabId>('overview');
  
  // AI state
  const [isAIMode, setIsAIMode] = useState(false);
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

  // Property selection handler
  const handleSelectProperty = useCallback((id: string, name?: string) => {
    setPropertyId(id);
    setPropertyName(name || id);
  }, []);

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
    
    setAIQuery(query);
    setAILoading(true);
    setAIModalOpen(true);
    
    try {
      // Detect portfolio-level questions
      const queryLower = query.toLowerCase();
      const isPortfolioQuery = 
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
        // Use portfolio chat endpoint for portfolio-level questions
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
        <header className="bg-indigo-700 text-white">
          <div className="max-w-7xl mx-auto px-4 py-4">
            {/* Top row: Logo and actions */}
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-white/20 flex items-center justify-center">
                  <Building2 className="w-5 h-5" />
                </div>
                <div>
                  <h1 className="text-xl font-bold">Venn</h1>
                  <p className="text-xs text-indigo-200">Owner Dashboard</p>
                </div>
              </div>
              
              <div className="flex items-center gap-2">
                {/* Hide PII Toggle - Full scramble */}
                <button
                  onClick={() => setScrambleMode(scrambleMode === 'full' ? 'off' : 'full')}
                  className={`
                    flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-all
                    ${scrambleMode === 'full' 
                      ? 'bg-amber-500 text-white' 
                      : 'bg-white/10 text-white hover:bg-white/20'
                    }
                  `}
                >
                  {scrambleMode === 'full' ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  <span>Hide PII</span>
                </button>

                {/* Demo Mode Toggle - Only hides Ridian/Northern */}
                <button
                  onClick={() => setScrambleMode(scrambleMode === 'demo' ? 'off' : 'demo')}
                  className={`
                    flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-all
                    ${scrambleMode === 'demo' 
                      ? 'bg-indigo-500 text-white' 
                      : 'bg-white/10 text-white hover:bg-white/20'
                    }
                  `}
                >
                  <Eye className="w-4 h-4" />
                  <span>Demo</span>
                </button>
                
                <button 
                  onClick={() => window.location.reload()}
                  className="p-2 bg-white/10 hover:bg-white/20 rounded-lg transition-colors"
                >
                  <RefreshCw className="w-5 h-5" />
                </button>
                <button className="p-2 bg-white/10 hover:bg-white/20 rounded-lg transition-colors">
                  <Settings className="w-5 h-5" />
                </button>
              </div>
            </div>

            {/* Search Bar */}
            <div className="py-4">
              <SearchBar
                onSearch={handleAISearch}
                isAIMode={isAIMode}
                onModeChange={setIsAIMode}
                isLoading={aiLoading}
              />
            </div>
          </div>
        </header>

        {/* Sub-header: Property selector, timeframe, tabs */}
        <div className="bg-white border-b border-slate-200 sticky top-0 z-30">
          <div className="max-w-7xl mx-auto px-4 py-3">
            <div className="flex items-center justify-between">
              {/* Left: Filters */}
              <div className="flex items-center gap-3">
                {/* More Filters */}
                <button className="flex items-center gap-2 px-3 py-2 text-sm text-slate-600 hover:bg-slate-100 rounded-lg transition-colors">
                  <Filter className="w-4 h-4" />
                  <span>More filters</span>
                </button>
              </div>

              {/* Right: Tab Navigation */}
              <TabNavigation activeTab={activeTab} onTabChange={setActiveTab} />
            </div>
          </div>
        </div>

        {/* Main Content */}
        <main className="max-w-7xl mx-auto px-4 py-6">
          {/* Portfolio Overview (collapsible) */}
          <div className="mb-6">
            <PortfolioView 
              onSelectProperty={handleSelectProperty}
              selectedPropertyId={propertyId}
            />
          </div>

          {/* Property Dashboard */}
          {propertyId ? (
            <PropertyDataProvider propertyId={propertyId}>
              <PropertyDashboard
                propertyId={propertyId}
                propertyName={scrambleName(propertyName, isScrambleActive, scrambleMode)}
                originalPropertyName={propertyName}
                pricing={pricing}
                marketComps={marketComps}
                activeTab={activeTab}
              />
            </PropertyDataProvider>
          ) : (
            <div className="bg-white rounded-2xl border border-slate-200 p-12 text-center">
              <div className="w-16 h-16 rounded-2xl bg-indigo-100 flex items-center justify-center mx-auto mb-4">
                <Building2 className="w-8 h-8 text-indigo-600" />
              </div>
              <h3 className="text-lg font-semibold text-slate-700 mb-2">Select a Property</h3>
              <p className="text-slate-500">Choose a property from the portfolio above to view detailed metrics</p>
            </div>
          )}
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
  propertyName: string;
  originalPropertyName: string;
  pricing: UnitPricingMetrics | null;
  marketComps: MarketComp[];
  activeTab: TabId;
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

function PropertyDashboard({ propertyId, propertyName, originalPropertyName, pricing, marketComps, activeTab }: PropertyDashboardProps) {
  const { occupancy, exposure, funnel, loading, error } = usePropertyData();

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

  // Calculate renewal trend (mock - would come from real data)
  const renewalTrend = 62.4;
  const prevRenewalTrend = 66;
  
  // Calculate lease trade-out values
  const avgTradeOut = pricing?.total_asking_rent || 2025;
  const prevTradeOut = pricing?.total_in_place_rent || 2000;
  const renewalAvg = pricing ? Math.round(pricing.total_asking_rent * 1.08) : 2200;

  return (
    <div className="space-y-6">
      {/* Main Grid: Property Card + KPIs */}
      <div className="grid grid-cols-12 gap-6">
        {/* Property Card - Left */}
        <div className="col-span-12 lg:col-span-3">
          <PropertyCard
            name={propertyName}
            units={occupancy?.totalUnits || 0}
            floors={32}
            rating={4.6}
            vacantReady={occupancy?.vacantReady || 0}
            agedVacancy={occupancy?.agedVacancy90Plus || 0}
            imageUrl={getPropertyImage(originalPropertyName)}
            isMock
          />
        </div>

        {/* KPIs Grid - Right */}
        <div className="col-span-12 lg:col-span-9">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {/* Row 1 */}
            <KPICard
              title="Occupancy"
              value={`${occupancy?.physicalOccupancy || 0}%`}
              icon={<Home className="w-4 h-4" />}
            />
            
            <KPICard
              title="In-Place"
              value={`$${pricing?.total_in_place_rent?.toLocaleString() || '—'}`}
              subtitle={`Asking $${pricing?.total_asking_rent?.toLocaleString() || '—'}`}
              icon={<DollarSign className="w-4 h-4" />}
            />
            
            <KPICard
              title="Renewal Trend"
              value={`${renewalTrend}%`}
              subtitle={`Current ${prevRenewalTrend}%`}
              trend={{
                value: -2.5,
                direction: 'down',
                isPositive: false,
              }}
              icon={<TrendingUp className="w-4 h-4" />}
              isMock
            />
            
            <KPICard
              title="Lease Trade Outs"
              value={`$${avgTradeOut.toLocaleString()}`}
              subtitle={`Prev Lease $${prevTradeOut.toLocaleString()}`}
              icon={<DollarSign className="w-4 h-4" />}
            />

            {/* Row 2 */}
            <VacantKPICard
              total={occupancy?.vacantUnits || 0}
              ready={occupancy?.vacantReady || 0}
              agedCount={occupancy?.agedVacancy90Plus}
            />
            
            <FunnelKPICard
              leads={funnel?.leads || 0}
              tours={funnel?.tours || 0}
              proposals={funnel?.applications || 0}
              leasesSigned={funnel?.leaseSigns || 0}
            />
            
            <KPICard
              title="Lease Renewals"
              value={`$${renewalAvg.toLocaleString()}`}
              subtitle={`Prev Lease $${(renewalAvg - 50).toLocaleString()}`}
              icon={<RefreshCw className="w-4 h-4" />}
              isCalc
            />
          </div>
        </div>
      </div>

      {/* Tab-specific content */}
      {activeTab === 'overview' && (
        <div className="grid grid-cols-12 gap-6">
          <div className="col-span-12 md:col-span-4">
            <UnitMixPricing floorplans={floorplans} />
          </div>
          <div className="col-span-12 md:col-span-5">
            <MarketCompsTable comps={compsData} subjectProperty={propertyName} propertyId={propertyId} />
          </div>
          <div className="col-span-12 md:col-span-3">
            <LeasingInsightPanel residentCount={occupancy?.occupiedUnits || 34} />
          </div>
        </div>
      )}

      {activeTab === 'renewals' && (
        <div className="bg-white rounded-xl border border-slate-200 p-6">
          <h3 className="text-lg font-semibold text-slate-800 mb-4">Lease Renewals</h3>
          <div className="grid grid-cols-3 gap-4 mb-6">
            <div className="bg-sky-50 rounded-lg p-4">
              <div className="text-2xl font-bold text-sky-700">{Math.round((exposure?.noticesTotal || 0) * 0.6)}</div>
              <div className="text-sm text-sky-600">Pending Renewals</div>
            </div>
            <div className="bg-emerald-50 rounded-lg p-4">
              <div className="text-2xl font-bold text-emerald-700">{Math.round((exposure?.noticesTotal || 0) * 0.3)}</div>
              <div className="text-sm text-emerald-600">Renewed MTD</div>
            </div>
            <div className="bg-amber-50 rounded-lg p-4">
              <div className="text-2xl font-bold text-amber-700">{exposure?.notices60Days || 0}</div>
              <div className="text-sm text-amber-600">Expiring (60 days)</div>
            </div>
          </div>
          <p className="text-sm text-slate-500">Average renewal rate increase: <strong className="text-emerald-600">+2.3%</strong></p>
        </div>
      )}

      {activeTab === 'leasing' && (
        <div className="bg-white rounded-xl border border-slate-200 p-6">
          <h3 className="text-lg font-semibold text-slate-800 mb-4">Leasing Activity</h3>
          <div className="grid grid-cols-4 gap-4 mb-6">
            <div className="bg-indigo-50 rounded-lg p-4">
              <div className="text-2xl font-bold text-indigo-700">{funnel?.leads || 0}</div>
              <div className="text-sm text-indigo-600">Total Leads</div>
            </div>
            <div className="bg-violet-50 rounded-lg p-4">
              <div className="text-2xl font-bold text-violet-700">{funnel?.tours || 0}</div>
              <div className="text-sm text-violet-600">Tours Scheduled</div>
            </div>
            <div className="bg-fuchsia-50 rounded-lg p-4">
              <div className="text-2xl font-bold text-fuchsia-700">{funnel?.applications || 0}</div>
              <div className="text-sm text-fuchsia-600">Applications</div>
            </div>
            <div className="bg-emerald-50 rounded-lg p-4">
              <div className="text-2xl font-bold text-emerald-700">{funnel?.leaseSigns || 0}</div>
              <div className="text-sm text-emerald-600">Leases Signed</div>
            </div>
          </div>
          <p className="text-sm text-slate-500">Conversion rate (Lead → Lease): <strong className="text-emerald-600">{funnel?.leads ? ((funnel.leaseSigns / funnel.leads) * 100).toFixed(1) : 0}%</strong></p>
        </div>
      )}

      {activeTab === 'delinquencies' && (
        <DelinquencySection propertyId={propertyId} />
      )}

      {activeTab === 'rentable' && (
        <RentableItemsSection propertyId={propertyId} />
      )}
    </div>
  );
}

export default DashboardV3;
