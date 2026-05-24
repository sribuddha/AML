import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import FileUploader from "./FileUploader";

function createFile(name = "test.csv") {
  return new File(["a,b,c\n1,2,3"], name, { type: "text/csv" });
}

function renderFileUploader(onUpload = async () => {}) {
  const utils = render(<FileUploader onUpload={onUpload} />);
  const input = utils.container.querySelector('input[type="file"]') as HTMLInputElement;
  return { ...utils, input };
}

describe("FileUploader", () => {
  it("shows drop zone prompt", () => {
    render(<FileUploader onUpload={async () => {}} />);
    expect(screen.getByText(/drag.*drop.*csv/i)).toBeInTheDocument();
  });

  it("accepts file via input", () => {
    const { input } = renderFileUploader();
    const file = createFile();
    fireEvent.change(input, { target: { files: [file] } });
    expect(screen.getByText("test.csv")).toBeInTheDocument();
  });

  it("shows upload button after file selected", () => {
    const { input } = renderFileUploader();
    fireEvent.change(input, { target: { files: [createFile()] } });
    expect(screen.getByRole("button", { name: /upload test.csv/i })).toBeInTheDocument();
  });

  it("calls onUpload when button clicked", async () => {
    const onUpload = vi.fn().mockResolvedValue(undefined);
    const { input } = renderFileUploader(onUpload);
    fireEvent.change(input, { target: { files: [createFile()] } });
    fireEvent.click(screen.getByRole("button", { name: /upload/i }));
    expect(onUpload).toHaveBeenCalledTimes(1);
  });

  it("shows uploading spinner while uploading", async () => {
    let resolve: () => void;
    const promise = new Promise<void>((r) => { resolve = r; });
    const onUpload = vi.fn().mockReturnValue(promise);

    const { input } = renderFileUploader(onUpload);
    fireEvent.change(input, { target: { files: [createFile()] } });
    fireEvent.click(screen.getByRole("button", { name: /upload/i }));

    expect(screen.getByText("Uploading...")).toBeInTheDocument();
    resolve!();
  });

  it("applies drag-over styles", () => {
    render(<FileUploader onUpload={async () => {}} />);
    const zone = screen.getByText(/drag.*drop.*csv/i).closest("div")!;
    fireEvent.dragOver(zone);
    expect(zone.className).toContain("border-blue-400");
  });

  it("accepts file via drop", () => {
    render(<FileUploader onUpload={async () => {}} />);
    const zone = screen.getByText(/drag.*drop.*csv/i).closest("div")!;
    const file = createFile("dropped.csv");
    fireEvent.drop(zone, { dataTransfer: { files: [file] } });
    expect(screen.getByText("dropped.csv")).toBeInTheDocument();
  });

  it("removes drag-over style on dragLeave", () => {
    render(<FileUploader onUpload={async () => {}} />);
    const zone = screen.getByText(/drag.*drop.*csv/i).closest("div")!;
    fireEvent.dragOver(zone);
    expect(zone.className).toContain("border-blue-400");
    fireEvent.dragLeave(zone);
    expect(zone.className).not.toContain("border-blue-400");
  });
});
