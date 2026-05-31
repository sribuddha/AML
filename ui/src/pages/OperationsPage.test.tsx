import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import OperationsPage from "./OperationsPage";
import type { UploadSummary, PaginatedResponse, EvalReport } from "../types";

const mockUploads: UploadSummary[] = [
  { id: "upload-001", filename: "data.csv", status: "pending_human", total_rows: 100, accepted_count: 95, failed_count: 5, uploaded_at: "2026-05-01T00:00:00Z", eval_file: null, pending_sar_count: 3 },
  { id: "upload-002", filename: "old.csv", status: "complete", total_rows: 50, accepted_count: 50, failed_count: 0, uploaded_at: "2026-04-01T00:00:00Z", eval_file: null, pending_sar_count: 0 },
  { id: "upload-003", filename: "eval_test.csv", status: "complete", total_rows: 200, accepted_count: 190, failed_count: 10, uploaded_at: "2026-05-02T00:00:00Z", eval_file: "test.eval", pending_sar_count: 0 },
];

const mockResponse: PaginatedResponse<UploadSummary> = {
  page: 1, per_page: 25, total: 3, items: mockUploads,
};

const mockEvalReport: EvalReport = {
  upload_id: "upload-003",
  total_transactions: 200,
  total_anomalous: 50,
  total_flagged: 40,
  pattern_metrics: [
    { pattern: "Structuring", total: 20, flagged: 18, precision: 0.9, recall: 0.85, f1: 0.87 },
  ],
  hallucination_results: [
    { sar_id: "sar001", transaction_id: "t001", hallucinated_facts: ["$10,000"], passed: false },
    { sar_id: "sar002", transaction_id: "t002", hallucinated_facts: [], passed: true },
  ],
  completeness_results: [
    { sar_id: "sar001", transaction_id: "t001", covered_rules: ["Rule A"], missed_rules: ["Rule B"], score: 0.5 },
    { sar_id: "sar003", transaction_id: "t003", covered_rules: ["Rule C"], missed_rules: [], score: 1 },
  ],
  overall_precision: 0.8,
  overall_recall: 0.75,
  overall_f1: 0.77,
  hallucination_free_rate: 0.85,
  avg_completeness: 0.75,
};

let mockGet = vi.fn();
let mockUpload = vi.fn();
let mockPost = vi.fn();

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
    upload: (...args: unknown[]) => mockUpload(...args),
    download: vi.fn(),
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

function renderPage() {
  return render(
    <MemoryRouter>
      <OperationsPage />
    </MemoryRouter>
  );
}

describe("OperationsPage", () => {
  beforeEach(() => {
    mockGet.mockReset();
    mockUpload.mockReset();
    mockPost.mockReset();
    mockToast.mockClear();
    mockToast.success.mockClear();
    mockToast.error.mockClear();
    mockGet.mockResolvedValue(mockResponse);
  });

  it("renders heading and description", () => {
    renderPage();
    expect(screen.getByText("Operations")).toBeInTheDocument();
    expect(screen.getByText("Upload files and manage uploads")).toBeInTheDocument();
  });

  it("shows Search Uploads tab active by default", () => {
    renderPage();
    const searchTab = screen.getByText("Search Uploads");
    expect(searchTab.className).toContain("bg-white");
    expect(searchTab.className).toContain("shadow-sm");
    expect(screen.getByPlaceholderText("Upload ID")).toBeInTheDocument();
  });

  it("switches to Upload tab", () => {
    renderPage();
    fireEvent.click(screen.getByText("Upload"));
    const uploadTab = screen.getByText("Upload");
    expect(uploadTab.className).toContain("bg-white");
    expect(uploadTab.className).toContain("shadow-sm");
    expect(screen.getByText(/Drag.*drop.*CSV/i)).toBeInTheDocument();
  });

  it("shows upload result after file upload", async () => {
    mockUpload.mockResolvedValue({ total_rows: 100, accepted_count: 95, failed_count: 5 });
    renderPage();
    fireEvent.click(screen.getByText("Upload"));
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    const file = new File(["a,b,c\n1,2,3"], "test.csv", { type: "text/csv" });
    fireEvent.change(input, { target: { files: [file] } });
    fireEvent.click(screen.getByRole("button", { name: /upload test.csv/i }));
    await waitFor(() => {
      expect(screen.getByText("Upload Result")).toBeInTheDocument();
    });
    expect(screen.getByText("100")).toBeInTheDocument();
    expect(screen.getByText("95")).toBeInTheDocument();
    expect(screen.getByText("5")).toBeInTheDocument();
  });

  it("shows View Uploads link after upload", async () => {
    mockUpload.mockResolvedValue({ total_rows: 100, accepted_count: 95, failed_count: 5 });
    renderPage();
    fireEvent.click(screen.getByText("Upload"));
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(input, { target: { files: [new File(["a"], "test.csv", { type: "text/csv" })] } });
    fireEvent.click(screen.getByRole("button", { name: /upload test.csv/i }));
    await waitFor(() => {
      expect(screen.getByText(/View Uploads/)).toBeInTheDocument();
    });
  });

  it("renders status filter tabs in search view", () => {
    renderPage();
    ["All", "Uploaded", "Processing", "Pending Review", "Complete", "Failed"].forEach(status => {
      const buttons = screen.getAllByText(status);
      expect(buttons.length).toBeGreaterThanOrEqual(1);
    });
  });

  it("shows date range and ID inputs in search view", () => {
    renderPage();
    fireEvent.click(screen.getByText("Search Uploads"));
    expect(screen.getByPlaceholderText("Upload ID")).toBeInTheDocument();
    const dateInputs = document.querySelectorAll('input[type="date"]');
    expect(dateInputs.length).toBeGreaterThanOrEqual(2);
  });

  it("fetches uploads on search", async () => {
    renderPage();
    fireEvent.click(screen.getByText("Search Uploads"));
    fireEvent.change(screen.getByPlaceholderText("Upload ID"), { target: { value: "upload-001" } });
    fireEvent.click(screen.getByText("Search"));
    await waitFor(() => {
      expect(mockGet).toHaveBeenCalledWith("/api/uploads/search", expect.objectContaining({
        upload_id: "upload-001", page: 1, per_page: 25,
      }));
    });
  });

  it("auto-searches on mount and shows empty state when no results", async () => {
    mockGet.mockResolvedValue({ data: [], total: 0, page: 1, per_page: 25, total_pages: 0 });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("No uploads found.")).toBeInTheDocument();
    });
  });

  it("calls toast.error on upload error", async () => {
    mockUpload.mockRejectedValue(new Error("Upload failed"));
    renderPage();
    fireEvent.click(screen.getByText("Upload"));
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(input, { target: { files: [new File(["a"], "test.csv", { type: "text/csv" })] } });
    fireEvent.click(screen.getByRole("button", { name: /upload test.csv/i }));
    await waitFor(() => {
      expect(mockToast.error).toHaveBeenCalledWith("Upload failed");
    });
  });

  it("displays uploads in DataTable after search", async () => {
    renderPage();
    fireEvent.click(screen.getByText("Search Uploads"));
    fireEvent.click(screen.getByText("Search"));
    await waitFor(() => {
      expect(screen.getByText(/data\.csv/)).toBeInTheDocument();
    });
    expect(screen.getByText(/old\.csv/)).toBeInTheDocument();
  });

  it("shows upload ID as clickable link for pending_human", async () => {
    renderPage();
    fireEvent.click(screen.getByText("Search Uploads"));
    fireEvent.click(screen.getByText("Search"));
    await waitFor(() => {
      expect(screen.getByText(/data\.csv/)).toBeInTheDocument();
    });
    const links = screen.getAllByText("upload-001");
    expect(links.length).toBeGreaterThanOrEqual(1);
  });

  it("shows Search Uploads tab active when selected", () => {
    renderPage();
    fireEvent.click(screen.getByText("Search Uploads"));
    const searchTab = screen.getByText("Search Uploads");
    expect(searchTab.className).toContain("bg-white");
    expect(searchTab.className).toContain("shadow-sm");
  });

  it("searches with date range", async () => {
    renderPage();
    fireEvent.click(screen.getByText("Search Uploads"));
    const dateInputs = document.querySelectorAll('input[type="date"]') as NodeListOf<HTMLInputElement>;
    fireEvent.change(dateInputs[0], { target: { value: "2026-01-01" } });
    fireEvent.change(dateInputs[1], { target: { value: "2026-12-31" } });
    fireEvent.click(screen.getByText("Search"));
    await waitFor(() => {
      expect(mockGet).toHaveBeenCalledWith("/api/uploads/search", expect.objectContaining({
        from_date: "2026-01-01", to_date: "2026-12-31", page: 1, per_page: 25,
      }));
    });
  });

  it("shows error state", async () => {
    mockGet.mockRejectedValue(new Error("API error"));
    renderPage();
    fireEvent.click(screen.getByText("Search Uploads"));
    fireEvent.click(screen.getByText("Search"));
    await waitFor(() => {
      expect(screen.getByText("API error")).toBeInTheDocument();
    });
  });

  it("shows empty message", async () => {
    mockGet.mockResolvedValue({ ...mockResponse, items: [], total: 0 });
    renderPage();
    fireEvent.click(screen.getByText("Search Uploads"));
    fireEvent.click(screen.getByText("Search"));
    await waitFor(() => {
      expect(screen.getByText("No uploads found.")).toBeInTheDocument();
    });
  });

  it("shows Eval button for completed upload with eval_file", async () => {
    renderPage();
    fireEvent.click(screen.getByText("Search Uploads"));
    fireEvent.click(screen.getByText("Search"));
    await waitFor(() => {
      expect(screen.getByText("eval_test.csv")).toBeInTheDocument();
    });
    expect(screen.getByRole("button", { name: "Eval" })).toBeInTheDocument();
  });

  it("opens eval modal on Eval click with loading spinner", async () => {
    let resolve: (v: unknown) => void;
    const promise = new Promise((r) => { resolve = r; });
    mockPost.mockReturnValue(promise);
    renderPage();
    fireEvent.click(screen.getByText("Search Uploads"));
    fireEvent.click(screen.getByText("Search"));
    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Eval" })).toBeInTheDocument();
    });
    fireEvent.click(screen.getByRole("button", { name: "Eval" }));
    await waitFor(() => {
      expect(screen.getByText("Running evaluation...")).toBeInTheDocument();
    });
    resolve!(mockEvalReport);
  });

  it("shows eval report after successful evaluation", async () => {
    mockPost.mockResolvedValue(mockEvalReport);
    renderPage();
    fireEvent.click(screen.getByText("Search Uploads"));
    fireEvent.click(screen.getByText("Search"));
    await waitFor(() => expect(screen.getByRole("button", { name: "Eval" })).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Eval" }));
    await waitFor(() => {
      expect(screen.getByText("Transactions")).toBeInTheDocument();
    });
    expect(screen.getByText("Anomalous (expected)")).toBeInTheDocument();
    expect(screen.getByText("Flagged (actual)")).toBeInTheDocument();
    expect(screen.getByText("Hallucination-Free")).toBeInTheDocument();
    expect(screen.getByText("Avg Completeness")).toBeInTheDocument();
    expect(screen.getByText("Structuring")).toBeInTheDocument();
  });

  it("shows hallucination issues in eval modal", async () => {
    mockPost.mockResolvedValue(mockEvalReport);
    renderPage();
    fireEvent.click(screen.getByText("Search Uploads"));
    fireEvent.click(screen.getByText("Search"));
    await waitFor(() => expect(screen.getByRole("button", { name: "Eval" })).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Eval" }));
    await waitFor(() => {
      expect(screen.getByText("Hallucination Issues")).toBeInTheDocument();
    });
    expect(screen.getByText(/\$10,000/)).toBeInTheDocument();
  });

  it("shows completeness issues in eval modal", async () => {
    mockPost.mockResolvedValue(mockEvalReport);
    renderPage();
    fireEvent.click(screen.getByText("Search Uploads"));
    fireEvent.click(screen.getByText("Search"));
    await waitFor(() => expect(screen.getByRole("button", { name: "Eval" })).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Eval" }));
    await waitFor(() => {
      expect(screen.getByText("Completeness Issues")).toBeInTheDocument();
    });
    expect(screen.getByText((content) => content.includes("Rule B"))).toBeInTheDocument();
  });

  it("shows error in eval modal on failure", async () => {
    mockPost.mockRejectedValue(new Error("Eval request failed"));
    renderPage();
    fireEvent.click(screen.getByText("Search Uploads"));
    fireEvent.click(screen.getByText("Search"));
    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Eval" })).toBeInTheDocument();
    });
    fireEvent.click(screen.getByRole("button", { name: "Eval" }));
    await waitFor(() => {
      expect(screen.getByText("Eval request failed")).toBeInTheDocument();
    });
  });

  it("closes eval modal on backdrop click", async () => {
    mockPost.mockResolvedValue(mockEvalReport);
    renderPage();
    fireEvent.click(screen.getByText("Search Uploads"));
    fireEvent.click(screen.getByText("Search"));
    await waitFor(() => expect(screen.getByRole("button", { name: "Eval" })).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Eval" }));
    await waitFor(() => {
      expect(screen.getByText("Transactions")).toBeInTheDocument();
    });
    const backdrop = document.querySelector(".fixed.inset-0");
    if (backdrop) fireEvent.click(backdrop);
    await waitFor(() => {
      expect(screen.queryByText("Transactions")).not.toBeInTheDocument();
    });
  });

  it("does not auto-search with ?tab=upload URL param", async () => {
    mockGet.mockResolvedValue(mockResponse);
    render(
      <MemoryRouter initialEntries={["/operations?tab=upload"]}>
        <OperationsPage />
      </MemoryRouter>
    );
    expect(screen.getByText(/Drag.*drop.*CSV/i)).toBeInTheDocument();
    expect(mockGet).not.toHaveBeenCalled();
  });

  it("closes eval modal via \u00D7 button", async () => {
    mockPost.mockResolvedValue(mockEvalReport);
    renderPage();
    fireEvent.click(screen.getByText("Search Uploads"));
    fireEvent.click(screen.getByText("Search"));
    await waitFor(() => expect(screen.getByRole("button", { name: "Eval" })).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Eval" }));
    await waitFor(() => {
      expect(screen.getByText("Eval Report")).toBeInTheDocument();
    });
    const closeBtn = screen.getByText("\u00D7");
    fireEvent.click(closeBtn);
    await waitFor(() => {
      expect(screen.queryByText("Eval Report")).not.toBeInTheDocument();
    });
  });

  it("switches back to Upload tab after search", async () => {
    renderPage();
    fireEvent.click(screen.getByText("Search Uploads"));
    fireEvent.click(screen.getByText("Upload"));
    const uploadTab = screen.getByText("Upload");
    expect(uploadTab.className).toContain("bg-white");
    expect(uploadTab.className).toContain("shadow-sm");
    expect(screen.getByText(/Drag.*drop.*CSV/i)).toBeInTheDocument();
  });

  it("clicks View Uploads link after upload", async () => {
    mockUpload.mockResolvedValue({ total_rows: 100, accepted_count: 95, failed_count: 5 });
    renderPage();
    fireEvent.click(screen.getByText("Upload"));
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(input, { target: { files: [new File(["a"], "test.csv", { type: "text/csv" })] } });
    fireEvent.click(screen.getByRole("button", { name: /upload test.csv/i }));
    await waitFor(() => {
      expect(screen.getByText(/View Uploads/)).toBeInTheDocument();
    });
    fireEvent.click(screen.getByText(/View Uploads/));
    await waitFor(() => {
      expect(screen.getByText("Search Uploads").className).toContain("bg-white");
    });
  });

  it("clicks status tab to filter", async () => {
    renderPage();
    fireEvent.click(screen.getByText("Search Uploads"));
    fireEvent.click(screen.getByText("Complete"));
    fireEvent.click(screen.getByText("Search"));
    await waitFor(() => {
      expect(mockGet).toHaveBeenCalledWith("/api/uploads/search", expect.objectContaining({
        status: "complete", page: 1, per_page: 25,
      }));
    });
  });
});
