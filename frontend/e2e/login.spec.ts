import { expect, test } from "@playwright/test";

import { mockBaseRoutes } from "./fixtures";

test.describe("Login", () => {
  test("successful login redirects to dashboard", async ({ page }) => {
    await mockBaseRoutes(page);
    await page.route("**/api/v1/auth/login", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          access_token: "test-token",
          token_type: "bearer",
          expires_in: 7200,
          user: {
            id: "user-1",
            email: "admin@example.com",
            full_name: "System Admin",
            role: "admin",
          },
        }),
      });
    });

    await page.goto("/login");
    await page.getByLabel("Email").fill("admin@example.com");
    await page.getByLabel("Password").fill("Admin12345678");
    await page.getByRole("button", { name: "Sign in" }).click();

    await expect(page).toHaveURL(/\/$/);
    await expect(page.getByRole("heading", { name: "Flight Collection Overview" })).toBeVisible();
  });

  test("failed login shows server message", async ({ page }) => {
    await page.route("**/api/v1/auth/login", async (route) => {
      await route.fulfill({
        status: 401,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Invalid email or password" }),
      });
    });

    await page.goto("/login");
    await page.getByLabel("Email").fill("admin@example.com");
    await page.getByLabel("Password").fill("wrong-password");
    await page.getByRole("button", { name: "Sign in" }).click();

    await expect(page.getByText("Invalid email or password")).toBeVisible();
    await expect(page).toHaveURL(/\/login$/);
  });
});
