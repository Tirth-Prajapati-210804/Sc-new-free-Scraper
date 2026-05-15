import type { Page, Route } from "@playwright/test";

export const MOCK_GROUP = {
  id: "group-1",
  name: "Canada to Vietnam",
  destination_label: "Vietnam",
  destinations: ["DAD", "HAN"],
  origins: ["YVR", "YYZ"],
  nights: 12,
  days_ahead: 180,
  trip_type: "one_way" as const,
  sheet_name_map: {
    YVR: "YVR",
    YYZ: "YYZ",
  },
  special_sheets: [],
  is_active: true,
  market: "us" as const,
  currency: "USD",
  max_stops: 1,
  start_date: "2026-06-01",
  end_date: "2026-09-30",
  created_at: "2026-04-18T10:00:00Z",
  updated_at: "2026-04-18T10:00:00Z",
};

const MOCK_GROUP_PROGRESS = {
  route_group_id: MOCK_GROUP.id,
  name: MOCK_GROUP.name,
  total_dates: 30,
  dates_with_data: 12,
  coverage_percent: 40,
  last_scraped_at: "2026-04-18T10:00:00Z",
  per_origin: {
    YVR: { total: 15, collected: 6 },
    YYZ: { total: 15, collected: 6 },
  },
  scraped_dates: ["2026-06-05", "2026-06-06"],
  health: {
    status: "ok",
    last_attempt_at: "2026-04-18T10:00:00Z",
    last_success_at: "2026-04-18T10:00:00Z",
    last_error_message: null,
    errors_last_hour: 0,
    successes_last_hour: 1,
  },
};

const MOCK_COLLECTION_STATUS = {
  is_collecting: false,
  scheduler_running: true,
};

const MOCK_STATS = {
  active_route_groups: 3,
  total_prices_collected: 1240,
  total_origins: 2,
  total_destinations: 2,
  last_collection_at: "2026-04-18T10:00:00Z",
  last_collection_status: "completed",
  provider_stats: {
    scrapingbee: {
      configured: true,
      last_success: "2026-04-18T10:00:00Z",
      success_rate: 0.95,
    },
  },
};

const MOCK_HEALTH = {
  status: "ok",
  environment: "development",
  database_status: "ok",
  scheduler_running: true,
  provider_status: {
    scrapingbee: "configured",
  },
  demo_mode: false,
};

function jsonRoute(data: unknown) {
  return async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(data),
    });
  };
}

export async function loginViaUI(page: Page) {
  await page.addInitScript(() => {
    window.sessionStorage.setItem("token", "test-token");
  });
}

export async function mockBaseRoutes(page: Page) {
  await page.route("**/health", jsonRoute(MOCK_HEALTH));
  await page.route(
    "**/api/v1/auth/me",
    jsonRoute({
      id: "user-1",
      email: "admin@example.com",
      full_name: "System Admin",
      role: "admin",
    }),
  );
  await page.route("**/api/v1/route-groups/?active_only=false", jsonRoute([MOCK_GROUP]));
  await page.route(`**/api/v1/route-groups/${MOCK_GROUP.id}`, jsonRoute(MOCK_GROUP));
  await page.route(
    `**/api/v1/route-groups/${MOCK_GROUP.id}/progress`,
    jsonRoute(MOCK_GROUP_PROGRESS),
  );
  await page.route("**/api/v1/collection/status", jsonRoute(MOCK_COLLECTION_STATUS));
  await page.route("**/api/v1/stats/overview", jsonRoute(MOCK_STATS));
  await page.route("**/api/v1/prices/trend*", jsonRoute([]));
  await page.route("**/api/v1/prices/*", jsonRoute([]));
  await page.route("**/api/v1/prices/?*", jsonRoute([]));
}
