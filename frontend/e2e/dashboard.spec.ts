import { expect, test } from "@playwright/test";

import { mockBaseRoutes } from "./fixtures";

test.describe("Dashboard", () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => {
      window.sessionStorage.setItem("token", "test-token");
    });
    await mockBaseRoutes(page);
  });

  test("loads dashboard overview and route groups", async ({ page }) => {
    await page.goto("/");

    await expect(page.getByRole("heading", { name: "Flight Collection Overview" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Route Groups" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Canada to Vietnam" })).toBeVisible();
  });

  test("can trigger a collection run", async ({ page }) => {
    await page.route("**/api/v1/collection/trigger", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ success: true, message: "Collection triggered" }),
      });
    });

    await page.goto("/");
    await page.getByRole("button", { name: "Trigger", exact: true }).click();

    await expect(page.getByText("Collection triggered")).toBeVisible();
  });

  test("can open the new group dialog", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("button", { name: "New Group" }).click();

    await expect(page.getByRole("heading", { name: "New Route Group" })).toBeVisible();
  });
});
