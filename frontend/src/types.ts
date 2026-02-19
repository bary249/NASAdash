/**
 * Types for Owner Dashboard V2
 * Per spec: Owners Dashboard Specification
 */

export type Timeframe = 'cm' | 'pm' | 'ytd' | 'l30' | 'l7';

export interface PropertyInfo {
  id: string;
  name: string;
  city?: string;
  state?: string;
  address?: string;
  floor_count?: number;
  google_rating?: number;
  google_review_count?: number;
}

export interface OccupancyMetrics {
  property_id: string;
  property_name: string;
  timeframe: string;
  period_start: string;
  period_end: string;
  total_units: number;
  occupied_units: number;
  vacant_units: number;
  leased_units: number;
  preleased_vacant: number;
  physical_occupancy: number;
  leased_percentage: number;
  vacant_ready: number;
  vacant_not_ready: number;
  available_units: number;
  aged_vacancy_90_plus: number;
}

export interface ExposureMetrics {
  property_id: string;
  timeframe: string;
  period_start: string;
  period_end: string;
  exposure_30_days: number;
  exposure_60_days: number;
  notices_total: number;
  notices_30_days: number;
  notices_60_days: number;
  pending_moveins_30_days: number;
  pending_moveins_60_days: number;
  move_ins: number;
  move_outs: number;
  net_absorption: number;
}

export interface LeasingFunnelMetrics {
  property_id: string;
  timeframe: string;
  period_start: string;
  period_end: string;
  leads: number;
  tours: number;
  applications: number;
  lease_signs: number;
  denials: number;
  sight_unseen: number;
  tour_to_app: number;
  lead_to_tour_rate: number;
  tour_to_app_rate: number;
  app_to_lease_rate: number;
  lead_to_lease_rate: number;
  marketing_net_leases?: number;
}

export interface OccupancyTrendPeriod {
  start_date: string;
  end_date: string;
  days: number;
  occupied_units: number;
  total_units: number;
  physical_occupancy: number;
}

export interface OccupancyTrend {
  property_id: string;
  current_period: OccupancyTrendPeriod;
  previous_period: OccupancyTrendPeriod;
  change: {
    occupancy_points: number;
    direction: 'up' | 'down' | 'flat';
  };
  methodology: string;
}

// Comprehensive trends for all metrics
export interface AllTrends {
  property_id: string;
  period_days: number;
  current_period: {
    start_date: string;
    end_date: string;
  };
  prior_period: {
    start_date: string;
    end_date: string;
  };
  occupancy: {
    current: {
      occupied_units: number;
      vacant_units: number;
      total_units: number;
      physical_occupancy: number;
      leased_percentage: number;
    };
    prior: {
      occupied_units: number;
      vacant_units: number;
      total_units: number;
      physical_occupancy: number;
      leased_percentage: number;
    };
  };
  exposure: {
    current: {
      move_ins: number;
      move_outs: number;
      net_absorption: number;
    };
    prior: {
      move_ins: number;
      move_outs: number;
      net_absorption: number;
    };
  };
  funnel: {
    current: {
      leads: number;
      tours: number;
      applications: number;
      lease_signs: number;
      lead_to_tour_rate: number;
      tour_to_app_rate: number;
      lead_to_lease_rate: number;
    };
    prior: {
      leads: number;
      tours: number;
      applications: number;
      lease_signs: number;
      lead_to_tour_rate: number;
      tour_to_app_rate: number;
      lead_to_lease_rate: number;
    };
  };
  methodology: string;
}

export interface FloorplanPricing {
  floorplan_id: string;
  name: string;
  unit_count: number;
  bedrooms: number;
  bathrooms: number;
  square_feet: number;
  in_place_rent: number;
  in_place_rent_per_sf: number;
  asking_rent: number;
  asking_rent_per_sf: number;
  rent_growth: number;
}

export interface UnitPricingMetrics {
  property_id: string;
  property_name: string;
  floorplans: FloorplanPricing[];
  total_in_place_rent: number;
  total_in_place_per_sf: number;
  total_asking_rent: number;
  total_asking_per_sf: number;
  total_rent_growth: number;
}

export interface DashboardSummary {
  property_info: PropertyInfo;
  timeframe: string;
  occupancy: OccupancyMetrics;
  exposure: ExposureMetrics;
  leasing_funnel: LeasingFunnelMetrics;
  pricing?: UnitPricingMetrics;
}

export interface UnitRaw {
  unit_id: string;
  floorplan: string;
  unit_type: string;
  bedrooms: number;
  bathrooms: number;
  square_feet: number;
  market_rent: number;
  status: string;
  occupancy_status: string;
  ready_status?: string;
  available?: boolean;
  days_vacant?: number;
  available_date?: string;
  on_notice_date?: string;
  unit_number?: string;
}

export interface ResidentRaw {
  resident_id: string;
  first_name: string;
  last_name: string;
  unit: string;
  rent: number;
  status: string;
  move_in_date?: string;
  move_out_date?: string;
  lease_start?: string;
  lease_end?: string;
  notice_date?: string;
}

export interface ProspectRaw {
  first_name: string;
  last_name: string;
  email: string;
  phone?: string;
  desired_floorplan?: string;
  target_move_in?: string;
  last_event: string;
  event_date?: string;
  event_count: number;
}

export interface MarketComp {
  aln_id: number;
  property_name: string;
  address: string;
  city: string;
  state: string;
  num_units: number;
  year_built?: number;
  property_class?: string;  // A, B, C, D
  occupancy?: number;
  average_rent?: number;
  studio_rent?: number;
  one_bed_rent?: number;
  two_bed_rent?: number;
  three_bed_rent?: number;
  latitude?: number;
  longitude?: number;
  distance_miles?: number;
}

export interface MarketCompsResponse {
  submarket: string;
  subject_property?: string;
  comps: MarketComp[];
  avg_market_rent: number;
  avg_occupancy: number;
}

// =========================================================================
// Portfolio/Unified Types
// =========================================================================

export type AggregationMode = 'weighted_avg' | 'row_metrics';
export type PMSSource = 'yardi' | 'realpage';

export interface UnifiedOccupancy {
  property_id: string;
  property_name?: string;
  pms_source: PMSSource;
  total_units: number;
  occupied_units: number;
  vacant_units: number;
  leased_units: number;
  preleased_vacant: number;
  vacant_ready: number;
  vacant_not_ready: number;
  physical_occupancy: number;
  leased_percentage: number;
}

export interface PortfolioOccupancy {
  property_ids: string[];
  aggregation_mode: AggregationMode;
  total_units: number;
  occupied_units: number;
  vacant_units: number;
  leased_units: number;
  preleased_vacant: number;
  vacant_ready: number;
  vacant_not_ready: number;
  physical_occupancy: number;
  leased_percentage: number;
  property_breakdown?: UnifiedOccupancy[];
}

export interface PortfolioPricing {
  property_ids: string[];
  aggregation_mode: AggregationMode;
  total_in_place_rent: number;
  total_in_place_per_sf: number;
  total_asking_rent: number;
  total_asking_per_sf: number;
  total_rent_growth: number;
}

export interface PortfolioSummary {
  property_ids: string[];
  property_names: string[];
  aggregation_mode: AggregationMode;
  occupancy: PortfolioOccupancy;
  pricing?: PortfolioPricing;
  total_unit_count: number;
  total_resident_count: number;
}

export interface UnifiedUnit {
  unit_id: string;
  property_id: string;
  pms_source: PMSSource;
  unit_number: string;
  floorplan: string;
  floorplan_name?: string;
  bedrooms: number;
  bathrooms: number;
  square_feet: number;
  market_rent: number;
  status: string;
  building?: string;
}

export interface UnifiedResident {
  resident_id: string;
  property_id: string;
  pms_source: PMSSource;
  unit_id: string;
  unit_number?: string;
  first_name: string;
  last_name: string;
  current_rent: number;
  status: string;
  lease_start?: string;
  lease_end?: string;
  move_in_date?: string;
  move_out_date?: string;
  notice_date?: string;
}

export interface AmenityItem {
  rid_id: string;
  item_name: string;
  item_type: string;
  description: string;
  billing_amount: number;
  frequency: string;
  status: string;
  date_available?: string;
  unit_id?: string;
  lease_id?: string;
}

export interface AmenityTypeSummary {
  type: string;
  total: number;
  available: number;
  rented: number;
  monthly_rate: number;
  potential_revenue: number;
  actual_revenue: number;
}

export interface AmenitiesSummary {
  total_items: number;
  total_available: number;
  total_rented: number;
  monthly_potential: number;
  monthly_actual: number;
  occupancy_rate: number;
  by_type: AmenityTypeSummary[];
}
