import { test, expect } from "@playwright/test";

test.describe("Sidebar Layout", () => {
  test("sidebar shows all navigation items", async ({ page }) => {
    await page.goto("/");
    await page.waitForLoadState("networkidle");
    await expect(page.getByText("Compliance")).toBeVisible();
    await expect(page.getByText("Operations")).toBeVisible();
    await expect(page.getByText("Customers")).toBeVisible();
    await expect(page.getByText("Transactions")).toBeVisible();
    await expect(page.getByText("Test Data Generator")).toBeVisible();
    await expect(page.getByText("API Docs")).toBeVisible();
  });

  test("Operations collapsible expands sub-nav", async ({ page }) => {
    await page.goto("/");
    await page.waitForLoadState("networkidle");
    await page.getByText("Operations").click();
    await expect(page.getByText("Upload")).toBeVisible();
    await expect(page.getByText("Rules")).toBeVisible();
  });

  test("navigates via sidebar links", async ({ page }) => {
    await page.goto("/");
    await page.getByText("Compliance").click();
    await page.waitForLoadState("networkidle");
    await expect(page).toHaveURL(/\/compliance/);

    await page.getByText("Transactions").click();
    await page.waitForLoadState("networkidle");
    await expect(page).toHaveURL(/\/transactions/);

    await page.getByText("Customers").click();
    await page.waitForLoadState("networkidle");
    await expect(page).toHaveURL(/\/customers/);
  });
});
