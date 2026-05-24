import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { api } from "../api/client";
import Layout from "./Layout";

vi.mock("../api/client", () => ({
  api: {
    get: vi.fn(),
  },
  ApiError: class extends Error {
    status: number;
    constructor(status: number, msg: string) {
      super(msg);
      this.status = status;
    }
  },
}));

function renderLayout(initialPath = "/") {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Layout />
    </MemoryRouter>
  );
}

describe("Layout", () => {
  beforeEach(() => {
    (api.get as ReturnType<typeof vi.fn>).mockReset();
    (api.get as ReturnType<typeof vi.fn>).mockResolvedValue({ total: 5 });
  });

  it("renders AML Monitor title as link", () => {
    renderLayout();
    const link = screen.getByText("AML Monitor");
    expect(link.tagName).toBe("A");
    expect(link).toHaveAttribute("href", "/");
  });

  it("shows compliance nav item", () => {
    renderLayout();
    expect(screen.getByText("Compliance")).toBeInTheDocument();
  });

  it("shows nav items", () => {
    renderLayout();
    expect(screen.getByText("Operations")).toBeInTheDocument();
    expect(screen.getByText("Customers")).toBeInTheDocument();
    expect(screen.getByText("Transactions")).toBeInTheDocument();
  });

  it("shows API Docs link", () => {
    renderLayout();
    const docs = screen.getByText("API Docs");
    expect(docs.closest("a")).toHaveAttribute("href", "/docs");
  });

  it("shows Test Data Generator nav item", () => {
    renderLayout();
    expect(screen.getByText("Test Data Generator")).toBeInTheDocument();
  });

  it("shows pending SAR badge when count > 0", async () => {
    renderLayout();
    const badge = await screen.findByText("5");
    expect(badge).toBeInTheDocument();
  });

  it("does not show badge when count is 0", () => {
    (api.get as ReturnType<typeof vi.fn>).mockResolvedValue({ total: 0 });
    renderLayout();
    expect(screen.queryByText("5")).not.toBeInTheDocument();
    expect(screen.queryByText("0")).not.toBeInTheDocument();
  });

  it("collapses and expands Operations sub-nav", () => {
    renderLayout();
    const opsBtn = screen.getByText("Operations");
    expect(screen.getByText("Upload")).toBeVisible();
    expect(screen.getByText("Rules")).toBeVisible();

    fireEvent.click(opsBtn);
    expect(screen.queryByText("Upload")).not.toBeInTheDocument();
    expect(screen.queryByText("Rules")).not.toBeInTheDocument();

    fireEvent.click(opsBtn);
    expect(screen.getByText("Upload")).toBeVisible();
    expect(screen.getByText("Rules")).toBeVisible();
  });

  it("highlights Operations when on an operations path", () => {
    renderLayout("/operations/rules");
    const ops = screen.getByText("Operations").closest("button")!;
    expect(ops.className).toContain("text-blue-700");
  });

  it("does not highlight Operations when on a non-ops path", () => {
    renderLayout("/transactions");
    const ops = screen.getByText("Operations").closest("button")!;
    expect(ops.className).not.toContain("text-blue-700");
  });
});
