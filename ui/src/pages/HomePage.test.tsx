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
  it("renders Dashboard heading", () => {
    renderPage();
    expect(screen.getByText("Dashboard")).toBeInTheDocument();
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
    expect(screen.getByText("Select a module to get started")).toBeInTheDocument();
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
    expect(screen.getByText(/Upload and manage transaction data/)).toBeInTheDocument();
    expect(screen.getByText(/Configure detection rules/)).toBeInTheDocument();
    expect(screen.getByText(/Browse customer profiles/)).toBeInTheDocument();
    expect(screen.getByText(/View and search all processed/)).toBeInTheDocument();
  });
});
