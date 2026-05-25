# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: test_generator.spec.ts >> Test Data Generator Page >> shows checkboxes for each generator type
- Location: ..\tests\e2e\ui\test_generator.spec.ts:11:7

# Error details

```
Error: expect(locator).toBeVisible() failed

Locator: getByLabel(/upload/i)
Expected: visible
Timeout: 5000ms
Error: element(s) not found

Call log:
  - Expect "toBeVisible" with timeout 5000ms
  - waiting for getByLabel(/upload/i)

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
  - heading "Test Data Generator" [level=2]
  - text: DEV ONLY ⚠️
  - strong: Development-only tool.
  - text: This generator runs arbitrary scripts against the database and application code. Do not use in production environments.
  - checkbox [checked]
  - text: Clean Upload
  - spinbutton: "1000"
  - text: bad rows
  - spinbutton: "50"
  - paragraph: Standard upload CSV with optional bad rows
  - checkbox
  - text: Stage 1 Fraud (tick to add)
  - spinbutton: "200"
  - paragraph: Transactions that trigger deterministic rules
  - checkbox
  - text: Stage 2 Triage (tick to add)
  - spinbutton: "20"
  - paragraph: Scenario-based transactions for LLM triage evaluation
  - checkbox
  - text: Synthetic Fraud Patterns (tick to add)
  - spinbutton: "500"
  - paragraph: 5 fraud patterns (structuring, velocity, travel, round-trip, watchlist) with clean txns
  - checkbox "Shuffle after generation" [checked]
  - text: Shuffle after generation Date
  - textbox: 2026-05-25
  - text: "Total rows:"
  - strong: 1,000
  - button "Generate"
```

# Test source

```ts
  1  | import { test, expect } from "@playwright/test";
  2  | 
  3  | test.describe("Test Data Generator Page", () => {
  4  |   test("renders heading with DEV ONLY badge", async ({ page }) => {
  5  |     await page.goto("/test");
  6  |     await page.waitForLoadState("networkidle");
  7  |     await expect(page.getByText("Test Data Generator")).toBeVisible();
  8  |     await expect(page.getByText("DEV ONLY")).toBeVisible();
  9  |   });
  10 | 
  11 |   test("shows checkboxes for each generator type", async ({ page }) => {
  12 |     await page.goto("/test");
  13 |     await page.waitForLoadState("networkidle");
> 14 |     await expect(page.getByLabel(/upload/i)).toBeVisible();
     |                                              ^ Error: expect(locator).toBeVisible() failed
  15 |     await expect(page.getByLabel(/stage1/i)).toBeVisible();
  16 |     await expect(page.getByLabel(/stage2/i)).toBeVisible();
  17 |     await expect(page.getByLabel(/synthetic/i)).toBeVisible();
  18 |   });
  19 | });
  20 | 
```