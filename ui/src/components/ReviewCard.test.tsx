import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import ReviewCard from "./ReviewCard";
import type { PendingSAR } from "../types";

function renderWithRouter(ui: React.ReactElement) {
  return render(<MemoryRouter>{ui}</MemoryRouter>);
}

const baseSar: PendingSAR = {
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
  flag_details: { rule1: "High Value Check", rule2: "Offshore Location" },
  risk_level: "high",
  triage_reasoning: "Suspicious pattern",
  enrichment: {
    customer_txn_count_30d: 12,
    customer_avg_30d: 8000,
    structuring_24h_count: 3,
    velocity_zscore: 2.5,
    dormancy_days: 0,
    account_type: "Checking",
  },
  rule_name: "High Value Check",
  rule_description: "Flags transactions over $10k",
  sar_content: "This transaction is suspicious because...",
  sar_status: "pending_review",
  created_at: "2026-05-01T00:00:00Z",
};

describe("ReviewCard", () => {
  it("renders transaction header info", () => {
    renderWithRouter(<ReviewCard sar={baseSar} onReview={async () => {}} reviewing={false} />);
    expect(screen.getByText("TXN001")).toBeInTheDocument();
    expect(screen.getByText("Offshore Corp")).toBeInTheDocument();
    expect(screen.getByText("$15,000")).toBeInTheDocument();
  });

  it("shows collapsed by default", () => {
    renderWithRouter(<ReviewCard sar={baseSar} onReview={async () => {}} reviewing={false} />);
    expect(screen.queryByText("Rules Triggered")).not.toBeInTheDocument();
  });

  it("expands detail section on click", () => {
    renderWithRouter(<ReviewCard sar={baseSar} onReview={async () => {}} reviewing={false} />);
    fireEvent.click(screen.getByText("TXN001"));
    expect(screen.getByText("Rules Triggered")).toBeInTheDocument();
    expect(screen.getByText("SAR Report")).toBeInTheDocument();
  });

  it("shows rule names in expanded detail", () => {
    renderWithRouter(<ReviewCard sar={baseSar} onReview={async () => {}} reviewing={false} />);
    fireEvent.click(screen.getByText("TXN001"));
    expect(screen.getAllByText(/High Value Check/).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(/Offshore Location/)).toBeInTheDocument();
  });

  it("shows enriched context stats", () => {
    renderWithRouter(<ReviewCard sar={baseSar} onReview={async () => {}} reviewing={false} />);
    fireEvent.click(screen.getByText("TXN001"));
    expect(screen.getByText("12")).toBeInTheDocument();
    expect(screen.getByText("30d Txn Count")).toBeInTheDocument();
    expect(screen.getByText("$8,000")).toBeInTheDocument();
    expect(screen.getByText("30d Avg Amount")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
    expect(screen.getByText("Structuring Alerts")).toBeInTheDocument();
    expect(screen.getByText("2.50")).toBeInTheDocument();
    expect(screen.getByText("Velocity Z-Score")).toBeInTheDocument();
    expect(screen.getByText("0d")).toBeInTheDocument();
    expect(screen.getByText("Dormancy")).toBeInTheDocument();
    expect(screen.getByText("Checking")).toBeInTheDocument();
    expect(screen.getByText("Account Type")).toBeInTheDocument();
  });

  it("shows velocity z-score in red when > 2", () => {
    renderWithRouter(<ReviewCard sar={baseSar} onReview={async () => {}} reviewing={false} />);
    fireEvent.click(screen.getByText("TXN001"));
    const score = screen.getByText("2.50");
    expect(score.className).toContain("text-red-600");
  });

  it("shows SAR report text", () => {
    renderWithRouter(<ReviewCard sar={baseSar} onReview={async () => {}} reviewing={false} />);
    fireEvent.click(screen.getByText("TXN001"));
    expect(screen.getByText("This transaction is suspicious because...")).toBeInTheDocument();
  });

  it("shows Dismiss and Confirm buttons", () => {
    renderWithRouter(<ReviewCard sar={baseSar} onReview={async () => {}} reviewing={false} />);
    expect(screen.getByText("Dismiss")).toBeInTheDocument();
    expect(screen.getByText("Confirm")).toBeInTheDocument();
  });

  it("calls onReview with dismissed when Dismiss clicked", async () => {
    const onReview = vi.fn().mockResolvedValue(undefined);
    renderWithRouter(<ReviewCard sar={baseSar} onReview={onReview} reviewing={false} />);
    fireEvent.click(screen.getByText("Dismiss"));
    expect(onReview).toHaveBeenCalledWith("dismissed");
  });

  it("calls onReview with confirmed when Confirm clicked", async () => {
    const onReview = vi.fn().mockResolvedValue(undefined);
    renderWithRouter(<ReviewCard sar={baseSar} onReview={onReview} reviewing={false} />);
    fireEvent.click(screen.getByText("Confirm"));
    expect(onReview).toHaveBeenCalledWith("confirmed");
  });

  it("disables buttons while reviewing", () => {
    renderWithRouter(<ReviewCard sar={baseSar} onReview={async () => {}} reviewing={true} />);
    const buttons = screen.getAllByText("...");
    expect(buttons.length).toBe(2);
    buttons.forEach(btn => expect(btn.closest("button")).toBeDisabled());
  });

  it("shows ... on buttons while reviewing", () => {
    renderWithRouter(<ReviewCard sar={baseSar} onReview={async () => {}} reviewing={true} />);
    expect(screen.getAllByText("...").length).toBe(2);
  });

  it("renders customer name as a link in header", () => {
    renderWithRouter(<ReviewCard sar={baseSar} onReview={async () => {}} reviewing={false} />);
    const link = screen.getByText("John Doe");
    expect(link).toBeInTheDocument();
    expect(link.closest("a")).toHaveAttribute("href", "/compliance?customer_id=CUST001");
  });

  it("renders customer_id link in expanded detail", () => {
    renderWithRouter(<ReviewCard sar={baseSar} onReview={async () => {}} reviewing={false} />);
    fireEvent.click(screen.getByText("TXN001"));
    const link = screen.getByText("Cust: John Doe");
    expect(link).toBeInTheDocument();
    expect(link.closest("a")).toHaveAttribute("href", "/compliance?customer_id=CUST001");
  });

  it("renders without enrichment data", () => {
    const sar = { ...baseSar, enrichment: null };
    renderWithRouter(<ReviewCard sar={sar} onReview={async () => {}} reviewing={false} />);
    fireEvent.click(screen.getByText("TXN001"));
    expect(screen.queryByText("Enriched Context")).not.toBeInTheDocument();
  });

  it("renders without flag_details", () => {
    const sar = { ...baseSar, flag_details: null };
    renderWithRouter(<ReviewCard sar={sar} onReview={async () => {}} reviewing={false} />);
    fireEvent.click(screen.getByText("TXN001"));
    expect(screen.queryByText("Rules Triggered")).not.toBeInTheDocument();
  });

  it("shows raw customer_id when customer name missing in header", () => {
    const sar = { ...baseSar, customer_first_name: undefined, customer_last_name: undefined };
    renderWithRouter(<ReviewCard sar={sar} onReview={async () => {}} reviewing={false} />);
    const link = screen.getByText("CUST001");
    expect(link).toBeInTheDocument();
    expect(link.closest("a")).toHaveAttribute("href", "/compliance?customer_id=CUST001");
  });

  it("shows raw customer_id when customer name missing in expanded section", () => {
    const sar = { ...baseSar, customer_first_name: undefined, customer_last_name: undefined };
    renderWithRouter(<ReviewCard sar={sar} onReview={async () => {}} reviewing={false} />);
    fireEvent.click(screen.getByText("TXN001"));
    const link = screen.getByText("Cust: CUST001");
    expect(link).toBeInTheDocument();
    expect(link.closest("a")).toHaveAttribute("href", "/compliance?customer_id=CUST001");
  });

  it("does not highlight velocity z-score when <= 2", () => {
    const sar = { ...baseSar, enrichment: { ...baseSar.enrichment!, velocity_zscore: 1.5 } };
    renderWithRouter(<ReviewCard sar={sar} onReview={async () => {}} reviewing={false} />);
    fireEvent.click(screen.getByText("TXN001"));
    const score = screen.getByText("1.50");
    expect(score.className).not.toContain("text-red-600");
  });
});
