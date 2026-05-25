# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: layout.spec.ts >> Sidebar Layout >> Operations collapsible expands sub-nav
- Location: ..\tests\e2e\ui\layout.spec.ts:15:7

# Error details

```
Error: locator.click: Error: strict mode violation: getByText('Operations') resolved to 2 elements:
    1) <span class="flex-1">Operations</span> aka getByRole('button', { name: '📤 Operations ▼' })
    2) <h3 class="text-base font-semibold text-slate-800 group-hover:text-blue-600 transition-colors">Operations</h3> aka getByRole('link', { name: '📤 Operations Upload and' })

Call log:
  - waiting for getByText('Operations')

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
        - heading "Dashboard" [level=2] [ref=e42]
        - paragraph [ref=e43]: Select a module to get started
      - generic [ref=e44]:
        - link "🛡️ Compliance Review suspicious activity reports and resolve flagged transactions" [ref=e45] [cursor=pointer]:
          - /url: /compliance
          - generic [ref=e46]:
            - generic [ref=e47]: 🛡️
            - generic [ref=e48]:
              - heading "Compliance" [level=3] [ref=e49]
              - paragraph [ref=e50]: Review suspicious activity reports and resolve flagged transactions
        - link "📤 Operations Upload and manage transaction data files" [ref=e51] [cursor=pointer]:
          - /url: /operations
          - generic [ref=e52]:
            - generic [ref=e53]: 📤
            - generic [ref=e54]:
              - heading "Operations" [level=3] [ref=e55]
              - paragraph [ref=e56]: Upload and manage transaction data files
        - link "⚙️ Rules Configure detection rules that drive the AML engine" [ref=e57] [cursor=pointer]:
          - /url: /operations/rules
          - generic [ref=e58]:
            - generic [ref=e59]: ⚙️
            - generic [ref=e60]:
              - heading "Rules" [level=3] [ref=e61]
              - paragraph [ref=e62]: Configure detection rules that drive the AML engine
        - link "👥 Customers Browse customer profiles, account history, and activity" [ref=e63] [cursor=pointer]:
          - /url: /customers
          - generic [ref=e64]:
            - generic [ref=e65]: 👥
            - generic [ref=e66]:
              - heading "Customers" [level=3] [ref=e67]
              - paragraph [ref=e68]: Browse customer profiles, account history, and activity
        - link "📋 Transactions View and search all processed transaction records" [ref=e69] [cursor=pointer]:
          - /url: /transactions
          - generic [ref=e70]:
            - generic [ref=e71]: 📋
            - generic [ref=e72]:
              - heading "Transactions" [level=3] [ref=e73]
              - paragraph [ref=e74]: View and search all processed transaction records
```

# Test source

```ts
  1  | import { test, expect } from "@playwright/test";
  2  | 
  3  | test.describe("Sidebar Layout", () => {
  4  |   test("sidebar shows all navigation items", async ({ page }) => {
  5  |     await page.goto("/");
  6  |     await page.waitForLoadState("networkidle");
  7  |     await expect(page.getByText("Compliance")).toBeVisible();
  8  |     await expect(page.getByText("Operations")).toBeVisible();
  9  |     await expect(page.getByText("Customers")).toBeVisible();
  10 |     await expect(page.getByText("Transactions")).toBeVisible();
  11 |     await expect(page.getByText("Test Data Generator")).toBeVisible();
  12 |     await expect(page.getByText("API Docs")).toBeVisible();
  13 |   });
  14 | 
  15 |   test("Operations collapsible expands sub-nav", async ({ page }) => {
  16 |     await page.goto("/");
  17 |     await page.waitForLoadState("networkidle");
> 18 |     await page.getByText("Operations").click();
     |                                        ^ Error: locator.click: Error: strict mode violation: getByText('Operations') resolved to 2 elements:
  19 |     await expect(page.getByText("Upload")).toBeVisible();
  20 |     await expect(page.getByText("Rules")).toBeVisible();
  21 |   });
  22 | 
  23 |   test("navigates via sidebar links", async ({ page }) => {
  24 |     await page.goto("/");
  25 |     await page.getByText("Compliance").click();
  26 |     await page.waitForLoadState("networkidle");
  27 |     await expect(page).toHaveURL(/\/compliance/);
  28 | 
  29 |     await page.getByText("Transactions").click();
  30 |     await page.waitForLoadState("networkidle");
  31 |     await expect(page).toHaveURL(/\/transactions/);
  32 | 
  33 |     await page.getByText("Customers").click();
  34 |     await page.waitForLoadState("networkidle");
  35 |     await expect(page).toHaveURL(/\/customers/);
  36 |   });
  37 | });
  38 | 
```