import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import CustomerDetailPage from "./CustomerDetailPage";
import type { CustomerDetail } from "../types";

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

let mockGet = vi.fn();

vi.mock("../api/client", () => ({
  api: {
    get: (...args: unknown[]) => mockGet(...args),
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
      </Routes>
    </MemoryRouter>
  );
}

describe("CustomerDetailPage", () => {
  beforeEach(() => {
    mockGet.mockReset();
    mockGet.mockResolvedValue(mockCustomer);
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
    mockGet.mockResolvedValue(sparseCustomer);
    renderPage("CUST003");
    await waitFor(() => {
      expect(screen.getByText("Charlie Brown")).toBeInTheDocument();
    });
    const dashes = screen.getAllByText("—");
    expect(dashes.length).toBeGreaterThanOrEqual(3);
    expect(screen.getByText("Accounts (0)")).toBeInTheDocument();
    expect(screen.getByText("No accounts found for this customer.")).toBeInTheDocument();
  });

  it("shows account name as dash when null", async () => {
    const customerNoName: CustomerDetail = {
      ...mockCustomer,
      accounts: [{ ...mockCustomer.accounts[0], name: null }],
    };
    mockGet.mockResolvedValue(customerNoName);
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Accounts (1)")).toBeInTheDocument();
    });
    const dashes = screen.getAllByText("—");
    expect(dashes.length).toBeGreaterThanOrEqual(1);
  });
});
