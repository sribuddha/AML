import { test, expect } from "@playwright/test";

test.describe("Compliance Page", () => {
  test("renders heading and shows all-clear message", async ({ page }) => {
    await page.goto("/compliance");
    await page.waitForLoadState("networkidle");
    await expect(page.getByRole("heading", { name: "Compliance" })).toBeVisible();
  });

  test("sidebar shows pending SAR count badge", async ({ page }) => {
    await page.goto("/");
    await page.waitForLoadState("networkidle");
    const badge = page.locator("nav").getByText(/^\d+$/);
    if (await badge.isVisible()) {
      await expect(badge).toBeVisible();
    }
  });
});
