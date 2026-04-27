import { expect, test } from "@playwright/test";
import { loginViaUI, MOCK_GROUP, mockBaseRoutes } from "./fixtures";

test.describe("Excel download", () => {
  test.beforeEach(async ({ page }) => {
    await mockBaseRoutes(page);
    // Mock price endpoints used on the detail page
    await page.route("**/api/v1/prices/trend*", (r) =>
      r.fulfill({ status: 200, contentType: "application/json", body: "[]" }),
    );
    await page.route("**/api/v1/prices*", (r) =>
      r.fulfill({ status: 200, contentType: "application/json", body: "[]" }),
    );
    await loginViaUI(page);
    await page.goto(`/route-groups/${MOCK_GROUP.id}`);
    await expect(page.getByText("Collection Progress")).toBeVisible();
  });

  test("Download Excel button triggers a file download", async ({ page }) => {
    // Serve a minimal xlsx-like binary so the browser doesn't reject the response
    const fakeXlsx = Buffer.from("PK\x03\x04"); // ZIP magic bytes (xlsx is a zip)
    await page.route(`**/api/v1/route-groups/${MOCK_GROUP.id}/export`, (r) =>
      r.fulfill({
        status: 200,
        contentType: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        body: fakeXlsx,
        headers: {
          "content-disposition": `attachment; filename="${MOCK_GROUP.name}.xlsx"`,
        },
      }),
    );

    const [download] = await Promise.all([
      page.waitForEvent("download"),
      page.getByRole("button", { name: "Download Excel" }).click(),
    ]);

    expect(download.suggestedFilename()).toMatch(/\.xlsx$/);
  });

  test("Download Excel shows success toast", async ({ page }) => {
    const fakeXlsx = Buffer.from("PK\x03\x04");
    await page.route(`**/api/v1/route-groups/${MOCK_GROUP.id}/export`, (r) =>
      r.fulfill({
        status: 200,
        contentType: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        body: fakeXlsx,
      }),
    );

    await page.getByRole("button", { name: "Download Excel" }).click();
    await expect(page.getByText("Excel downloaded")).toBeVisible();
  });

  test("failed download shows error toast", async ({ page }) => {
    await page.route(`**/api/v1/route-groups/${MOCK_GROUP.id}/export`, (r) =>
      r.fulfill({ status: 500, contentType: "application/json", body: '{"detail":"Server error"}' }),
    );

    await page.getByRole("button", { name: "Download Excel" }).click();
    await expect(page.getByText("Download failed")).toBeVisible();
  });
});
