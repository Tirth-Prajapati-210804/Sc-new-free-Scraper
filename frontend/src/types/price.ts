export interface DailyPrice {
  id: string;
  origin: string;
  destination: string;
  depart_date: string; // "2026-04-15"
  airline: string;
  price: number;
  currency: string;
  provider: string;
  stops: number | null;
  stop_label?: string | null;
  duration_minutes: number | null;
  scraped_at: string;
}

export interface PriceTrend {
  date: string; // mapped from depart_date
  price: number;
  airline: string;
}

export interface CollectionRun {
  id: string;
  started_at: string;
  finished_at: string | null;
  status: "running" | "completed" | "failed" | "stopped";
  routes_total: number;
  routes_success: number;
  routes_failed: number;
  dates_scraped: number;
  errors: string[] | null;
}

export interface ScrapeLogEntry {
  id: string;
  origin: string;
  destination: string;
  depart_date: string;
  provider: string;
  status: "success" | "error" | "no_results" | "rate_limited" | "quota_exhausted" | "auth_error";
  offers_found: number;
  cheapest_price: number | null;
  error_message: string | null;
  duration_ms: number | null;
  created_at: string;
}
