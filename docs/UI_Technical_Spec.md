# AML UI — Technical Specification

**Author:** Srikanth Buddha (AI-assisted)
**Date:** 2026-05-24
**Status:** Draft

---

## 1. Overview

A single-page application (SPA) for the AML transaction monitoring system. The UI is a React + TypeScript frontend served by the FastAPI BFF, providing search, review, and operational workflows for compliance analysts.

### 1.1 Technology Stack

| Layer | Technology | Version |
|-------|-----------|---------|
| Framework | React | 19 |
| Language | TypeScript | 5.x |
| Build tool | Vite | 6.x |
| Styling | Tailwind CSS | 4 |
| Routing | React Router | v6 |
| HTTP | fetch (native) | — |
| Testing (unit) | Vitest + Testing Library | latest |
| Testing (E2E) | Playwright | latest |

### 1.2 Architecture

```
Browser (SPA) → FastAPI BFF (port 8000)
                    │
                    ├── /api/rules — CRUD + status toggle
                    ├── /api/transactions — search
                    ├── /api/customers — search + detail
                    ├── /api/accounts — lookup
                    ├── /api/sar/pending — compliance review
                    ├── /api/uploads — file upload + search
                    ├── /api/generate — test data generation
                    └── /api/* — existing endpoints
```

- **Dev**: Vite dev server on port 5173 proxies `/api` → `localhost:8000`
- **Prod**: FastAPI mounts `ui/dist/` as static files with SPA fallback (`GET /{full_path:path}` route serves `index.html` for non-`/api` paths)

---

## 2. Pages & Routes

| Route | Page | Purpose |
|-------|------|---------|
| `/` | HomePage | Dashboard with 5 navigation cards |
| `/transactions` | TransactionsPage | Search transactions by any field |
| `/customers` | CustomersPage | Search customers by name |
| `/customers/:customerId` | CustomerDetailPage | Customer info + accounts |
| `/compliance` | CompliancePage | Review pending SARs |
| `/operations` | OperationsPage | Two tabs: Upload / Search Uploads |
| `/operations/rules` | RulesPage | CRUD for AML detection rules |
| `/test` | TestPage | Generate test CSV data |

### 2.1 HomePage

5-card dashboard grid at `/`. Each card links to its respective page:
- **Compliance** — links to `/compliance`
- **Operations** — links to `/operations`
- **Rules** — links to `/operations/rules`
- **Customers** — links to `/customers`
- **Transactions** — links to `/transactions`

No data fetching — purely navigational. Subtitle: "Select a module to get started".

### 2.2 TransactionsPage

**Search filters:**
| Field | Type | Behavior |
|-------|------|----------|
| `source_txn_id` | text | Exact match on source system ID |
| `account_id` | text | Case-sensitive match |
| `customer_id` | text | Case-sensitive match |
| `amount_min` / `amount_max` | number | Inclusive range |
| `counterparty` | text | Substring match |
| `from_date` / `to_date` | date | Inclusive range on `Transaction.date` |

**Active filter chips:** Removable badges above the DataTable showing each active filter. Click × to remove a filter and re-fetch.

**Results table columns:**
source_txn_id, account_name (link → customer detail page), customer_id, amount ($ formatted), counterparty, date, location (city/state/country concatenation)

**States:** loading (skeleton rows), empty ("No transactions match your search"), error (retry banner), populated

### 2.3 CustomersPage

**Search filters:**
| Field | Type | Behavior |
|-------|------|----------|
| `first_name` | text | SQL LIKE `%query%` |
| `last_name` | text | SQL LIKE `%query%` |

**Results table columns:**
customer_id (link → detail), first_name, last_name, city, state

**States:** loading, empty ("No customers found"), error, populated

### 2.4 CustomerDetailPage

**Customer info card:** first_name, last_name, address_line, city, state, zip

**Accounts table:** account_id (link → `/transactions?account_id=X`), name, bank, type, date_opened

**States:** loading, not found (404 message with back link), error, populated

### 2.5 CompliancePage

**Flat list of pending SARs with per-row checkboxes and batch review.**

| Section | Content |
|---------|---------|
| Transaction header | source_txn_id, risk pill badge (colored), amount ($), counterparty, location, date, rule_name |
| Rules triggered | Rule name list (from flag_details) |
| Enriched context (if available) | 30d stats (count, avg), structuring count, velocity z-score (red-highlighted if > 2), dormancy days, account type |
| SAR narrative | Full content text |
| Actions | Dismiss / Confirm buttons (disabled during review, show "..." while in progress) |

**Risk filter pills:** Row of filter pills above the list — **All | High | Medium | Low** — filters displayed SARs by `risk_level`. Pending count updates to show `N pending (M high)` when a filter is active.

**Batch review toolbar:**
- **Select All** checkbox: selects/deselects all visible (filtered) SARs
- **Accept All** / **Dismiss All** buttons: disabled when nothing selected, show "..." while processing
- Calls `POST /api/sar/batch-review` with `{ sar_ids: [...], action }`

**Behavior:**
- Fetches `GET /api/sar/pending?upload_id=` (optional filter from URL param)
- After Confirm/Dismiss, waits **1 second** then refetches
- While reviewing, buttons show "..." and are disabled
- If all SARs resolved, shows completion message ("You are all up to date.")
- On 404 from API, treats as "all resolved" (no pending SARs)
- After any review (single or batch), dispatches `window.dispatchEvent(new CustomEvent("sar-reviewed"))` for sidebar badge update
- Loading state: 3 skeleton cards with pulsing bars
- Error state: inline banner with Retry button
- Customer name persisted in separate `customerName` state to survive after SARs cleared by Accept All / Dismiss All
- When completed while filtered by customer (`?customer_id=X`): shows "View all pending reviews" link → `/compliance`

**States:** loading, error, empty ("all up to date", with optional "View all pending reviews" link when customer-filtered), populated with checkboxes + ReviewCards

### 2.6 OperationsPage

Two tabs:

**Tab 1 — Upload:**
- Drag-and-drop file uploader (`.csv` only), click to browse
- Filename shown after selection
- Upload progress indicator (spinner)
- Result summary card: total_rows / accepted_count / failed_count
- "View Uploads" link → switches to Tab 2

**Tab 2 — Search Uploads:**
- Status filter tabs: All, Uploaded, Processing, Pending Review, Complete, Failed
- Filters: upload_id (text), from_date / to_date (date range on `uploaded_at`)
- Search button triggers API fetch
- Unsearched state shows hint: "Enter an Upload ID, select a date range, and click Search"
- Results table: upload_id (link → Compliance if `pending_human`), filename, status (color badge), total_rows, accepted_count, failed_count, uploaded_at, Eval button (shown only when `eval_file` is present and status is `complete`)

### 2.7 RulesPage

**CRUD for AML detection rules.**

- **List view:** DataTable with columns: Name (clickable → edit), Type, Status (color badge), Description, Actions (Deactivate/Activate toggle)
- **Filters:** Type (text), Status (select: All/Active/Inactive), Name (text), Search button
- **Create:** "+ Add Rule" button opens inline form with fields: Name, Type (select: deterministic), Status (select: active/inactive), Description, Rules JSON (textarea)
- **Edit:** Click rule name → opens same form prefilled
- **Delete:** Removed from UI — replaced by Deactivate/Activate toggle
- **Status toggle:** PATCH `/api/rules/{id}/status` with `{status: "active"|"inactive"}` — requires confirmation dialog

**States:** loading, error (with Retry), empty ("No rules found."), populated

### 2.8 TestPage

**Form with 4 generator checkboxes:**
| Type | Label | Default count | Description |
|------|-------|--------------|-------------|
| `upload` | Clean Upload | 1000 | Standard upload CSV with optional bad rows |
| `stage1` | Stage 1 Fraud | 200 | Transactions that trigger deterministic rules |
| `stage2` | Stage 2 Triage | 20 | Scenario-based transactions for LLM triage eval |
| `synthetic` | Synthetic Fraud Patterns | 500 | 5 fraud patterns (structuring, velocity, travel, round-trip, watchlist) with clean txns |

**Behavior:**
- Only checked generators are included in generation steps
- Unchecked rows show dashed border + "tick to add" hint
- Each checked row shows a count input (number, min 1)
- "Upload" type additionally shows "bad rows" input (number, min 0)
- **Shuffle after generation** checkbox (default: checked)
- **Date** input (default: today)
- Total rows counter at bottom (sum of all enabled generators' counts)
- Generate button disabled when 0 total rows
- Spinner "Generating..." while in progress
- On success: 2-tab preview area (CSV File / Eval Data) in scrollable tables, plus Download CSV and Upload to Pipeline buttons
- Upload to Pipeline calls `POST /api/uploads/from-work/{filename}`, then navigates to Operations
- On failure: error banner with message
- Warning banner: "Development-only tool"

**API calls:**
- `POST /api/generate` with body `{steps: [{type, count, bad_rate}], shuffle, date}` → returns `{download_url, filename, eval_url}`
- `GET /api/generate/preview/{filename}` → returns first 50 CSV rows as JSON `{fieldnames, rows}`
- `GET /api/generate/eval/{filename}` → returns `.eval` JSONL entries or `.manifest.json` as JSON array
- `POST /api/uploads/from-work/{filename}` → uploads server-side CSV through normal pipeline

---

## 3. Component Tree

```
App (BrowserRouter)
└── Layout
    ├── Sidebar
    │   ├── Title (link → /)
    │   ├── Compliance (nav + pending-count badge)
    │   ├── Operations (collapsible)
    │   │   ├── Upload (sub-nav)
    │   │   └── Rules (sub-nav)
    │   ├── Customers (nav)
    │   ├── Transactions (nav)
    │   ├── ───── (separator)
    │   ├── Test Data Generator (nav)
    │   └── API Docs (external link)
    └── <Outlet /> (content area, full-width)
        ├── HomePage
        ├── TransactionsPage
        │   ├── SearchForm (inline filters + search button)
        │   ├── ActiveFilterChips (inline)
        │   ├── DataTable
        │   └── Pagination (inside DataTable)
        ├── CustomersPage
        │   ├── SearchForm
        │   ├── DataTable
        │   └── Pagination (inside DataTable)
        ├── CustomerDetailPage
        │   ├── CustomerInfoCard
        │   └── AccountsTable (raw HTML table)
        ├── CompliancePage
        │   ├── RiskFilterPills (All | High | Medium | Low)
        │   ├── BatchToolbar (Select All + Accept All / Dismiss All)
        │   └── ReviewCard[]
        │       ├── Collapsed summary
        │       └── Expanded detail
        │           ├── Rules Triggered
        │           ├── Enriched Context
        │           └── SAR Narrative
        ├── OperationsPage
        │   ├── TabBar (Upload | Search Uploads)
        │   ├── FileUploader (Tab 1)
        │   └── Search Uploads (Tab 2)
        │       ├── StatusFilterTabs
        │       ├── SearchForm
        │       ├── DataTable
        │       └── Pagination (inside DataTable)
        ├── RulesPage
        │   ├── FilterForm (Type, Status, Name + Search)
        │   ├── Create/Edit Form (inline, toggled by action state)
        │   └── DataTable
        │       └── Pagination (inside DataTable)
        └── TestPage
            ├── GeneratorCheckboxList (4 types)
            ├── Options (shuffle, date)
            └── ResultCard
                ├── TabBar (CSV File | Eval Data)
                ├── CSV preview table (scrollable)
                ├── Eval preview table (scrollable)
                └── Action buttons (Download CSV, Upload to Pipeline)
```

---

## 4. API Endpoints (BFF)

### 4.1 Endpoints Consumed by UI

| Method | Path | Purpose | Request | Response |
|--------|------|---------|---------|----------|
| GET | `/api/transactions` | Search transactions | query: source_txn_id, account_id, customer_id, amount_min, amount_max, counterparty, from_date, to_date, page, per_page | PaginatedResponse of TransactionRow |
| GET | `/api/customers` | Search customers | query: first_name, last_name, page, per_page | PaginatedResponse of CustomerSummary |
| GET | `/api/customers/{customer_id}` | Customer detail | path: customer_id | CustomerDetail |
| GET | `/api/accounts/{account_id}` | Account lookup | path: account_id | AccountDetail |
| GET | `/api/sar/pending` | Pending SARs | query: upload_id (optional), page, per_page | PaginatedResponse of PendingSAR |
| PATCH | `/api/sar/{sar_id}/review` | Review single SAR | body: `{action, notes}` | Updated SAR |
| POST | `/api/sar/batch-review` | Batch review multiple SARs | body: `{sar_ids: string[], action}` | `{reviewed: count}` |
| POST | `/api/uploads` | Upload CSV | multipart form: file | `{total_rows, accepted_count, failed_count}` |
| GET | `/api/uploads/search` | Search uploads | query: upload_id, status, from_date, to_date, page, per_page | PaginatedResponse of UploadSummary |
| GET | `/api/rules` | List rules | query: type, status, name, page, per_page | PaginatedResponse of RuleResponse |
| POST | `/api/rules` | Create rule | body: RuleCreate | RuleResponse |
| PUT | `/api/rules/{rule_id}` | Update rule | path + body: RuleCreate | RuleResponse |
| DELETE | `/api/rules/{rule_id}` | Delete rule | path | 204 |
| PATCH | `/api/rules/{rule_id}/status` | Toggle status | body: `{status: "active"|"inactive"}` | RuleResponse |
| POST | `/api/generate` | Generate test data | body: `{steps: [{type, count, bad_rate}], shuffle, date}` | `{download_url, filename, eval_url}` |
| GET | `/api/generate/download/{filename}` | Download generated file | path: filename | File stream (Content-Disposition attachment) |
| GET | `/api/generate/preview/{filename}` | Preview CSV rows | path: filename, query: limit | `{fieldnames, rows}` |
| GET | `/api/generate/eval/{filename}` | Get eval ground truth | path: filename | `EvalEntry[]` (JSON array) |
| POST | `/api/uploads/from-work/{filename}` | Upload CSV from server-side work/ | path: filename | `{total_rows, accepted_count, failed_count}` |
| POST | `/api/uploads/{upload_id}/eval` | Evaluate processed upload | path: upload_id | `EvalReportResponse` |
| GET | `/api/sar` | List SARs | query: status, per_page | PaginatedResponse (used by sidebar badge) |

### 4.2 PaginatedResponse Shape

```typescript
interface PaginatedResponse<T> {
  page: number;
  per_page: number;
  total: number;
  items: T[];
}
```

---

## 5. Data Flows

### 5.1 Homepage Navigation Flow

```
User opens app (GET /)
    → HomePage renders 5 navigation cards
    → User clicks a card
    → navigate to respective route
```

### 5.2 Transaction Search Flow

```
User enters search params
    → Search button click
    → setSearchParams updates URL (active filter chips appear)
    → GET /api/transactions?source_txn_id=X&account_id=Y&...
    → BFF joins Transaction + Account + ValidationResult
    → Returns paginated rows with account_name + customer_id
    → UI renders DataTable
    → User clicks account_name link → navigate to /customers/{customer_id}
    → User clicks filter chip × → removes filter, re-fetches
```

### 5.3 Compliance Review Flow

```
User opens Compliance page
    → GET /api/sar/pending
    → BFF joins SAR + Transaction + ValidationResult + EnrichmentSnapshot + Rule
    → Returns list of pending SARs with all context
    → UI renders RiskFilterPills + BatchToolbar + ReviewCards (collapsed)
    → User filters by risk level (All/High/Medium/Low)
    → User selects individual SARs or uses Select All
    → User clicks Confirm/Dismiss (single) OR Accept All/Dismiss All (batch)

SINGLE REVIEW:
    → PATCH /api/sar/{sar_id}/review {action, notes}
    → Wait 1 second
    → Refetch pending list

BATCH REVIEW:
    → POST /api/sar/batch-review {sar_ids: [...], action}
    → Wait 1 second
    → Refetch pending list

After both paths:
    → Dispatch window CustomEvent("sar-reviewed")
    → Clear selection
    → If empty, show completion status ("You are all up to date.")
    → Sidebar badge updates via custom event listener
```

### 5.4 Rules CRUD Flow

```
LIST:
    On mount → GET /api/rules?page=1&per_page=25
    → DataTable shows rules with sortable columns
    → Each row has Deactivate/Activate toggle button

CREATE:
    User clicks "+ Add Rule"
    → Inline form appears with Name, Type, Status, Description, Rules JSON
    → User fills form, clicks Save
    → POST /api/rules {name, type, status, description, rules_json}
    → On success: form closes, list refreshes
    → On error: error message shown below form

EDIT:
    User clicks rule name in DataTable
    → Inline form appears prefilled
    → User edits, clicks Save
    → PUT /api/rules/{id} {...}
    → On success: form closes, list refreshes

STATUS TOGGLE:
    User clicks "Deactivate" / "Activate"
    → ConfirmDialog prompts "Deactivate rule 'X'?"
    → PATCH /api/rules/{id}/status {status: "inactive"|"active"}
    → List refreshes
    → Button text and status badge update
```

### 5.5 Test Data Generation Flow

```
User checks desired generators, sets counts, bad_rows, shuffle, date
    → POST /api/generate {steps: [{type, count, bad_rate}], shuffle, date}
    → BFF calls generate script functions directly
    → Script writes CSV to work/{uuid}_{type}.csv + possibly .eval sidecar
    → Returns {download_url, filename, eval_url}
    → UI fetches CSV preview (GET /api/generate/preview/{filename})
    → UI fetches eval entries (GET /api/generate/eval/{filename}) if eval_url exists
    → Shows two tabs: CSV File (read-only table) | Eval Data (JSONL entries as table)
    → User reviews data in scrollable tables
    → User clicks "Upload to Pipeline"
    → POST /api/uploads/from-work/{filename}
    → BFF reads CSV from work/, processes through standard pipeline
    → .eval sidecar path stored in uploaded_files.eval_file
    → Pipeline triggers (run_validation)
    → UI navigates to /operations
```

### 5.6 Operations Eval Flow

```
User searches uploads → sees DataTable with Eval column
    → Clicks "Eval" on a completed upload with eval_file present
    → POST /api/uploads/{upload_id}/eval
    → BFF reads .eval file, queries DB (Transaction, ValidationResult, SAR)
    → Computes pattern metrics, hallucination, completeness
    → Returns EvalReportResponse
    → UI opens modal showing:
        - Summary cards (transactions, anomalous, flagged)
        - Overall metrics (precision, recall, F1)
        - Hallucination-free rate + avg completeness
        - Per-pattern metrics table (color-coded by score)
        - Hallucination issues (red cards per failed SAR)
        - Completeness issues (amber cards per incomplete SAR)
```

---

## 6. UI Component Library

### 6.1 Shared Components

**Layout** — Fixed sidebar (64px icons + labels) + scrollable full-width content area. Sidebar title links to `/` (homepage). Active nav item highlighted with blue background + left border indicator. Operations section is collapsible with Upload and Rules sub-navigation. Bottom section has API Docs external link. SAR pending count badge shown on Compliance nav item (fetched on mount via `GET /api/sar?status=pending_review&per_page=1`; updated in real-time by listening for `window "sar-reviewed"` custom event dispatched from CompliancePage). Shows `99+` when count > 99.

**DataTable** — Generic table component:
- Column configuration (key, label, sortable, render callback, className)
- **Self-sorting** with 3-state cycle: no sort → ascending → descending → no sort
- `sortable` defaults to `true`; set `sortable: false` to disable on a column
- Sorting auto-detects numeric vs string values
- Zebra striping (`even:bg-slate-50/50`)
- Sort indicator arrows (▲/▼) on active sort column (blue)
- Numbers right-aligned, text left-aligned (via className)
- Loading state: skeleton rows (pulsing gray bars)
- Empty state: centered message (configurable via `emptyMessage`)
- Error state: inline banner with error message + Retry button (if `onRetry` provided)
- Pagination rendered inline when `total > 0` and `onPageChange` provided

**Pagination** — Page number buttons + total count display. Hidden when totalPages ≤ 1. Disabled prev on first page, disabled next on last page.

**StatusBadge** — Color-coded pill:
- green: `clean`, `complete`, `confirmed`
- yellow: `pending`, `processing`, `pending_review`, `pending_human`
- red: `flagged`, `failed`, `escalated`
- gray/slate: `uploaded`, `dismissed`, `inactive`
- Replaces underscores with spaces in displayed text

**FileUploader** — Drag-and-drop zone with dashed border, click to browse. Shows filename after selection. Upload button appears after selection. Upload progress spinner. Drag-over highlights blue border. dragLeave restores default border.

**ReviewCard** — SAR review card:
- Collapsed: transaction summary (source_txn_id, amount, counterparty, location, date) + risk pill badge (colored: red/amber/green) + StatusBadge + expand arrow
- Expanded: Rules Triggered (from flag_details), Enriched Context (grid of stat cards), SAR Narrative
- Expand/collapse toggle on header click
- Action buttons: Dismiss (slate) / Confirm (blue), disabled with "..." text while `reviewing=true`
- Shows velocity z-score in red when > 2

### 6.2 Design Tokens

| Token | Value | Usage |
|-------|-------|-------|
| color-primary | `#2563eb` (blue-600) | Buttons, links, active states |
| color-success | `#16a34a` (green-600) | Confirm, complete, clean |
| color-warning | `#d97706` (amber-600) | Deactivate, pending |
| color-danger | `#dc2626` (red-600) | Flagged, failed, errors |
| color-surface | `#f8fafc` (slate-50) | Page background |
| color-card | `#ffffff` | Card background |
| color-text | `#1e293b` (slate-800) | Primary text |
| color-muted | `#64748b` (slate-500) | Secondary text |
| spacing-grid | 4px | Base spacing unit |
| card-padding | `24px` | Card inner padding |
| border-radius | `8px` | Card radius, button radius |
| font-family | `-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif` | System font stack |
| font-mono | `"SF Mono", "Cascadia Code", "Fira Code", monospace` | Code/serial numbers |

---

## 7. Error Handling

### 7.1 API Client Behavior

The `api/client.ts` wrapper handles:

- **Non-2xx responses** — parse error body (`body.detail`), throw structured `ApiError` with status + message
- **Network errors** — throw `ApiError` (caught in request function)
- **JSON parse failures** — fallback to `HTTP {status}` message

Available methods: `get`, `post`, `put`, `patch`, `del`, `upload` (FormData), `download` (anchor click)

### 7.2 Page-Level Error States

- **Data loading failure** — inline error banner in DataTable with Retry button
- **Form submission failure** — inline error message below form (e.g., RulesPage)
- **Action failure** — `toast.error()` (compliance review, status toggle) (see §2.8)
- **404 on detail page** — "Customer/Transaction not found" message + "Back to list" link
- **Compliance 404** — treated as "all SARs resolved" (completion state)

---

## 8. State Management

No external state library. Each page manages its own state with React hooks:

- `useState` for form values, active page, current data, loading/error flags
- `useEffect` for data fetching (triggered by search, mount, or page change)
- `useCallback` for memoized fetch functions with stable dependencies
- `useSearchParams` for URL-synced filter state (TransactionsPage)
- `useLocation` for active nav highlighting (Layout)
- `useNavigate` for programmatic navigation
- Sidebar badge count fetched with `useEffect` in Layout (no global context)

---

## 9. Testing Strategy

### 9.1 Unit Tests (Vitest)

**Framework:** Vitest v4 + jsdom + @testing-library/react

**Test files (15 files, 196 tests):**

```
ui/src/
├── api/
│   └── client.test.ts        — HTTP methods, error handling, download (13 tests)
├── components/
│   ├── DataTable.test.tsx     — Render, sort, pagination, error/empty/loading (15 tests)
│   ├── FileUploader.test.tsx  — Drag/drop, file select, upload spinner, drag-leave (8 tests)
│   ├── Layout.test.tsx        — Nav items, badge, collapsible ops, active state (10 tests)
│   ├── Pagination.test.tsx    — Render, disabled, page change callbacks (9 tests)
│   ├── ReviewCard.test.tsx    — Expand/collapse, enrichment, actions, disabled (16 tests)
│   └── StatusBadge.test.tsx   — Colors for all statuses, underscore replacement (12 tests)
└── pages/
    ├── HomePage.test.tsx       — Cards, links, descriptions (5 tests)
    ├── CompliancePage.test.tsx — Loading, SAR list, empty, error, review, batch select, batch review (16 tests)
    ├── CustomerDetailPage.test.tsx — Loading, error, not-found, info+accounts (9 tests)
    ├── CustomersPage.test.tsx  — Search, DataTable, error/empty/retry (13 tests)
    ├── OperationsPage.test.tsx — Tabs, upload result, search, error/empty (17 tests)
    ├── RulesPage.test.tsx      — CRUD form, status toggle, filter, error (16 tests)
    ├── TestPage.test.tsx       — Checkboxes, counts, generate, preview tabs, upload (18 tests)
    └── TransactionsPage.test.tsx — Filters, DataTable, search, tags, page change (18 tests)
```

**Coverage target:** ≥ 80% statements (current: 87.6%)

**Commands:**
```bash
cd ui && npm test              # Run all tests
cd ui && npm run test:coverage  # Run with coverage report
cd ui && npm run test:watch     # Watch mode
```

### 9.2 Playwright E2E Tests

**Test files (7 spec files):**
```
tests/e2e/ui/
├── rules.spec.ts
├── compliance.spec.ts
├── customers.spec.ts
├── transactions.spec.ts
├── operations.spec.ts
├── test_generator.spec.ts
└── layout.spec.ts
```

**Config:** `ui/playwright.config.ts` — auto-starts FastAPI backend (seeded DB) + Vite dev server via `webServer`

**Run command:**
```bash
cd ui && npx playwright test
```

---

## 10. Build & Deployment

### 10.1 Development

```bash
# Terminal 1 — Backend
python -m uvicorn src.bff.app:app --reload --port 8000

# Terminal 2 — Frontend
cd ui && npm run dev
```

Vite dev server on port 5173 proxies `/api/*` to `http://localhost:8000`.

### 10.2 Production

```bash
cd ui && npm run build
# Output: ui/dist/
```

FastAPI mounts `ui/dist/` via `StaticFiles` and serves `index.html` for any non-`/api/` path using a catch-all route `GET /{full_path:path}` (not `StaticFiles(html=True)`, because that only resolves `path/index.html`, not root `index.html` for deep paths).

### 10.3 Frontend Dependencies

- `react`, `react-dom`, `react-router-dom`
- `tailwindcss`, `@tailwindcss/vite`
- `typescript`, `@types/react`, `@types/react-dom`
- `vite`, `@vitejs/plugin-react`
- Dev: `vitest`, `@vitest/coverage-v8`, `@testing-library/react`, `@testing-library/jest-dom`, `jsdom`
- Dev: `playwright`, `@playwright/test`

---

## 11. Security Considerations

- All file downloads validated against path traversal (`Path(filename).name`)
- Upload file type validated server-side (`.csv` extension check)
- No authentication in v1 — API access unrestricted if exposed on network
- Generated files go to `work/` (already gitignored)
- CSP headers advisable if deploying to shared network (deferred)
