import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import Pagination from "./Pagination";

describe("Pagination", () => {
  it("renders total results count", () => {
    render(<Pagination page={1} perPage={10} total={50} onPageChange={() => {}} />);
    expect(screen.getByText("50 results")).toBeInTheDocument();
  });

  it("renders plural result text", () => {
    render(<Pagination page={1} perPage={10} total={11} onPageChange={() => {}} />);
    expect(screen.getByText("11 results")).toBeInTheDocument();
  });

  it("does not render when totalPages <= 1", () => {
    const { container } = render(<Pagination page={1} perPage={10} total={5} onPageChange={() => {}} />);
    expect(container.innerHTML).toBe("");
  });

  it("calls onPageChange with next page", () => {
    const onPageChange = vi.fn();
    render(<Pagination page={1} perPage={10} total={50} onPageChange={onPageChange} />);
    fireEvent.click(screen.getByText("Next →"));
    expect(onPageChange).toHaveBeenCalledWith(2);
  });

  it("calls onPageChange with previous page", () => {
    const onPageChange = vi.fn();
    render(<Pagination page={3} perPage={10} total={50} onPageChange={onPageChange} />);
    fireEvent.click(screen.getByText("← Prev"));
    expect(onPageChange).toHaveBeenCalledWith(2);
  });

  it("disables prev button on first page", () => {
    render(<Pagination page={1} perPage={10} total={50} onPageChange={() => {}} />);
    expect(screen.getByText("← Prev")).toBeDisabled();
  });

  it("disables next button on last page", () => {
    render(<Pagination page={5} perPage={10} total={50} onPageChange={() => {}} />);
    expect(screen.getByText("Next →")).toBeDisabled();
  });

  it("calls onPageChange with page number when clicked", () => {
    const onPageChange = vi.fn();
    render(<Pagination page={3} perPage={10} total={50} onPageChange={onPageChange} />);
    fireEvent.click(screen.getByText("3"));
    expect(onPageChange).toHaveBeenCalledWith(3);
  });

  it("highlights current page button", () => {
    render(<Pagination page={2} perPage={10} total={50} onPageChange={() => {}} />);
    const btn = screen.getByText("2");
    expect(btn.className).toContain("bg-blue-600");
  });

});
