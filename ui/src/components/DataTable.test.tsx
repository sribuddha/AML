import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import DataTable from "./DataTable";
import type { Column } from "./DataTable";

interface Item {
  id: string;
  name: string;
  value: number;
}

const columns: Column<Item>[] = [
  { key: "name", label: "Name" },
  { key: "value", label: "Value" },
];

const data: Item[] = [
  { id: "1", name: "Charlie", value: 30 },
  { id: "2", name: "Alice", value: 10 },
  { id: "3", name: "Bob", value: 20 },
];

describe("DataTable", () => {
  it("renders data rows", () => {
    render(<DataTable columns={columns} data={data} />);
    expect(screen.getByText("Charlie")).toBeInTheDocument();
    expect(screen.getByText("Alice")).toBeInTheDocument();
    expect(screen.getByText("Bob")).toBeInTheDocument();
  });

  it("renders column headers", () => {
    render(<DataTable columns={columns} data={data} />);
    expect(screen.getByText("Name")).toBeInTheDocument();
    expect(screen.getByText("Value")).toBeInTheDocument();
  });

  it("shows empty message when no data", () => {
    render(<DataTable columns={columns} data={[]} emptyMessage="Nothing here" />);
    expect(screen.getByText("Nothing here")).toBeInTheDocument();
  });

  it("shows loading skeleton by default", () => {
    const { container } = render(<DataTable columns={columns} data={[]} loading />);
    const skeletons = container.querySelectorAll(".animate-pulse");
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it("shows error message and retry button", () => {
    const onRetry = vi.fn();
    render(<DataTable columns={columns} data={[]} error="Oops" onRetry={onRetry} />);
    expect(screen.getByText("Oops")).toBeInTheDocument();
    fireEvent.click(screen.getByText("Retry"));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it("sorts ascending on first click", () => {
    render(<DataTable columns={columns} data={data} />);
    fireEvent.click(screen.getByText("Name"));
    const rows = screen.getAllByRole("row");
    expect(rows[1]).toHaveTextContent("Alice");
    expect(rows[2]).toHaveTextContent("Bob");
    expect(rows[3]).toHaveTextContent("Charlie");
  });

  it("sorts descending on second click", () => {
    render(<DataTable columns={columns} data={data} />);
    const header = screen.getByText("Name");
    fireEvent.click(header);
    fireEvent.click(header);
    const rows = screen.getAllByRole("row");
    expect(rows[1]).toHaveTextContent("Charlie");
    expect(rows[2]).toHaveTextContent("Bob");
    expect(rows[3]).toHaveTextContent("Alice");
  });

  it("restores original order on third click", () => {
    render(<DataTable columns={columns} data={data} />);
    const header = screen.getByText("Name");
    fireEvent.click(header);
    fireEvent.click(header);
    fireEvent.click(header);
    const rows = screen.getAllByRole("row");
    expect(rows[1]).toHaveTextContent("Charlie");
    expect(rows[2]).toHaveTextContent("Alice");
    expect(rows[3]).toHaveTextContent("Bob");
  });

  it("sorts numeric values correctly", () => {
    render(<DataTable columns={columns} data={data} />);
    fireEvent.click(screen.getByText("Value"));
    const rows = screen.getAllByRole("row");
    expect(rows[1]).toHaveTextContent("10");
    expect(rows[2]).toHaveTextContent("20");
    expect(rows[3]).toHaveTextContent("30");
  });

  it("switches sort column on different header click", () => {
    render(<DataTable columns={columns} data={data} />);
    fireEvent.click(screen.getByText("Value"));
    fireEvent.click(screen.getByText("Name"));
    const rows = screen.getAllByRole("row");
    expect(rows[1]).toHaveTextContent("Alice");
    expect(rows[2]).toHaveTextContent("Bob");
    expect(rows[3]).toHaveTextContent("Charlie");
  });

  it("renders pagination when total > 0 and onPageChange provided", () => {
    render(<DataTable columns={columns} data={data} total={30} perPage={10} page={1} onPageChange={() => {}} />);
    expect(screen.getByText("30 results")).toBeInTheDocument();
  });

  it("does not render pagination when onPageChange is missing", () => {
    render(<DataTable columns={columns} data={data} total={30} perPage={10} page={1} />);
    expect(screen.queryByText("30 results")).not.toBeInTheDocument();
  });

  it("marks column with sortable:false as unsortable", () => {
    const cols: Column<Item>[] = [
      { key: "name", label: "Name", sortable: false },
      { key: "value", label: "Value" },
    ];
    render(<DataTable columns={cols} data={data} />);
    fireEvent.click(screen.getByText("Name"));
    const rows = screen.getAllByRole("row");
    expect(rows[1]).toHaveTextContent("Charlie");
  });

  it("renders custom cell content via render prop", () => {
    const cols: Column<Item>[] = [
      { key: "name", label: "Name", render: (item) => <a href={`/${item.id}`}>{item.name}</a> },
    ];
    render(<DataTable columns={cols} data={data} />);
    expect(screen.getByRole("link", { name: "Charlie" })).toHaveAttribute("href", "/1");
  });

  it("sorts numeric strings correctly", () => {
    interface NumStrItem { id: string; code: string; }
    const cols: Column<NumStrItem>[] = [{ key: "code", label: "Code" }];
    const items: NumStrItem[] = [
      { id: "1", code: "100" },
      { id: "2", code: "50" },
      { id: "3", code: "200" },
    ];
    render(<DataTable columns={cols} data={items} />);
    fireEvent.click(screen.getByText("Code"));
    const rows = screen.getAllByRole("row");
    expect(rows[1]).toHaveTextContent("50");
    expect(rows[2]).toHaveTextContent("100");
    expect(rows[3]).toHaveTextContent("200");
  });
});
