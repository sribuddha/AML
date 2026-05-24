import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import CustomerDetailPage from "./CustomerDetailPage";
import type { CustomerDetail, PendingSAR, PaginatedResponse } from "../types";

const mockCustomer: CustomerDetail = {
  customer_id: "CUST001",
  first_name: "Alice",
  last_name: "Smith",
  address_line: "123 Main St",
  city: "New York",
  state: "NY",
  zip: "10001",
  accounts: [
    { account_id: "ACC001", name: "Checking", bank: "Chase", type: "checking", date_opened: "2024-01-15" },
    { account_id: "ACC002", name: "Savings", bank: "Chase", type: "savings", date_opened: "2024-06-01" },
  ],
};

const mockSar: PendingSAR = {
  sar_id: "s1",
  transaction_id: "t1",
  upload_id: "u1",
  source_txn_id: "TXN001",
  account_id: "ACC001",
  customer_id: "CUST001",
  customer_first_name: "Alice",
  customer_last_name: "Smith",
  amount: 15000,
  counterparty: "Offshore Corp",
  city: "New York",
  state: "NY",
  country: "US",
  date: "2026-05-01",
  flag_details: { r1: "High Value Check" },
  risk_level: "high",
  triage_reasoning: "Suspicious pattern",
  enrichment: null,
  rule_name: "High Value Check",
  rule_description: "Flags transactions over $10k",
  sar_content: "Suspicious transaction detected",
  sar_status: "pending_review",
  created_at: "2026-05-01T00:00:00Z",
};

const mockSarsResponse: PaginatedResponse<PendingSAR> = {
  page: 1, per_page: 100, total: 1, items: [mockSar],
};

const emptySarsResponse: PaginatedResponse<PendingSAR> = {
  page: 1, per_page: 100, total: 0, items: [],
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

function renderPage(customerId = "CUST001") {
  return render(
    <MemoryRouter initialEntries={[`/customers/${customerId}`]}>
      <Routes>
        <Route path="/customers/:customerId" element={<CustomerDetailPage />} />
        <Route path="/customers" element={<div>Customers List</div>} />
        <Route path="/transactions" element={<div>Transactions Page</div>} />
        <Route path="/compliance" element={<div>Compliance Page</div>} />
      </Routes>
    </MemoryRouter>
  );
}

describe("CustomerDetailPage", () => {
  let mockGetImpl = (url: string) => {
    if (url.includes("/api/sar/pending")) return Promise.resolve(emptySarsResponse);
    return Promise.resolve(mockCustomer);
  };

  beforeEach(() => {
    mockGet.mockReset();
    mockPatch.mockReset();
    mockPost.mockReset();
    mockGet.mockImplementation(mockGetImpl);
  });

  it("shows loading skeleton on mount", () => {
    mockGet.mockReturnValue(new Promise(() => {}));
    renderPage();
    const skeletons = document.querySelectorAll(".animate-pulse");
    expect(skeletons.length).toBeGreaterThanOrEqual(1);
  });

  it("displays customer name and ID", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Alice Smith")).toBeInTheDocument();
    });
    expect(screen.getByText("CUST001")).toBeInTheDocument();
  });

  it("shows customer info details", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("123 Main St")).toBeInTheDocument();
    });
    expect(screen.getByText("New York")).toBeInTheDocument();
    expect(screen.getByText("NY")).toBeInTheDocument();
    expect(screen.getByText("10001")).toBeInTheDocument();
  });

  it("shows accounts table with count", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Accounts (2)")).toBeInTheDocument();
    });
    expect(screen.getByText("ACC001")).toBeInTheDocument();
    expect(screen.getByText("ACC002")).toBeInTheDocument();
    expect(screen.getByText("Checking")).toBeInTheDocument();
    expect(screen.getByText("Savings")).toBeInTheDocument();
  });

  it("shows back link", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText(/Back to customers/)).toBeInTheDocument();
    });
  });

  it("shows error state on fetch failure", async () => {
    mockGet.mockRejectedValue(new Error("Server error"));
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Failed to load customer")).toBeInTheDocument();
    });
    expect(screen.getByText("Server error")).toBeInTheDocument();
    expect(screen.getByText(/Back to customers/)).toBeInTheDocument();
  });

  it("shows not-found when data is null after load", async () => {
    mockGet.mockResolvedValue(null);
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Customer not found")).toBeInTheDocument();
    });
  });

  it("shows dash for missing fields", async () => {
    const sparseCustomer: CustomerDetail = {
      customer_id: "CUST003",
      first_name: "Charlie",
      last_name: "Brown",
      address_line: null,
      city: null,
      state: null,
      zip: null,
      accounts: [],
    };
    mockGet.mockImplementation((url: string) => {
      if (url.includes("/api/sar/pending")) return Promise.resolve(emptySarsResponse);
      return Promise.resolve(sparseCustomer);
    });
    renderPage("CUST003");
    await waitFor(() => {
      expect(screen.getByText("Charlie Brown")).toBeInTheDocument();
    });
    const dashes = screen.getAllByText("—");
    expect(dashes.length).toBeGreaterThanOrEqual(3);
    expect(screen.getByText("Accounts (0)")).toBeInTheDocument();
    expect(screen.getByText("No accounts found for this customer.")).toBeInTheDocument();
  });

  it("shows zero pending SARs by default", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Pending SARs (0)")).toBeInTheDocument();
    });
    expect(screen.getByText("No pending SARs for this customer.")).toBeInTheDocument();
  });

  it("displays pending SARs when present", async () => {
    mockGet.mockImplementation((url: string) => {
      if (url.includes("/api/sar/pending")) return Promise.resolve(mockSarsResponse);
      return Promise.resolve(mockCustomer);
    });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Pending SARs (1)")).toBeInTheDocument();
    });
    expect(screen.getByText("TXN001")).toBeInTheDocument();
    expect(screen.getByText("Select all")).toBeInTheDocument();
  });

  it("shows Accept All / Dismiss All buttons when SARs present", async () => {
    mockGet.mockImplementation((url: string) => {
      if (url.includes("/api/sar/pending")) return Promise.resolve(mockSarsResponse);
      return Promise.resolve(mockCustomer);
    });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Accept All")).toBeInTheDocument();
    });
    expect(screen.getByText("Dismiss All")).toBeInTheDocument();
  });

  it("calls api.patch on review action", async () => {
    mockGet.mockImplementation((url: string) => {
      if (url.includes("/api/sar/pending")) return Promise.resolve(mockSarsResponse);
      return Promise.resolve(mockCustomer);
    });
    mockPatch.mockResolvedValue({});
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Confirm")).toBeInTheDocument();
    });
    fireEvent.click(screen.getByText("Confirm"));
    await waitFor(() => {
      expect(mockPatch).toHaveBeenCalledWith("/api/sar/s1/review", { action: "confirmed", notes: "" });
    });
  });

  it("shows account name as dash when null", async () => {
    const customerNoName: CustomerDetail = {
      ...mockCustomer,
      accounts: [{ ...mockCustomer.accounts[0], name: null }],
    };
    mockGet.mockImplementation((url: string) => {
      if (url.includes("/api/sar/pending")) return Promise.resolve(emptySarsResponse);
      return Promise.resolve(customerNoName);
    });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Accounts (1)")).toBeInTheDocument();
    });
    const dashes = screen.getAllByText("—");
    expect(dashes.length).toBeGreaterThanOrEqual(1);
  });

  it("shows SARs loading skeleton", async () => {
    mockGet.mockImplementation((url: string) => {
      if (url.includes("/api/sar/pending")) return new Promise(() => {});
      return Promise.resolve(mockCustomer);
    });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Pending SARs (0)")).toBeInTheDocument();
    });
    const skeletons = document.querySelectorAll(".animate-pulse");
    expect(skeletons.length).toBeGreaterThanOrEqual(2);
  });

  it("shows SARs error state with retry", async () => {
    mockGet.mockImplementation((url: string) => {
      if (url.includes("/api/sar/pending")) return Promise.reject(new Error("SAR load failed"));
      return Promise.resolve(mockCustomer);
    });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("SAR load failed")).toBeInTheDocument();
    });
    expect(screen.getByText("Retry")).toBeInTheDocument();
  });

  it("retries SARs fetch on retry click", async () => {
    let sarsCall = 0;
    mockGet.mockImplementation((url: string) => {
      if (url.includes("/api/sar/pending")) {
        sarsCall++;
        if (sarsCall === 1) return Promise.reject(new Error("SAR fail"));
        return Promise.resolve(mockSarsResponse);
      }
      return Promise.resolve(mockCustomer);
    });
    renderPage();
    await waitFor(() => expect(screen.getByText("SAR fail")).toBeInTheDocument());
    fireEvent.click(screen.getByText("Retry"));
    await waitFor(() => {
      expect(screen.getByText("Pending SARs (1)")).toBeInTheDocument();
    });
  });

  it("handles 404 for SARs as empty", async () => {
    const { ApiError } = await import("../api/client");
    mockGet.mockImplementation((url: string) => {
      if (url.includes("/api/sar/pending")) return Promise.reject(new ApiError(404, "Not found"));
      return Promise.resolve(mockCustomer);
    });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("No pending SARs for this customer.")).toBeInTheDocument();
    });
  });

  it("toggles select all for SARs", async () => {
    mockGet.mockImplementation((url: string) => {
      if (url.includes("/api/sar/pending")) return Promise.resolve(mockSarsResponse);
      return Promise.resolve(mockCustomer);
    });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Select all")).toBeInTheDocument();
    });
    const checkbox = screen.getAllByRole("checkbox")[0];
    fireEvent.click(checkbox);
    expect(screen.getByText("1 selected")).toBeInTheDocument();
    fireEvent.click(checkbox);
    expect(screen.getByText("Select all")).toBeInTheDocument();
  });

  it("calls api.post on Accept All batch review", async () => {
    mockGet.mockImplementation((url: string) => {
      if (url.includes("/api/sar/pending")) return Promise.resolve(mockSarsResponse);
      return Promise.resolve(mockCustomer);
    });
    mockPost.mockResolvedValue({ reviewed: 1 });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Accept All")).toBeInTheDocument();
    });
    const selectAll = screen.getAllByRole("checkbox")[0];
    fireEvent.click(selectAll);
    fireEvent.click(screen.getByText("Accept All"));
    await waitFor(() => {
      expect(mockPost).toHaveBeenCalledWith("/api/sar/batch-review", { sar_ids: ["s1"], action: "confirmed" });
    });
  });

  it("dispatches custom event on batch review", async () => {
    const dispatchSpy = vi.spyOn(window, "dispatchEvent");
    mockGet.mockImplementation((url: string) => {
      if (url.includes("/api/sar/pending")) return Promise.resolve(mockSarsResponse);
      return Promise.resolve(mockCustomer);
    });
    mockPost.mockResolvedValue({ reviewed: 1 });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Accept All")).toBeInTheDocument();
    });
    const selectAll = screen.getAllByRole("checkbox")[0];
    fireEvent.click(selectAll);
    fireEvent.click(screen.getByText("Accept All"));
    await waitFor(() => {
      expect(dispatchSpy).toHaveBeenCalledWith(expect.objectContaining({ type: "sar-reviewed" }));
    });
    dispatchSpy.mockRestore();
  });

  it("shows alert on batch review error", async () => {
    const alertSpy = vi.spyOn(window, "alert").mockImplementation(() => {});
    mockGet.mockImplementation((url: string) => {
      if (url.includes("/api/sar/pending")) return Promise.resolve(mockSarsResponse);
      return Promise.resolve(mockCustomer);
    });
    mockPost.mockRejectedValue(new Error("Batch failed"));
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Accept All")).toBeInTheDocument();
    });
    const selectAll = screen.getAllByRole("checkbox")[0];
    fireEvent.click(selectAll);
    fireEvent.click(screen.getByText("Accept All"));
    await waitFor(() => {
      expect(alertSpy).toHaveBeenCalledWith("Batch failed");
    });
    alertSpy.mockRestore();
  });

  it("shows alert on individual review error", async () => {
    const alertSpy = vi.spyOn(window, "alert").mockImplementation(() => {});
    mockGet.mockImplementation((url: string) => {
      if (url.includes("/api/sar/pending")) return Promise.resolve(mockSarsResponse);
      return Promise.resolve(mockCustomer);
    });
    mockPatch.mockRejectedValue(new Error("Review failed"));
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Confirm")).toBeInTheDocument();
    });
    fireEvent.click(screen.getByText("Confirm"));
    await waitFor(() => {
      expect(alertSpy).toHaveBeenCalledWith("Review failed");
    });
    alertSpy.mockRestore();
  });

  it("clicks Back to customers in error state", async () => {
    mockGet.mockRejectedValue(new Error("Server error"));
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Failed to load customer")).toBeInTheDocument();
    });
    fireEvent.click(screen.getByText(/Back to customers/));
    expect(screen.getByText("Customers List")).toBeInTheDocument();
  });

  it("clicks Back to customers in not-found state", async () => {
    mockGet.mockResolvedValue(null);
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Customer not found")).toBeInTheDocument();
    });
    fireEvent.click(screen.getByText(/Back to customers/));
    expect(screen.getByText("Customers List")).toBeInTheDocument();
  });

  it("clicks account ID to navigate to transactions", async () => {
    mockGet.mockImplementation((url: string) => {
      if (url.includes("/api/sar/pending")) return Promise.resolve(emptySarsResponse);
      return Promise.resolve(mockCustomer);
    });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("ACC001")).toBeInTheDocument();
    });
    fireEvent.click(screen.getByText("ACC001"));
    expect(screen.getByText("Transactions Page")).toBeInTheDocument();
  });

  it("calls api.post on Dismiss All batch review", async () => {
    mockGet.mockImplementation((url: string) => {
      if (url.includes("/api/sar/pending")) return Promise.resolve(mockSarsResponse);
      return Promise.resolve(mockCustomer);
    });
    mockPost.mockResolvedValue({ reviewed: 1 });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Dismiss All")).toBeInTheDocument();
    });
    const selectAll = screen.getAllByRole("checkbox")[0];
    fireEvent.click(selectAll);
    fireEvent.click(screen.getByText("Dismiss All"));
    await waitFor(() => {
      expect(mockPost).toHaveBeenCalledWith("/api/sar/batch-review", { sar_ids: ["s1"], action: "dismissed" });
    });
  });

  it("toggles individual SAR checkbox", async () => {
    mockGet.mockImplementation((url: string) => {
      if (url.includes("/api/sar/pending")) return Promise.resolve(mockSarsResponse);
      return Promise.resolve(mockCustomer);
    });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Select all")).toBeInTheDocument();
    });
    const individualCheckbox = screen.getAllByRole("checkbox")[1];
    expect(individualCheckbox).not.toBeChecked();
    fireEvent.click(individualCheckbox);
    expect(individualCheckbox).toBeChecked();
  });
});
