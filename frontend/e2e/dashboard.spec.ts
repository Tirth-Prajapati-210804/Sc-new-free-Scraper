import { expect, test } from "@playwright/test";
import { loginViaUI, MOCK_GROUP, mockBaseRoutes } from "./fixtures";

test.describe("Dashboard", () => {
  test.beforeEach(async ({ page }) => {
    await mockBaseRoutes(page);
    await loginViaUI(page);
  });

  test("shows stat cards with data", async ({ page }) => {
    await expect(page.getByText("Route Groups").first()).toBeVisible();
    await expect(page.getByText("Prices Collected")).toBeVisible();
    await expect(page.getByText("Origins").first()).toBeVisible();
  });

  test("shows route group card", async ({ page }) => {
    await expect(page.getByText(MOCK_GROUP.name)).toBeVisible();
    await expect(page.getByText(MOCK_GROUP.destination_label, { exact: true })).toBeVisible();
  });

  test("trigger collection shows success toast", async ({ page }) => {
    await page.route("**/api/v1/collection/trigger", (r) =>
      r.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ status: "triggered" }),
      }),
    );
    await page.getByRole("button", { name: "Trigger collection", exact: true }).click();
    await expect(page.getByText("Collection triggered successfully")).toBeVisible();
  });

  test("already running collection shows info toast", async ({ page }) => {
    await page.route("**/api/v1/collection/trigger", (r) =>
      r.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ status: "already_running" }),
      }),
    );
    await page.getByRole("button", { name: "Trigger collection", exact: true }).click();
    await expect(page.getByText("Collection is already running")).toBeVisible();
  });

  test("clicking route group card opens detail page", async ({ page }) => {
    await page.route("**/api/v1/prices/trend*", (r) =>
      r.fulfill({ status: 200, contentType: "application/json", body: "[]" }),
    );
    await page.route("**/api/v1/prices*", (r) =>
      r.fulfill({ status: 200, contentType: "application/json", body: "[]" }),
    );
    await page.getByText(MOCK_GROUP.name).click();
    await expect(page).toHaveURL(`/route-groups/${MOCK_GROUP.id}`);
    await expect(page.getByText("Collection Progress")).toBeVisible();
  });

  test("new group button opens the create form", async ({ page }) => {
    await page.getByRole("button", { name: "New group" }).click();
    await expect(page.getByRole("dialog")).toBeVisible();
  });
});