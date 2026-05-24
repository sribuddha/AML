import { test, expect } from "@playwright/test";

test.describe("Rules Page", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/operations/rules");
    await page.waitForLoadState("networkidle");
  });

  test("renders heading and description", async ({ page }) => {
    await expect(page.getByRole("heading", { name: "Rules" })).toBeVisible();
    await expect(page.getByText("Manage AML detection rules")).toBeVisible();
  });

  test("shows seeded rules in table", async ({ page }) => {
    const rows = page.locator("table tbody tr");
    await expect(rows.first()).toBeVisible({ timeout: 10000 });
  });

  test("filters by status", async ({ page }) => {
    await page.selectOption("select", "inactive");
    await page.getByRole("button", { name: "Search" }).click();
    await page.waitForLoadState("networkidle");
    const badges = page.locator("table tbody tr td span.rounded-full");
    const count = await badges.count();
    for (let i = 0; i < count; i++) {
      await expect(badges.nth(i)).toHaveText("inactive");
    }
  });

  test("creates a new rule", async ({ page }) => {
    await page.getByRole("button", { name: "+ Add Rule" }).click();
    await page.fill("input", "Test E2E Rule");
    await page.locator("textarea").fill(JSON.stringify([{ field: "amount", operator: "gt", value: 10000 }], null, 2));
    await page.getByRole("button", { name: "Save" }).click();
    await page.waitForLoadState("networkidle");
    await expect(page.getByText("Test E2E Rule")).toBeVisible();
  });

  test("edits an existing rule", async ({ page }) => {
    const nameCell = page.locator("table tbody tr").first().locator("td").first().locator("button");
    await nameCell.click();
    await page.fill("input", "Edited E2E Rule");
    await page.getByRole("button", { name: "Save" }).click();
    await page.waitForLoadState("networkidle");
    await expect(page.getByText("Edited E2E Rule")).toBeVisible();
  });

  test("deactivates and reactivates a rule", async ({ page }) => {
    const toggleBtn = page.locator("table tbody tr").first().locator("td").last().locator("button");
    const initialText = await toggleBtn.textContent();
    const wasActive = initialText?.trim() === "Deactivate";

    await toggleBtn.click();
    page.on("dialog", (d) => d.accept());
    await page.waitForLoadState("networkidle");

    const badge = page.locator("table tbody tr").first().locator("td").nth(2).locator("span.rounded-full");
    await expect(badge).toHaveText(wasActive ? "inactive" : "active");

    const toggleBtnAgain = page.locator("table tbody tr").first().locator("td").last().locator("button");
    await expect(toggleBtnAgain).toHaveText(wasActive ? "Activate" : "Deactivate");
  });

  test("shows status in edit form", async ({ page }) => {
    const nameCell = page.locator("table tbody tr").first().locator("td").first().locator("button");
    await nameCell.click();
    const statusSelect = page.locator("form select").nth(1);
    await expect(statusSelect).toBeVisible();
    await expect(statusSelect).toHaveValue(/active|inactive/);
  });
});
