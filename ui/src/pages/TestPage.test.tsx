import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import TestPage from "./TestPage";

let mockPost = vi.fn();
let mockGet = vi.fn();
let mockDownload = vi.fn();

vi.mock("../api/client", () => ({
  api: {
    post: (...args: unknown[]) => mockPost(...args),
    get: (...args: unknown[]) => mockGet(...args),
    download: (...args: unknown[]) => mockDownload(...args),
  },
  ApiError: class extends Error {
    status: number;
    constructor(status: number, msg: string) {
      super(msg);
      this.status = status;
    }
  },
}));

function renderPage() {
  return render(
    <MemoryRouter>
      <TestPage />
    </MemoryRouter>
  );
}

describe("TestPage", () => {
  beforeEach(() => {
    mockPost.mockReset();
    mockGet.mockReset();
    mockDownload.mockReset();
    mockGet.mockResolvedValue(undefined);
    Element.prototype.scrollIntoView = vi.fn();
  });

  it("renders heading and DEV ONLY badge", () => {
    renderPage();
    expect(screen.getByText("Test Data Generator")).toBeInTheDocument();
    expect(screen.getByText("DEV ONLY")).toBeInTheDocument();
  });

  it("renders warning banner", () => {
    renderPage();
    expect(screen.getByText(/Development-only tool/)).toBeInTheDocument();
  });

  it("renders all 4 generator types", () => {
    renderPage();
    expect(screen.getByText("Clean Upload")).toBeInTheDocument();
    expect(screen.getByText("Stage 1 Fraud")).toBeInTheDocument();
    expect(screen.getByText("Stage 2 Triage")).toBeInTheDocument();
    expect(screen.getByText("Synthetic Fraud Patterns")).toBeInTheDocument();
  });

  it("has upload checked by default, others unchecked", () => {
    renderPage();
    const checkboxes = screen.getAllByRole("checkbox") as HTMLInputElement[];
    expect(checkboxes[0].checked).toBe(true);
    expect(checkboxes[1].checked).toBe(false);
    expect(checkboxes[2].checked).toBe(false);
    expect(checkboxes[3].checked).toBe(false);
  });

  it("toggles checkbox on click", () => {
    renderPage();
    const checkboxes = screen.getAllByRole("checkbox") as HTMLInputElement[];
    fireEvent.click(checkboxes[1]);
    expect(checkboxes[1].checked).toBe(true);
    fireEvent.click(checkboxes[1]);
    expect(checkboxes[1].checked).toBe(false);
  });

  it("shows 'tick to add' hint for unchecked items", () => {
    renderPage();
    const hints = screen.getAllByText("(tick to add)");
    expect(hints.length).toBe(3);
  });

  it("shows bad rows input only for upload type", () => {
    renderPage();
    expect(screen.getByText("bad rows")).toBeInTheDocument();
    const badRowsInput = screen.getByDisplayValue("50") as HTMLInputElement;
    expect(badRowsInput).toBeInTheDocument();
  });

  it("updates count input", () => {
    renderPage();
    const countInputs = screen.getAllByRole("spinbutton") as HTMLInputElement[];
    fireEvent.change(countInputs[0], { target: { value: "500" } });
    expect(countInputs[0].value).toBe("500");
  });

  it("updates bad rows input", () => {
    renderPage();
    const badRowsInput = screen.getByDisplayValue("50") as HTMLInputElement;
    fireEvent.change(badRowsInput, { target: { value: "25" } });
    expect(badRowsInput.value).toBe("25");
  });

  it("renders shuffle checkbox checked by default", () => {
    renderPage();
    expect(screen.getByText("Shuffle after generation")).toBeInTheDocument();
    const shuffleCheckbox = screen.getByLabelText("Shuffle after generation") as HTMLInputElement;
    expect(shuffleCheckbox.checked).toBe(true);
  });

  it("renders date input", () => {
    renderPage();
    const dateInput = document.querySelector('input[type="date"]') as HTMLInputElement;
    expect(dateInput).toBeInTheDocument();
  });

  it("shows total rows count", () => {
    renderPage();
    expect(screen.getByText(/Total rows:/)).toBeInTheDocument();
    expect(screen.getByText("1,000")).toBeInTheDocument();
  });

  it("disables generate button when 0 rows", () => {
    renderPage();
    const checkboxes = screen.getAllByRole("checkbox") as HTMLInputElement[];
    fireEvent.click(checkboxes[0]);
    const btn = screen.getByText("Generate");
    expect(btn.closest("button")).toBeDisabled();
  });

  it("calls api.post on generate", async () => {
    mockPost.mockResolvedValue({ download_url: "/work/test.csv" });
    renderPage();
    fireEvent.click(screen.getByText("Generate"));
    await waitFor(() => {
      expect(mockPost).toHaveBeenCalledWith("/api/generate", expect.objectContaining({
        steps: [expect.objectContaining({ type: "upload", count: 1000 })],
        shuffle: true,
      }));
    });
  });

  it("shows spinner while generating", async () => {
    let resolve: (v: unknown) => void;
    const promise = new Promise((r) => { resolve = r; });
    mockPost.mockReturnValue(promise);
    renderPage();
    fireEvent.click(screen.getByText("Generate"));
    await waitFor(() => {
      expect(screen.getByText("Generating...")).toBeInTheDocument();
    });
    resolve!({ download_url: "/work/test.csv" });
  });

  it("shows download section after success", async () => {
    mockGet.mockResolvedValue({ fieldnames: ["a"], rows: [{ a: "1" }] });
    mockPost.mockResolvedValue({ download_url: "/api/generate/download/test.csv", filename: "test.csv" });
    renderPage();
    fireEvent.click(screen.getByText("Generate"));
    await waitFor(() => {
      expect(screen.getByText("File generated successfully")).toBeInTheDocument();
    });
    expect(screen.getByText("Download CSV")).toBeInTheDocument();
    expect(screen.getByText("Upload to Pipeline")).toBeInTheDocument();
  });

  it("shows error message on failure", async () => {
    mockPost.mockRejectedValue(new Error("Generation failed"));
    renderPage();
    fireEvent.click(screen.getByText("Generate"));
    await waitFor(() => {
      expect(screen.getByText("Generation failed")).toBeInTheDocument();
    });
  });

  it("allows toggling multiple generators for combined steps", async () => {
    mockPost.mockResolvedValue({ download_url: "/work/test.csv" });
    renderPage();
    const checkboxes = screen.getAllByRole("checkbox") as HTMLInputElement[];
    fireEvent.click(checkboxes[1]);
    fireEvent.click(checkboxes[2]);
    fireEvent.click(screen.getByText("Generate"));
    await waitFor(() => {
      expect(mockPost).toHaveBeenCalledWith("/api/generate", expect.objectContaining({
        steps: [
          expect.objectContaining({ type: "upload" }),
          expect.objectContaining({ type: "stage1" }),
          expect.objectContaining({ type: "stage2" }),
        ],
      }));
    });
  });

  it("toggles shuffle checkbox off", () => {
    renderPage();
    const shuffleCheckbox = screen.getByLabelText("Shuffle after generation") as HTMLInputElement;
    fireEvent.click(shuffleCheckbox);
    expect(shuffleCheckbox.checked).toBe(false);
  });

  it("changes date input", () => {
    renderPage();
    const dateInput = document.querySelector('input[type="date"]') as HTMLInputElement;
    fireEvent.change(dateInput, { target: { value: "2026-06-15" } });
    expect(dateInput.value).toBe("2026-06-15");
  });

  it("renders label click toggling unchecked generator", () => {
    renderPage();
    const label = screen.getByText("Stage 1 Fraud");
    fireEvent.click(label);
    const checkboxes = screen.getAllByRole("checkbox") as HTMLInputElement[];
    expect(checkboxes[1].checked).toBe(true);
  });

  it("calls api.download on Download CSV click", async () => {
    mockGet.mockResolvedValue({ fieldnames: ["a"], rows: [{ a: "1" }] });
    mockPost.mockResolvedValue({ download_url: "/api/generate/download/test.csv", filename: "test.csv" });
    renderPage();
    fireEvent.click(screen.getByText("Generate"));
    await waitFor(() => {
      expect(screen.getByText("Download CSV")).toBeInTheDocument();
    });
    fireEvent.click(screen.getByText("Download CSV"));
    expect(mockDownload).toHaveBeenCalledWith("/api/generate/download/test.csv");
  });

  it("calls api.post on Upload to Pipeline click", async () => {
    mockGet.mockResolvedValue({ fieldnames: ["a"], rows: [{ a: "1" }] });
    mockPost.mockResolvedValue({ download_url: "/api/generate/download/test.csv", filename: "test.csv" });
    renderPage();
    fireEvent.click(screen.getByText("Generate"));
    await waitFor(() => {
      expect(screen.getByText("File generated successfully")).toBeInTheDocument();
    });
    mockPost.mockResolvedValue({});
    fireEvent.click(screen.getByText("Upload to Pipeline"));
    await waitFor(() => {
      expect(mockPost).toHaveBeenCalledWith("/api/uploads/from-work/test.csv");
    });
  });

  it("shows spinner while uploading", async () => {
    let resolveUpload: (v: unknown) => void;
    const uploadPromise = new Promise((r) => { resolveUpload = r; });
    mockGet.mockResolvedValue({ fieldnames: ["a"], rows: [{ a: "1" }] });
    mockPost.mockResolvedValue({ download_url: "/api/generate/download/test.csv", filename: "test.csv" });
    renderPage();
    fireEvent.click(screen.getByText("Generate"));
    await waitFor(() => {
      expect(screen.getByText("File generated successfully")).toBeInTheDocument();
    });
    mockPost.mockReturnValue(uploadPromise);
    fireEvent.click(screen.getByText("Upload to Pipeline"));
    await waitFor(() => {
      expect(screen.getByText("Uploading...")).toBeInTheDocument();
    });
    resolveUpload!({});
  });

  it("shows error on upload failure", async () => {
    mockGet.mockResolvedValue({ fieldnames: ["a"], rows: [{ a: "1" }] });
    mockPost.mockResolvedValue({ download_url: "/api/generate/download/test.csv", filename: "test.csv" });
    renderPage();
    fireEvent.click(screen.getByText("Generate"));
    await waitFor(() => {
      expect(screen.getByText("File generated successfully")).toBeInTheDocument();
    });
    mockPost.mockRejectedValue(new Error("Upload rejected"));
    fireEvent.click(screen.getByText("Upload to Pipeline"));
    await waitFor(() => {
      expect(screen.getByText("Upload rejected")).toBeInTheDocument();
    });
  });

  it("shows eval data tab when eval_url present", async () => {
    mockGet.mockImplementation((url: string) => {
      if (url.includes("/preview/")) return Promise.resolve({ fieldnames: ["a"], rows: [{ a: "1" }] });
      return Promise.resolve([{ source_txn_id: "T1", scenario: "structuring", expected_escalate: true, ground_truth: "Structuring", reason_hint: "Pattern" }]);
    });
    mockPost.mockResolvedValue({
      download_url: "/api/generate/download/test.csv",
      eval_url: "/api/download/eval.json",
      filename: "test.csv",
    });
    renderPage();
    fireEvent.click(screen.getByText("Generate"));
    await waitFor(() => {
      expect(screen.getByText("File generated successfully")).toBeInTheDocument();
    });
    fireEvent.click(screen.getByText("Eval Data"));
    await waitFor(() => {
      expect(screen.getByText("T1")).toBeInTheDocument();
    });
    expect(screen.getByText("structuring")).toBeInTheDocument();
  });
});
