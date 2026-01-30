import { useState, createContext, useContext } from 'react';
import { Building2, Settings, RefreshCw, ChevronRight, EyeOff, Eye } from 'lucide-react';
import { OccupancySectionV2 } from './components/OccupancySectionV2';
import { UnitPricingSection } from './components/UnitPricingSection';
import { TradeOutSection } from './components/TradeOutSection';
import { MarketCompsSection } from './components/MarketCompsSection';
import { AmenitiesSection } from './components/AmenitiesSection';
import { PortfolioView } from './components/PortfolioView';
import { WhyVennSection } from './components/WhyVennSection';
import { AIInsightsSection } from './components/AIInsightsSection';
import { DelinquencySection } from './components/DelinquencySection';
import { PropertyDataProvider } from './data/PropertyDataContext';

// Scramble PII Context
const ScrambleContext = createContext<boolean>(false);
export const useScramble = () => useContext(ScrambleContext);

// Scramble function - consistent mapping for demo
const SCRAMBLED_NAMES: Record<string, string> = {};
let nameCounter = 1;
export function scrambleName(name: string, enabled: boolean): string {
  if (!enabled || !name) return name;
  if (!SCRAMBLED_NAMES[name]) {
    SCRAMBLED_NAMES[name] = `Property ${String.fromCharCode(64 + nameCounter++)}`;
  }
  return SCRAMBLED_NAMES[name];
}

export default function App() {
  const [propertyId, setPropertyId] = useState('');
  const [propertyName, setPropertyName] = useState('');
  const [scramblePII, setScramblePII] = useState(false);

  const handleSelectProperty = (id: string, name?: string) => {
    setPropertyId(id);
    setPropertyName(name || id);
  };

  return (
    <div className="min-h-screen bg-[#faf9f7]">
      {/* Header - Venn Branded with Warm Glow */}
      <header className="venn-gradient-header shadow-venn-lg relative overflow-hidden">
        <div className="max-w-7xl mx-auto px-4 py-6 sm:px-6 lg:px-8 relative z-10">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-5">
              {/* Venn Logo Mark - Warm amber accent */}
              <div className="flex items-center justify-center w-12 h-12 rounded-venn-lg bg-gradient-to-br from-venn-amber to-venn-copper shadow-lg shadow-venn-amber/20">
                <Building2 className="w-6 h-6 text-venn-navy" />
              </div>
              <div>
                <div className="flex items-center gap-3">
                  <h1 className="text-2xl font-bold text-white tracking-tight">Venn</h1>
                  <span className="text-venn-charcoal font-light">|</span>
                  <span className="text-lg font-medium text-venn-amber">Owner Dashboard</span>
                </div>
                <p className="text-sm text-slate-400 mt-1">
                  Real-time asset performance • Direct PMS integration
                </p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              {/* Scramble PII Toggle */}
              <button
                onClick={() => setScramblePII(!scramblePII)}
                className={`flex items-center gap-2 px-3 py-2 rounded-xl transition-all duration-200 ${
                  scramblePII 
                    ? 'bg-venn-amber/20 text-venn-amber border border-venn-amber/30' 
                    : 'text-slate-400 hover:text-venn-amber hover:bg-white/5'
                }`}
                title={scramblePII ? 'Show Real Names' : 'Scramble PII for Demo'}
              >
                {scramblePII ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                <span className="text-xs font-medium">{scramblePII ? 'PII Hidden' : 'Hide PII'}</span>
              </button>
              <button 
                onClick={() => window.location.reload()}
                className="p-3 text-slate-400 hover:text-venn-amber hover:bg-white/5 rounded-xl transition-all duration-200"
                title="Refresh Data"
              >
                <RefreshCw className="w-5 h-5" />
              </button>
              <button className="p-3 text-slate-400 hover:text-venn-amber hover:bg-white/5 rounded-xl transition-all duration-200">
                <Settings className="w-5 h-5" />
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Property Info Bar - shows selected property */}
      {propertyId && (
        <div className="bg-gradient-to-r from-venn-amber/5 via-venn-gold/5 to-venn-amber/5 border-b border-venn-amber/10">
          <div className="max-w-7xl mx-auto px-4 py-3 sm:px-6 lg:px-8">
            <div className="flex items-center gap-2 text-sm">
              <span className="text-slate-500">Viewing:</span>
              <ChevronRight className="w-4 h-4 text-venn-amber" />
              <span className="font-semibold text-venn-navy">{scrambleName(propertyName, scramblePII)}</span>
            </div>
          </div>
        </div>
      )}

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 py-8 sm:px-6 lg:px-8">
        <div className="space-y-8">
          {/* Portfolio Overview - All properties at a glance */}
          <ScrambleContext.Provider value={scramblePII}>
          <PortfolioView 
            onSelectProperty={handleSelectProperty} 
            selectedPropertyId={propertyId} 
          />

          {/* Single Property Detail View */}
          {propertyId ? (
            <PropertyDataProvider propertyId={propertyId}>
              <div className="space-y-8">
                {/* AI Insights Section - Auto-generates top 3 facts */}
                <AIInsightsSection propertyId={propertyId} propertyName={scrambleName(propertyName, scramblePII)} />

                {/* Occupancy & Leasing Section - Bottom-up metrics from raw data */}
                <OccupancySectionV2 propertyId={propertyId} />

                {/* Unit Pricing Section */}
                <UnitPricingSection propertyId={propertyId} />

                {/* Lease Trade-Outs Section */}
                <TradeOutSection propertyId={propertyId} />

                {/* Amenities Section - Parking, Storage, etc. */}
                <AmenitiesSection propertyId={propertyId} />

                {/* Delinquencies & Collections Section */}
                <DelinquencySection propertyId={propertyId} />

                {/* Market Comps Section */}
                <MarketCompsSection propertyId={propertyId} subjectProperty={scrambleName(propertyName, scramblePII)} />
              </div>
            </PropertyDataProvider>
          ) : (
            <div className="venn-section text-center py-20 venn-dotted-bg">
              <div className="inline-flex items-center justify-center w-16 h-16 rounded-venn-xl bg-gradient-to-br from-venn-amber/20 to-venn-gold/10 mb-5">
                <Building2 className="w-8 h-8 text-venn-amber" />
              </div>
              <p className="text-slate-600 text-lg font-medium">Select a property from the portfolio above</p>
              <p className="text-slate-400 text-sm mt-2">Click on any property row to drill down into metrics</p>
            </div>
          )}

          </ScrambleContext.Provider>
          {/* Why Venn Section - Competitive differentiation */}
          <WhyVennSection />
        </div>
      </main>

      {/* Footer */}
      <footer className="bg-venn-navy border-t border-venn-charcoal mt-12">
        <div className="max-w-7xl mx-auto px-4 py-6 sm:px-6 lg:px-8">
          <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-venn-amber to-venn-copper flex items-center justify-center">
                <Building2 className="w-4 h-4 text-venn-navy" />
              </div>
              <span className="text-slate-400 text-sm font-medium">Venn Owner Dashboard</span>
            </div>
            <p className="text-center text-sm text-slate-500">
              Data Source: Yardi + RealPage PMS • <span className="text-venn-amber">READ-ONLY</span>
            </p>
          </div>
        </div>
      </footer>
    </div>
  );
}
