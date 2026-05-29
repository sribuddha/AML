import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import App from "./App";

import { api } from "./api/client";

vi.mock("./api/client", () => ({
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

describe("App", () => {
  beforeEach(() => {
    (api.get as ReturnType<typeof vi.fn>).mockReset();
    (api.get as ReturnType<typeof vi.fn>).mockResolvedValue({ total: 0 });
  });

  it("renders AML Monitor title", () => {
    render(<App />);
    expect(screen.getAllByText("AML Monitor").length).toBeGreaterThanOrEqual(1);
  });

  it("renders dashboard navigation cards on home route", () => {
    render(<App />);
    expect(screen.getAllByText("Compliance").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Operations").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("AML Monitor").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("Anti-Money Laundering Transaction Monitoring System")).toBeInTheDocument();
  });
});
