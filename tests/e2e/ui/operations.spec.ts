import { test, expect } from "@playwright/test";

test.describe("Operations Page", () => {
  test("renders heading and shows search hint initially", async ({ page }) => {
    await page.goto("/operations");
    await page.waitForLoadState("networkidle");
    await expect(page.getByRole("heading", { name: /Operations/ })).toBeVisible();
    await expect(page.getByText(/enter a search|upload|search/i)).toBeVisible();
  });
});
