import { test, expect } from "@playwright/test";

test.describe("Transactions Page", () => {
  test("renders heading with DEV ONLY badge", async ({ page }) => {
    await page.goto("/transactions");
    await page.waitForLoadState("networkidle");
    await expect(page.getByRole("heading", { name: /Transactions/ })).toBeVisible();
    await expect(page.getByText("DEV ONLY")).toBeVisible();
  });
});
