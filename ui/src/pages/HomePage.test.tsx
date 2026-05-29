import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import HomePage from "./HomePage";

function renderPage() {
  return render(
    <MemoryRouter>
      <HomePage />
    </MemoryRouter>
  );
}

describe("HomePage", () => {
  it("renders AML Monitor heading", () => {
    renderPage();
    expect(screen.getByText("AML Monitor")).toBeInTheDocument();
  });

  it("renders all 5 navigation cards", () => {
    renderPage();
    expect(screen.getByText("Compliance")).toBeInTheDocument();
    expect(screen.getByText("Operations")).toBeInTheDocument();
    expect(screen.getByText("Rules")).toBeInTheDocument();
    expect(screen.getByText("Customers")).toBeInTheDocument();
    expect(screen.getByText("Transactions")).toBeInTheDocument();
  });

  it("renders subtitle", () => {
    renderPage();
    expect(screen.getByText("Anti-Money Laundering Transaction Monitoring System")).toBeInTheDocument();
  });

  it("links to correct routes", () => {
    renderPage();
    const complianceLink = screen.getByText("Compliance").closest("a");
    expect(complianceLink).toHaveAttribute("href", "/compliance");

    const operationsLink = screen.getByText("Operations").closest("a");
    expect(operationsLink).toHaveAttribute("href", "/operations");

    const rulesLink = screen.getByText("Rules").closest("a");
    expect(rulesLink).toHaveAttribute("href", "/operations/rules");

    const customersLink = screen.getByText("Customers").closest("a");
    expect(customersLink).toHaveAttribute("href", "/customers");

    const transactionsLink = screen.getByText("Transactions").closest("a");
    expect(transactionsLink).toHaveAttribute("href", "/transactions");
  });

  it("renders descriptions for each card", () => {
    renderPage();
    expect(screen.getByText(/Review suspicious activity reports/)).toBeInTheDocument();
    expect(screen.getByText(/Upload transaction files/)).toBeInTheDocument();
    expect(screen.getByText(/Manage AML detection rules/)).toBeInTheDocument();
    expect(screen.getByText(/Search and view customer profiles/)).toBeInTheDocument();
    expect(screen.getByText(/Browse and search transaction records/)).toBeInTheDocument();
  });
});
