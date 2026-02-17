/**
 * Property Data Context - Bottom-up metrics architecture
 * 
 * Fetches ALL raw data for a property once, then:
 * 1. Calculation layer computes metrics from raw data
 * 2. Same filtered data is used for drill-through
 * 
 * This ensures metric counts ALWAYS match drill-through row counts.
 */
import { createContext, useContext, useState, useEffect, useCallback, useMemo, useRef, ReactNode } from 'react';
import { api } from '../api';
import type { Timeframe, UnitRaw, ResidentRaw, ProspectRaw } from '../types';

// ============= Types =============

interface PropertyRawData {
  units: UnitRaw[];
  residents: {
    current: ResidentRaw[];
    notice: ResidentRaw[];
    past: ResidentRaw[];
    future: ResidentRaw[];
  };
  prospects: ProspectRaw[];
}

interface OccupancyMetrics {
  totalUnits: number;
  occupiedUnits: number;
  vacantUnits: number;
  leasedUnits: number;
  preleasedVacant: number;
  availableUnits: number;  // Vacant units NOT preleased (truly available to rent)
  physicalOccupancy: number;
  leasedPercentage: number;
  vacantReady: number;
  vacantNotReady: number;
  agedVacancy90Plus: number;
}

interface ExposureMetrics {
  exposure30Days: number;
  exposure60Days: number;
  noticesTotal: number;
  notices30Days: number;
  notices60Days: number;
  pendingMoveins30Days: number;
  pendingMoveins60Days: number;
  scheduledMoveIns: number;  // Future residents (Applicant - Lease Signed)
  moveIns: number;
  moveOuts: number;
  netAbsorption: number;
}

interface FunnelMetrics {
  leads: number;
  tours: number;
  applications: number;
  leaseSigns: number;
  denials: number;
  sightUnseen: number;
  tourToApp: number;
  leadToTourRate: number;
  tourToAppRate: number;
  appToLeaseRate: number;
  leadToLeaseRate: number;
  marketingNetLeases?: number | null;
}

interface ExpirationPeriod {
  label: string;
  expirations: number;
  renewals: number;
  signed: number;
  submitted: number;
  selected: number;
  renewal_pct: number;
  vacating?: number;
  unknown?: number;
  mtm?: number;
  moved_out?: number;
}

interface ExpirationMetrics {
  periods: ExpirationPeriod[];
}

interface FilteredData {
  // Units filtered for each metric
  occupiedUnits: UnitRaw[];
  vacantUnits: UnitRaw[];
  vacantReadyUnits: UnitRaw[];
  vacantNotReadyUnits: UnitRaw[];
  agedVacancyUnits: UnitRaw[];
  preleasedVacantUnits: UnitRaw[];
  leasedUnits: UnitRaw[];  // occupied + preleased vacant
  availableUnits: UnitRaw[];  // vacant units NOT preleased (truly available)
  
  // Residents filtered for each metric
  moveInResidents: ResidentRaw[];
  moveOutResidents: ResidentRaw[];
  notices30Residents: ResidentRaw[];
  notices60Residents: ResidentRaw[];
  allNoticeResidents: ResidentRaw[];
  
  // Prospects filtered for each metric
  leadProspects: ProspectRaw[];
  tourProspects: ProspectRaw[];
  applicationProspects: ProspectRaw[];
  leaseSignProspects: ProspectRaw[];
}

interface PropertyDataContextValue {
  // Raw data
  rawData: PropertyRawData | null;
  loading: boolean;
  refreshing: boolean;
  error: string | null;
  
  // Timeframe
  timeframe: Timeframe;
  setTimeframe: (tf: Timeframe) => void;
  periodStart: Date;
  periodEnd: Date;
  
  // Custom date range (overrides timeframe when set)
  setCustomDateRange: (start: string, end: string) => void;
  clearCustomDateRange: () => void;
  
  // Calculated metrics (computed from raw data)
  occupancy: OccupancyMetrics | null;
  exposure: ExposureMetrics | null;
  funnel: FunnelMetrics | null;
  priorFunnel: FunnelMetrics | null;
  priorFunnelLabel: string;
  expirations: ExpirationMetrics | null;
  
  // Filtered data for drill-through (same data used for metrics)
  filteredData: FilteredData | null;
  
  // Refresh
  refresh: () => void;
}

// ============= Date Helpers =============

function getDateRange(timeframe: Timeframe): [Date, Date] {
  const today = new Date();
  today.setHours(23, 59, 59, 999);
  
  let start: Date;
  
  switch (timeframe) {
    case 'cm': // Current Month: 1st of month to today
      start = new Date(today.getFullYear(), today.getMonth(), 1);
      break;
    case 'pm': // Previous Month: full previous month
      start = new Date(today.getFullYear(), today.getMonth() - 1, 1);
      const end = new Date(today.getFullYear(), today.getMonth(), 0);
      end.setHours(23, 59, 59, 999);
      return [start, end];
    case 'ytd': // Year to Date: Jan 1 to today
      start = new Date(today.getFullYear(), 0, 1);
      break;
    case 'l30': // Last 30 days
      start = new Date(today);
      start.setDate(start.getDate() - 30);
      break;
    case 'l7': // Last 7 days
      start = new Date(today);
      start.setDate(start.getDate() - 7);
      break;
    default:
      start = new Date(today.getFullYear(), today.getMonth(), 1);
  }
  
  start.setHours(0, 0, 0, 0);
  return [start, today];
}

function parseDate(dateStr?: string | null): Date | null {
  if (!dateStr) return null;
  const d = new Date(dateStr);
  return isNaN(d.getTime()) ? null : d;
}

function isInPeriod(date: Date | null, start: Date, end: Date): boolean {
  if (!date) return false;
  return date >= start && date <= end;
}

function isWithinDays(date: Date | null, fromDate: Date, days: number): boolean {
  if (!date) return false;
  const future = new Date(fromDate);
  future.setDate(future.getDate() + days);
  return date >= fromDate && date <= future;
}

// ============= Calculation Functions =============

function calculateOccupancy(units: UnitRaw[], futureResidents: ResidentRaw[]): OccupancyMetrics {
  // Exclude down/model units from inventory (consistent with box score)
  const downUnits = units.filter(u => u.occupancy_status === 'down' || u.occupancy_status === 'model').length;
  const totalUnits = units.length - downUnits;
  
  // 'notice' is mapped to 'occupied' upstream; count both for safety
  const occupiedUnits = units.filter(u => u.occupancy_status === 'occupied' || u.occupancy_status === 'notice').length;
  const vacantUnits = units.filter(u => u.occupancy_status === 'vacant').length;
  
  // Preleased vacant = vacant units with a future resident
  const vacantUnitIds = new Set(units.filter(u => u.occupancy_status === 'vacant').map(u => u.unit_id));
  const futureUnitIds = new Set(futureResidents.map(r => r.unit));
  const preleasedVacant = [...vacantUnitIds].filter(id => futureUnitIds.has(id)).length;
  
  const leasedUnits = occupiedUnits + preleasedVacant;
  
  // Available = units with RealPage Available flag set (vacant ready OR occupied on notice)
  // Falls back to vacant - preleased for Yardi
  const availableUnits = units.filter(u => u.available === true).length || (vacantUnits - preleasedVacant);
  
  const physicalOccupancy = totalUnits > 0 ? Math.round((occupiedUnits / totalUnits) * 1000) / 10 : 0;
  const leasedPercentage = totalUnits > 0 ? Math.round((leasedUnits / totalUnits) * 1000) / 10 : 0;
  
  const vacantReady = units.filter(u => 
    u.occupancy_status === 'vacant' && (u.ready_status === 'ready' || u.status?.toLowerCase().includes('ready'))
  ).length;
  const vacantNotReady = vacantUnits - vacantReady;
  
  const agedVacancy90Plus = units.filter(u => 
    u.occupancy_status === 'vacant' && (u.days_vacant ?? 0) > 90
  ).length;
  
  return {
    totalUnits,
    occupiedUnits,
    vacantUnits,
    leasedUnits,
    preleasedVacant,
    availableUnits,
    physicalOccupancy,
    leasedPercentage,
    vacantReady,
    vacantNotReady,
    agedVacancy90Plus,
  };
}

function calculateExposure(
  units: UnitRaw[],
  residents: PropertyRawData['residents'],
  periodStart: Date,
  periodEnd: Date
): ExposureMetrics {
  const today = new Date();
  const vacantCount = units.filter(u => u.occupancy_status === 'vacant').length;
  
  // Move-ins: residents who moved in during the period
  const moveIns = [...residents.current, ...residents.future].filter(r => {
    const moveInDate = parseDate(r.move_in_date);
    return isInPeriod(moveInDate, periodStart, periodEnd);
  }).length;
  
  // Move-outs: residents who moved out during the period
  const moveOuts = residents.past.filter(r => {
    const moveOutDate = parseDate(r.move_out_date);
    return isInPeriod(moveOutDate, periodStart, periodEnd);
  }).length;
  
  // Notices with move-out in next 30/60 days
  const notices30Days = residents.notice.filter(r => {
    const moveOutDate = parseDate(r.move_out_date || r.lease_end);
    return isWithinDays(moveOutDate, today, 30);
  }).length;
  
  const notices60Days = residents.notice.filter(r => {
    const moveOutDate = parseDate(r.move_out_date || r.lease_end);
    return isWithinDays(moveOutDate, today, 60);
  }).length;
  
  const noticesTotal = residents.notice.length;
  
  // Pending move-outs (notices) in next 30/60 days
  const pendingMoveouts30 = notices30Days;
  const pendingMoveouts60 = notices60Days;
  
  // Pending move-ins in next 30/60 days
  const pendingMoveins30 = residents.future.filter(r => {
    const moveInDate = parseDate(r.move_in_date);
    return isWithinDays(moveInDate, today, 30);
  }).length;
  
  const pendingMoveins60 = residents.future.filter(r => {
    const moveInDate = parseDate(r.move_in_date);
    return isWithinDays(moveInDate, today, 60);
  }).length;
  
  // Exposure = (Vacant + Pending Move-outs) - Pending Move-ins
  const exposure30Days = (vacantCount + pendingMoveouts30) - pendingMoveins30;
  const exposure60Days = (vacantCount + pendingMoveouts60) - pendingMoveins60;
  
  const netAbsorption = moveIns - moveOuts;
  
  // Scheduled Move-Ins = all future residents (Applicant - Lease Signed)
  const scheduledMoveIns = residents.future.length;
  
  return {
    exposure30Days,
    exposure60Days,
    noticesTotal,
    notices30Days,
    notices60Days,
    pendingMoveins30Days: pendingMoveins30,
    pendingMoveins60Days: pendingMoveins60,
    scheduledMoveIns,
    moveIns,
    moveOuts,
    netAbsorption,
  };
}

function calculateFunnel(prospects: ProspectRaw[], periodStart: Date, periodEnd: Date): FunnelMetrics {
  // Filter prospects to those with events in the period
  const periodProspects = prospects.filter(p => {
    const eventDate = parseDate(p.event_date);
    return isInPeriod(eventDate, periodStart, periodEnd);
  });
  
  const leadEvents = ['Email', 'CallFromProspect', 'Webservice', 'Walkin', 'Lead', 'Inquiry'];
  const tourEvents = ['Show', 'Tour', 'Visit'];
  const appEvents = ['Application', 'Apply'];
  const leaseEvents = ['LeaseSign', 'Lease', 'Signed'];
  const denialEvents = ['ApplicationDenied', 'Denied'];
  
  const leads = periodProspects.filter(p => 
    leadEvents.some(e => p.last_event?.toLowerCase().includes(e.toLowerCase()))
  ).length;
  
  const tours = periodProspects.filter(p => 
    tourEvents.some(e => p.last_event?.toLowerCase().includes(e.toLowerCase()))
  ).length;
  
  const applications = periodProspects.filter(p => 
    appEvents.some(e => p.last_event?.toLowerCase().includes(e.toLowerCase()))
  ).length;
  
  const leaseSigns = periodProspects.filter(p => 
    leaseEvents.some(e => p.last_event?.toLowerCase().includes(e.toLowerCase()))
  ).length;
  
  const denials = periodProspects.filter(p => 
    denialEvents.some(e => p.last_event?.toLowerCase().includes(e.toLowerCase()))
  ).length;
  
  const leadToTourRate = leads > 0 ? Math.round((tours / leads) * 1000) / 10 : 0;
  const tourToAppRate = tours > 0 ? Math.round((applications / tours) * 1000) / 10 : 0;
  const appToLeaseRate = applications > 0 ? Math.round((leaseSigns / applications) * 1000) / 10 : 0;
  const leadToLeaseRate = leads > 0 ? Math.round((leaseSigns / leads) * 1000) / 10 : 0;
  
  return {
    leads,
    tours,
    applications,
    leaseSigns,
    denials,
    sightUnseen: 0,
    tourToApp: 0,
    leadToTourRate,
    tourToAppRate,
    appToLeaseRate,
    leadToLeaseRate,
  };
}

function calculateFilteredData(
  rawData: PropertyRawData,
  periodStart: Date,
  periodEnd: Date
): FilteredData {
  const today = new Date();
  const { units, residents, prospects } = rawData;
  
  // Units
  const occupiedUnits = units.filter(u => u.occupancy_status === 'occupied');
  const vacantUnits = units.filter(u => u.occupancy_status === 'vacant');
  const vacantReadyUnits = units.filter(u => 
    u.occupancy_status === 'vacant' && (u.ready_status === 'ready' || u.status?.toLowerCase().includes('ready'))
  );
  const vacantNotReadyUnits = vacantUnits.filter(u => 
    u.ready_status !== 'ready' && !u.status?.toLowerCase().includes('ready')
  );
  const agedVacancyUnits = units.filter(u => 
    u.occupancy_status === 'vacant' && (u.days_vacant ?? 0) > 90
  );
  
  // Preleased vacant
  const futureUnitIds = new Set(residents.future.map(r => r.unit));
  const preleasedVacantUnits = vacantUnits.filter(u => futureUnitIds.has(u.unit_id));
  
  // Move-ins during period
  const moveInResidents = [...residents.current, ...residents.future].filter(r => {
    const moveInDate = parseDate(r.move_in_date);
    return isInPeriod(moveInDate, periodStart, periodEnd);
  });
  
  // Move-outs during period
  const moveOutResidents = residents.past.filter(r => {
    const moveOutDate = parseDate(r.move_out_date);
    return isInPeriod(moveOutDate, periodStart, periodEnd);
  });
  
  // Notices
  const notices30Residents = residents.notice.filter(r => {
    const moveOutDate = parseDate(r.move_out_date || r.lease_end);
    return isWithinDays(moveOutDate, today, 30);
  });
  
  const notices60Residents = residents.notice.filter(r => {
    const moveOutDate = parseDate(r.move_out_date || r.lease_end);
    return isWithinDays(moveOutDate, today, 60);
  });
  
  const allNoticeResidents = residents.notice;
  
  // Prospects by stage
  const periodProspects = prospects.filter(p => {
    const eventDate = parseDate(p.event_date);
    return isInPeriod(eventDate, periodStart, periodEnd);
  });
  
  const leadEvents = ['Email', 'CallFromProspect', 'Webservice', 'Walkin', 'Lead', 'Inquiry'];
  const tourEvents = ['Show', 'Tour', 'Visit'];
  const appEvents = ['Application', 'Apply'];
  const leaseEvents = ['LeaseSign', 'Lease', 'Signed'];
  
  const leadProspects = periodProspects.filter(p => 
    leadEvents.some(e => p.last_event?.toLowerCase().includes(e.toLowerCase()))
  );
  
  const tourProspects = periodProspects.filter(p => 
    tourEvents.some(e => p.last_event?.toLowerCase().includes(e.toLowerCase()))
  );
  
  const applicationProspects = periodProspects.filter(p => 
    appEvents.some(e => p.last_event?.toLowerCase().includes(e.toLowerCase()))
  );
  
  const leaseSignProspects = periodProspects.filter(p => 
    leaseEvents.some(e => p.last_event?.toLowerCase().includes(e.toLowerCase()))
  );
  
  // Leased = occupied + preleased vacant (same calculation as metric)
  const leasedUnits = [...occupiedUnits, ...preleasedVacantUnits];
  
  // Available = units with RealPage Available flag (vacant ready OR occupied on notice)
  // Falls back to vacant NOT preleased for Yardi
  const unitsWithAvailableFlag = units.filter(u => u.available === true);
  const availableUnits = unitsWithAvailableFlag.length > 0 
    ? unitsWithAvailableFlag 
    : vacantUnits.filter(u => !futureUnitIds.has(u.unit_id));
  
  return {
    occupiedUnits,
    vacantUnits,
    vacantReadyUnits,
    vacantNotReadyUnits,
    agedVacancyUnits,
    preleasedVacantUnits,
    leasedUnits,
    availableUnits,
    moveInResidents,
    moveOutResidents,
    notices30Residents,
    notices60Residents,
    allNoticeResidents,
    leadProspects,
    tourProspects,
    applicationProspects,
    leaseSignProspects,
  };
}

// ============= Per-property API cache =============
// Avoids redundant fetches when switching between multi/single property views.
// Keyed by `${propertyId}_${timeframe}`. TTL = 5 minutes.
const CACHE_TTL_MS = 5 * 60 * 1000;
interface CacheEntry<T> { data: T; ts: number; }
const _funnelCache = new Map<string, CacheEntry<any>>();
const _priorFunnelCache = new Map<string, CacheEntry<any>>();
const _expirationCache = new Map<string, CacheEntry<any>>();
const _unitsCache = new Map<string, CacheEntry<any>>();
const _residentsCache = new Map<string, CacheEntry<any>>();

function getCached<T>(cache: Map<string, CacheEntry<T>>, key: string): T | null {
  const entry = cache.get(key);
  if (entry && Date.now() - entry.ts < CACHE_TTL_MS) return entry.data;
  return null;
}
function setCache<T>(cache: Map<string, CacheEntry<T>>, key: string, data: T) {
  cache.set(key, { data, ts: Date.now() });
}

// ============= Context =============

const PropertyDataContext = createContext<PropertyDataContextValue | null>(null);

interface PropertyDataProviderProps {
  propertyId: string;
  propertyIds?: string[];  // For multi-property mode
  timeframe?: Timeframe;   // Passed from parent (DashboardV3 time filter)
  children: ReactNode;
}

export function PropertyDataProvider({ propertyId, propertyIds, timeframe: propTimeframe, children }: PropertyDataProviderProps) {
  // Effective IDs: use propertyIds array if provided, otherwise single propertyId
  const effectiveIds = propertyIds && propertyIds.length > 0 ? propertyIds : [propertyId];
  const effectiveKey = effectiveIds.sort().join(',');
  const [rawData, setRawData] = useState<PropertyRawData | null>(null);
  const [apiFunnelData, setApiFunnelData] = useState<FunnelMetrics | null>(null);
  const [apiPriorFunnelData, setApiPriorFunnelData] = useState<FunnelMetrics | null>(null);
  const [priorFunnelLabel, setPriorFunnelLabel] = useState<string>('prev period');
  const [expirationsData, setExpirationsData] = useState<ExpirationMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const hasLoadedOnce = useRef(false);
  const [timeframe, setTimeframe] = useState<Timeframe>(propTimeframe || 'cm');
  
  // Sync timeframe from parent prop
  useEffect(() => {
    if (propTimeframe && propTimeframe !== timeframe) {
      setTimeframe(propTimeframe);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [propTimeframe]);
  
  // Fetch all raw data for the property (or multiple properties)
  const fetchRawData = useCallback(async () => {
    if (effectiveIds.length === 0 || !effectiveIds[0]) return;
    
    // Stale-while-revalidate: only show full loading spinner on first load.
    // On subsequent fetches keep old data visible and show a subtle refreshing state.
    if (!hasLoadedOnce.current) {
      setLoading(true);
    } else {
      setRefreshing(true);
    }
    setError(null);
    
    try {
      // Portfolio APIs already accept arrays of property IDs (with cache)
      const unitsCK = `units_${effectiveKey}`;
      const resCK = `res_${effectiveKey}`;
      const cachedUnits = getCached(_unitsCache, unitsCK);
      const cachedRes = getCached(_residentsCache, resCK);
      const [unifiedUnits, unifiedResidents] = await Promise.all([
        cachedUnits ? Promise.resolve(cachedUnits) : api.getPortfolioUnits(effectiveIds).then(d => { setCache(_unitsCache, unitsCK, d); return d; }),
        cachedRes ? Promise.resolve(cachedRes) : api.getPortfolioResidents(effectiveIds).then(d => { setCache(_residentsCache, resCK, d); return d; }),
      ]);
      
      // Map unified units to UnitRaw format
      const units: UnitRaw[] = unifiedUnits.map((u: any) => ({
        unit_id: u.unit_id,
        floorplan: u.floorplan_name || u.floorplan,
        unit_type: u.floorplan_name || u.floorplan,
        bedrooms: u.bedrooms,
        bathrooms: u.bathrooms,
        square_feet: u.square_feet,
        market_rent: u.market_rent,
        status: u.status,
        occupancy_status: (u.status === 'notice' ? 'occupied' : u.status === 'down' ? 'down' : u.status), // notice units are physically occupied; down units are out of inventory
        ready_status: (u as any).ready_status,
        available: (u as any).available,
        days_vacant: (u as any).days_vacant,
        available_date: (u as any).available_date,
        on_notice_date: (u as any).on_notice_date,
      }));
      
      // Map unified residents to ResidentRaw format and categorize by status
      const allResidents: ResidentRaw[] = unifiedResidents.map((r: any) => ({
        resident_id: r.resident_id,
        first_name: r.first_name,
        last_name: r.last_name,
        unit: r.unit_id,
        rent: r.current_rent,
        status: r.status,
        move_in_date: (r as any).move_in_date || r.lease_start,
        move_out_date: (r as any).move_out_date || r.lease_end,
        lease_start: r.lease_start,
        lease_end: r.lease_end,
        notice_date: (r as any).notice_date,
      }));
      
      // Categorize residents by status
      const currentRes = allResidents.filter(r => r.status === 'Current' || r.status === 'current');
      const noticeRes = allResidents.filter(r => r.status === 'Notice' || r.status === 'notice');
      const pastRes = allResidents.filter(r => r.status === 'Past' || r.status === 'past');
      const futureRes = allResidents.filter(r => r.status === 'Future' || r.status === 'future');
      
      // Fetch prospects for all properties (may fail for RealPage)
      let prospects: ProspectRaw[] = [];
      await Promise.all(effectiveIds.map(async (pid) => {
        try {
          const p = await api.getRawProspects(pid, undefined, timeframe);
          prospects = prospects.concat(p);
        } catch {
          // RealPage doesn't have prospect data yet
        }
      }));
      
      // Fetch expirations/renewals for all properties and merge (with cache)
      try {
        const allExpData = await Promise.all(
          effectiveIds.map(pid => {
            const ck = `${pid}_exp`;
            const cached = getCached(_expirationCache, ck);
            if (cached) return Promise.resolve(cached);
            return api.getExpirations(pid).then(d => { setCache(_expirationCache, ck, d); return d; }).catch(() => null);
          })
        );
        // Merge expiration periods by label
        const periodMap: Record<string, { expirations: number; renewals: number; signed: number; submitted: number; selected: number; vacating: number; unknown: number; mtm: number; moved_out: number }> = {};
        for (const expData of allExpData) {
          if (expData?.periods) {
            for (const p of expData.periods) {
              if (!periodMap[p.label]) periodMap[p.label] = { expirations: 0, renewals: 0, signed: 0, submitted: 0, selected: 0, vacating: 0, unknown: 0, mtm: 0, moved_out: 0 };
              periodMap[p.label].expirations += p.expirations;
              periodMap[p.label].renewals += p.renewals;
              periodMap[p.label].signed += p.signed || 0;
              periodMap[p.label].submitted += p.submitted || 0;
              periodMap[p.label].selected += p.selected || 0;
              periodMap[p.label].vacating += (p as any).vacating || 0;
              periodMap[p.label].unknown += (p as any).unknown || 0;
              periodMap[p.label].mtm += (p as any).mtm || 0;
              periodMap[p.label].moved_out += (p as any).moved_out || 0;
            }
          }
        }
        const mergedPeriods = Object.entries(periodMap).map(([label, data]) => ({
          label,
          expirations: data.expirations,
          renewals: data.renewals,
          signed: data.signed,
          submitted: data.submitted,
          selected: data.selected,
          renewal_pct: data.expirations > 0 ? Math.round(data.renewals / data.expirations * 100) : 0,
          vacating: data.vacating,
          unknown: data.unknown,
          mtm: data.mtm,
          moved_out: data.moved_out,
        }));
        if (mergedPeriods.length > 0) {
          setExpirationsData({ periods: mergedPeriods });
        } else {
          setExpirationsData(null);
        }
      } catch {
        setExpirationsData(null);
      }

      // Fetch funnel data for all properties and merge (current + prior period)
      if (prospects.length === 0) {
        try {
          // Compute prior period date range matching current timeframe
          const now = new Date();
          let priorStart: string | undefined;
          let priorEnd: string | undefined;
          let priorLabel = 'prev period';
          setPriorFunnelLabel('prev period');

          if (timeframe === 'l7') {
            // L7: compare against 8-14 days ago
            const e = new Date(now); e.setDate(e.getDate() - 7);
            const s = new Date(now); s.setDate(s.getDate() - 14);
            priorStart = s.toISOString().slice(0, 10);
            priorEnd = e.toISOString().slice(0, 10);
            priorLabel = 'prev 7d';
          } else if (timeframe === 'l30') {
            // L30: compare against 31-60 days ago
            const e = new Date(now); e.setDate(e.getDate() - 30);
            const s = new Date(now); s.setDate(s.getDate() - 60);
            priorStart = s.toISOString().slice(0, 10);
            priorEnd = e.toISOString().slice(0, 10);
            priorLabel = 'prev 30d';
          } else if (timeframe === 'cm') {
            // MTD: compare against same days in previous month
            const prevMonth = new Date(now.getFullYear(), now.getMonth() - 1, 1);
            const prevEnd = new Date(prevMonth.getFullYear(), prevMonth.getMonth(), Math.min(now.getDate(), new Date(prevMonth.getFullYear(), prevMonth.getMonth() + 1, 0).getDate()));
            priorStart = prevMonth.toISOString().slice(0, 10);
            priorEnd = prevEnd.toISOString().slice(0, 10);
            priorLabel = 'prev month';
          }
          setPriorFunnelLabel(priorLabel);
          // For pm/ytd, just use 'pm' timeframe directly (no custom dates needed)

          const [allFunnels, allPriorFunnels] = await Promise.all([
            Promise.all(effectiveIds.map(pid => {
              const ck = `${pid}_${timeframe}`;
              const cached = getCached(_funnelCache, ck);
              if (cached) return Promise.resolve(cached);
              return api.getLeasingFunnel(pid, timeframe).then(d => { setCache(_funnelCache, ck, d); return d; }).catch(() => null);
            })),
            Promise.all(effectiveIds.map(pid => {
              const priorKey = priorStart && priorEnd ? `${pid}_${timeframe}_${priorStart}_${priorEnd}` : `${pid}_pm`;
              const cached = getCached(_priorFunnelCache, priorKey);
              if (cached) return Promise.resolve(cached);
              const p = priorStart && priorEnd
                ? api.getLeasingFunnel(pid, timeframe, priorStart, priorEnd)
                : api.getLeasingFunnel(pid, 'pm');
              return p.then(d => { setCache(_priorFunnelCache, priorKey, d); return d; }).catch(() => null);
            })),
          ]);
          const merged = allFunnels.reduce((acc, f) => {
            if (f && (f.leads > 0 || f.tours > 0 || f.applications > 0)) {
              acc.leads += f.leads;
              acc.tours += f.tours;
              acc.applications += f.applications;
              acc.leaseSigns += f.lease_signs;
              acc.denials += f.denials;
              acc.sightUnseen += (f as any).sight_unseen || 0;
              acc.tourToApp += (f as any).tour_to_app || 0;
              if ((f as any).marketing_net_leases != null) {
                acc.marketingNetLeases = (acc.marketingNetLeases || 0) + (f as any).marketing_net_leases;
              }
            }
            return acc;
          }, { leads: 0, tours: 0, applications: 0, leaseSigns: 0, denials: 0, sightUnseen: 0, tourToApp: 0, marketingNetLeases: null as number | null });
          if (merged.leads > 0 || merged.tours > 0 || merged.applications > 0) {
            const finalData = {
              ...merged,
              leadToTourRate: merged.leads > 0 ? Math.round(merged.tours / merged.leads * 100) : 0,
              tourToAppRate: merged.tours > 0 ? Math.round(merged.applications / merged.tours * 100) : 0,
              appToLeaseRate: merged.applications > 0 ? Math.round(merged.leaseSigns / merged.applications * 100) : 0,
              leadToLeaseRate: merged.leads > 0 ? Math.round(merged.leaseSigns / merged.leads * 100) : 0,
            };
            setApiFunnelData(finalData);
          } else {
            setApiFunnelData(null);
          }
          // Merge prior period funnel
          const mergedPrior = allPriorFunnels.reduce((acc, f) => {
            if (f && (f.leads > 0 || f.tours > 0 || f.applications > 0)) {
              acc.leads += f.leads;
              acc.tours += f.tours;
              acc.applications += f.applications;
              acc.leaseSigns += f.lease_signs;
              acc.denials += f.denials;
              acc.sightUnseen += (f as any).sight_unseen || 0;
              acc.tourToApp += (f as any).tour_to_app || 0;
            }
            return acc;
          }, { leads: 0, tours: 0, applications: 0, leaseSigns: 0, denials: 0, sightUnseen: 0, tourToApp: 0 });
          if (mergedPrior.leads > 0 || mergedPrior.tours > 0 || mergedPrior.applications > 0) {
            setApiPriorFunnelData({
              ...mergedPrior,
              leadToTourRate: mergedPrior.leads > 0 ? Math.round(mergedPrior.tours / mergedPrior.leads * 100) : 0,
              tourToAppRate: mergedPrior.tours > 0 ? Math.round(mergedPrior.applications / mergedPrior.tours * 100) : 0,
              appToLeaseRate: mergedPrior.applications > 0 ? Math.round(mergedPrior.leaseSigns / mergedPrior.applications * 100) : 0,
              leadToLeaseRate: mergedPrior.leads > 0 ? Math.round(mergedPrior.leaseSigns / mergedPrior.leads * 100) : 0,
            });
          } else {
            setApiPriorFunnelData(null);
          }
        } catch {
          setApiFunnelData(null);
          setApiPriorFunnelData(null);
        }
      } else {
        setApiFunnelData(null);
        setApiPriorFunnelData(null);
      }
      
      setRawData({
        units,
        residents: {
          current: currentRes,
          notice: noticeRes,
          past: pastRes,
          future: futureRes,
        },
        prospects,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load property data');
    } finally {
      hasLoadedOnce.current = true;
      setLoading(false);
      setRefreshing(false);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [effectiveKey, timeframe]);
  
  useEffect(() => {
    fetchRawData();
  }, [fetchRawData]);
  
  // Custom date range state (overrides timeframe when set)
  const [customDateRange, setCustomDateRangeState] = useState<{ start: Date; end: Date } | null>(null);
  
  const setCustomDateRange = useCallback((start: string, end: string) => {
    const startDate = new Date(start);
    startDate.setHours(0, 0, 0, 0);
    const endDate = new Date(end);
    endDate.setHours(23, 59, 59, 999);
    setCustomDateRangeState({ start: startDate, end: endDate });
  }, []);
  
  const clearCustomDateRange = useCallback(() => {
    setCustomDateRangeState(null);
  }, []);
  
  // Calculate date range based on timeframe OR custom range
  const [periodStart, periodEnd] = useMemo(() => {
    if (customDateRange) {
      return [customDateRange.start, customDateRange.end];
    }
    return getDateRange(timeframe);
  }, [timeframe, customDateRange]);
  
  // Calculate metrics from raw data
  const occupancy = useMemo(() => {
    if (!rawData) return null;
    return calculateOccupancy(rawData.units, rawData.residents.future);
  }, [rawData]);
  
  const exposure = useMemo(() => {
    if (!rawData) return null;
    return calculateExposure(rawData.units, rawData.residents, periodStart, periodEnd);
  }, [rawData, periodStart, periodEnd]);
  
  const funnel = useMemo(() => {
    // Use API funnel data if available (imported Excel data for RealPage)
    if (apiFunnelData) {
      return apiFunnelData;
    }
    if (!rawData) return null;
    return calculateFunnel(rawData.prospects, periodStart, periodEnd);
  }, [rawData, apiFunnelData, periodStart, periodEnd]);
  
  // Calculate filtered data for drill-through
  const filteredData = useMemo(() => {
    if (!rawData) return null;
    return calculateFilteredData(rawData, periodStart, periodEnd);
  }, [rawData, periodStart, periodEnd]);
  
  const value: PropertyDataContextValue = {
    rawData,
    loading,
    refreshing,
    error,
    timeframe,
    setTimeframe,
    periodStart,
    periodEnd,
    setCustomDateRange,
    clearCustomDateRange,
    occupancy,
    exposure,
    funnel,
    priorFunnel: apiPriorFunnelData,
    priorFunnelLabel,
    expirations: expirationsData,
    filteredData,
    refresh: fetchRawData,
  };
  
  return (
    <PropertyDataContext.Provider value={value}>
      {children}
    </PropertyDataContext.Provider>
  );
}

export function usePropertyData() {
  const context = useContext(PropertyDataContext);
  if (!context) {
    throw new Error('usePropertyData must be used within PropertyDataProvider');
  }
  return context;
}

// Export types for use in components
export type { OccupancyMetrics, ExposureMetrics, FunnelMetrics, ExpirationMetrics, FilteredData, PropertyRawData };
