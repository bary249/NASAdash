/**
 * Occupancy Section V2 - Bottom-up metrics from raw data
 * 
 * Uses PropertyDataContext for metrics calculated from raw data.
 * Drill-through shows the EXACT same filtered data used for metrics.
 * 
 * Custom date range applies to ALL metrics in this section.
 * Trend indicators show change vs prior period of same duration.
 */
import { useState, useEffect } from 'react';
import { Building2, Users, DoorOpen, TrendingUp, AlertTriangle, Calendar, ArrowUp, ArrowDown, Minus } from 'lucide-react';
import { MetricCard, MetricThreshold } from './MetricCard';
import { api } from '../api';
import type { AllTrends } from '../types';

// Trend indicator component for showing change vs prior period
interface TrendBadgeProps {
  currentValue: number;
  priorValue: number;
  higherIsBetter?: boolean;
  suffix?: string;
  priorLabel?: string;
}

function TrendBadge({ currentValue, priorValue, higherIsBetter = true, suffix = '', priorLabel = 'prior' }: TrendBadgeProps) {
  const change = currentValue - priorValue;
  const direction = change > 0 ? 'up' : change < 0 ? 'down' : 'flat';
  const isGood = higherIsBetter ? direction === 'up' : direction === 'down';
  const isBad = higherIsBetter ? direction === 'down' : direction === 'up';
  
  return (
    <div className="flex items-center gap-1 text-xs mt-1">
      {direction === 'up' && (
        <ArrowUp className={`w-3 h-3 ${isGood ? 'text-green-600' : 'text-red-600'}`} />
      )}
      {direction === 'down' && (
        <ArrowDown className={`w-3 h-3 ${isBad ? 'text-red-600' : 'text-green-600'}`} />
      )}
      {direction === 'flat' && (
        <Minus className="w-3 h-3 text-gray-500" />
      )}
      <span className={
        isGood ? 'text-green-600 font-medium' :
        isBad ? 'text-red-600 font-medium' :
        'text-gray-600'
      }>
        {change > 0 ? '+' : ''}{Number(change.toFixed(1))}{suffix}
      </span>
      <span className="text-gray-400">vs {priorLabel} ({Number(priorValue.toFixed(1))}{suffix})</span>
    </div>
  );
}

// Configurable thresholds - these can be customized per client
const THRESHOLDS = {
  physicalOccupancy: { good: 95, warning: 90, higherIsBetter: true } as MetricThreshold,
  leasedPercentage: { good: 97, warning: 93, higherIsBetter: true } as MetricThreshold,
  vacantUnits: { good: 3, warning: 8, higherIsBetter: false } as MetricThreshold,
  agedVacancy: { good: 0, warning: 2, higherIsBetter: false } as MetricThreshold,
  exposure30: { good: 3, warning: 6, higherIsBetter: false } as MetricThreshold,
  exposure60: { good: 5, warning: 10, higherIsBetter: false } as MetricThreshold,
  leadToTour: { good: 40, warning: 25, higherIsBetter: true } as MetricThreshold,
  tourToApp: { good: 50, warning: 30, higherIsBetter: true } as MetricThreshold,
  leadToLease: { good: 15, warning: 8, higherIsBetter: true } as MetricThreshold,
};

// Metric definitions for tooltips
const DEFINITIONS = {
  physicalOccupancy: 'Occupied Units ÷ Total Units. Measures how many units currently have residents living in them.',
  leasedPercentage: '(Occupied + Preleased Vacant) ÷ Total Units. Includes units with signed leases but not yet moved in.',
  availableUnits: 'Vacant units that are NOT preleased. These are truly available to rent to new prospects.',
  vacantUnits: 'Units with no current resident. Split into "Ready" (move-in ready) and "Not Ready" (needs make-ready).',
  agedVacancy: 'Units vacant for more than 90 days. High aged vacancy indicates pricing or marketing issues.',
  exposure30: 'Vacant + Move-outs in 30 days − Move-ins in 30 days. Your net risk of vacancy.',
  exposure60: 'Vacant + Move-outs in 60 days − Move-ins in 60 days. Extended vacancy risk outlook.',
  notices30: 'Residents who have given Notice to Vacate with move-out date in next 30 days.',
  notices60: 'Residents who have given Notice to Vacate with move-out date in next 60 days.',
  moveIns: 'Residents who moved in during the selected period.',
  moveOuts: 'Residents who moved out during the selected period.',
  netAbsorption: 'Move-ins minus Move-outs. Positive = growing occupancy, Negative = shrinking.',
  leads: 'Unique prospect contacts/inquiries (Guest Cards) created in the period.',
  tours: 'Prospects with a verified visit/showing event in the period.',
  applications: 'Submitted rental applications in the period.',
  leaseSigns: 'Countersigned leases (approved applications that signed) in the period.',
  leadToTour: 'Tours ÷ Leads × 100. How effective is your marketing at generating visits?',
  tourToApp: 'Applications ÷ Tours × 100. How effective are your tours at generating applications?',
  leadToLease: 'Lease Signs ÷ Leads × 100. Overall funnel conversion efficiency.',
};
import { SectionHeader } from './SectionHeader';
// import { TimeframeSelector } from './TimeframeSelector';  // Hidden but kept for future use
import { DrillThroughModal } from './DrillThroughModal';
import { usePropertyData } from '../data/PropertyDataContext';

type DrillType = 'units' | 'residents' | 'prospects' | null;
type DrillKey = 
  | 'occupied' | 'vacant' | 'vacantReady' | 'vacantNotReady' | 'aged' | 'preleased' | 'leased' | 'available'
  | 'moveIns' | 'moveOuts' | 'notices30' | 'notices60' | 'allNotices'
  | 'leads' | 'tours' | 'applications' | 'leaseSigns';

const UNIT_COLUMNS = [
  { key: 'unit_id', label: 'Unit' },
  { key: 'floorplan', label: 'Floorplan' },
  { key: 'unit_type', label: 'Type' },
  { key: 'bedrooms', label: 'BR' },
  { key: 'bathrooms', label: 'BA' },
  { key: 'square_feet', label: 'SqFt' },
  { key: 'market_rent', label: 'Market Rent', format: (v: unknown) => v ? `$${Number(v).toLocaleString()}` : '—' },
  { key: 'status', label: 'Status' },
  { key: 'occupancy_status', label: 'Occupancy' },
  { key: 'ready_status', label: 'Ready Status' },
  { key: 'made_ready_date', label: 'Make Ready Date' },
  { key: 'available', label: 'Available', format: (v: unknown) => v === true ? 'Yes' : v === false ? 'No' : '—' },
  { key: 'available_date', label: 'Available Date' },
  { key: 'on_notice_date', label: 'Notice Date' },
  { key: 'days_vacant', label: 'Days Vacant' },
];

const RESIDENT_COLUMNS = [
  { key: 'first_name', label: 'First Name' },
  { key: 'last_name', label: 'Last Name' },
  { key: 'unit', label: 'Unit' },
  { key: 'rent', label: 'Rent', format: (v: unknown) => v ? `$${v}` : '—' },
  { key: 'status', label: 'Status' },
  { key: 'move_in_date', label: 'Move In' },
  { key: 'move_out_date', label: 'Move Out' },
  { key: 'notice_date', label: 'Notice Date' },
];

const PROSPECT_COLUMNS = [
  { key: 'first_name', label: 'First Name' },
  { key: 'last_name', label: 'Last Name' },
  { key: 'email', label: 'Email' },
  { key: 'desired_floorplan', label: 'Desired Unit' },
  { key: 'target_move_in', label: 'Target Move-In' },
  { key: 'last_event', label: 'Last Event' },
  { key: 'event_count', label: 'Events' },
];

interface OccupancySectionV2Props {
  propertyId: string;
}

export function OccupancySectionV2({ propertyId }: OccupancySectionV2Props) {
  const {
    loading,
    error,
    occupancy,
    exposure,
    funnel,
    filteredData,
    rawData,
    setCustomDateRange,
  } = usePropertyData();
  
  const [drillType, setDrillType] = useState<DrillType>(null);
  const [drillTitle, setDrillTitle] = useState('');
  const [drillKey, setDrillKey] = useState<DrillKey | null>(null);
  
  // All trends state (occupancy, exposure, funnel)
  const [trends, setTrends] = useState<AllTrends | null>(null);
  const [trendsLoading, setTrendsLoading] = useState(false);
  
  // Lease expirations state
  const [expirations, setExpirations] = useState<{periods: {label: string; expirations: number; renewals: number; renewal_pct: number; vacating?: number; unknown?: number; mtm?: number; moved_out?: number}[]} | null>(null);
  
  // Tab mode: 'dateRange' or 'month'
  const [dateMode, setDateMode] = useState<'dateRange' | 'month'>('month');
  const [monthMode, setMonthMode] = useState<'CM' | 'PM' | 'MTD'>('CM');
  
  // Custom date range for trends
  const today = new Date();
  const defaultEnd = today.toISOString().split('T')[0];
  const defaultStart = new Date(today.getTime() - 7 * 24 * 60 * 60 * 1000).toISOString().split('T')[0];
  const [trendsStartDate, setTrendStartDate] = useState(defaultStart);
  const [trendsEndDate, setTrendEndDate] = useState(defaultEnd);
  
  // Calculate dates based on month mode
  const getMonthDates = (mode: 'CM' | 'PM' | 'MTD') => {
    const now = new Date();
    let start: Date, end: Date;
    
    if (mode === 'CM') {
      // Current Month: 1st of current month to today
      start = new Date(now.getFullYear(), now.getMonth(), 1);
      end = now;
    } else if (mode === 'PM') {
      // Previous Month: Full previous month
      const prevMonth = now.getMonth() === 0 ? 11 : now.getMonth() - 1;
      const prevYear = now.getMonth() === 0 ? now.getFullYear() - 1 : now.getFullYear();
      start = new Date(prevYear, prevMonth, 1);
      end = new Date(prevYear, prevMonth + 1, 0); // Last day of previous month
    } else {
      // MTD (Month-to-Date): Same as CM
      start = new Date(now.getFullYear(), now.getMonth(), 1);
      end = now;
    }
    
    return {
      start: start.toISOString().split('T')[0],
      end: end.toISOString().split('T')[0]
    };
  };
  
  // Get effective dates based on mode
  const effectiveDates = dateMode === 'month' ? getMonthDates(monthMode) : { start: trendsStartDate, end: trendsEndDate };
  
  // Update data context with selected date range (filters all metrics)
  useEffect(() => {
    setCustomDateRange(effectiveDates.start, effectiveDates.end);
  }, [effectiveDates.start, effectiveDates.end, setCustomDateRange]);
  
  // Fetch all trends (occupancy, exposure, funnel)
  useEffect(() => {
    if (!propertyId) return;
    
    setTrendsLoading(true);
    api.getAllTrends(propertyId, effectiveDates.start, effectiveDates.end)
      .then(setTrends)
      .catch(err => console.warn('Failed to fetch trends:', err))
      .finally(() => setTrendsLoading(false));
  }, [propertyId, effectiveDates.start, effectiveDates.end]);

  // Fetch lease expirations
  useEffect(() => {
    if (!propertyId) return;
    fetch(`/api/v2/properties/${propertyId}/expirations`)
      .then(res => res.json())
      .then(setExpirations)
      .catch(err => console.warn('Failed to fetch expirations:', err));
  }, [propertyId]);

  // Open drill-through with pre-filtered data (instant, no API call!)
  const openDrill = (type: DrillType, title: string, key: DrillKey) => {
    setDrillType(type);
    setDrillTitle(title);
    setDrillKey(key);
  };

  const closeDrill = () => {
    setDrillType(null);
    setDrillKey(null);
  };

  // Get drill-through data from already-loaded filtered data (instant - no API call!)
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const getDrillData = (): any[] => {
    if (!filteredData || !drillKey) return [];
    
    switch (drillKey) {
      // Units
      case 'occupied': return filteredData.occupiedUnits;
      case 'vacant': return filteredData.vacantUnits;
      case 'vacantReady': return filteredData.vacantReadyUnits;
      case 'vacantNotReady': return filteredData.vacantNotReadyUnits;
      case 'aged': return filteredData.agedVacancyUnits;
      case 'preleased': return filteredData.preleasedVacantUnits;
      case 'leased': return filteredData.leasedUnits;
      case 'available': return filteredData.availableUnits;
      
      // Residents
      case 'moveIns': return filteredData.moveInResidents;
      case 'moveOuts': return filteredData.moveOutResidents;
      case 'notices30': return filteredData.notices30Residents;
      case 'notices60': return filteredData.notices60Residents;
      case 'allNotices': return filteredData.allNoticeResidents;
      
      // Prospects
      case 'leads': return filteredData.leadProspects;
      case 'tours': return filteredData.tourProspects;
      case 'applications': return filteredData.applicationProspects;
      case 'leaseSigns': return filteredData.leaseSignProspects;
      
      default: return [];
    }
  };

  const getColumns = () => {
    if (drillType === 'units') return UNIT_COLUMNS;
    if (drillType === 'residents') return RESIDENT_COLUMNS;
    if (drillType === 'prospects') return PROSPECT_COLUMNS;
    return [];
  };

  // const formatDate = (d: Date) => d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });  // Hidden but kept for future use

  if (loading) {
    return (
      <div className="bg-white rounded-xl shadow-venn-card border border-slate-100 p-6">
        <SectionHeader title="Occupancy & Leasing" icon={Building2} />
        <div className="animate-pulse space-y-4">
          <div className="h-12 bg-slate-200 rounded-xl" />
          <div className="grid grid-cols-4 gap-4">
            {[...Array(8)].map((_, i) => (
              <div key={i} className="h-24 bg-slate-200 rounded-xl" />
            ))}
          </div>
        </div>
        <p className="text-sm text-slate-500 mt-4">Loading all property data for bottom-up calculations...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-white rounded-xl shadow-venn-card border border-slate-100 p-6">
        <SectionHeader title="Occupancy & Leasing" icon={Building2} />
        <div className="text-rose-600 p-4 bg-rose-50 rounded-xl border border-rose-200">{error}</div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-xl shadow-venn-card border border-slate-100 p-6">
      <SectionHeader
        title="Occupancy & Leasing"
        icon={Building2}
        description={`${occupancy?.totalUnits ?? 0} total units • Metrics calculated from ${rawData?.units.length ?? 0} units, ${Object.values(rawData?.residents ?? {}).flat().length ?? 0} residents`}
      />

      <div className="space-y-6">
        {/* Timeframe Selector - HIDDEN but kept for future use */}
        {/* <TimeframeSelector
          value={timeframe}
          onChange={setTimeframe}
          periodStart={formatDate(periodStart)}
          periodEnd={formatDate(periodEnd)}
        /> */}

        {/* Date Selection Tabs */}
        <div className="bg-slate-50 rounded-xl border border-slate-200">
          {/* Tab Headers */}
          <div className="flex border-b border-slate-200">
            <button
              onClick={() => setDateMode('month')}
              className={`px-4 py-2.5 text-sm font-medium transition-all ${
                dateMode === 'month'
                  ? 'bg-white border-b-2 border-venn-teal text-venn-teal rounded-tl-xl'
                  : 'text-slate-500 hover:text-slate-700'
              }`}
            >
              Month
            </button>
            <button
              onClick={() => setDateMode('dateRange')}
              className={`px-4 py-2.5 text-sm font-medium transition-all ${
                dateMode === 'dateRange'
                  ? 'bg-white border-b-2 border-venn-teal text-venn-teal'
                  : 'text-slate-500 hover:text-slate-700'
              }`}
            >
              Date Range
            </button>
          </div>
          
          {/* Tab Content */}
          <div className="p-4">
            {dateMode === 'month' ? (
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <Calendar className="w-4 h-4 text-venn-teal" />
                  <div className="flex bg-white rounded-lg border border-slate-200 overflow-hidden">
                    <button
                      onClick={() => setMonthMode('CM')}
                      className={`px-3 py-1.5 text-sm font-medium transition-all ${
                        monthMode === 'CM'
                          ? 'bg-venn-teal  text-blue-600'
                          : 'text-slate-600 hover:bg-slate-50'
                      }`}
                    >
                      Current Month
                    </button>
                    <button
                      onClick={() => setMonthMode('PM')}
                      className={`px-3 py-1.5 text-sm font-medium border-l border-slate-200 transition-all ${
                        monthMode === 'PM'
                          ? 'bg-venn-teal text-blue-600'
                          : 'text-slate-600 hover:bg-slate-50'
                      }`}
                    >
                      Previous Month
                    </button>
                    <button
                      onClick={() => setMonthMode('MTD')}
                      className={`px-3 py-1.5 text-sm font-medium border-l border-slate-200 transition-all ${
                        monthMode === 'MTD'
                          ? 'bg-venn-teal  text-blue-600'
                          : 'text-slate-600 hover:bg-slate-50'
                      }`}
                    >
                      MTD
                    </button>
                  </div>
                  <span className="text-sm text-slate-500 ml-2">
                    {effectiveDates.start} → {effectiveDates.end}
                  </span>
                </div>
                <div className="text-xs text-slate-500">
                  {trendsLoading ? 'Loading...' : trends ? `Comparing to prior ${trends.period_days} days` : ''}
                </div>
              </div>
            ) : (
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <Calendar className="w-4 h-4 text-venn-teal" />
                  <span className="text-sm font-medium text-slate-700">From:</span>
                  <input
                    type="date"
                    value={trendsStartDate}
                    onChange={(e) => setTrendStartDate(e.target.value)}
                    className="px-3 py-1.5 border border-slate-200 rounded-lg text-sm bg-white focus:ring-2 focus:ring-venn-teal/30 focus:border-venn-teal transition-all"
                  />
                  <span className="text-slate-400">to</span>
                  <input
                    type="date"
                    value={trendsEndDate}
                    onChange={(e) => setTrendEndDate(e.target.value)}
                    className="px-3 py-1.5 border border-slate-200 rounded-lg text-sm bg-white focus:ring-2 focus:ring-venn-teal/30 focus:border-venn-teal transition-all"
                  />
                </div>
                <div className="text-xs text-slate-500">
                  {trendsLoading ? 'Loading...' : trends ? `Comparing to prior ${trends.period_days} days` : ''}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* ═══════════════════════════════════════════════════════════════════════════ */}
        {/* SECTION 1: Core Metrics */}
        {/* ═══════════════════════════════════════════════════════════════════════════ */}
        <div className="border-b-2 border-slate-200 pb-6">
          <h3 className="text-sm font-bold text-slate-700 mb-4 uppercase tracking-wider">Core Metrics</h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {occupancy?.totalUnits != null && (
              <div>
                <MetricCard
                  title="Physical Occupancy"
                  value={`${occupancy?.physicalOccupancy ?? 0}%`}
                  subtitle={`${occupancy?.occupiedUnits ?? 0} / ${occupancy?.totalUnits ?? 0} units`}
                  icon={Building2}
                  onClick={() => openDrill('units', `Occupied Units (${occupancy?.occupiedUnits ?? 0})`, 'occupied')}
                  definition={DEFINITIONS.physicalOccupancy}
                  threshold={THRESHOLDS.physicalOccupancy}
                  rawValue={occupancy?.physicalOccupancy ?? 0}
                />
                {trends && !trendsLoading && (
                  <TrendBadge
                    currentValue={trends.occupancy.current.physical_occupancy}
                    priorValue={trends.occupancy.prior.physical_occupancy}
                    higherIsBetter={true}
                    suffix="%"
                    priorLabel={`prior ${trends.period_days}d`}
                  />
                )}
              </div>
            )}
            {occupancy?.leasedUnits != null && (
              <div>
                <MetricCard
                  title="Leased Percentage"
                  value={`${occupancy?.leasedPercentage ?? 0}%`}
                  subtitle={`${occupancy?.leasedUnits ?? 0} leased`}
                  icon={Users}
                  onClick={() => openDrill('units', `Leased Units (${occupancy?.leasedUnits ?? 0})`, 'leased')}
                  definition={DEFINITIONS.leasedPercentage}
                  threshold={THRESHOLDS.leasedPercentage}
                  rawValue={occupancy?.leasedPercentage ?? 0}
                />
                {trends && !trendsLoading && (
                  <TrendBadge
                    currentValue={occupancy?.leasedPercentage ?? 0}
                    priorValue={trends.occupancy.prior.leased_percentage}
                    higherIsBetter={true}
                    suffix="%"
                    priorLabel={`prior ${trends.period_days}d`}
                  />
                )}
              </div>
            )}
            {exposure?.exposure30Days != null && (
              <MetricCard
                title="Exposure (30 Days)"
                value={exposure.exposure30Days}
                subtitle={`${occupancy?.vacantUnits ?? 0} + ${exposure?.notices30Days ?? 0} − ${exposure?.pendingMoveins30Days ?? 0}`}
                onClick={() => openDrill('residents', `Notices 30 Days (${exposure?.notices30Days ?? 0})`, 'notices30')}
                definition={DEFINITIONS.exposure30}
                threshold={THRESHOLDS.exposure30}
                rawValue={exposure.exposure30Days}
              />
            )}
            {exposure?.exposure60Days != null && (
              <MetricCard
                title="Exposure (60 Days)"
                value={exposure.exposure60Days}
                subtitle={`${occupancy?.vacantUnits ?? 0} + ${exposure?.notices60Days ?? 0} − ${exposure?.pendingMoveins60Days ?? 0}`}
                onClick={() => openDrill('residents', `Notices 60 Days (${exposure?.notices60Days ?? 0})`, 'notices60')}
                definition={DEFINITIONS.exposure60}
                threshold={THRESHOLDS.exposure60}
                rawValue={exposure.exposure60Days}
              />
            )}
          </div>
        </div>

        {/* ═══════════════════════════════════════════════════════════════════════════ */}
        {/* SECTION 2: Vacancy */}
        {/* ═══════════════════════════════════════════════════════════════════════════ */}
        <div className="border-b-2 border-slate-200 pb-6">
          <h3 className="text-sm font-bold text-slate-700 mb-4 uppercase tracking-wider">Vacancy</h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {occupancy?.vacantReady != null && occupancy.vacantReady > 0 && (
              <MetricCard
                title="Vacant Ready"
                value={occupancy.vacantReady}
                subtitle="Move-in ready"
                onClick={() => openDrill('units', `Vacant Ready (${occupancy.vacantReady})`, 'vacant')}
                definition="Units that are vacant and ready for immediate move-in."
              />
            )}
            {occupancy?.vacantNotReady != null && occupancy.vacantNotReady > 0 && (
              <MetricCard
                title="Vacant Not Ready"
                value={occupancy.vacantNotReady}
                subtitle="Needs make-ready"
                onClick={() => openDrill('units', `Vacant Not Ready (${occupancy.vacantNotReady})`, 'vacant')}
                definition="Units that are vacant but require make-ready work before move-in."
              />
            )}
            {occupancy?.vacantUnits != null && (
              <div>
                <MetricCard
                  title="Total Vacant Units"
                  value={occupancy.vacantUnits}
                  subtitle={`${occupancy?.vacantReady ?? 0} ready, ${occupancy?.vacantNotReady ?? 0} not ready`}
                  onClick={() => openDrill('units', `Vacant Units (${occupancy.vacantUnits})`, 'vacant')}
                  definition={DEFINITIONS.vacantUnits}
                  threshold={THRESHOLDS.vacantUnits}
                  rawValue={occupancy.vacantUnits}
                />
                {trends && !trendsLoading && (
                  <TrendBadge
                    currentValue={occupancy.vacantUnits}
                    priorValue={trends.occupancy.prior.vacant_units}
                    higherIsBetter={false}
                    priorLabel={`prior ${trends.period_days}d`}
                  />
                )}
              </div>
            )}
            {occupancy?.agedVacancy90Plus != null && occupancy.agedVacancy90Plus > 0 && (
              <MetricCard
                title="Vacant > 90 Days"
                value={occupancy.agedVacancy90Plus}
                icon={AlertTriangle}
                onClick={() => openDrill('units', `Aged Vacancy >90 days (${occupancy.agedVacancy90Plus})`, 'aged')}
                definition={DEFINITIONS.agedVacancy}
                threshold={THRESHOLDS.agedVacancy}
                rawValue={occupancy.agedVacancy90Plus}
              />
            )}
          </div>
        </div>

        {/* ═══════════════════════════════════════════════════════════════════════════ */}
        {/* SECTION 3: Lease Expirations & Renewals */}
        {/* ═══════════════════════════════════════════════════════════════════════════ */}
        {expirations && expirations.periods.length > 0 && (
          <div className="border-b-2 border-slate-200 pb-6">
            <h3 className="text-sm font-bold text-slate-700 mb-4 uppercase tracking-wider">Lease Expirations</h3>
            <div className="overflow-x-auto">
              <table className="min-w-full">
                <thead>
                  <tr className="border-b border-gray-200">
                    <th className="text-left text-xs font-medium text-gray-500 uppercase py-2 pr-4"></th>
                    {expirations.periods.map(p => (
                      <th key={p.label} className="text-right text-xs font-medium text-gray-500 uppercase py-2 px-4">{p.label}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  <tr className="border-b border-gray-100">
                    <td className="text-sm text-gray-700 py-2 pr-4 font-medium">Expiring</td>
                    {expirations.periods.map(p => (
                      <td key={p.label} className="text-right text-sm text-gray-900 py-2 px-4 font-semibold">{p.expirations}</td>
                    ))}
                  </tr>
                  <tr className="border-b border-gray-100">
                    <td className="text-sm text-green-700 py-2 pr-4 font-medium">Renewed</td>
                    {expirations.periods.map(p => (
                      <td key={p.label} className="text-right text-sm text-green-700 py-2 px-4 font-semibold">{p.renewals}</td>
                    ))}
                  </tr>
                  {expirations.periods[0]?.vacating != null && (
                    <tr className="border-b border-gray-100">
                      <td className="text-sm text-red-600 py-2 pr-4 font-medium">Vacating</td>
                      {expirations.periods.map(p => (
                        <td key={p.label} className="text-right text-sm text-red-600 py-2 px-4 font-semibold">{p.vacating || 0}</td>
                      ))}
                    </tr>
                  )}
                  {expirations.periods[0]?.unknown != null && expirations.periods[0].unknown > 0 && (
                    <tr className="border-b border-gray-100">
                      <td className="text-sm text-amber-600 py-2 pr-4 font-medium">Pending</td>
                      {expirations.periods.map(p => (
                        <td key={p.label} className="text-right text-sm text-amber-600 py-2 px-4">{p.unknown || 0}</td>
                      ))}
                    </tr>
                  )}
                  {expirations.periods[0]?.mtm != null && expirations.periods[0].mtm > 0 && (
                    <tr className="border-b border-gray-100">
                      <td className="text-sm text-gray-500 py-2 pr-4 font-medium">Month-to-Month</td>
                      {expirations.periods.map(p => (
                        <td key={p.label} className="text-right text-sm text-gray-500 py-2 px-4">{p.mtm || 0}</td>
                      ))}
                    </tr>
                  )}
                  <tr>
                    <td className="text-sm text-gray-700 py-2 pr-4 font-medium">Renewal %</td>
                    {expirations.periods.map(p => (
                      <td key={p.label} className={`text-right text-sm py-2 px-4 font-semibold ${p.renewal_pct >= 50 ? 'text-green-600' : p.renewal_pct >= 30 ? 'text-yellow-600' : 'text-red-600'}`}>
                        {p.renewal_pct}%
                      </td>
                    ))}
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* ═══════════════════════════════════════════════════════════════════════════ */}
        {/* SECTION 4: Movement */}
        {/* ═══════════════════════════════════════════════════════════════════════════ */}
        <div className="border-b-2 border-slate-200 pb-6">
          <h3 className="text-sm font-bold text-slate-700 mb-4 uppercase tracking-wider">Movement</h3>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            {exposure?.notices30Days != null && (
              <MetricCard
                title="Notices (30d)"
                value={exposure.notices30Days}
                subtitle="Pending move-outs"
                icon={Calendar}
                onClick={() => openDrill('residents', `Notices 30 Days (${exposure.notices30Days})`, 'notices30')}
                definition={DEFINITIONS.notices30}
              />
            )}
            {exposure?.scheduledMoveIns != null && exposure.scheduledMoveIns > 0 && (
              <MetricCard
                title="Scheduled Move-Ins"
                value={exposure.scheduledMoveIns}
                subtitle="Leases signed, awaiting move-in"
                icon={Users}
                definition="Total future residents with signed leases (Applicant - Lease Signed status). These are confirmed move-ins without exact dates from the API."
              />
            )}
            {exposure?.moveOuts != null && (
              <div>
                <MetricCard
                  title="Move-Out"
                  value={exposure.moveOuts}
                  icon={DoorOpen}
                  onClick={() => openDrill('residents', `Move-Outs (${exposure.moveOuts})`, 'moveOuts')}
                  definition={DEFINITIONS.moveOuts}
                />
                {trends && !trendsLoading && (
                  <TrendBadge
                    currentValue={exposure.moveOuts}
                    priorValue={trends.exposure.prior.move_outs}
                    higherIsBetter={false}
                    priorLabel={`prior ${trends.period_days}d`}
                  />
                )}
              </div>
            )}
            {exposure?.moveIns != null && (
              <div>
                <MetricCard
                  title="Move-In"
                  value={exposure.moveIns}
                  icon={DoorOpen}
                  onClick={() => openDrill('residents', `Move-Ins (${exposure.moveIns})`, 'moveIns')}
                  definition={DEFINITIONS.moveIns}
                />
                {trends && !trendsLoading && (
                  <TrendBadge
                    currentValue={exposure.moveIns}
                    priorValue={trends.exposure.prior.move_ins}
                    higherIsBetter={true}
                    priorLabel={`prior ${trends.period_days}d`}
                  />
                )}
              </div>
            )}
            {exposure?.netAbsorption != null && (
              <div>
                <MetricCard
                  title="Net Move-In"
                  value={exposure.netAbsorption}
                  subtitle={exposure.netAbsorption > 0 ? 'Growing' : exposure.netAbsorption < 0 ? 'Shrinking' : 'Flat'}
                  definition={DEFINITIONS.netAbsorption}
                />
                {trends && !trendsLoading && (
                  <TrendBadge
                    currentValue={exposure.netAbsorption}
                    priorValue={trends.exposure.prior.net_absorption}
                    higherIsBetter={true}
                    priorLabel={`prior ${trends.period_days}d`}
                  />
                )}
              </div>
            )}
          </div>
        </div>

        {/* ═══════════════════════════════════════════════════════════════════════════ */}
        {/* SECTION 5: Funnel */}
        {/* ═══════════════════════════════════════════════════════════════════════════ */}
        <div className="border-b-2 border-slate-200 pb-6">
          <h3 className="text-sm font-bold text-slate-700 mb-4 uppercase tracking-wider">Funnel</h3>
          <div className="grid grid-cols-2 md:grid-cols-6 gap-4">
            {funnel?.leads != null && funnel.leads > 0 && (
              <div>
                <MetricCard
                  title="Leads"
                  value={funnel.leads}
                  icon={TrendingUp}
                  onClick={() => openDrill('prospects', `Leads (${funnel.leads})`, 'leads')}
                  definition={DEFINITIONS.leads}
                />
                {trends && !trendsLoading && (
                  <TrendBadge
                    currentValue={funnel.leads}
                    priorValue={trends.funnel.prior.leads}
                    higherIsBetter={true}
                    priorLabel={`prior ${trends.period_days}d`}
                  />
                )}
              </div>
            )}
            {funnel?.tours != null && funnel.tours > 0 && (
              <div>
                <MetricCard
                  title="Tours"
                  value={funnel.tours}
                  onClick={() => openDrill('prospects', `Tours (${funnel.tours})`, 'tours')}
                  definition={DEFINITIONS.tours}
                />
                {trends && !trendsLoading && (
                  <TrendBadge
                    currentValue={funnel.tours}
                    priorValue={trends.funnel.prior.tours}
                    higherIsBetter={true}
                    priorLabel={`prior ${trends.period_days}d`}
                  />
                )}
              </div>
            )}
            {funnel?.leadToTourRate != null && funnel.leadToTourRate > 0 && (
              <MetricCard
                title="Lead/Tour Conv."
                value={`${funnel.leadToTourRate}%`}
                definition={DEFINITIONS.leadToTour}
                threshold={THRESHOLDS.leadToTour}
                rawValue={funnel.leadToTourRate}
              />
            )}
            {funnel?.applications != null && funnel.applications > 0 && (
              <div>
                <MetricCard
                  title="Applications"
                  value={funnel.applications}
                  onClick={() => openDrill('prospects', `Applications (${funnel.applications})`, 'applications')}
                  definition={DEFINITIONS.applications}
                />
                {trends && !trendsLoading && (
                  <TrendBadge
                    currentValue={funnel.applications}
                    priorValue={trends.funnel.prior.applications}
                    higherIsBetter={true}
                    priorLabel={`prior ${trends.period_days}d`}
                  />
                )}
              </div>
            )}
            {funnel?.tourToAppRate != null && funnel.tourToAppRate > 0 && (
              <MetricCard
                title="Tour/App Conv."
                value={`${funnel.tourToAppRate}%`}
                definition={DEFINITIONS.tourToApp}
                threshold={THRESHOLDS.tourToApp}
                rawValue={funnel.tourToAppRate}
              />
            )}
            {funnel?.leaseSigns != null && funnel.leaseSigns > 0 && (
              <div>
                <MetricCard
                  title="Leases"
                  value={funnel.leaseSigns}
                  onClick={() => openDrill('prospects', `Lease Signs (${funnel.leaseSigns})`, 'leaseSigns')}
                  definition={DEFINITIONS.leaseSigns}
                />
                {trends && !trendsLoading && (
                  <TrendBadge
                    currentValue={funnel.leaseSigns}
                    priorValue={trends.funnel.prior.lease_signs}
                    higherIsBetter={true}
                    priorLabel={`prior ${trends.period_days}d`}
                  />
                )}
              </div>
            )}
          </div>
        </div>

        {/* ═══════════════════════════════════════════════════════════════════════════ */}
        {/* SECTION 6: Conversion Rates */}
        {/* ═══════════════════════════════════════════════════════════════════════════ */}
        <div>
          <h3 className="text-sm font-bold text-slate-700 mb-4 uppercase tracking-wider">Conversion Rates</h3>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
            {funnel?.leadToLeaseRate != null && funnel.leadToLeaseRate > 0 && (
              <div>
                <MetricCard
                  title="Lease/Lead Conversion"
                  value={`${funnel.leadToLeaseRate}%`}
                  definition={DEFINITIONS.leadToLease}
                  threshold={THRESHOLDS.leadToLease}
                  rawValue={funnel.leadToLeaseRate}
                />
                {trends && !trendsLoading && (
                  <TrendBadge
                    currentValue={funnel.leadToLeaseRate}
                    priorValue={trends.funnel.prior.lead_to_lease_rate}
                    higherIsBetter={true}
                    suffix="%"
                    priorLabel={`prior ${trends.period_days}d`}
                  />
                )}
              </div>
            )}
            {funnel?.leadToTourRate != null && funnel.leadToTourRate > 0 && (
              <div>
                <MetricCard
                  title="Lease/Tour Conversion"
                  value={`${funnel?.tours && funnel?.leaseSigns ? ((funnel.leaseSigns / funnel.tours) * 100).toFixed(1) : 0}%`}
                  definition="Percentage of tours that convert to signed leases."
                />
                {trends && !trendsLoading && (
                  <TrendBadge
                    currentValue={funnel?.tours && funnel?.leaseSigns ? (funnel.leaseSigns / funnel.tours) * 100 : 0}
                    priorValue={trends.funnel.prior.tour_to_app_rate}
                    higherIsBetter={true}
                    suffix="%"
                    priorLabel={`prior ${trends.period_days}d`}
                  />
                )}
              </div>
            )}
            {funnel?.appToLeaseRate != null && funnel.appToLeaseRate > 0 && (
              <div>
                <MetricCard
                  title="Lease/Application Conv."
                  value={`${funnel.appToLeaseRate}%`}
                  definition="Percentage of applications that convert to signed leases."
                />
                {trends && !trendsLoading && (
                  <TrendBadge
                    currentValue={funnel.appToLeaseRate}
                    priorValue={trends.funnel.prior.tour_to_app_rate}
                    higherIsBetter={true}
                    suffix="%"
                    priorLabel={`prior ${trends.period_days}d`}
                  />
                )}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Drill-Through Modal - Data is INSTANT (already loaded) */}
      <DrillThroughModal
        isOpen={drillType !== null}
        onClose={closeDrill}
        title={drillTitle}
        data={getDrillData()}
        columns={getColumns()}
        loading={false}  // Never loading - data is pre-computed!
      />
    </div>
  );
}
