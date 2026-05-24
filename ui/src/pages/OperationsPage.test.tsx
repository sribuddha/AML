import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import OperationsPage from "./OperationsPage";
import type { UploadSummary, PaginatedResponse } from "../types";

const mockUploads: UploadSummary[] = [
  { id: "upload-001", filename: "data.csv", status: "pending_human", total_rows: 100, accepted_count: 95, failed_count: 5, uploaded_at: "2026-05-01T00:00:00Z" },
  { id: "upload-002", filename: "old.csv", status: "complete", total_rows: 50, accepted_count: 50, failed_count: 0, uploaded_at: "2026-04-01T00:00:00Z" },
];

const mockResponse: PaginatedResponse<UploadSummary> = {
  page: 1, per_page: 25, total: 2, items: mockUploads,
};

let mockGet = vi.fn();
let mockUpload = vi.fn();

vi.mock("../api/client", () => ({
  api: {
    get: (...args: unknown[]) => mockGet(...args),
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
    mockGet.mockResolvedValue(mockResponse);
  });

  it("renders heading and description", () => {
    renderPage();
    expect(screen.getByText("Operations")).toBeInTheDocument();
    expect(screen.getByText("Upload files and manage uploads")).toBeInTheDocument();
  });

  it("shows Upload tab active by default", () => {
    renderPage();
    const uploadTab = screen.getByText("Upload");
    expect(uploadTab.className).toContain("bg-white");
    expect(screen.getByText(/drag.*drop.*csv/i)).toBeInTheDocument();
  });

  it("switches to Search Uploads tab", () => {
    renderPage();
    fireEvent.click(screen.getByText("Search Uploads"));
    const searchTab = screen.getByText("Search Uploads");
    expect(searchTab.className).toContain("bg-white");
    expect(screen.getByPlaceholderText("Upload ID")).toBeInTheDocument();
  });

  it("shows upload result after file upload", async () => {
    mockUpload.mockResolvedValue({ total_rows: 100, accepted_count: 95, failed_count: 5 });
    renderPage();
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
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(input, { target: { files: [new File(["a"], "test.csv", { type: "text/csv" })] } });
    fireEvent.click(screen.getByRole("button", { name: /upload test.csv/i }));
    await waitFor(() => {
      expect(screen.getByText(/View Uploads/)).toBeInTheDocument();
    });
  });

  it("renders status filter tabs in search view", () => {
    renderPage();
    fireEvent.click(screen.getByText("Search Uploads"));
    ["All", "Uploaded", "Processing", "Pending Review", "Complete", "Failed"].forEach(status => {
      expect(screen.getByText(status)).toBeInTheDocument();
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

  it("shows unsearched hint before first search", () => {
    renderPage();
    fireEvent.click(screen.getByText("Search Uploads"));
    expect(screen.getByText(/Enter an Upload ID/)).toBeInTheDocument();
  });

  it("shows alert on upload error", async () => {
    mockUpload.mockRejectedValue(new Error("Upload failed"));
    const alertMock = vi.spyOn(window, "alert").mockImplementation(() => {});
    renderPage();
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(input, { target: { files: [new File(["a"], "test.csv", { type: "text/csv" })] } });
    fireEvent.click(screen.getByRole("button", { name: /upload test.csv/i }));
    await vi.waitFor(() => {
      expect(alertMock).toHaveBeenCalledWith("Upload failed");
    });
    alertMock.mockRestore();
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
    const links = screen.getAllByText(/…/);
    expect(links.length).toBeGreaterThanOrEqual(1);
  });

  it("shows Search Uploads tab active when selected", () => {
    renderPage();
    fireEvent.click(screen.getByText("Search Uploads"));
    const searchTab = screen.getByText("Search Uploads");
    expect(searchTab.className).toContain("bg-white");
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
});
