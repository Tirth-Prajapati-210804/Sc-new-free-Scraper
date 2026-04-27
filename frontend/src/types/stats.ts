export interface OverviewStats {
  active_route_groups: number;
  total_prices_collected: number;
  total_origins: number;
  total_destinations: number;
  last_collection_at: string | null;
  last_collection_status: string | null;
  provider_stats: Record<string, ProviderStat>;
}

export interface ProviderStat {
  configured: boolean;
  last_success?: string;
  success_rate?: number;
}

export interface HealthResponse {
  status: string;
  environment: string;
  database_status: string;
  scheduler_running: boolean;
  provider_status: Record<string, string>;
  demo_mode: boolean;
}
