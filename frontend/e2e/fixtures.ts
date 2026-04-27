import type { Page, Route } from "@playwright/test";

// ── Canonical mock data ──────────────────────────────────────────────────────

export const MOCK_TOKEN = "test-jwt-token";

export const MOCK_USER = {
  id: "00000000-0000-0000-0000-000000000001",
  email: "admin@example.com",
  full_name: "Test Admin",
  role: "admin",
  is_active: true,
};

export const MOCK_GROUP = {
  id: "00000000-0000-0000-0000-000000000002",
  name: "Canada → Vietnam",
  destination_label: "Vietnam",
  destinations: ["SGN", "HAN"],
  origins: ["YVR", "YYZ"],
  nights: 10,
  days_ahead: 90,
  sheet_name_map: { YVR: "YVR", YYZ: "YYZ" },
  special_sheets: [],
  is_active: true,
  currency: "USD",
  max_stops: null,
  start_date: null,
  end_date: null,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

export const MOCK_PROGRESS = {
  route_group_id: MOCK_GROUP.id,
  name: MOCK_GROUP.name,
  total_dates: 360,
  dates_with_data: 180,
  coverage_percent: 50.0,
  last_scraped_at: "2026-04-18T10:00:00Z",
  per_origin: {
    YVR: { total: 180, collected: 90 },
    YYZ: { total: 180, collected: 90 },
  },
  scraped_dates: [],
};

export const MOCK_STATS = {
  active_route_groups: 1,
  total_prices_collected: 12345,
  total_origins: 2,
  last_collection_at: "2026-04-18T10:00:00Z",
};

export const MOCK_HEALTH = {
  status: "ok",
  demo_mode: false,
  provider_status: { serpapi: "configured" },
};

// ── Route helpers ────────────────────────────────────────────────────────────

function json(route: Route, body: unknown, status = 200) {
  return route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
}

/** Mock all auth and base-data endpoints so every page can load. */
export async function mockBaseRoutes(page: Page) {
  await page.route("**/api/v1/auth/login", (r) =>
    json(r, { access_token: MOCK_TOKEN, token_type: "bearer", expires_in: 3600, user: MOCK_USER }),
  );
  await page.route("**/api/v1/auth/me", (r) => json(r, MOCK_USER));
  await page.route("**/api/v1/stats/overview", (r) => json(r, MOCK_STATS));
  await page.route("**/health", (r) => json(r, MOCK_HEALTH));
  await page.route("**/api/v1/collection/status", (r) =>
    json(r, { is_collecting: false, scheduler_running: true }),
  );
  await page.route("**/api/v1/collection/runs*", (r) => json(r, []));
  await page.route("**/api/v1/route-groups/", (r) => json(r, [MOCK_GROUP]));
  await page.route(`**/api/v1/route-groups/${MOCK_GROUP.id}`, (r) => json(r, MOCK_GROUP));
  await page.route(`**/api/v1/route-groups/${MOCK_GROUP.id}/progress`, (r) =>
    json(r, MOCK_PROGRESS),
  );
}

/** Log in via the UI and land on the dashboard. */
export async function loginViaUI(page: Page) {
  await page.goto("/login");
  await page.getByLabel("Email").fill("admin@example.com");
  await page.getByLabel("Password").fill("StrongPass123!");
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.waitForURL("/");
  await page.waitForLoadState("networkidle");
}
