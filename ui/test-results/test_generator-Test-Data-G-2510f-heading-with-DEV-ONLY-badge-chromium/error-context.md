# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: test_generator.spec.ts >> Test Data Generator Page >> renders heading with DEV ONLY badge
- Location: ..\tests\e2e\ui\test_generator.spec.ts:4:7

# Error details

```
Error: expect(locator).toBeVisible() failed

Locator: getByText('Test Data Generator')
Expected: visible
Error: strict mode violation: getByText('Test Data Generator') resolved to 2 elements:
    1) <span>Test Data Generator</span> aka getByRole('link', { name: '🧪 Test Data Generator' })
    2) <h2 class="text-xl font-bold text-slate-800">Test Data Generator</h2> aka getByRole('heading', { name: 'Test Data Generator' })

Call log:
  - Expect "toBeVisible" with timeout 5000ms
  - waiting for getByText('Test Data Generator')

```

# Page snapshot

```yaml
- generic [ref=e3]:
  - complementary [ref=e4]:
    - link "AML Monitor" [ref=e6] [cursor=pointer]:
      - /url: /
    - navigation [ref=e7]:
      - link "🛡️ Compliance 3" [ref=e8] [cursor=pointer]:
        - /url: /compliance
        - generic [ref=e9]: 🛡️
        - generic [ref=e10]: Compliance
        - generic [ref=e11]: "3"
      - generic [ref=e12]:
        - button "📤 Operations ▼" [ref=e13]:
          - generic [ref=e14]: 📤
          - generic [ref=e15]: Operations
          - generic [ref=e16]: ▼
        - generic [ref=e17]:
          - link "↑ Upload" [ref=e18] [cursor=pointer]:
            - /url: /operations
            - generic [ref=e19]: ↑
            - generic [ref=e20]: Upload
          - link "⚙ Rules" [ref=e21] [cursor=pointer]:
            - /url: /operations/rules
            - generic [ref=e22]: ⚙
            - generic [ref=e23]: Rules
      - link "👥 Customers" [ref=e24] [cursor=pointer]:
        - /url: /customers
        - generic [ref=e25]: 👥
        - generic [ref=e26]: Customers
      - link "📋 Transactions" [ref=e27] [cursor=pointer]:
        - /url: /transactions
        - generic [ref=e28]: 📋
        - generic [ref=e29]: Transactions
      - separator [ref=e30]
      - link "🧪 Test Data Generator" [ref=e31] [cursor=pointer]:
        - /url: /test
        - generic [ref=e32]: 🧪
        - generic [ref=e33]: Test Data Generator
    - link "📄 API Docs" [ref=e35] [cursor=pointer]:
      - /url: /docs
      - generic [ref=e36]: 📄
      - generic [ref=e37]: API Docs
  - main [ref=e38]:
    - generic [ref=e40]:
      - generic [ref=e41]:
        - heading "Test Data Generator" [level=2] [ref=e42]
        - generic [ref=e43]: DEV ONLY
      - generic [ref=e44]:
        - generic [ref=e45]: ⚠️
        - generic [ref=e46]:
          - strong [ref=e47]: Development-only tool.
          - text: This generator runs arbitrary scripts against the database and application code. Do not use in production environments.
      - generic [ref=e48]:
        - generic [ref=e49]:
          - checkbox [checked] [ref=e50]
          - generic [ref=e51]:
            - generic [ref=e52]:
              - generic [ref=e53] [cursor=pointer]: Clean Upload
              - spinbutton [ref=e54]: "1000"
              - generic [ref=e55]: bad rows
              - spinbutton [ref=e56]: "50"
            - paragraph [ref=e57]: Standard upload CSV with optional bad rows
        - generic [ref=e58]:
          - checkbox [ref=e59]
          - generic [ref=e60]:
            - generic [ref=e61]:
              - generic [ref=e62] [cursor=pointer]: Stage 1 Fraud
              - generic [ref=e63]: (tick to add)
              - spinbutton [ref=e64]: "200"
            - paragraph [ref=e65]: Transactions that trigger deterministic rules
        - generic [ref=e66]:
          - checkbox [ref=e67]
          - generic [ref=e68]:
            - generic [ref=e69]:
              - generic [ref=e70] [cursor=pointer]: Stage 2 Triage
              - generic [ref=e71]: (tick to add)
              - spinbutton [ref=e72]: "20"
            - paragraph [ref=e73]: Scenario-based transactions for LLM triage evaluation
        - generic [ref=e74]:
          - checkbox [ref=e75]
          - generic [ref=e76]:
            - generic [ref=e77]:
              - generic [ref=e78] [cursor=pointer]: Synthetic Fraud Patterns
              - generic [ref=e79]: (tick to add)
              - spinbutton [ref=e80]: "500"
            - paragraph [ref=e81]: 5 fraud patterns (structuring, velocity, travel, round-trip, watchlist) with clean txns
        - generic [ref=e82]:
          - generic [ref=e83] [cursor=pointer]:
            - checkbox "Shuffle after generation" [checked] [ref=e84]
            - text: Shuffle after generation
          - generic [ref=e85]:
            - text: Date
            - textbox [ref=e86]: 2026-05-25
        - generic [ref=e87]:
          - text: "Total rows:"
          - strong [ref=e88]: 1,000
        - button "Generate" [ref=e89]
```

# Test source

```ts
  1  | import { test, expect } from "@playwright/test";
  2  | 
  3  | test.describe("Test Data Generator Page", () => {
  4  |   test("renders heading with DEV ONLY badge", async ({ page }) => {
  5  |     await page.goto("/test");
  6  |     await page.waitForLoadState("networkidle");
> 7  |     await expect(page.getByText("Test Data Generator")).toBeVisible();
     |                                                         ^ Error: expect(locator).toBeVisible() failed
  8  |     await expect(page.getByText("DEV ONLY")).toBeVisible();
  9  |   });
  10 | 
  11 |   test("shows checkboxes for each generator type", async ({ page }) => {
  12 |     await page.goto("/test");
  13 |     await page.waitForLoadState("networkidle");
  14 |     await expect(page.getByLabel(/upload/i)).toBeVisible();
  15 |     await expect(page.getByLabel(/stage1/i)).toBeVisible();
  16 |     await expect(page.getByLabel(/stage2/i)).toBeVisible();
  17 |     await expect(page.getByLabel(/synthetic/i)).toBeVisible();
  18 |   });
  19 | });
  20 | 
```