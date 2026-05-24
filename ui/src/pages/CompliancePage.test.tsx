import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import CompliancePage from "./CompliancePage";
import type { PendingSAR, PaginatedResponse } from "../types";

const mockSar: PendingSAR = {
  sar_id: "s1",
  transaction_id: "t1",
  upload_id: "u1",
  source_txn_id: "TXN001",
  account_id: "ACC001",
  customer_id: "CUST001",
  amount: 15000,
  counterparty: "Offshore Corp",
  city: "New York",
  state: "NY",
  country: "US",
  date: "2026-05-01",
  flag_details: { r1: "High Value Check" },
  risk_level: "high",
  triage_reasoning: "Suspicious pattern",
  enrichment: { customer_txn_count_30d: 12, customer_avg_30d: 8000, structuring_24h_count: 3, velocity_zscore: 2.5, dormancy_days: 0, account_type: "Checking" },
  rule_name: "High Value Check",
  rule_description: "Flags transactions over $10k",
  sar_content: "Suspicious transaction detected",
  sar_status: "pending_review",
  created_at: "2026-05-01T00:00:00Z",
};

const mockResponse: PaginatedResponse<PendingSAR> = {
  page: 1, per_page: 100, total: 1, items: [mockSar],
};

let mockGet = vi.fn();
let mockPatch = vi.fn();

vi.mock("../api/client", () => ({
  api: {
    get: (...args: unknown[]) => mockGet(...args),
    patch: (...args: unknown[]) => mockPatch(...args),
  },
  ApiError: class extends Error {
    status: number;
    constructor(status: number, msg: string) {
      super(msg);
      this.status = status;
    }
  },
}));

function renderPage(path = "/compliance") {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <CompliancePage />
    </MemoryRouter>
  );
}

describe("CompliancePage", () => {
  beforeEach(() => {
    mockGet.mockReset();
    mockPatch.mockReset();
    mockGet.mockResolvedValue(mockResponse);
  });

  it("renders heading", () => {
    renderPage();
    expect(screen.getByText("Compliance")).toBeInTheDocument();
  });

  it("shows loading skeleton on mount", () => {
    mockGet.mockReturnValue(new Promise(() => {}));
    renderPage();
    const skeletons = document.querySelectorAll(".animate-pulse");
    expect(skeletons.length).toBeGreaterThanOrEqual(1);
  });

  it("displays pending SAR count", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("1 pending")).toBeInTheDocument();
    });
  });

  it("renders ReviewCard for each SAR", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("TXN001")).toBeInTheDocument();
    });
    expect(screen.getByText("Offshore Corp")).toBeInTheDocument();
  });

  it("shows upload ID in subtitle when provided", () => {
    renderPage("/compliance?upload_id=u1");
    expect(screen.getByText("Upload: u1")).toBeInTheDocument();
  });

  it("shows 'All pending reviews' subtitle without upload_id", () => {
    renderPage();
    expect(screen.getByText("All pending reviews")).toBeInTheDocument();
  });

  it("shows completed state when no SARs returned", async () => {
    mockGet.mockResolvedValue({ ...mockResponse, items: [], total: 0 });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("You are all up to date.")).toBeInTheDocument();
    });
  });

  it("shows completed state on 404", async () => {
    const { ApiError } = await import("../api/client");
    mockGet.mockRejectedValue(new ApiError(404, "Not found"));
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("You are all up to date.")).toBeInTheDocument();
    });
  });

  it("shows error state with retry on non-404 errors", async () => {
    mockGet.mockRejectedValue(new Error("Server error"));
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Server error")).toBeInTheDocument();
    });
    expect(screen.getByText("Retry")).toBeInTheDocument();
  });

  it("retry re-fetches after error", async () => {
    mockGet.mockRejectedValueOnce(new Error("Server error")).mockResolvedValueOnce(mockResponse);
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Server error")).toBeInTheDocument();
    });
    mockGet.mockClear();
    mockGet.mockResolvedValue(mockResponse);
    fireEvent.click(screen.getByText("Retry"));
    await waitFor(() => {
      expect(screen.getByText("TXN001")).toBeInTheDocument();
    });
  });

  it("calls api.patch on review action", async () => {
    mockPatch.mockResolvedValue(undefined);
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Dismiss")).toBeInTheDocument();
    });
    fireEvent.click(screen.getByText("Dismiss"));
    await waitFor(() => {
      expect(mockPatch).toHaveBeenCalledWith("/api/sar/s1/review", { action: "dismissed", notes: "" });
    });
  });
});
