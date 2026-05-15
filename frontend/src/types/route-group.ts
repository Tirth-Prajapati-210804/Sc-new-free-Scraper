export type TripType = "one_way" | "round_trip" | "multi_city";
export type RouteMarket = "us" | "ca";

export interface RouteGroup {
  id: string;
  name: string;
  destination_label: string;
  destinations: string[];
  origins: string[];
  nights: number;
  days_ahead: number;
  trip_type: TripType;
  sheet_name_map: Record<string, string>;
  special_sheets: SpecialSheet[];
  is_active: boolean;
  market: RouteMarket;
  currency: string;
  max_stops: number | null;
  start_date: string | null;
  end_date: string | null;
  created_at: string;
  updated_at: string;
}

export interface SpecialSheet {
  name: string;
  origin: string;
  destination_label: string;
  destinations: string[];
  columns: number;
}

export type ScrapeHealthStatus =
  | "ok"
  | "never_scraped"
  | "rate_limited"
  | "quota_exhausted"
  | "auth_error"
  | "parse_error"
  | "provider_error"
  | "stopped";

export interface ScrapeHealth {
  status: ScrapeHealthStatus;
  last_attempt_at: string | null;
  last_success_at: string | null;
  last_error_message: string | null;
  errors_last_hour: number;
  successes_last_hour: number;
}

export interface RouteGroupProgress {
  route_group_id: string;
  name: string;
  total_dates: number;
  dates_with_data: number;
  coverage_percent: number;
  last_scraped_at: string | null;
  per_origin: Record<string, { total: number; collected: number }>;
  scraped_dates: string[];
  health: ScrapeHealth;
}
