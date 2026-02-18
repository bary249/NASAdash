/**
 * MarketCompsTable - Horizontal comparison table for market comps
 * Matches design: Property rows with rent columns by bedroom type
 * Includes filters: location (submarket), radius, bedroom type
 */
import { useState, useEffect } from 'react';
import { Building2, Filter, ChevronDown, ChevronUp, MapPin, Crosshair } from 'lucide-react';
import { api } from '../api';

interface MarketCompRow {
  name: string;
  studioRent?: number;
  oneBedRent?: number;
  twoBedRent?: number;
  threeBedRent?: number;
  isSubject?: boolean;
}

interface Submarket {
  id: string;
  name: string;
}

interface MarketCompsTableProps {
  comps: MarketCompRow[];
  subjectProperty?: string;
  propertyId?: string;
  onSubmarketChange?: (submarket: string) => void;
  onBedroomFilterChange?: (bedrooms: string[]) => void;
}

const BEDROOM_OPTIONS = [
  { value: 'studio', label: 'Studio' },
  { value: '1br', label: '1 BR' },
  { value: '2br', label: '2 BR' },
  { value: '3br', label: '3 BR' },
];

export function MarketCompsTable({ comps: initialComps, subjectProperty, propertyId, onSubmarketChange, onBedroomFilterChange }: MarketCompsTableProps) {
  const [selectedBedrooms, setSelectedBedrooms] = useState<string[]>(['studio', '1br', '2br', '3br']);
  const [showFilters, setShowFilters] = useState(false);
  const [isExpanded, setIsExpanded] = useState(true);
  
  // Location/submarket state
  const [submarkets, setSubmarkets] = useState<Submarket[]>([]);
  const [selectedSubmarket, setSelectedSubmarket] = useState('');
  const [propertyLocation, setPropertyLocation] = useState<{ city: string; state: string } | null>(null);
  const [loadingSubmarkets, setLoadingSubmarkets] = useState(true);
  
  // Comps data - managed internally, fetched when submarket changes
  const [comps, setComps] = useState<MarketCompRow[]>(initialComps);
  const [loadingComps, setLoadingComps] = useState(false);

  // Load submarkets on mount
  useEffect(() => {
    api.getSubmarkets()
      .then(data => {
        setSubmarkets(data);
        if (data.length > 0 && !selectedSubmarket) {
          setSelectedSubmarket(data[0].id);
        }
        setLoadingSubmarkets(false);
      })
      .catch(() => {
        setSubmarkets([
          { id: 'South Asheville / Arden', name: 'South Asheville / Arden' },
          { id: 'Downtown', name: 'Downtown' },
        ]);
        setLoadingSubmarkets(false);
      });
  }, []);

  // Load property location
  useEffect(() => {
    if (!propertyId) return;
    api.getPropertyLocation(propertyId)
      .then(loc => {
        setPropertyLocation({ city: loc.city, state: loc.state });
        // Auto-select matching submarket
        const match = submarkets.find(s => 
          s.name.toLowerCase().includes(loc.city.toLowerCase())
        );
        if (match) setSelectedSubmarket(match.id);
      })
      .catch(() => {});
  }, [propertyId, submarkets]);

  // Fetch comps when submarket changes
  useEffect(() => {
    if (!selectedSubmarket) return;
    
    setLoadingComps(true);
    api.getMarketComps(selectedSubmarket, subjectProperty, 10)
      .then(result => {
        const mappedComps = result.comps.map(c => ({
          name: c.property_name,
          studioRent: c.studio_rent,
          oneBedRent: c.one_bed_rent,
          twoBedRent: c.two_bed_rent,
          threeBedRent: c.three_bed_rent,
          isSubject: c.property_name === subjectProperty,
        }));
        setComps(mappedComps);
        setLoadingComps(false);
      })
      .catch(() => {
        setComps(initialComps);
        setLoadingComps(false);
      });
  }, [selectedSubmarket, subjectProperty]);

  const handleSubmarketChange = (submarket: string) => {
    setSelectedSubmarket(submarket);
    onSubmarketChange?.(submarket);
  };

  const zoomToPropertyArea = () => {
    if (propertyLocation && submarkets.length > 0) {
      const match = submarkets.find(s => 
        s.name.toLowerCase().includes(propertyLocation.city.toLowerCase()) ||
        s.name.toLowerCase().includes(propertyLocation.state.toLowerCase())
      );
      if (match) setSelectedSubmarket(match.id);
    }
  };

  const toggleBedroom = (bedroom: string) => {
    const newSelection = selectedBedrooms.includes(bedroom)
      ? selectedBedrooms.filter(b => b !== bedroom)
      : [...selectedBedrooms, bedroom];
    setSelectedBedrooms(newSelection);
    onBedroomFilterChange?.(newSelection);
  };
  const formatCurrency = (value?: number) => {
    if (!value) return '—';
    return `$${value.toLocaleString()}`;
  };

  // Calculate averages for comparison
  const getAverage = (key: keyof MarketCompRow) => {
    const values = comps
      .filter(c => !c.isSubject && c[key])
      .map(c => c[key] as number);
    if (values.length === 0) return null;
    return Math.round(values.reduce((a, b) => a + b, 0) / values.length);
  };

  const avgStudio = getAverage('studioRent');
  const avgOneBed = getAverage('oneBedRent');
  const avgTwoBed = getAverage('twoBedRent');
  const avgThreeBed = getAverage('threeBedRent');

  // Find subject property and move to top
  const sortedComps = [...comps].sort((a, b) => {
    if (a.isSubject) return -1;
    if (b.isSubject) return 1;
    return 0;
  });

  const getDeltaIndicator = (value?: number, avg?: number | null) => {
    if (!value || !avg) return null;
    const diff = value - avg;
    const percent = Math.round((diff / avg) * 100);
    if (Math.abs(percent) < 1) return null;
    
    return (
      <span className={`
        ml-1 text-xs font-medium
        ${diff > 0 ? 'text-emerald-600' : 'text-rose-600'}
      `}>
        {diff > 0 ? '+' : ''}{percent}%
      </span>
    );
  };

  return (
    <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
      {/* Header with toggle and filters */}
      <div className="px-4 py-3 border-b border-slate-200 bg-slate-50">
        <div className="flex items-center justify-between">
          <button 
            onClick={() => setIsExpanded(!isExpanded)}
            className="flex items-center gap-2"
          >
            <h3 className="text-sm font-semibold text-slate-700">Market Comps</h3>
            {isExpanded ? (
              <ChevronUp className="w-4 h-4 text-slate-400" />
            ) : (
              <ChevronDown className="w-4 h-4 text-slate-400" />
            )}
          </button>
          
          <button
            onClick={() => setShowFilters(!showFilters)}
            className={`flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium rounded-lg transition-colors ${
              showFilters ? 'bg-indigo-100 text-indigo-700' : 'text-slate-600 hover:bg-slate-100'
            }`}
          >
            <Filter className="w-3.5 h-3.5" />
            Filters
          </button>
        </div>

        {/* Location selector - always visible */}
        <div className="mt-3 pt-3 border-t border-slate-200">
          <div className="flex items-center gap-2 flex-wrap">
            <MapPin className="w-4 h-4 text-slate-400" />
            <select
              value={selectedSubmarket}
              onChange={(e) => handleSubmarketChange(e.target.value)}
              className="px-2 py-1.5 text-xs border border-slate-200 rounded-lg bg-white focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 min-w-[180px]"
              disabled={loadingSubmarkets}
            >
              {loadingSubmarkets ? (
                <option>Loading...</option>
              ) : (
                submarkets.map(s => (
                  <option key={s.id} value={s.id}>{s.name}</option>
                ))
              )}
            </select>
            <button
              onClick={zoomToPropertyArea}
              className="flex items-center gap-1 px-2 py-1.5 text-xs font-medium text-indigo-600 bg-indigo-50 border border-indigo-200 rounded-lg hover:bg-indigo-100 transition-colors"
              title={propertyLocation ? `Zoom to ${propertyLocation.city}, ${propertyLocation.state}` : 'Zoom to property area'}
            >
              <Crosshair className="w-3 h-3" />
              Property Area
            </button>
            {propertyLocation && (
              <span className="text-xs text-slate-400">
                ({propertyLocation.city}, {propertyLocation.state})
              </span>
            )}
          </div>
        </div>

        {/* Filter panel */}
        {showFilters && (
          <div className="mt-3 pt-3 border-t border-slate-200 flex flex-wrap gap-4">
            {/* Bedroom filter */}
            <div className="flex items-center gap-2">
              <span className="text-xs text-slate-500">Bedrooms:</span>
              <div className="flex gap-1">
                {BEDROOM_OPTIONS.map(opt => (
                  <button
                    key={opt.value}
                    onClick={() => toggleBedroom(opt.value)}
                    className={`px-2 py-1 text-xs rounded-md transition-colors ${
                      selectedBedrooms.includes(opt.value) 
                        ? 'bg-indigo-600 text-white' 
                        : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                    }`}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>

      {isExpanded && <div className="overflow-x-auto">
        {loadingComps ? (
          <div className="p-8 text-center">
            <div className="inline-block w-6 h-6 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin mb-2" />
            <p className="text-sm text-slate-500">Loading market comps...</p>
          </div>
        ) : (
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-100">
              <th className="px-4 py-2 text-left text-xs font-medium text-slate-500">Property</th>
              <th className="px-4 py-2 text-right text-xs font-medium text-slate-500">Studio</th>
              <th className="px-4 py-2 text-right text-xs font-medium text-slate-500">1BR</th>
              <th className="px-4 py-2 text-right text-xs font-medium text-slate-500">2BR</th>
              <th className="px-4 py-2 text-right text-xs font-medium text-slate-500">3BR</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-50">
            {sortedComps.map((comp) => (
              <tr 
                key={comp.name}
                className={`
                  hover:bg-slate-50 transition-colors
                  ${comp.isSubject ? 'bg-indigo-50/50' : ''}
                `}
              >
                <td className="px-4 py-2.5">
                  <div className="flex items-center gap-2">
                    {comp.isSubject && (
                      <Building2 className="w-4 h-4 text-indigo-600" />
                    )}
                    <span className={`
                      font-medium
                      ${comp.isSubject ? 'text-indigo-700' : 'text-slate-700'}
                    `}>
                      {comp.name}
                    </span>
                    {comp.isSubject && (
                      <span className="text-xs text-indigo-500">(Subject)</span>
                    )}
                  </div>
                </td>
                <td className="px-4 py-2.5 text-right font-medium text-slate-700">
                  {formatCurrency(comp.studioRent)}
                  {comp.isSubject && getDeltaIndicator(comp.studioRent, avgStudio)}
                </td>
                <td className="px-4 py-2.5 text-right font-medium text-slate-700">
                  {formatCurrency(comp.oneBedRent)}
                  {comp.isSubject && getDeltaIndicator(comp.oneBedRent, avgOneBed)}
                </td>
                <td className="px-4 py-2.5 text-right font-medium text-slate-700">
                  {formatCurrency(comp.twoBedRent)}
                  {comp.isSubject && getDeltaIndicator(comp.twoBedRent, avgTwoBed)}
                </td>
                <td className="px-4 py-2.5 text-right font-medium text-slate-700">
                  {formatCurrency(comp.threeBedRent)}
                  {comp.isSubject && getDeltaIndicator(comp.threeBedRent, avgThreeBed)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        )}
      </div>}
    </div>
  );
}
