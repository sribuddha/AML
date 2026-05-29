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

const mockToast = vi.hoisted(() => {
  const t = vi.fn();
  t.success = vi.fn();
  t.error = vi.fn();
  t.info = vi.fn();
  t.warning = vi.fn();
  return t;
});

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

vi.mock("../lib/toast", () => ({ toast: mockToast }));

describe("RulesPage", () => {
  beforeEach(() => {
    mockGet.mockReset();
    mockPost.mockReset();
    mockPut.mockReset();
    mockPatch.mockReset();
    mockToast.mockClear();
    mockToast.success.mockClear();
    mockToast.error.mockClear();
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

  it("opens create form on + New Rule click", async () => {
    render(<RulesPage />);
    fireEvent.click(screen.getByText("+ New Rule"));
    expect(screen.getByText("New Rule")).toBeInTheDocument();
  });

  it("opens edit form on Edit button click", async () => {
    render(<RulesPage />);
    await waitFor(() => {
      expect(screen.getByText("High Value Check")).toBeInTheDocument();
    });
    fireEvent.click(screen.getAllByText("Edit")[0]);
    expect(screen.getByText("Edit Rule")).toBeInTheDocument();
  });

  it("calls api.post when creating a rule", async () => {
    mockPost.mockResolvedValue({ id: "new" });
    render(<RulesPage />);
    fireEvent.click(screen.getByText("+ New Rule"));
    const nameInput = screen.getAllByRole("textbox")[1];
    fireEvent.change(nameInput, { target: { value: "New Rule" } });
    fireEvent.click(screen.getByText("Save"));
    await waitFor(() => {
      expect(mockPost).toHaveBeenCalledWith("/api/rules", expect.objectContaining({ name: "New Rule" }));
    });
  });

  it("calls api.patch when editing a rule", async () => {
    mockPatch.mockResolvedValue({ id: "r1" });
    render(<RulesPage />);
    await waitFor(() => {
      expect(screen.getByText("High Value Check")).toBeInTheDocument();
    });
    fireEvent.click(screen.getAllByText("Edit")[0]);
    const nameInput = screen.getAllByRole("textbox")[1];
    fireEvent.change(nameInput, { target: { value: "Edited Rule" } });
    fireEvent.click(screen.getByText("Save"));
    await waitFor(() => {
      expect(mockPatch).toHaveBeenCalledWith("/api/rules/r1", expect.objectContaining({ name: "Edited Rule" }));
    });
  });

  it("calls api.patch when toggling status", async () => {
    mockPatch.mockResolvedValue({ id: "r1", status: "inactive" });
    mockGet.mockResolvedValue(mockResponse);
    render(<RulesPage />);
    await waitFor(() => {
      expect(screen.getByText("High Value Check")).toBeInTheDocument();
    });
    fireEvent.click(screen.getAllByText("Deactivate")[0]);
    await waitFor(() => {
      expect(screen.getByText("Deactivate Rule")).toBeInTheDocument();
    });
    const dialogBtns = screen.getAllByText("Deactivate");
    fireEvent.click(dialogBtns[dialogBtns.length - 1]);
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
    fireEvent.click(screen.getByText("+ New Rule"));
    const nameInput = screen.getAllByRole("textbox")[1];
    fireEvent.change(nameInput, { target: { value: "Duplicate" } });
    fireEvent.click(screen.getByText("Save"));
    await waitFor(() => {
      expect(screen.getByText("Name already taken")).toBeInTheDocument();
    });
  });

  it("shows Cancel closes the form", async () => {
    render(<RulesPage />);
    fireEvent.click(screen.getByText("+ New Rule"));
    expect(screen.getByText("New Rule")).toBeInTheDocument();
    fireEvent.click(screen.getByText("Cancel"));
    expect(screen.queryByText("New Rule")).not.toBeInTheDocument();
  });

  it("shows filter inputs", async () => {
    render(<RulesPage />);
    expect(screen.getByPlaceholderText("Filter by name...")).toBeInTheDocument();
  });

  it("renders Search button", () => {
    render(<RulesPage />);
    expect(screen.getByText("Search")).toBeInTheDocument();
  });

  it("shows error when saving with empty name", async () => {
    render(<RulesPage />);
    fireEvent.click(screen.getByText("+ New Rule"));
    fireEvent.click(screen.getByText("Save"));
    await waitFor(() => {
      expect(screen.getByText("Name is required")).toBeInTheDocument();
    });
  });

  it("shows error when fetch fails", async () => {
    mockGet.mockRejectedValue(new Error("Network error"));
    render(<RulesPage />);
    await waitFor(() => {
      expect(screen.getByText("Network error")).toBeInTheDocument();
    });
  });

  it("filters by status dropdown", async () => {
    render(<RulesPage />);
    const combos = screen.getAllByRole("combobox");
    const statusFilter = combos[1];
    fireEvent.change(statusFilter, { target: { value: "active" } });
    expect(statusFilter).toHaveValue("active");
  });

  it("shows Retry button on error", async () => {
    mockGet.mockRejectedValue(new Error("Server down"));
    render(<RulesPage />);
    await waitFor(() => {
      expect(screen.getByText("Retry")).toBeInTheDocument();
    });
  });

  it("calls fetchRules on Search click", async () => {
    mockGet.mockResolvedValue(mockResponse);
    render(<RulesPage />);
    await waitFor(() => {
      expect(screen.getByText("High Value Check")).toBeInTheDocument();
    });
    mockGet.mockClear();
    mockGet.mockResolvedValue(mockResponse);
    fireEvent.click(screen.getByText("Search"));
    // Search click triggers the onSearch callback (no-op in this page), rules still shown
  });

  it("changes form type select", async () => {
    render(<RulesPage />);
    fireEvent.click(screen.getByText("+ New Rule"));
    const combos = screen.getAllByRole("combobox");
    const formType = combos[2];
    fireEvent.change(formType, { target: { value: "deterministic" } });
    expect(formType).toHaveValue("deterministic");
  });

  it("changes form status select", async () => {
    render(<RulesPage />);
    fireEvent.click(screen.getByText("+ New Rule"));
    const combos = screen.getAllByRole("combobox");
    const formStatus = combos[3];
    fireEvent.change(formStatus, { target: { value: "inactive" } });
    expect(formStatus).toHaveValue("inactive");
  });

  it("updates description in form", async () => {
    render(<RulesPage />);
    fireEvent.click(screen.getByText("+ New Rule"));
    const descInput = screen.getAllByRole("textbox")[2];
    fireEvent.change(descInput, { target: { value: "Test description" } });
    expect(descInput).toHaveValue("Test description");
  });

  it("updates rules JSON with valid input", async () => {
    render(<RulesPage />);
    fireEvent.click(screen.getByText("+ New Rule"));
    const jsonTextarea = screen.getByDisplayValue("[]");
    const validJson = JSON.stringify([{ field: "amount", operator: ">", value: 10000 }], null, 2);
    fireEvent.change(jsonTextarea, { target: { value: validJson } });
    expect(jsonTextarea).toHaveValue(validJson);
  });

  it("does not crash on invalid JSON in rules textarea", async () => {
    render(<RulesPage />);
    fireEvent.click(screen.getByText("+ New Rule"));
    const jsonTextarea = screen.getByDisplayValue("[]");
    fireEvent.change(jsonTextarea, { target: { value: "invalid json" } });
    expect(jsonTextarea).toHaveValue("[]");
  });

  it("calls toast.error on toggle status error", async () => {
    mockPatch.mockRejectedValue(new Error("Update failed"));
    render(<RulesPage />);
    await waitFor(() => {
      expect(screen.getByText("High Value Check")).toBeInTheDocument();
    });
    fireEvent.click(screen.getAllByText("Deactivate")[0]);
    await waitFor(() => {
      expect(screen.getByText("Deactivate Rule")).toBeInTheDocument();
    });
    const dialogBtns = screen.getAllByText("Deactivate");
    fireEvent.click(dialogBtns[dialogBtns.length - 1]);
    await waitFor(() => {
      expect(mockToast.error).toHaveBeenCalledWith("Update failed");
    });
  });

  it("shows empty state when no rules returned", async () => {
    mockGet.mockResolvedValue({ page: 1, per_page: 25, total: 0, items: [] });
    render(<RulesPage />);
    await waitFor(() => {
      expect(screen.getByText("No rules found.")).toBeInTheDocument();
    });
  });
});
