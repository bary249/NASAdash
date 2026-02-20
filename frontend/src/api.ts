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

function getAuthHeaders(): Record<string, string> {
  try {
    const stored = localStorage.getItem('ownerDashAuth');
    if (stored) {
      const { token } = JSON.parse(stored);
      if (token) return { Authorization: `Bearer ${token}` };
    }
  } catch { /* no auth */ }
  return {};
}

// ── Concurrency limiter ──
// Railway runs a single uvicorn worker with sync SQLite queries.
// Firing 20+ requests at once blocks the event loop and causes 504s.
// Limit to 6 concurrent fetches; the rest queue automatically.
const MAX_CONCURRENT = 6;
let _activeRequests = 0;
const _requestQueue: Array<() => void> = [];

function acquireSlot(): Promise<void> {
  if (_activeRequests < MAX_CONCURRENT) {
    _activeRequests++;
    return Promise.resolve();
  }
  return new Promise<void>(resolve => _requestQueue.push(resolve));
}

function releaseSlot() {
  if (_requestQueue.length > 0) {
    const next = _requestQueue.shift()!;
    next(); // hand the slot to next queued request
  } else {
    _activeRequests--;
  }
}

// ── In-memory response cache ──
// Prevents redundant fetches when switching properties back and forth
// and deduplicates in-flight requests from parallel component mounts.
const CACHE_TTL_MS = 5 * 60 * 1000; // 5 minutes
const responseCache = new Map<string, { data: unknown; ts: number }>();
const inflightRequests = new Map<string, Promise<unknown>>();

function getCached<T>(url: string): T | undefined {
  const entry = responseCache.get(url);
  if (entry && Date.now() - entry.ts < CACHE_TTL_MS) return entry.data as T;
  if (entry) responseCache.delete(url);
  return undefined;
}

function invalidateCache(urlPrefix: string) {
  for (const key of responseCache.keys()) {
    if (key.includes(urlPrefix)) responseCache.delete(key);
  }
}

async function fetchJson<T>(url: string, retries = 2): Promise<T> {
  // 1. Return from cache if fresh
  const cached = getCached<T>(url);
  if (cached !== undefined) return cached;

  // 2. Deduplicate in-flight requests to the same URL
  const inflight = inflightRequests.get(url);
  if (inflight) return inflight as Promise<T>;

  const request = (async (): Promise<T> => {
    await acquireSlot();
    try {
      for (let attempt = 0; attempt <= retries; attempt++) {
        try {
          const response = await fetch(url, { headers: getAuthHeaders() });
          if (response.status === 401) {
            localStorage.removeItem('ownerDashAuth');
            window.location.reload();
            throw new Error('Session expired');
          }
          if (response.ok) {
            const data: T = await response.json();
            responseCache.set(url, { data, ts: Date.now() });
            return data;
          }
          // Retry on 500/502/503/504 (cold start / transient errors)
          if (attempt < retries && response.status >= 500) {
            await new Promise(r => setTimeout(r, 1000 * (attempt + 1)));
            continue;
          }
          throw new Error(`API error: ${response.status} ${response.statusText}`);
        } catch (err) {
          // Retry on network errors (fetch failure / timeout)
          if (attempt < retries && err instanceof TypeError) {
            await new Promise(r => setTimeout(r, 1000 * (attempt + 1)));
            continue;
          }
          throw err;
        }
      }
      throw new Error('Request failed after retries');
    } finally {
      releaseSlot();
    }
  })();

  inflightRequests.set(url, request);
  try {
    return await request;
  } finally {
    inflightRequests.delete(url);
  }
}

export const api = {
  getProperties: (): Promise<PropertyInfo[]> =>
    fetchJson(`${API_BASE}/properties`),

  getOccupancy: (propertyId: string, timeframe: Timeframe = 'cm'): Promise<OccupancyMetrics> =>
    fetchJson(`${API_BASE}/properties/${propertyId}/occupancy?timeframe=${timeframe}`),

  getExposure: (propertyId: string, timeframe: Timeframe = 'cm'): Promise<ExposureMetrics> =>
    fetchJson(`${API_BASE}/properties/${propertyId}/exposure?timeframe=${timeframe}`),

  getLeasingFunnel: (propertyId: string, timeframe: Timeframe = 'cm', startDate?: string, endDate?: string): Promise<LeasingFunnelMetrics> => {
    let url = `${API_BASE}/properties/${propertyId}/leasing-funnel?timeframe=${timeframe}`;
    if (startDate && endDate) url += `&start_date=${startDate}&end_date=${endDate}`;
    return fetchJson(url);
  },

  getExpirations: (propertyId: string): Promise<{ periods: { label: string; expirations: number; renewals: number; signed: number; submitted: number; selected: number; renewal_pct: number; vacating?: number; unknown?: number; mtm?: number; moved_out?: number }[] }> =>
    fetchJson(`${API_BASE}/properties/${propertyId}/expirations`),

  getExpirationDetails: (propertyId: string, days: number = 90, filter?: 'renewed' | 'expiring' | 'vacating' | 'pending' | 'mtm' | 'moved_out', month?: string): Promise<{ leases: { unit: string; lease_end: string; market_rent: number; status: string; floorplan: string; sqft: number; move_in: string; lease_start: string }[]; count: number }> => {
    const params = new URLSearchParams({ days: String(days) });
    if (filter) params.set('filter', filter);
    if (month) params.set('month', month);
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
      propertyClass?: string;
      maxDistance?: number;
      subjectLat?: number;
      subjectLon?: number;
      amenities?: string[];
    }
  ): Promise<MarketCompsResponse> => {
    const params = new URLSearchParams({ submarket, limit: String(limit) });
    if (subjectProperty) params.set('subject_property', subjectProperty);
    if (filters?.minUnits) params.set('min_units', String(filters.minUnits));
    if (filters?.maxUnits) params.set('max_units', String(filters.maxUnits));
    if (filters?.minYearBuilt) params.set('min_year_built', String(filters.minYearBuilt));
    if (filters?.maxYearBuilt) params.set('max_year_built', String(filters.maxYearBuilt));
    if (filters?.propertyClass) params.set('property_class', filters.propertyClass);
    if (filters?.maxDistance) params.set('max_distance', String(filters.maxDistance));
    if (filters?.subjectLat) params.set('subject_lat', String(filters.subjectLat));
    if (filters?.subjectLon) params.set('subject_lon', String(filters.subjectLon));
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

  getAvailabilityUnits: (propertyId: string, floorplan?: string, status?: string, bucket?: string): Promise<{
    units: { unit: string; floorplan: string; status: string; sqft: number; market_rent: number; actual_rent: number; lease_start: string; lease_end: string; move_in: string; move_out: string }[];
    count: number;
  }> => {
    const params = new URLSearchParams();
    if (floorplan) params.set('floorplan', floorplan);
    if (status) params.set('status', status);
    if (bucket) params.set('bucket', bucket);
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
    prior_month?: { atr: number; atr_pct: number; snapshot_date: string } | null;
  }> => fetchJson(`${API_BASE}/properties/${propertyId}/availability`),

  getUnitStatusBreakdown: (propertyId: string): Promise<{
    property_id: string;
    total_units: number;
    statuses: { label: string; count: number; pct: number }[];
    subtotals: {
      vacant: { label: string; count: number; pct: number; breakdown: string };
      ready: { label: string; count: number; pct: number; description: string };
      notice: { label: string; count: number; pct: number; breakdown: string };
      atr: { label: string; count: number; pct: number; formula: string };
    };
  }> => fetchJson(`${API_BASE}/properties/${propertyId}/unit-status-breakdown`),

  getOccupancySnapshots: (propertyId: string): Promise<{
    property_id: string;
    snapshots: { date: string; total_units: number; occupied: number; vacant: number; occupancy_pct: number; leased_pct: number; on_notice: number; preleased: number }[];
  }> => fetchJson(`${API_BASE}/properties/${propertyId}/occupancy-snapshots`),

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

  getConsolidatedByBedroom: (propertyId: string, groupBy: 'bedroom' | 'floorplan' = 'bedroom'): Promise<{
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
  }> => fetchJson(`${API_BASE}/properties/${propertyId}/consolidated-by-bedroom?group_by=${groupBy}`),

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

  getApartmentsReviews: (propertyId: string): Promise<{
    rating: number | null; review_count: number;
    reviews: { review_id: string; author: string; rating: number; text: string; time_desc: string; has_response: boolean; response_text: string | null; response_date: string | null }[];
    star_distribution: Record<string, number>;
    reviews_fetched: number; responded: number; not_responded: number;
    needs_response: number; response_rate: number;
    source: string; url: string;
    error?: string;
  }> => fetchJson(`${API_BASE}/properties/${propertyId}/apartments-reviews`),

  getPropertyImage: (propertyId: string): Promise<{
    property_id: string; image_url: string | null; source: string;
  }> => fetchJson(`${API_BASE}/properties/${propertyId}/image`),

  getAIInsights: (propertyId: string): Promise<{
    alerts: { severity: string; title: string; fact: string; risk: string; action: string }[];
    qna: { question: string; answer: string }[];
    error?: string;
  }> => fetchJson(`${API_BASE}/properties/${propertyId}/ai-insights`),

  refreshAIInsights: (propertyId: string): Promise<{
    alerts: { severity: string; title: string; fact: string; risk: string; action: string }[];
    qna: { question: string; answer: string }[];
    error?: string;
  }> => {
    // Bust the client-side fetchJson cache for this property's AI insights
    invalidateCache(`/properties/${propertyId}/ai-insights`);
    return fetchJson(`${API_BASE}/properties/${propertyId}/ai-insights?refresh=1`);
  },

  // Financials (Monthly Transaction Summary)
  getFinancials: (propertyId: string): Promise<{
    property_id: string;
    summary: {
      fiscal_period: string; report_date: string;
      gross_market_rent: number; gain_to_lease: number; loss_to_lease: number;
      gross_potential: number; total_other_charges: number;
      total_possible_collections: number; total_collection_losses: number;
      total_adjustments: number;
      past_due_end_prior: number; prepaid_end_prior: number;
      past_due_end_current: number; prepaid_end_current: number;
      net_change_past_due_prepaid: number; total_losses_and_adjustments: number;
      current_monthly_collections: number; total_monthly_collections: number;
      collection_rate: number;
    };
    charges: { group: string; group_name: string; code: string; description: string; ytd_last_month: number; this_month: number; ytd_through: number }[];
    losses: { group: string; group_name: string; code: string; description: string; ytd_last_month: number; this_month: number; ytd_through: number }[];
    payments: { group: string; group_name: string; code: string; description: string; ytd_last_month: number; this_month: number; ytd_through: number }[];
  }> => fetchJson(`${API_BASE}/properties/${propertyId}/financials`),

  // Marketing (Primary Advertising Source)
  getMarketing: (propertyId: string, timeframe: string = 'ytd'): Promise<{
    property_id: string;
    date_range: string;
    timeframe: string;
    sources: { source: string; new_prospects: number; phone_calls: number; visits: number; return_visits: number; leases: number; net_leases: number; cancelled_denied: number; prospect_to_lease_pct: number; visit_to_lease_pct: number }[];
    totals: { total_prospects: number; total_calls: number; total_visits: number; total_leases: number; total_net_leases: number; overall_prospect_to_lease: number; overall_visit_to_lease: number };
  }> => fetchJson(`${API_BASE}/properties/${propertyId}/marketing?timeframe=${timeframe}`),

  // Maintenance / Make Ready
  getMaintenance: (propertyId: string): Promise<{
    property_id: string;
    pipeline: { unit: string; sqft: number; days_vacant: number; date_vacated: string; date_due: string; num_work_orders: number; unit_status: string; lease_status: string }[];
    completed: { unit: string; num_work_orders: number; date_closed: string; amount_charged: number }[];
    summary: { units_in_pipeline: number; avg_days_vacant: number; overdue_count: number; completed_this_period: number };
  }> => fetchJson(`${API_BASE}/properties/${propertyId}/maintenance`),

  // Make Ready Status (not-ready vs ready units with pipeline data)
  getMakeReadyStatus: (propertyId: string): Promise<{
    property_id: string;
    not_ready: { unit: string; floorplan: string; sqft: number; market_rent: number; days_vacant: number; date_vacated: string; date_due: string; days_until_ready: number | null; work_orders: number; in_pipeline: boolean; lost_rent: number; status: string }[];
    ready: { unit: string; floorplan: string; sqft: number; market_rent: number; days_vacant: number; date_vacated: string; date_due: string; days_until_ready: number | null; work_orders: number; in_pipeline: boolean; lost_rent: number; made_ready_date: string }[];
    summary: { total_vacant_unrented: number; ready_count: number; not_ready_count: number; in_progress: number; overdue: number; not_started: number; total_lost_rent: number };
  }> => fetchJson(`${API_BASE}/properties/${propertyId}/make-ready-status`),

  // Lost Rent Summary (unit-level loss-to-lease)
  getLostRent: (propertyId: string): Promise<{
    property_id: string;
    units: { unit: string; market_rent: number; lease_rent: number; rent_charged: number; lost_rent: number; loss_pct: number; move_out_date: string }[];
    summary: { fiscal_period: string; total_units: number; occupied_count: number; vacant_count: number; avg_market_rent: number; avg_lease_rent: number; total_lost_rent: number; loss_to_lease_pct: number; avg_loss_per_unit: number };
  }> => fetchJson(`${API_BASE}/properties/${propertyId}/lost-rent`),

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

  // Watchpoints (Portfolio-level metric thresholds)
  getWatchpoints: (ownerGroup?: string): Promise<{
    owner_group: string;
    watchpoints: { id: string; metric: string; operator: string; threshold: number; label: string; enabled: boolean; created_at: string; status: string; current_value: number | null }[];
    available_metrics: Record<string, { label: string; unit: string; direction: string }>;
    current_metrics: Record<string, number>;
  }> => fetchJson(`${PORTFOLIO_BASE}/watchpoints${ownerGroup ? '?owner_group=' + ownerGroup : ''}`),

  createWatchpoint: async (body: { metric: string; operator: string; threshold: number; label?: string }, ownerGroup?: string): Promise<{ id: string; metric: string; operator: string; threshold: number; label: string; enabled: boolean }> => {
    const response = await fetch(`${PORTFOLIO_BASE}/watchpoints${ownerGroup ? '?owner_group=' + ownerGroup : ''}`, {
      method: 'POST', headers: { 'Content-Type': 'application/json', ...getAuthHeaders() }, body: JSON.stringify(body),
    });
    if (!response.ok) throw new Error(`API error: ${response.status}`);
    invalidateCache('/watchpoints');
    return response.json();
  },

  deleteWatchpoint: async (watchpointId: string, ownerGroup?: string): Promise<{ deleted: boolean }> => {
    const response = await fetch(`${PORTFOLIO_BASE}/watchpoints/${watchpointId}${ownerGroup ? '?owner_group=' + ownerGroup : ''}`, { method: 'DELETE', headers: getAuthHeaders() });
    if (!response.ok) throw new Error(`API error: ${response.status}`);
    invalidateCache('/watchpoints');
    return response.json();
  },

  // AI Chat
  getChatStatus: (): Promise<{ available: boolean; message: string }> =>
    fetchJson(`${API_BASE}/chat/status`),

  sendChatMessage: async (propertyId: string, message: string, history: { role: string; content: string }[] = []): Promise<{ response: string; columns?: Array<{key: string; label: string}>; data?: Array<Record<string, unknown>>; actions?: Array<{label: string}> }> => {
    const response = await fetch(`${API_BASE}/properties/${propertyId}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
      body: JSON.stringify({ message, history }),
    });
    if (!response.ok) {
      throw new Error(`API error: ${response.status} ${response.statusText}`);
    }
    return response.json();
  },

  // Income Statement (Report 3836 — Revenue P&L by GL)
  getIncomeStatement: (propertyId: string): Promise<{
    property_id: string;
    summary: {
      fiscal_period: string;
      market_rent: number; loss_to_lease: number; loss_to_lease_pct: number;
      vacancy: number; vacancy_pct: number;
      concessions: number; concessions_pct: number;
      bad_debt: number; admin_down_units: number; employee_units: number;
      other_income: number;
      total_potential_income: number; total_income: number; effective_rent_pct: number;
    };
    totals: Record<string, number>;
    sections: Record<string, { gl_code: string; name: string; sign: string; amount: number; category: string }[]>;
  }> => fetchJson(`${API_BASE}/properties/${propertyId}/income-statement`),

  getMoveOutReasons: (propertyId: string): Promise<{
    property_id: string;
    date_range: string;
    former: { category: string; count: number; pct: number; reasons: { reason: string; count: number; pct: number }[] }[];
    notice: { category: string; count: number; pct: number; reasons: { reason: string; count: number; pct: number }[] }[];
    totals: { former: number; notice: number; total: number };
  }> => fetchJson(`${API_BASE}/properties/${propertyId}/move-out-reasons`),

  // Portfolio-level AI Chat (Asset Manager perspective)
  sendPortfolioChatMessage: async (message: string, history: { role: string; content: string }[] = []): Promise<{ response: string; columns?: Array<{key: string; label: string}>; data?: Array<Record<string, unknown>>; actions?: Array<{label: string}> }> => {
    const response = await fetch(`${PORTFOLIO_BASE}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
      body: JSON.stringify({ message, history }),
    });
    if (!response.ok) {
      throw new Error(`API error: ${response.status} ${response.statusText}`);
    }
    return response.json();
  },
};
