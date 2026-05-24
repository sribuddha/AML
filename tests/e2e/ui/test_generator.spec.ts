import { test, expect } from "@playwright/test";

test.describe("Test Data Generator Page", () => {
  test("renders heading with DEV ONLY badge", async ({ page }) => {
    await page.goto("/test");
    await page.waitForLoadState("networkidle");
    await expect(page.getByText("Test Data Generator")).toBeVisible();
    await expect(page.getByText("DEV ONLY")).toBeVisible();
  });

  test("shows checkboxes for each generator type", async ({ page }) => {
    await page.goto("/test");
    await page.waitForLoadState("networkidle");
    await expect(page.getByLabel(/upload/i)).toBeVisible();
    await expect(page.getByLabel(/stage1/i)).toBeVisible();
    await expect(page.getByLabel(/stage2/i)).toBeVisible();
    await expect(page.getByLabel(/synthetic/i)).toBeVisible();
  });
});
