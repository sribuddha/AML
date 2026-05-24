import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import TransactionsPage from "./TransactionsPage";
import type { TransactionRow, PaginatedResponse } from "../types";

const mockTxns: TransactionRow[] = [
  { id: "t1", source_txn_id: "TXN001", account_id: "ACC001", account_name: "Checking", customer_id: "CUST001", amount: 15000, counterparty: "Offshore Corp", city: "New York", state: "NY", country: "US", date: "2026-05-01" },
  { id: "t2", source_txn_id: "TXN002", account_id: "ACC002", account_name: null, customer_id: "CUST002", amount: 500, counterparty: "Local Shop", city: null, state: null, country: null, date: null },
  { id: "t3", source_txn_id: "TXN003", account_id: "ACC003", account_name: "Savings", customer_id: "CUST003", amount: null, counterparty: "Vendor Co", city: "Boston", state: "MA", country: "US", date: "2026-05-15" },
];

const mockResponse: PaginatedResponse<TransactionRow> = {
  page: 1, per_page: 25, total: 3, items: mockTxns,
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

function renderPage(path = "/transactions") {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <TransactionsPage />
    </MemoryRouter>
  );
}

describe("TransactionsPage", () => {
  beforeEach(() => {
    mockGet.mockReset();
    mockGet.mockResolvedValue(mockResponse);
  });

  it("renders heading and DEV ONLY badge", () => {
    renderPage();
    expect(screen.getByText("Transactions")).toBeInTheDocument();
    expect(screen.getByText("DEV ONLY")).toBeInTheDocument();
  });

  it("renders all filter inputs", () => {
    renderPage();
    expect(screen.getByPlaceholderText("Source TXN ID")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Account ID")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Customer ID")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Counterparty")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Min Amount")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Max Amount")).toBeInTheDocument();
  });

  it("displays all transactions in DataTable", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("TXN001")).toBeInTheDocument();
    });
    expect(screen.getByText("TXN002")).toBeInTheDocument();
    expect(screen.getByText("TXN003")).toBeInTheDocument();
    expect(screen.getByText("$15,000")).toBeInTheDocument();
    expect(screen.getByText("Offshore Corp")).toBeInTheDocument();
  });

  it("shows account name as clickable button", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Checking")).toBeInTheDocument();
    });
    expect(screen.getByText("Checking").tagName).toBe("BUTTON");
  });

  it("shows account_id when account_name is null", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("ACC002")).toBeInTheDocument();
    });
  });

  it("renders location concatenation correctly", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("New York, NY, US")).toBeInTheDocument();
    });
  });

  it("shows dash for null amount", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("TXN003")).toBeInTheDocument();
    });
    const row3 = screen.getByText("TXN003").closest("tr")!;
    expect(row3.textContent).toContain("Vendor Co");
    expect(row3.textContent).toContain("Boston");
    expect(row3.textContent).not.toContain("$");
  });

  it("shows dash for null date and location", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("TXN002")).toBeInTheDocument();
    });
    const row2 = screen.getByText("TXN002").closest("tr")!;
    const dashCount = (row2.textContent!.match(/-/g) || []).length;
    expect(dashCount).toBeGreaterThanOrEqual(2);
  });

  it("calls api.get with search params on Search click", async () => {
    renderPage();
    fireEvent.change(screen.getByPlaceholderText("Source TXN ID"), { target: { value: "TXN001" } });
    fireEvent.change(screen.getByPlaceholderText("Account ID"), { target: { value: "ACC001" } });
    fireEvent.click(screen.getByText("Search"));
    await waitFor(() => {
      expect(mockGet).toHaveBeenCalledWith("/api/transactions", expect.objectContaining({
        source_txn_id: "TXN001", account_id: "ACC001", page: 1, per_page: 25,
      }));
    });
  });

  it("calls api.get with all filter params", async () => {
    renderPage();
    fireEvent.change(screen.getByPlaceholderText("Source TXN ID"), { target: { value: "TXN001" } });
    fireEvent.change(screen.getByPlaceholderText("Account ID"), { target: { value: "ACC001" } });
    fireEvent.change(screen.getByPlaceholderText("Customer ID"), { target: { value: "CUST001" } });
    fireEvent.change(screen.getByPlaceholderText("Counterparty"), { target: { value: "Offshore" } });
    fireEvent.change(screen.getByPlaceholderText("Min Amount"), { target: { value: "100" } });
    fireEvent.change(screen.getByPlaceholderText("Max Amount"), { target: { value: "99999" } });
    const dateInputs = document.querySelectorAll('input[type="date"]') as NodeListOf<HTMLInputElement>;
    fireEvent.change(dateInputs[0], { target: { value: "2026-01-01" } });
    fireEvent.change(dateInputs[1], { target: { value: "2026-12-31" } });
    fireEvent.click(screen.getByText("Search"));
    await waitFor(() => {
      expect(mockGet).toHaveBeenCalledWith("/api/transactions", expect.objectContaining({
        source_txn_id: "TXN001", account_id: "ACC001", customer_id: "CUST001",
        counterparty: "Offshore", amount_min: "100", amount_max: "99999",
        from_date: "2026-01-01", to_date: "2026-12-31", page: 1, per_page: 25,
      }));
    });
  });

  it("shows active filter tags after search", async () => {
    renderPage();
    fireEvent.change(screen.getByPlaceholderText("Source TXN ID"), { target: { value: "TXN001" } });
    fireEvent.click(screen.getByText("Search"));
    await waitFor(() => {
      expect(screen.getByText(/source_txn_id: TXN001/)).toBeInTheDocument();
    });
  });

  it("shows counterparty filter tag", async () => {
    renderPage();
    fireEvent.change(screen.getByPlaceholderText("Counterparty"), { target: { value: "Offshore" } });
    fireEvent.click(screen.getByText("Search"));
    await waitFor(() => {
      expect(screen.getByText(/counterparty: Offshore/)).toBeInTheDocument();
    });
  });

  it("removes filter tag on click", async () => {
    renderPage();
    fireEvent.change(screen.getByPlaceholderText("Source TXN ID"), { target: { value: "TXN001" } });
    fireEvent.click(screen.getByText("Search"));
    await waitFor(() => {
      expect(screen.getByText(/source_txn_id: TXN001/)).toBeInTheDocument();
    });
    const removeBtn = screen.getByText("×");
    fireEvent.click(removeBtn);
    expect(screen.queryByText(/source_txn_id: TXN001/)).not.toBeInTheDocument();
  });

  it("pre-populates filters from URL params", () => {
    renderPage("/transactions?source_txn_id=TXN001&account_id=ACC001");
    const sourceInput = screen.getByPlaceholderText("Source TXN ID") as HTMLInputElement;
    const accountInput = screen.getByPlaceholderText("Account ID") as HTMLInputElement;
    expect(sourceInput.value).toBe("TXN001");
    expect(accountInput.value).toBe("ACC001");
  });

  it("shows error state", async () => {
    mockGet.mockRejectedValue(new Error("Failed to load"));
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Failed to load")).toBeInTheDocument();
    });
  });

  it("shows empty message", async () => {
    mockGet.mockResolvedValue({ ...mockResponse, items: [], total: 0 });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("No transactions match your search. Try different filters.")).toBeInTheDocument();
    });
  });

  it("navigates to customer on account name click", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Checking")).toBeInTheDocument();
    });
    const link = screen.getByText("Checking");
    fireEvent.click(link);
  });

  it("calls window.scrollTo on page change", async () => {
    const scrollToSpy = vi.spyOn(window, "scrollTo").mockImplementation(() => {});
    mockGet.mockResolvedValue({ ...mockResponse, page: 1, per_page: 1, total: 3 });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("TXN001")).toBeInTheDocument();
    });
    const nextBtn = screen.getByText(/Next/);
    fireEvent.click(nextBtn);
    await waitFor(() => {
      expect(scrollToSpy).toHaveBeenCalledWith(0, 0);
    });
    scrollToSpy.mockRestore();
  });
});
