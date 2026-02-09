/**
 * API client for Owner Dashboard V2
 * All operations are GET-only.
 */
import type {
  PropertyInfo,
  OccupancyMetrics,
  ExposureMetrics,
  LeasingFunnelMetrics,
  UnitPricingMetrics,
  OccupancyTrend,
  AllTrends,
  DashboardSummary,
  Timeframe,
  UnitRaw,
  ResidentRaw,
  ProspectRaw,
  MarketCompsResponse,
  AggregationMode,
  PortfolioOccupancy,
  PortfolioPricing,
  PortfolioSummary,
  UnifiedUnit,
  UnifiedResident,
  AmenityItem,
  AmenitiesSummary,
} from './types';

const API_BASE = '/api/v2';
const PORTFOLIO_BASE = '/api/portfolio';

async function fetchJson<T>(url: string): Promise<T> {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`API error: ${response.status} ${response.statusText}`);
  }
  return response.json();
}

export const api = {
  getProperties: (): Promise<PropertyInfo[]> =>
    fetchJson(`${API_BASE}/properties`),

  getOccupancy: (propertyId: string, timeframe: Timeframe = 'cm'): Promise<OccupancyMetrics> =>
    fetchJson(`${API_BASE}/properties/${propertyId}/occupancy?timeframe=${timeframe}`),

  getExposure: (propertyId: string, timeframe: Timeframe = 'cm'): Promise<ExposureMetrics> =>
    fetchJson(`${API_BASE}/properties/${propertyId}/exposure?timeframe=${timeframe}`),

  getLeasingFunnel: (propertyId: string, timeframe: Timeframe = 'cm'): Promise<LeasingFunnelMetrics> =>
    fetchJson(`${API_BASE}/properties/${propertyId}/leasing-funnel?timeframe=${timeframe}`),

  getExpirations: (propertyId: string): Promise<{ periods: { label: string; expirations: number; renewals: number; renewal_pct: number }[] }> =>
    fetchJson(`${API_BASE}/properties/${propertyId}/expirations`),

  getExpirationDetails: (propertyId: string, days: number = 90, filter?: 'renewed' | 'expiring'): Promise<{ leases: { unit: string; lease_end: string; market_rent: number; status: string; floorplan: string; sqft: number; move_in: string; lease_start: string }[]; count: number }> => {
    const params = new URLSearchParams({ days: String(days) });
    if (filter) params.set('filter', filter);
    return fetchJson(`${API_BASE}/properties/${propertyId}/expirations/details?${params}`);
  },

  getPricing: (propertyId: string): Promise<UnitPricingMetrics> =>
    fetchJson(`${API_BASE}/properties/${propertyId}/pricing`),

  getOccupancyTrend: (propertyId: string, startDate?: string, endDate?: string): Promise<OccupancyTrend> => {
    const params = new URLSearchParams();
    if (startDate) params.set('start_date', startDate);
    if (endDate) params.set('end_date', endDate);
    const query = params.toString();
    return fetchJson(`${API_BASE}/properties/${propertyId}/occupancy-trend${query ? `?${query}` : ''}`);
  },

  getAllTrends: (propertyId: string, startDate?: string, endDate?: string): Promise<AllTrends> => {
    const params = new URLSearchParams();
    if (startDate) params.set('start_date', startDate);
    if (endDate) params.set('end_date', endDate);
    const query = params.toString();
    return fetchJson(`${API_BASE}/properties/${propertyId}/all-trends${query ? `?${query}` : ''}`);
  },

  getSummary: (propertyId: string, timeframe: Timeframe = 'cm'): Promise<DashboardSummary> =>
    fetchJson(`${API_BASE}/properties/${propertyId}/summary?timeframe=${timeframe}`),

  // Drill-through endpoints
  getRawUnits: (propertyId: string, status?: string): Promise<UnitRaw[]> => {
    const params = new URLSearchParams();
    if (status) params.set('status', status);
    const query = params.toString();
    return fetchJson(`${API_BASE}/properties/${propertyId}/units/raw${query ? `?${query}` : ''}`);
  },

  getRawResidents: (propertyId: string, status = 'all', timeframe: Timeframe = 'cm', metricFilter?: string): Promise<ResidentRaw[]> => {
    const params = new URLSearchParams({ status, timeframe });
    if (metricFilter) params.set('metric_filter', metricFilter);
    return fetchJson(`${API_BASE}/properties/${propertyId}/residents/raw?${params}`);
  },

  getRawProspects: (propertyId: string, stage?: string, timeframe: Timeframe = 'cm'): Promise<ProspectRaw[]> => {
    const params = new URLSearchParams({ timeframe });
    if (stage) params.set('stage', stage);
    return fetchJson(`${API_BASE}/properties/${propertyId}/prospects/raw?${params}`);
  },

  // Market Comps
  getMarketComps: (
    submarket: string, 
    subjectProperty?: string, 
    limit = 20,
    filters?: {
      minUnits?: number;
      maxUnits?: number;
      minYearBuilt?: number;
      maxYearBuilt?: number;
      amenities?: string[];
    }
  ): Promise<MarketCompsResponse> => {
    const params = new URLSearchParams({ submarket, limit: String(limit) });
    if (subjectProperty) params.set('subject_property', subjectProperty);
    if (filters?.minUnits) params.set('min_units', String(filters.minUnits));
    if (filters?.maxUnits) params.set('max_units', String(filters.maxUnits));
    if (filters?.minYearBuilt) params.set('min_year_built', String(filters.minYearBuilt));
    if (filters?.maxYearBuilt) params.set('max_year_built', String(filters.maxYearBuilt));
    if (filters?.amenities && filters.amenities.length > 0) {
      params.set('amenities', filters.amenities.join(','));
    }
    return fetchJson(`${API_BASE}/market-comps?${params}`);
  },

  getSubmarkets: (): Promise<{ id: string; name: string }[]> =>
    fetchJson(`${API_BASE}/submarkets`),

  getPropertyLocation: (propertyId: string): Promise<{ property_id: string; name: string; city: string; state: string }> =>
    fetchJson(`${API_BASE}/properties/${propertyId}/location`),

  // =========================================================================
  // Portfolio API (Multi-property aggregation)
  // =========================================================================

  getPortfolioOccupancy: (
    propertyIds: string[],
    mode: AggregationMode = 'weighted_avg',
    pmsTypes?: string[]
  ): Promise<PortfolioOccupancy> => {
    const params = new URLSearchParams({
      property_ids: propertyIds.join(','),
      mode,
    });
    if (pmsTypes) params.set('pms_types', pmsTypes.join(','));
    return fetchJson(`${PORTFOLIO_BASE}/occupancy?${params}`);
  },

  getPortfolioPricing: (
    propertyIds: string[],
    mode: AggregationMode = 'weighted_avg',
    pmsTypes?: string[]
  ): Promise<PortfolioPricing> => {
    const params = new URLSearchParams({
      property_ids: propertyIds.join(','),
      mode,
    });
    if (pmsTypes) params.set('pms_types', pmsTypes.join(','));
    return fetchJson(`${PORTFOLIO_BASE}/pricing?${params}`);
  },

  getPortfolioSummary: (
    propertyIds: string[],
    mode: AggregationMode = 'weighted_avg',
    pmsTypes?: string[]
  ): Promise<PortfolioSummary> => {
    const params = new URLSearchParams({
      property_ids: propertyIds.join(','),
      mode,
    });
    if (pmsTypes) params.set('pms_types', pmsTypes.join(','));
    return fetchJson(`${PORTFOLIO_BASE}/summary?${params}`);
  },

  getPortfolioUnits: (
    propertyIds: string[],
    status?: string,
    pmsTypes?: string[]
  ): Promise<UnifiedUnit[]> => {
    const params = new URLSearchParams({
      property_ids: propertyIds.join(','),
    });
    if (status) params.set('status', status);
    if (pmsTypes) params.set('pms_types', pmsTypes.join(','));
    return fetchJson(`${PORTFOLIO_BASE}/units?${params}`);
  },

  getPortfolioResidents: (
    propertyIds: string[],
    status?: string,
    pmsTypes?: string[]
  ): Promise<UnifiedResident[]> => {
    const params = new URLSearchParams({
      property_ids: propertyIds.join(','),
    });
    if (status) params.set('status', status);
    if (pmsTypes) params.set('pms_types', pmsTypes.join(','));
    return fetchJson(`${PORTFOLIO_BASE}/residents?${params}`);
  },

  getPortfolioProperties: (): Promise<{ id: string; name: string; pms_type: string }[]> =>
    fetchJson(`${PORTFOLIO_BASE}/properties`),

  // Amenities
  getAmenities: (propertyId: string, itemType?: string): Promise<AmenityItem[]> => {
    const params = new URLSearchParams();
    if (itemType) params.set('item_type', itemType);
    const query = params.toString();
    return fetchJson(`${API_BASE}/properties/${propertyId}/amenities${query ? `?${query}` : ''}`);
  },

  getAmenitiesSummary: (propertyId: string): Promise<AmenitiesSummary> =>
    fetchJson(`${API_BASE}/properties/${propertyId}/amenities/summary`),

  // AI Chat
  getChatStatus: (): Promise<{ available: boolean; message: string }> =>
    fetchJson(`${API_BASE}/chat/status`),

  sendChatMessage: async (propertyId: string, message: string, history: { role: string; content: string }[] = []): Promise<{ response: string; columns?: Array<{key: string; label: string}>; data?: Array<Record<string, unknown>>; actions?: Array<{label: string}> }> => {
    const response = await fetch(`${API_BASE}/properties/${propertyId}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message, history }),
    });
    if (!response.ok) {
      throw new Error(`API error: ${response.status} ${response.statusText}`);
    }
    return response.json();
  },

  // Portfolio-level AI Chat (Asset Manager perspective)
  sendPortfolioChatMessage: async (message: string, history: { role: string; content: string }[] = []): Promise<{ response: string; columns?: Array<{key: string; label: string}>; data?: Array<Record<string, unknown>>; actions?: Array<{label: string}> }> => {
    const response = await fetch(`${PORTFOLIO_BASE}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message, history }),
    });
    if (!response.ok) {
      throw new Error(`API error: ${response.status} ${response.statusText}`);
    }
    return response.json();
  },
};
