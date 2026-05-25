# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: rules.spec.ts >> Rules Page >> edits an existing rule
- Location: ..\tests\e2e\ui\rules.spec.ts:39:7

# Error details

```
Error: expect(locator).toBeVisible() failed

Locator: getByText('Edited E2E Rule')
Expected: visible
Timeout: 5000ms
Error: element(s) not found

Call log:
  - Expect "toBeVisible" with timeout 5000ms
  - waiting for getByText('Edited E2E Rule')

```

```yaml
- complementary:
  - link "AML Monitor":
    - /url: /
  - navigation:
    - link "🛡️ Compliance 3":
      - /url: /compliance
    - button "📤 Operations ▼"
    - link "↑ Upload":
      - /url: /operations
    - link "⚙ Rules":
      - /url: /operations/rules
    - link "👥 Customers":
      - /url: /customers
    - link "📋 Transactions":
      - /url: /transactions
    - separator
    - link "🧪 Test Data Generator":
      - /url: /test
  - link "📄 API Docs":
    - /url: /docs
- main:
  - heading "Rules" [level=3]
  - paragraph: Manage AML detection rules
  - text: Type
  - textbox "Filter by type": Edited E2E Rule
  - text: Status
  - combobox:
    - option "All" [selected]
    - option "Active"
    - option "Inactive"
  - text: Name
  - textbox "Filter by name"
  - button "Search"
  - button "+ Add Rule"
  - table:
    - rowgroup:
      - row "Name Type Status Description":
        - columnheader "Name"
        - columnheader "Type"
        - columnheader "Status"
        - columnheader "Description"
        - columnheader
    - rowgroup:
      - row "No rules found.":
        - cell "No rules found."
```

# Test source

```ts
  1  | import { test, expect } from "@playwright/test";
  2  | 
  3  | test.describe("Rules Page", () => {
  4  |   test.beforeEach(async ({ page }) => {
  5  |     await page.goto("/operations/rules");
  6  |     await page.waitForLoadState("networkidle");
  7  |   });
  8  | 
  9  |   test("renders heading and description", async ({ page }) => {
  10 |     await expect(page.getByRole("heading", { name: "Rules" })).toBeVisible();
  11 |     await expect(page.getByText("Manage AML detection rules")).toBeVisible();
  12 |   });
  13 | 
  14 |   test("shows seeded rules in table", async ({ page }) => {
  15 |     const rows = page.locator("table tbody tr");
  16 |     await expect(rows.first()).toBeVisible({ timeout: 10000 });
  17 |   });
  18 | 
  19 |   test("filters by status", async ({ page }) => {
  20 |     await page.selectOption("select", "inactive");
  21 |     await page.getByRole("button", { name: "Search" }).click();
  22 |     await page.waitForLoadState("networkidle");
  23 |     const badges = page.locator("table tbody tr td span.rounded-full");
  24 |     const count = await badges.count();
  25 |     for (let i = 0; i < count; i++) {
  26 |       await expect(badges.nth(i)).toHaveText("inactive");
  27 |     }
  28 |   });
  29 | 
  30 |   test("creates a new rule", async ({ page }) => {
  31 |     await page.getByRole("button", { name: "+ Add Rule" }).click();
  32 |     await page.fill("input", "Test E2E Rule");
  33 |     await page.locator("textarea").fill(JSON.stringify([{ field: "amount", operator: "gt", value: 10000 }], null, 2));
  34 |     await page.getByRole("button", { name: "Save" }).click();
  35 |     await page.waitForLoadState("networkidle");
  36 |     await expect(page.getByText("Test E2E Rule")).toBeVisible();
  37 |   });
  38 | 
  39 |   test("edits an existing rule", async ({ page }) => {
  40 |     const nameCell = page.locator("table tbody tr").first().locator("td").first().locator("button");
  41 |     await nameCell.click();
  42 |     await page.fill("input", "Edited E2E Rule");
  43 |     await page.getByRole("button", { name: "Save" }).click();
  44 |     await page.waitForLoadState("networkidle");
> 45 |     await expect(page.getByText("Edited E2E Rule")).toBeVisible();
     |                                                     ^ Error: expect(locator).toBeVisible() failed
  46 |   });
  47 | 
  48 |   test("deactivates and reactivates a rule", async ({ page }) => {
  49 |     const toggleBtn = page.locator("table tbody tr").first().locator("td").last().locator("button");
  50 |     const initialText = await toggleBtn.textContent();
  51 |     const wasActive = initialText?.trim() === "Deactivate";
  52 | 
  53 |     await toggleBtn.click();
  54 |     page.on("dialog", (d) => d.accept());
  55 |     await page.waitForLoadState("networkidle");
  56 | 
  57 |     const badge = page.locator("table tbody tr").first().locator("td").nth(2).locator("span.rounded-full");
  58 |     await expect(badge).toHaveText(wasActive ? "inactive" : "active");
  59 | 
  60 |     const toggleBtnAgain = page.locator("table tbody tr").first().locator("td").last().locator("button");
  61 |     await expect(toggleBtnAgain).toHaveText(wasActive ? "Activate" : "Deactivate");
  62 |   });
  63 | 
  64 |   test("shows status in edit form", async ({ page }) => {
  65 |     const nameCell = page.locator("table tbody tr").first().locator("td").first().locator("button");
  66 |     await nameCell.click();
  67 |     const statusSelect = page.locator("form select").nth(1);
  68 |     await expect(statusSelect).toBeVisible();
  69 |     await expect(statusSelect).toHaveValue(/active|inactive/);
  70 |   });
  71 | });
  72 | 
```