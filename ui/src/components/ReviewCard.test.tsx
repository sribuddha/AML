import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import ReviewCard from "./ReviewCard";
import type { PendingSAR } from "../types";

const baseSar: PendingSAR = {
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
    render(<ReviewCard sar={baseSar} onReview={async () => {}} reviewing={false} />);
    expect(screen.getByText("TXN001")).toBeInTheDocument();
    expect(screen.getByText("Offshore Corp")).toBeInTheDocument();
    expect(screen.getByText("$15,000")).toBeInTheDocument();
  });

  it("shows collapsed by default", () => {
    render(<ReviewCard sar={baseSar} onReview={async () => {}} reviewing={false} />);
    expect(screen.queryByText("Rules Triggered")).not.toBeInTheDocument();
  });

  it("expands detail section on click", () => {
    render(<ReviewCard sar={baseSar} onReview={async () => {}} reviewing={false} />);
    fireEvent.click(screen.getByText("TXN001"));
    expect(screen.getByText("Rules Triggered")).toBeInTheDocument();
    expect(screen.getByText("SAR Report")).toBeInTheDocument();
  });

  it("shows rule names in expanded detail", () => {
    render(<ReviewCard sar={baseSar} onReview={async () => {}} reviewing={false} />);
    fireEvent.click(screen.getByText("TXN001"));
    expect(screen.getAllByText(/High Value Check/).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(/Offshore Location/)).toBeInTheDocument();
  });

  it("shows enriched context stats", () => {
    render(<ReviewCard sar={baseSar} onReview={async () => {}} reviewing={false} />);
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
    render(<ReviewCard sar={baseSar} onReview={async () => {}} reviewing={false} />);
    fireEvent.click(screen.getByText("TXN001"));
    const score = screen.getByText("2.50");
    expect(score.className).toContain("text-red-600");
  });

  it("shows SAR report text", () => {
    render(<ReviewCard sar={baseSar} onReview={async () => {}} reviewing={false} />);
    fireEvent.click(screen.getByText("TXN001"));
    expect(screen.getByText("This transaction is suspicious because...")).toBeInTheDocument();
  });

  it("shows Dismiss and Confirm buttons", () => {
    render(<ReviewCard sar={baseSar} onReview={async () => {}} reviewing={false} />);
    expect(screen.getByText("Dismiss")).toBeInTheDocument();
    expect(screen.getByText("Confirm")).toBeInTheDocument();
  });

  it("calls onReview with dismissed when Dismiss clicked", async () => {
    const onReview = vi.fn().mockResolvedValue(undefined);
    render(<ReviewCard sar={baseSar} onReview={onReview} reviewing={false} />);
    fireEvent.click(screen.getByText("Dismiss"));
    expect(onReview).toHaveBeenCalledWith("dismissed");
  });

  it("calls onReview with confirmed when Confirm clicked", async () => {
    const onReview = vi.fn().mockResolvedValue(undefined);
    render(<ReviewCard sar={baseSar} onReview={onReview} reviewing={false} />);
    fireEvent.click(screen.getByText("Confirm"));
    expect(onReview).toHaveBeenCalledWith("confirmed");
  });

  it("disables buttons while reviewing", () => {
    render(<ReviewCard sar={baseSar} onReview={async () => {}} reviewing={true} />);
    const buttons = screen.getAllByText("...");
    expect(buttons.length).toBe(2);
    buttons.forEach(btn => expect(btn.closest("button")).toBeDisabled());
  });

  it("shows ... on buttons while reviewing", () => {
    render(<ReviewCard sar={baseSar} onReview={async () => {}} reviewing={true} />);
    expect(screen.getAllByText("...").length).toBe(2);
  });

  it("renders without enrichment data", () => {
    const sar = { ...baseSar, enrichment: null };
    render(<ReviewCard sar={sar} onReview={async () => {}} reviewing={false} />);
    fireEvent.click(screen.getByText("TXN001"));
    expect(screen.queryByText("Enriched Context")).not.toBeInTheDocument();
  });

  it("renders without flag_details", () => {
    const sar = { ...baseSar, flag_details: null };
    render(<ReviewCard sar={sar} onReview={async () => {}} reviewing={false} />);
    fireEvent.click(screen.getByText("TXN001"));
    expect(screen.queryByText("Rules Triggered")).not.toBeInTheDocument();
  });
});
