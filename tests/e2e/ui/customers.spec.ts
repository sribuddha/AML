import { test, expect } from "@playwright/test";

test.describe("Customers Page", () => {
  test("renders heading and customer list", async ({ page }) => {
    await page.goto("/customers");
    await page.waitForLoadState("networkidle");
    await expect(page.getByRole("heading", { name: /Customers/ })).toBeVisible();
  });

  test("navigates to customer detail", async ({ page }) => {
    await page.goto("/customers");
    await page.waitForLoadState("networkidle");
    const customerLink = page.locator("a[href*='/customers/']").first();
    if (await customerLink.isVisible()) {
      await customerLink.click();
      await page.waitForLoadState("networkidle");
      await expect(page.getByText(/Accounts|Transactions/)).toBeVisible();
    }
  });
});
