import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import RulesPage from "./RulesPage";
import type { RuleResponse, PaginatedResponse } from "../types";

const mockRules: RuleResponse[] = [
  { id: "r1", name: "High Value Check", description: "Flags > $10k", type: "deterministic", status: "active", rules_json: [{ field: "amount", operator: ">", value: 10000 }] },
  { id: "r2", name: "Offshore Monitor", description: "Flags offshore", type: "deterministic", status: "active", rules_json: [{ field: "country", operator: "==", value: "KY" }] },
  { id: "r3", name: "Old Rule", description: null, type: "deterministic", status: "inactive", rules_json: [] },
];

const mockResponse: PaginatedResponse<RuleResponse> = {
  page: 1, per_page: 25, total: 3, items: mockRules,
};

let mockGet = vi.fn();
let mockPost = vi.fn();
let mockPut = vi.fn();
let mockPatch = vi.fn();

vi.mock("../api/client", () => ({
  api: {
    get: (...args: unknown[]) => mockGet(...args),
    post: (...args: unknown[]) => mockPost(...args),
    put: (...args: unknown[]) => mockPut(...args),
    patch: (...args: unknown[]) => mockPatch(...args),
    del: vi.fn(),
    download: vi.fn(),
    upload: vi.fn(),
  },
  ApiError: class extends Error {
    status: number;
    constructor(status: number, msg: string) {
      super(msg);
      this.status = status;
    }
  },
}));

describe("RulesPage", () => {
  beforeEach(() => {
    mockGet.mockReset();
    mockPost.mockReset();
    mockPut.mockReset();
    mockPatch.mockReset();
    mockGet.mockResolvedValue(mockResponse);
  });

  it("renders heading and description", async () => {
    render(<RulesPage />);
    expect(screen.getByText("Rules")).toBeInTheDocument();
    expect(screen.getByText("Manage AML detection rules")).toBeInTheDocument();
  });

  it("fetches and displays rules on mount", async () => {
    render(<RulesPage />);
    await waitFor(() => {
      expect(screen.getByText("High Value Check")).toBeInTheDocument();
    });
    expect(screen.getByText("Offshore Monitor")).toBeInTheDocument();
    expect(screen.getByText("Old Rule")).toBeInTheDocument();
  });

  it("shows status badges", async () => {
    render(<RulesPage />);
    await waitFor(() => {
      expect(screen.getAllByText("active").length).toBe(2);
    });
    expect(screen.getByText("inactive")).toBeInTheDocument();
  });

  it("opens create form on Add Rule click", async () => {
    render(<RulesPage />);
    fireEvent.click(screen.getByText("+ Add Rule"));
    expect(screen.getByText("Add Rule")).toBeInTheDocument();
    expect(screen.getByDisplayValue("deterministic")).toBeInTheDocument();
  });

  it("opens edit form on rule name click", async () => {
    render(<RulesPage />);
    await waitFor(() => {
      expect(screen.getByText("High Value Check")).toBeInTheDocument();
    });
    fireEvent.click(screen.getByText("High Value Check"));
    expect(screen.getByText("Edit Rule")).toBeInTheDocument();
  });

  it("calls api.post when creating a rule", async () => {
    mockPost.mockResolvedValue({ id: "new" });
    render(<RulesPage />);
    fireEvent.click(screen.getByText("+ Add Rule"));
    const nameInput = screen.getAllByRole("textbox")[2];
    fireEvent.change(nameInput, { target: { value: "New Rule" } });
    fireEvent.click(screen.getByText("Save"));
    await waitFor(() => {
      expect(mockPost).toHaveBeenCalledWith("/api/rules", expect.objectContaining({ name: "New Rule" }));
    });
  });

  it("calls api.put when editing a rule", async () => {
    mockPut.mockResolvedValue({ id: "r1" });
    render(<RulesPage />);
    await waitFor(() => {
      expect(screen.getByText("High Value Check")).toBeInTheDocument();
    });
    fireEvent.click(screen.getByText("High Value Check"));
    const nameInput = screen.getAllByRole("textbox")[2];
    fireEvent.change(nameInput, { target: { value: "Edited Rule" } });
    fireEvent.click(screen.getByText("Save"));
    await waitFor(() => {
      expect(mockPut).toHaveBeenCalledWith("/api/rules/r1", expect.objectContaining({ name: "Edited Rule" }));
    });
  });

  it("calls api.patch when toggling status", async () => {
    mockPatch.mockResolvedValue({ id: "r1", status: "inactive" });
    mockGet.mockResolvedValue(mockResponse);
    render(<RulesPage />);
    await waitFor(() => {
      expect(screen.getByText("High Value Check")).toBeInTheDocument();
    });
    const deactivateBtn = screen.getAllByText("Deactivate")[0];
    window.confirm = vi.fn(() => true);
    fireEvent.click(deactivateBtn);
    await waitFor(() => {
      expect(mockPatch).toHaveBeenCalledWith("/api/rules/r1/status", { status: "inactive" });
    });
  });

  it("shows Activate for inactive rules", async () => {
    render(<RulesPage />);
    await waitFor(() => {
      expect(screen.getByText("Old Rule")).toBeInTheDocument();
    });
    const activateBtn = screen.getByText("Activate");
    expect(activateBtn).toBeInTheDocument();
  });

  it("shows API error message in form", async () => {
    mockPost.mockRejectedValue(new Error("Name already taken"));
    render(<RulesPage />);
    fireEvent.click(screen.getByText("+ Add Rule"));
    const nameInput = screen.getAllByRole("textbox")[2];
    fireEvent.change(nameInput, { target: { value: "Duplicate" } });
    fireEvent.click(screen.getByText("Save"));
    await waitFor(() => {
      expect(screen.getByText("Name already taken")).toBeInTheDocument();
    });
  });

  it("shows Cancel closes the form", async () => {
    render(<RulesPage />);
    fireEvent.click(screen.getByText("+ Add Rule"));
    expect(screen.getByText("Add Rule")).toBeInTheDocument();
    fireEvent.click(screen.getByText("Cancel"));
    expect(screen.queryByText("Add Rule")).not.toBeInTheDocument();
  });

  it("shows filter inputs", async () => {
    render(<RulesPage />);
    expect(screen.getByPlaceholderText("Filter by type")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Filter by name")).toBeInTheDocument();
  });

  it("renders Search button", () => {
    render(<RulesPage />);
    expect(screen.getByText("Search")).toBeInTheDocument();
  });
});
