# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: operations.spec.ts >> Operations Page >> renders heading and shows search hint initially
- Location: ..\tests\e2e\ui\operations.spec.ts:4:7

# Error details

```
Error: expect(locator).toBeVisible() failed

Locator: getByText(/enter a search|upload|search/i)
Expected: visible
Error: strict mode violation: getByText(/enter a search|upload|search/i) resolved to 4 elements:
    1) <span>Upload</span> aka getByRole('link', { name: '↑ Upload' })
    2) <p class="text-sm text-slate-500 mt-0.5">Upload files and manage uploads</p> aka getByText('Upload files and manage')
    3) <button class="px-4 py-2 text-sm font-medium rounded-md transition-colors bg-white text-slate-800 shadow-sm">Upload</button> aka getByRole('button', { name: 'Upload', exact: true })
    4) <button class="px-4 py-2 text-sm font-medium rounded-md transition-colors text-slate-500 hover:text-slate-700">Search Uploads</button> aka getByRole('button', { name: 'Search Uploads' })

Call log:
  - Expect "toBeVisible" with timeout 5000ms
  - waiting for getByText(/enter a search|upload|search/i)

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
        - heading "Operations" [level=2] [ref=e42]
        - paragraph [ref=e43]: Upload files and manage uploads
      - generic [ref=e44]:
        - button "Upload" [ref=e45]
        - button "Search Uploads" [ref=e46]
      - generic [ref=e49] [cursor=pointer]:
        - generic [ref=e50]: 📂
        - paragraph [ref=e51]: Drag & drop a CSV file here, or click to browse
```

# Test source

```ts
  1  | import { test, expect } from "@playwright/test";
  2  | 
  3  | test.describe("Operations Page", () => {
  4  |   test("renders heading and shows search hint initially", async ({ page }) => {
  5  |     await page.goto("/operations");
  6  |     await page.waitForLoadState("networkidle");
  7  |     await expect(page.getByRole("heading", { name: /Operations/ })).toBeVisible();
> 8  |     await expect(page.getByText(/enter a search|upload|search/i)).toBeVisible();
     |                                                                   ^ Error: expect(locator).toBeVisible() failed
  9  |   });
  10 | });
  11 | 
```