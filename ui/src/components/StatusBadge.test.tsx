import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import StatusBadge from "./StatusBadge";

describe("StatusBadge", () => {
  it("renders status text with underscores replaced", () => {
    render(<StatusBadge status="pending_review" />);
    expect(screen.getByText("pending review")).toBeInTheDocument();
  });

  it("renders simple status", () => {
    render(<StatusBadge status="complete" />);
    expect(screen.getByText("complete")).toBeInTheDocument();
  });

  it("applies green colors for clean status", () => {
    render(<StatusBadge status="clean" />);
    expect(screen.getByText("clean").className).toContain("text-green-700");
  });

  it("applies green colors for complete status", () => {
    render(<StatusBadge status="complete" />);
    expect(screen.getByText("complete").className).toContain("text-green-700");
  });

  it("applies green colors for confirmed status", () => {
    render(<StatusBadge status="confirmed" />);
    expect(screen.getByText("confirmed").className).toContain("text-green-700");
  });

  it("applies yellow colors for pending status", () => {
    render(<StatusBadge status="pending" />);
    expect(screen.getByText("pending").className).toContain("text-yellow-700");
  });

  it("applies yellow colors for processing status", () => {
    render(<StatusBadge status="processing" />);
    expect(screen.getByText("processing").className).toContain("text-yellow-700");
  });

  it("applies red colors for flagged status", () => {
    render(<StatusBadge status="flagged" />);
    expect(screen.getByText("flagged").className).toContain("text-red-700");
  });

  it("applies red colors for failed status", () => {
    render(<StatusBadge status="failed" />);
    expect(screen.getByText("failed").className).toContain("text-red-700");
  });

  it("applies slate colors for dismissed status", () => {
    render(<StatusBadge status="dismissed" />);
    expect(screen.getByText("dismissed").className).toContain("text-slate-600");
  });

  it("applies slate colors for inactive status", () => {
    render(<StatusBadge status="inactive" />);
    expect(screen.getByText("inactive").className).toContain("text-slate-600");
  });

  it("falls back to slate for unknown status", () => {
    render(<StatusBadge status="unknown" />);
    expect(screen.getByText("unknown").className).toContain("text-slate-600");
  });
});
