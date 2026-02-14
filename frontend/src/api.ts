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

  getExpirations: (propertyId: string): Promise<{ periods: { label: string; expirations: number; renewals: number; signed: number; submitted: number; selected: number; renewal_pct: number; vacating?: number; unknown?: number; mtm?: number; moved_out?: number }[] }> =>
    fetchJson(`${API_BASE}/properties/${propertyId}/expirations`),

  getExpirationDetails: (propertyId: string, days: number = 90, filter?: 'renewed' | 'expiring' | 'vacating' | 'pending' | 'mtm' | 'moved_out'): Promise<{ leases: { unit: string; lease_end: string; market_rent: number; status: string; floorplan: string; sqft: number; move_in: string; lease_start: string }[]; count: number }> => {
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

  getPortfolioProperties: (ownerGroup?: string): Promise<{ id: string; name: string; pms_type: string; owner_group: string }[]> => {
    const params = new URLSearchParams();
    if (ownerGroup) params.set('owner_group', ownerGroup);
    const query = params.toString();
    return fetchJson(`${PORTFOLIO_BASE}/properties${query ? `?${query}` : ''}`);
  },

  getOwnerGroups: (): Promise<string[]> =>
    fetchJson(`${PORTFOLIO_BASE}/owner-groups`),

  // Amenities
  getAmenities: (propertyId: string, itemType?: string): Promise<AmenityItem[]> => {
    const params = new URLSearchParams();
    if (itemType) params.set('item_type', itemType);
    const query = params.toString();
    return fetchJson(`${API_BASE}/properties/${propertyId}/amenities${query ? `?${query}` : ''}`);
  },

  getAmenitiesSummary: (propertyId: string): Promise<AmenitiesSummary> =>
    fetchJson(`${API_BASE}/properties/${propertyId}/amenities/summary`),

  // Customer KPIs (Feb 2026)
  getAvailabilityByFloorplan: (propertyId: string): Promise<{
    floorplans: { floorplan: string; group: string; total_units: number; vacant_units: number; vacant_not_leased: number; vacant_leased: number; occupied_units: number; on_notice: number; model_units: number; down_units: number; avg_market_rent: number; occupancy_pct: number; leased_pct: number }[];
    totals: { total: number; vacant: number; notice: number; vacant_leased: number; vacant_not_leased: number; occupied: number; model: number; down: number };
  }> => fetchJson(`${API_BASE}/properties/${propertyId}/availability-by-floorplan`),

  getAvailabilityUnits: (propertyId: string, floorplan?: string, status?: string): Promise<{
    units: { unit: string; floorplan: string; status: string; sqft: number; market_rent: number; actual_rent: number; lease_start: string; lease_end: string; move_in: string; move_out: string }[];
    count: number;
  }> => {
    const params = new URLSearchParams();
    if (floorplan) params.set('floorplan', floorplan);
    if (status) params.set('status', status);
    const q = params.toString();
    return fetchJson(`${API_BASE}/properties/${propertyId}/availability-by-floorplan/units${q ? `?${q}` : ''}`);
  },

  getShows: (propertyId: string, days = 7): Promise<{
    total_shows: number; days: number;
    by_date: { date: string; count: number }[];
    by_type: Record<string, number>;
    details: { date: string; type: string; unit: string | null; floorplan: string | null }[];
  }> => fetchJson(`${API_BASE}/properties/${propertyId}/shows?days=${days}`),

  getTradeouts: (propertyId: string, days?: number): Promise<{
    tradeouts: { unit_id: string; unit_type: string; prior_rent: number; new_rent: number; dollar_change: number; pct_change: number; move_in_date: string }[];
    summary: { count: number; avg_prior_rent: number; avg_new_rent: number; avg_dollar_change: number; avg_pct_change: number };
  }> => {
    const url = days ? `${API_BASE}/properties/${propertyId}/tradeouts?days=${days}` : `${API_BASE}/properties/${propertyId}/tradeouts`;
    return fetchJson(url);
  },

  getRenewals: (propertyId: string, days?: number, month?: string): Promise<{
    renewals: { unit_id: string; renewal_rent: number; prior_rent: number; vs_prior: number; vs_prior_pct: number; lease_start: string; lease_term: string; floorplan: string }[];
    summary: { count: number; avg_renewal_rent: number; avg_prior_rent: number; avg_vs_prior: number; avg_vs_prior_pct: number };
  }> => {
    const params = new URLSearchParams();
    if (days) params.set('days', String(days));
    if (month) params.set('month', month);
    const qs = params.toString();
    return fetchJson(`${API_BASE}/properties/${propertyId}/renewals${qs ? `?${qs}` : ''}`);
  },

  getAvailability: (propertyId: string): Promise<{
    property_id: string; total_units: number; occupied: number; vacant: number;
    on_notice: number; preleased: number; atr: number; atr_pct: number; availability_pct: number;
    buckets: { available_0_30: number; available_30_60: number; total: number };
    trend: { direction: string; weeks: { week_ending: string; atr: number; atr_pct: number; occupancy_pct: number; move_ins: number; move_outs: number }[] };
  }> => fetchJson(`${API_BASE}/properties/${propertyId}/availability`),

  getOccupancyForecast: (propertyId: string, weeks = 12): Promise<{
    forecast: { week: number; week_start: string; week_end: string; projected_occupied: number; projected_occupancy_pct: number; scheduled_move_ins: number; notice_move_outs: number; lease_expirations: number; net_change: number }[];
    current_occupied: number; total_units: number; current_notice: number;
    vacant_leased: number; undated_move_ins: number;
    notice_units: { unit: string; date: string; floorplan: string; rent: number; type: string }[];
    move_in_units: { unit: string; date: string | null; floorplan: string; rent: number; type: string }[];
    expiration_units: { unit: string; date: string; floorplan: string; rent: number; type: string }[];
  }> => fetchJson(`${API_BASE}/properties/${propertyId}/occupancy-forecast?weeks=${weeks}`),

  getLossToLease: (propertyId: string): Promise<{
    property_id: string; avg_market_rent: number; avg_actual_rent: number;
    loss_per_unit: number; total_loss_to_lease: number; loss_to_lease_pct: number;
    occupied_units: number; total_units: number; data_available: boolean;
  }> => fetchJson(`${API_BASE}/properties/${propertyId}/loss-to-lease`),

  getConsolidatedByBedroom: (propertyId: string): Promise<{
    bedrooms: {
      bedroom_type: string; bedrooms: number; floorplan_count: number; floorplans: string[];
      total_units: number; occupied: number; vacant: number; vacant_leased: number; vacant_not_leased: number; on_notice: number;
      occupancy_pct: number; avg_market_rent: number; avg_in_place_rent: number; rent_delta: number;
      expiring_90d: number; renewed_90d: number; renewal_pct_90d: number | null;
    }[];
    totals: {
      total_units: number; occupied: number; vacant: number; vacant_leased: number; on_notice: number;
      occupancy_pct: number; expiring_90d: number; renewed_90d: number; renewal_pct_90d: number | null;
    };
  }> => fetchJson(`${API_BASE}/properties/${propertyId}/consolidated-by-bedroom`),

  getReputation: (propertyId: string): Promise<{
    property_id: string; overall_rating: number;
    sources: { source: string; name: string; rating: number | null; review_count: number; url: string; star_distribution: Record<string, number> | null }[];
    review_power: { response_rate: number; avg_response_hours: number | null; avg_response_label: string | null; needs_attention: number; responded: number; not_responded: number; total_reviews: number };
  }> => fetchJson(`${API_BASE}/properties/${propertyId}/reputation`),

  getReviews: (propertyId: string): Promise<{
    rating: number; review_count: number; place_id: string; google_maps_url: string;
    reviews: { author: string; author_photo: string; author_url: string; rating: number; text: string; time_desc: string; publish_time: string; google_maps_uri: string; has_response?: boolean; response_text?: string | null; response_date?: string | null; response_time?: string | null }[];
    star_distribution: Record<string, number>;
    needs_response: number; reviews_fetched: number; responded?: number; not_responded?: number;
    response_rate?: number; avg_response_hours?: number | null; avg_response_label?: string | null;
    source?: string; error?: string;
  }> => fetchJson(`${API_BASE}/properties/${propertyId}/reviews`),

  getAIInsights: (propertyId: string): Promise<{
    alerts: { severity: string; title: string; fact: string; risk: string; action: string }[];
    qna: { question: string; answer: string }[];
    error?: string;
  }> => fetchJson(`${API_BASE}/properties/${propertyId}/ai-insights`),

  // Risk Scores (Churn & Delinquency Prediction)
  getRiskScores: (propertyId: string): Promise<{
    property_id: string;
    snapshot_date: string;
    total_scored: number;
    notice_count: number;
    at_risk_total: number;
    churn: { avg_score: number; median_score: number; high_risk: number; medium_risk: number; low_risk: number; threshold_high: number; threshold_low: number };
    delinquency: { avg_score: number; median_score: number; high_risk: number; medium_risk: number; low_risk: number };
    insights: { pct_scheduled_moveout: number; pct_with_app: number; avg_tenure_months: number; avg_rent: number; avg_open_tickets: number };
  }> => fetchJson(`${API_BASE}/properties/${propertyId}/risk-scores`),

  getPortfolioRiskScores: (propertyIds?: string[]): Promise<{
    properties: {
      property_id: string; property_name: string; total_scored: number;
      avg_churn_score: number; avg_delinquency_score: number;
      churn_high: number; churn_medium: number; churn_low: number;
      delinq_high: number; delinq_medium: number; delinq_low: number;
      avg_tenure_months: number; avg_rent: number; avg_open_tickets: number;
      snapshot_date: string;
    }[];
    summary: { total_properties: number; total_scored: number; avg_churn_score: number; avg_delinquency_score: number; total_churn_high_risk: number; total_delinq_high_risk: number } | null;
  }> => {
    const params = new URLSearchParams();
    if (propertyIds && propertyIds.length > 0) params.set('property_ids', propertyIds.join(','));
    const q = params.toString();
    return fetchJson(`${PORTFOLIO_BASE}/risk-scores${q ? `?${q}` : ''}`);
  },

  // Watch List
  getWatchlist: (params?: { owner_group?: string; occ_threshold?: number; delinq_threshold?: number; renewal_threshold?: number; review_threshold?: number }): Promise<{
    total_properties: number; flagged_count: number;
    thresholds: { occupancy_pct: number; delinquent_total: number; renewal_rate_90d: number; google_rating: number };
    watchlist: {
      id: string; name: string; owner_group: string; total_units: number;
      occupancy_pct: number; vacant: number; on_notice: number; preleased: number;
      delinquent_total: number; delinquent_units: number;
      renewal_rate_90d: number | null; google_rating: number | null;
      churn_score: number | null; at_risk_residents: number;
      flags: { metric: string; label: string; severity: string; value: number; threshold: number }[];
      flag_count: number;
    }[];
  }> => {
    const qs = new URLSearchParams();
    if (params?.owner_group) qs.set('owner_group', params.owner_group);
    if (params?.occ_threshold != null) qs.set('occ_threshold', String(params.occ_threshold));
    if (params?.delinq_threshold != null) qs.set('delinq_threshold', String(params.delinq_threshold));
    if (params?.renewal_threshold != null) qs.set('renewal_threshold', String(params.renewal_threshold));
    if (params?.review_threshold != null) qs.set('review_threshold', String(params.review_threshold));
    const q = qs.toString();
    return fetchJson(`${PORTFOLIO_BASE}/watchlist${q ? '?' + q : ''}`);
  },

  // Watchpoints (Custom AI Metrics)
  getWatchpoints: (propertyId: string): Promise<{
    property_id: string;
    watchpoints: { id: string; metric: string; operator: string; threshold: number; label: string; enabled: boolean; created_at: string; status: string; current_value: number | null }[];
    available_metrics: Record<string, { label: string; unit: string; direction: string }>;
    current_metrics: Record<string, number>;
  }> => fetchJson(`${API_BASE}/properties/${propertyId}/watchpoints`),

  createWatchpoint: async (propertyId: string, body: { metric: string; operator: string; threshold: number; label?: string }): Promise<{ id: string; metric: string; operator: string; threshold: number; label: string; enabled: boolean }> => {
    const response = await fetch(`${API_BASE}/properties/${propertyId}/watchpoints`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
    });
    if (!response.ok) throw new Error(`API error: ${response.status}`);
    return response.json();
  },

  deleteWatchpoint: async (propertyId: string, watchpointId: string): Promise<{ deleted: boolean }> => {
    const response = await fetch(`${API_BASE}/properties/${propertyId}/watchpoints/${watchpointId}`, { method: 'DELETE' });
    if (!response.ok) throw new Error(`API error: ${response.status}`);
    return response.json();
  },

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
