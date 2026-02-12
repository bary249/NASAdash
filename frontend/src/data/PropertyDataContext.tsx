/**
 * Property Data Context - Bottom-up metrics architecture
 * 
 * Fetches ALL raw data for a property once, then:
 * 1. Calculation layer computes metrics from raw data
 * 2. Same filtered data is used for drill-through
 * 
 * This ensures metric counts ALWAYS match drill-through row counts.
 */
import { createContext, useContext, useState, useEffect, useCallback, useMemo, ReactNode } from 'react';
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
  leadToTourRate: number;
  tourToAppRate: number;
  appToLeaseRate: number;
  leadToLeaseRate: number;
}

interface ExpirationPeriod {
  label: string;
  expirations: number;
  renewals: number;
  renewal_pct: number;
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
  const totalUnits = units.length;
  
  const occupiedUnits = units.filter(u => u.occupancy_status === 'occupied').length;
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

// ============= Context =============

const PropertyDataContext = createContext<PropertyDataContextValue | null>(null);

interface PropertyDataProviderProps {
  propertyId: string;
  children: ReactNode;
}

export function PropertyDataProvider({ propertyId, children }: PropertyDataProviderProps) {
  const [rawData, setRawData] = useState<PropertyRawData | null>(null);
  const [apiFunnelData, setApiFunnelData] = useState<FunnelMetrics | null>(null);
  const [expirationsData, setExpirationsData] = useState<ExpirationMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [timeframe, setTimeframe] = useState<Timeframe>('cm');
  
  // Fetch all raw data for the property
  const fetchRawData = useCallback(async () => {
    if (!propertyId) return;
    
    setLoading(true);
    setError(null);
    setApiFunnelData(null);  // Reset API funnel data when switching properties
    setExpirationsData(null);
    
    try {
      // Use portfolio API which supports both Yardi and RealPage properties
      const [unifiedUnits, unifiedResidents] = await Promise.all([
        api.getPortfolioUnits([propertyId]),
        api.getPortfolioResidents([propertyId]),
      ]);
      
      // Map unified units to UnitRaw format
      const units: UnitRaw[] = unifiedUnits.map(u => ({
        unit_id: u.unit_id,
        floorplan: u.floorplan_name || u.floorplan,
        unit_type: u.floorplan_name || u.floorplan,
        bedrooms: u.bedrooms,
        bathrooms: u.bathrooms,
        square_feet: u.square_feet,
        market_rent: u.market_rent,
        status: u.status,
        occupancy_status: u.status, // unified status is already 'occupied' or 'vacant'
        ready_status: (u as any).ready_status,
        available: (u as any).available,
        days_vacant: (u as any).days_vacant,
        available_date: (u as any).available_date,
        on_notice_date: (u as any).on_notice_date,
      }));
      
      // Map unified residents to ResidentRaw format and categorize by status
      const allResidents: ResidentRaw[] = unifiedResidents.map(r => ({
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
      
      // Try to get prospects from Yardi API (may fail for RealPage properties)
      let prospects: ProspectRaw[] = [];
      try {
        prospects = await api.getRawProspects(propertyId, undefined, 'ytd');
      } catch {
        // RealPage doesn't have prospect data yet - that's OK
      }
      
      // Fetch expirations/renewals data from API
      try {
        const expData = await api.getExpirations(propertyId);
        if (expData && expData.periods && expData.periods.length > 0) {
          setExpirationsData(expData);
        }
      } catch {
        // No expirations data available
      }

      // If no prospects, try to get funnel data from API (imported Excel data for RealPage)
      if (prospects.length === 0) {
        try {
          const apiFunnel = await api.getLeasingFunnel(propertyId, 'l30');
          if (apiFunnel && apiFunnel.leads > 0) {
            // Map API response to FunnelMetrics format
            setApiFunnelData({
              leads: apiFunnel.leads,
              tours: apiFunnel.tours,
              applications: apiFunnel.applications,
              leaseSigns: apiFunnel.lease_signs,
              denials: apiFunnel.denials,
              leadToTourRate: apiFunnel.lead_to_tour_rate,
              tourToAppRate: apiFunnel.tour_to_app_rate,
              appToLeaseRate: apiFunnel.app_to_lease_rate,
              leadToLeaseRate: apiFunnel.lead_to_lease_rate,
            });
          }
        } catch {
          // No API funnel data available
        }
      } else {
        setApiFunnelData(null);
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
      setLoading(false);
    }
  }, [propertyId]);
  
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
