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
  customer_first_name: "John",
  customer_last_name: "Doe",
  amount: 15000,
  counterparty: "Offshore Corp",
  city: "New York",
  state: "NY",
  country: "US",
  date: "2026-05-01",
  flag_details: { r1: "High Value Check" },
  risk_level: "high",
  triage_reasoning: "Suspicious pattern",
  llm_confidence: null,
  triage_stage: null,
  enrichment: { customer_txn_count_30d: 12, customer_avg_30d: 8000, structuring_24h_count: 3, velocity_zscore: 2.5, dormancy_days: 0, account_type: "Checking" },
  rule_name: "High Value Check",
  rule_description: "Flags transactions over $10k",
  sar_content: "Suspicious transaction detected",
  sar_status: "pending_review",
  created_at: "2026-05-01T00:00:00Z",
};

const mockSar2: PendingSAR = {
  sar_id: "s2",
  transaction_id: "t2",
  upload_id: "u1",
  source_txn_id: "TXN002",
  account_id: "ACC002",
  customer_id: "CUST002",
  customer_first_name: "Jane",
  customer_last_name: "Smith",
  amount: 25000,
  counterparty: "Shell Co",
  city: "London",
  state: "",
  country: "GB",
  date: "2026-05-02",
  flag_details: { r2: "Large Cash" },
  risk_level: "high",
  triage_reasoning: "Unusual pattern",
  llm_confidence: null,
  triage_stage: null,
  enrichment: { customer_txn_count_30d: 5, customer_avg_30d: 5000, structuring_24h_count: 0, velocity_zscore: 1.2, dormancy_days: 90, account_type: "Savings" },
  rule_name: "Large Cash",
  rule_description: "Flags large cash transactions",
  sar_content: "Large cash transaction detected",
  sar_status: "pending_review",
  created_at: "2026-05-02T00:00:00Z",
};

const mockResponse: PaginatedResponse<PendingSAR> = {
  page: 1, per_page: 100, total: 1, items: [mockSar],
};

let mockGet = vi.fn();
let mockPatch = vi.fn();
let mockPost = vi.fn();

vi.mock("../api/client", () => ({
  api: {
    get: (...args: unknown[]) => mockGet(...args),
    patch: (...args: unknown[]) => mockPatch(...args),
    post: (...args: unknown[]) => mockPost(...args),
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
    mockPost.mockReset();
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

  it("renders checkboxes for each SAR", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("TXN001")).toBeInTheDocument();
    });
    const checkboxes = screen.getAllByRole("checkbox");
    expect(checkboxes.length).toBeGreaterThanOrEqual(1);
  });

  it("toggles selection on checkbox click", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("TXN001")).toBeInTheDocument();
    });
    const checkbox = screen.getAllByRole("checkbox")[1];
    expect(checkbox).not.toBeChecked();
    fireEvent.click(checkbox);
    expect(checkbox).toBeChecked();
    fireEvent.click(checkbox);
    expect(checkbox).not.toBeChecked();
  });

  it("shows 'Select all' when nothing selected", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Select all")).toBeInTheDocument();
    });
  });

  it("shows selected count when items selected", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("TXN001")).toBeInTheDocument();
    });
    const checkbox = screen.getAllByRole("checkbox")[1];
    fireEvent.click(checkbox);
    expect(screen.getByText("1 selected")).toBeInTheDocument();
  });

  it("toggles select all", async () => {
    mockGet.mockResolvedValue({ ...mockResponse, items: [mockSar, mockSar2], total: 2 });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("TXN002")).toBeInTheDocument();
    });
    const selectAllCheckbox = screen.getAllByRole("checkbox")[0];
    fireEvent.click(selectAllCheckbox);
    expect(screen.getByText("2 selected")).toBeInTheDocument();
    fireEvent.click(selectAllCheckbox);
    expect(screen.getByText("Select all")).toBeInTheDocument();
  });

  it("disables batch buttons when nothing selected", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Accept All")).toBeInTheDocument();
    });
    expect(screen.getByText("Accept All").closest("button")).toBeDisabled();
    expect(screen.getByText("Dismiss All").closest("button")).toBeDisabled();
  });

  it("calls api.post on Accept All with selected sar_ids", async () => {
    mockPost.mockResolvedValue({ reviewed: 1, action: "confirmed" });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("TXN001")).toBeInTheDocument();
    });
    const checkbox = screen.getAllByRole("checkbox")[1];
    fireEvent.click(checkbox);
    fireEvent.click(screen.getByText("Accept All"));
    await waitFor(() => {
      expect(mockPost).toHaveBeenCalledWith("/api/sar/batch-review", { sar_ids: ["s1"], action: "confirmed" });
    });
  });

  it("calls api.post on Dismiss All with selected sar_ids", async () => {
    mockPost.mockResolvedValue({ reviewed: 1, action: "dismissed" });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("TXN001")).toBeInTheDocument();
    });
    const checkbox = screen.getAllByRole("checkbox")[1];
    fireEvent.click(checkbox);
    fireEvent.click(screen.getByText("Dismiss All"));
    await waitFor(() => {
      expect(mockPost).toHaveBeenCalledWith("/api/sar/batch-review", { sar_ids: ["s1"], action: "dismissed" });
    });
  });

  it("shows customer name chip when customer_id in URL", async () => {
    mockGet.mockResolvedValue(mockResponse);
    renderPage("/compliance?customer_id=CUST001");
    await waitFor(() => {
      expect(screen.getByText("All pending reviews")).toBeInTheDocument();
    });
    const subtitle = screen.getByText("All pending reviews").parentElement!;
    expect(subtitle.textContent).toContain("John Doe");
    expect(subtitle.querySelector("button")?.textContent).toBe("×");
  });

  it("clears customer filter when × chip clicked", async () => {
    mockGet.mockResolvedValueOnce(mockResponse).mockResolvedValueOnce({ ...mockResponse, items: [], total: 0 });
    renderPage("/compliance?customer_id=CUST001");
    await waitFor(() => {
      expect(screen.getByText("All pending reviews")).toBeInTheDocument();
    });
    const subtitle = screen.getByText("All pending reviews").parentElement!;
    fireEvent.click(subtitle.querySelector("button")!);
    await waitFor(() => {
      expect(mockGet).toHaveBeenCalledTimes(2);
    });
  });

  it("shows 'View all pending reviews' link when completed with customer filter", async () => {
    mockGet.mockResolvedValue({ ...mockResponse, items: [], total: 0 });
    renderPage("/compliance?customer_id=CUST001");
    await waitFor(() => {
      expect(screen.getByText("You are all up to date.")).toBeInTheDocument();
    });
    const link = screen.getByText("View all pending reviews");
    expect(link).toBeInTheDocument();
    expect(link).toHaveAttribute("href", "/compliance");
  });

  it("shows customer filter input and Filter/Clear buttons", async () => {
    mockGet.mockResolvedValue(mockResponse);
    renderPage("/compliance?customer_id=CUST001");
    await waitFor(() => {
      expect(screen.getByText("TXN001")).toBeInTheDocument();
    });
    expect(screen.getByPlaceholderText("Filter by customer ID...")).toBeInTheDocument();
    expect(screen.getByText("Filter")).toBeInTheDocument();
    expect(screen.getByText("Clear")).toBeInTheDocument();
  });

  it("filters by customer ID via input and Filter button", async () => {
    mockGet.mockResolvedValue(mockResponse);
    renderPage("/compliance");
    await waitFor(() => {
      expect(screen.getByText("TXN001")).toBeInTheDocument();
    });
    const input = screen.getByPlaceholderText("Filter by customer ID...");
    fireEvent.change(input, { target: { value: "CUST001" } });
    fireEvent.click(screen.getByText("Filter"));
    await waitFor(() => {
      expect(mockGet).toHaveBeenCalledWith("/api/sar/pending", {
        upload_id: undefined,
        customer_id: "CUST001",
        per_page: 100,
      });
    });
  });

  it("calls alert on batch review error", async () => {
    const alertSpy = vi.spyOn(window, "alert").mockImplementation(() => {});
    mockPost.mockRejectedValue(new Error("Batch failed"));
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("TXN001")).toBeInTheDocument();
    });
    const checkbox = screen.getAllByRole("checkbox")[1];
    fireEvent.click(checkbox);
    fireEvent.click(screen.getByText("Accept All"));
    await waitFor(() => {
      expect(alertSpy).toHaveBeenCalledWith("Batch failed");
    });
    alertSpy.mockRestore();
  });

  it("shows alert on individual review error", async () => {
    const alertSpy = vi.spyOn(window, "alert").mockImplementation(() => {});
    mockPatch.mockRejectedValue(new Error("Review failed"));
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Dismiss")).toBeInTheDocument();
    });
    fireEvent.click(screen.getByText("Dismiss"));
    await waitFor(() => {
      expect(alertSpy).toHaveBeenCalledWith("Review failed");
    });
    alertSpy.mockRestore();
  });

  it("clears customer filter via Clear button", async () => {
    mockGet.mockResolvedValueOnce(mockResponse).mockResolvedValueOnce({ ...mockResponse, items: [], total: 0 });
    renderPage("/compliance?customer_id=CUST001");
    await waitFor(() => {
      expect(screen.getByText("TXN001")).toBeInTheDocument();
    });
    fireEvent.click(screen.getByText("Clear"));
    await waitFor(() => {
      expect(mockGet).toHaveBeenCalledTimes(2);
    });
  });

  it("filters by Enter key in customer input", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("TXN001")).toBeInTheDocument();
    });
    const input = screen.getByPlaceholderText("Filter by customer ID...");
    fireEvent.change(input, { target: { value: "CUST005" } });
    fireEvent.keyDown(input, { key: "Enter", code: "Enter" });
    await waitFor(() => {
      expect(mockGet).toHaveBeenCalledWith("/api/sar/pending", {
        upload_id: undefined,
        customer_id: "CUST005",
        per_page: 100,
      });
    });
  });

  it("filters by risk level pills", async () => {
    const lowRisk: PendingSAR = { ...mockSar, sar_id: "s3", risk_level: "low", transaction_id: "t3", source_txn_id: "TXN003" };
    mockGet.mockResolvedValue({ ...mockResponse, items: [mockSar, lowRisk], total: 2 });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("TXN001")).toBeInTheDocument();
    });
    expect(screen.getByText("2 pending")).toBeInTheDocument();
    fireEvent.click(screen.getByText("High"));
    await waitFor(() => {
      expect(screen.getByText((content) => content.includes("(1 high)"))).toBeInTheDocument();
    });
  });
});
