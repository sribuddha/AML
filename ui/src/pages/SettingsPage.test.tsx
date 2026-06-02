import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { api, ApiError, getApiKey } from "../api/client";
import SettingsPage from "./SettingsPage";

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
  setApiKey: vi.fn(),
  clearApiKey: vi.fn(),
  getApiKey: vi.fn(() => ""),
  STORAGE_KEY: "aml_api_key",
}));

const mockNavigate = vi.fn();
vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual("react-router-dom");
  return { ...actual, useNavigate: () => mockNavigate };
});

function renderSettings() {
  return render(
    <MemoryRouter>
      <SettingsPage />
    </MemoryRouter>
  );
}

describe("SettingsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getApiKey.mockReturnValue("");
  });

  it("renders the settings heading", () => {
    renderSettings();
    expect(screen.getByText("Settings")).toBeInTheDocument();
  });

  it("shows an input for the API key", () => {
    renderSettings();
    expect(screen.getByLabelText("API Key")).toBeInTheDocument();
  });

  it("shows Save button", () => {
    renderSettings();
    expect(screen.getByText("Save")).toBeInTheDocument();
  });

  it("does not show Clear button when no key is stored", () => {
    renderSettings();
    expect(screen.queryByText("Clear")).not.toBeInTheDocument();
  });

  it("shows Clear button when a key is stored", async () => {
    const { getApiKey } = await import("../api/client");
    getApiKey.mockReturnValue("stored-key");
    renderSettings();
    expect(screen.getByText("Clear")).toBeInTheDocument();
    expect(screen.getByLabelText("API Key")).toHaveValue("stored-key");
  });

  it("calls clearApiKey and navigates on Clear", async () => {
    const { getApiKey, clearApiKey } = await import("../api/client");
    getApiKey.mockReturnValue("stored-key");
    renderSettings();
    fireEvent.click(screen.getByText("Clear"));
    expect(clearApiKey).toHaveBeenCalled();
    expect(mockNavigate).toHaveBeenCalledWith("/");
  });

  it("validates the key on Save", async () => {
    (api.get as ReturnType<typeof vi.fn>).mockResolvedValue({ items: [], total: 0 });
    renderSettings();
    const input = screen.getByLabelText("API Key");
    fireEvent.change(input, { target: { value: "my-key" } });
    fireEvent.click(screen.getByText("Save"));
    expect(await screen.findByText("API key is valid")).toBeInTheDocument();
  });

  it("shows error when key is invalid", async () => {
    (api.get as ReturnType<typeof vi.fn>).mockRejectedValue(new ApiError(401, "Unauthorized"));
    renderSettings();
    const input = screen.getByLabelText("API Key");
    fireEvent.change(input, { target: { value: "bad-key" } });
    fireEvent.click(screen.getByText("Save"));
    expect(await screen.findByText("Unauthorized")).toBeInTheDocument();
  });

  it("clears key and navigates when saving empty key", async () => {
    const { clearApiKey } = await import("../api/client");
    renderSettings();
    fireEvent.click(screen.getByText("Save"));
    expect(clearApiKey).toHaveBeenCalled();
    expect(mockNavigate).toHaveBeenCalledWith("/");
  });

  it("calls setApiKey on successful validation", async () => {
    const { setApiKey } = await import("../api/client");
    (api.get as ReturnType<typeof vi.fn>).mockResolvedValue({ items: [], total: 0 });
    renderSettings();
    const input = screen.getByLabelText("API Key");
    fireEvent.change(input, { target: { value: "valid-key" } });
    fireEvent.click(screen.getByText("Save"));
    await screen.findByText("API key is valid");
    expect(setApiKey).toHaveBeenCalledWith("valid-key");
  });
});
