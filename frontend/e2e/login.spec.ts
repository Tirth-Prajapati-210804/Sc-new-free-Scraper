import { expect, test } from "@playwright/test";
import { loginViaUI, MOCK_USER, mockBaseRoutes } from "./fixtures";

test.describe("Login page", () => {
  test("shows Flight Price Tracker heading", async ({ page }) => {
    await mockBaseRoutes(page);
    await page.goto("/login");
    await expect(page.getByRole("heading", { name: "Flight Price Tracker" })).toBeVisible();
  });

  test("successful login redirects to dashboard", async ({ page }) => {
    await mockBaseRoutes(page);
    await loginViaUI(page);
    await expect(page).toHaveURL("/");
    await expect(page.getByRole("heading", { name: "Overview" })).toBeVisible();
  });

  test("shows error message on wrong credentials", async ({ page }) => {
    await page.route("**/api/v1/auth/login", (r) =>
      r.fulfill({ status: 401, contentType: "application/json", body: '{"detail":"Unauthorized"}' }),
    );
    await page.goto("/login");
    await page.getByLabel("Email").fill("wrong@example.com");
    await page.getByLabel("Password").fill("badpassword");
    await page.getByRole("button", { name: "Sign in" }).click();
    await expect(page.getByText("Invalid email or password")).toBeVisible();
    await expect(page).toHaveURL("/login");
  });

  test("protected routes redirect to /login when unauthenticated", async ({ page }) => {
    await page.goto("/");
    await expect(page).toHaveURL(/\/login/);
  });

  test("unknown routes show 404 page", async ({ page }) => {
    await mockBaseRoutes(page);
    await loginViaUI(page);
    await page.goto("/this-does-not-exist");
    await expect(page.getByText("404")).toBeVisible();
    await expect(page.getByText("Page not found")).toBeVisible();
  });

  test("displays user's name after login (sidebar)", async ({ page }) => {
    await mockBaseRoutes(page);
    await loginViaUI(page);
    await expect(page.getByText(MOCK_USER.full_name)).toBeVisible();
  });
});
