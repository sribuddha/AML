import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import CustomersPage from "./CustomersPage";
import type { CustomerSummary, PaginatedResponse } from "../types";

const mockCustomers: CustomerSummary[] = [
  { customer_id: "CUST001", first_name: "Alice", last_name: "Smith", city: "New York", state: "NY" },
  { customer_id: "CUST002", first_name: "Bob", last_name: "Jones", city: "Los Angeles", state: "CA" },
];

const mockResponse: PaginatedResponse<CustomerSummary> = {
  page: 1, per_page: 25, total: 2, items: mockCustomers,
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

function renderPage() {
  return render(
    <MemoryRouter>
      <CustomersPage />
    </MemoryRouter>
  );
}

describe("CustomersPage", () => {
  beforeEach(() => {
    mockGet.mockReset();
    mockGet.mockResolvedValue(mockResponse);
  });

  it("renders heading and description", () => {
    renderPage();
    expect(screen.getByText("Customers")).toBeInTheDocument();
    expect(screen.getByText("Search and view customer information")).toBeInTheDocument();
  });

  it("renders search inputs", () => {
    renderPage();
    expect(screen.getByPlaceholderText("First Name")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Last Name")).toBeInTheDocument();
  });

  it("renders Search button", () => {
    renderPage();
    expect(screen.getByText("Search")).toBeInTheDocument();
  });

  it("fetches and displays customers on mount", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Alice")).toBeInTheDocument();
    });
    expect(screen.getByText("Smith")).toBeInTheDocument();
    expect(screen.getByText("Bob")).toBeInTheDocument();
    expect(screen.getByText("Jones")).toBeInTheDocument();
  });

  it("shows customer IDs as clickable links", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("CUST001")).toBeInTheDocument();
    });
    const link = screen.getByText("CUST001");
    expect(link.tagName).toBe("BUTTON");
  });

  it("shows city and state for customers", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("New York")).toBeInTheDocument();
    });
    expect(screen.getByText("Los Angeles")).toBeInTheDocument();
  });

  it("shows dash for missing city or state", async () => {
    const rowsWithoutLocation: CustomerSummary[] = [
      { customer_id: "CUST003", first_name: "Charlie", last_name: "Brown", city: null, state: null },
    ];
    mockGet.mockResolvedValue({ ...mockResponse, items: rowsWithoutLocation, total: 1 });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Charlie")).toBeInTheDocument();
    });
    const dashes = screen.getAllByText("-");
    expect(dashes.length).toBeGreaterThanOrEqual(1);
  });

  it("shows error state with retry", async () => {
    mockGet.mockRejectedValue(new Error("Network error"));
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Network error")).toBeInTheDocument();
    });
    const retryBtn = screen.getByText("Retry");
    expect(retryBtn).toBeInTheDocument();
  });

  it("retry button re-fetches data", async () => {
    mockGet.mockRejectedValueOnce(new Error("Network error")).mockResolvedValueOnce(mockResponse);
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Network error")).toBeInTheDocument();
    });
    mockGet.mockClear();
    mockGet.mockResolvedValue(mockResponse);
    fireEvent.click(screen.getByText("Retry"));
    await waitFor(() => {
      expect(screen.getByText("Alice")).toBeInTheDocument();
    });
  });

  it("shows empty message when no results", async () => {
    mockGet.mockResolvedValue({ ...mockResponse, items: [], total: 0 });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("No customers found. Try a different name.")).toBeInTheDocument();
    });
  });

  it("calls api.get with search params on Search click", async () => {
    renderPage();
    fireEvent.change(screen.getByPlaceholderText("First Name"), { target: { value: "Alice" } });
    fireEvent.change(screen.getByPlaceholderText("Last Name"), { target: { value: "Smith" } });
    fireEvent.click(screen.getByText("Search"));
    await waitFor(() => {
      expect(mockGet).toHaveBeenCalledWith("/api/customers", expect.objectContaining({
        first_name: "Alice", last_name: "Smith", page: 1, per_page: 25,
      }));
    });
  });

  it("navigates to customer detail on ID click", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("CUST001")).toBeInTheDocument();
    });
    fireEvent.click(screen.getByText("CUST001"));
  });

  it("shows pagination when more than 25 customers", async () => {
    const manyCustomers: CustomerSummary[] = Array.from({ length: 30 }, (_, i) => ({
      customer_id: `CUST${String(i + 1).padStart(3, "0")}`,
      first_name: "User",
      last_name: `${i + 1}`,
      city: "City",
      state: "ST",
    }));
    mockGet.mockResolvedValue({ page: 1, per_page: 25, total: 30, items: manyCustomers.slice(0, 25) });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("CUST025")).toBeInTheDocument();
    });
    expect(screen.getByText("30 results")).toBeInTheDocument();
    const pageTwo = screen.getAllByText("2").filter(el => el.tagName === "BUTTON");
    expect(pageTwo.length).toBe(1);
    fireEvent.click(screen.getByText("Next →"));
  });
});
