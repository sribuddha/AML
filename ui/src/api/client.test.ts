import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { api, ApiError } from "./client";

const mockFetch = vi.fn();
globalThis.fetch = mockFetch;

function okResponse(body: unknown) {
  return Promise.resolve(new Response(JSON.stringify(body), { status: 200 }));
}

function noContentResponse() {
  return Promise.resolve(new Response(null, { status: 204 }));
}

function errorResponse(status: number, detail?: string) {
  return Promise.resolve(new Response(detail ? JSON.stringify({ detail }) : null, { status }));
}

beforeEach(() => mockFetch.mockReset());
afterEach(() => mockFetch.mockReset());

describe("api.get", () => {
  it("makes GET request and returns JSON", async () => {
    mockFetch.mockResolvedValue(okResponse({ id: "1" }));
    const result = await api.get<{ id: string }>("/api/test");
    expect(result).toEqual({ id: "1" });
    expect(mockFetch).toHaveBeenCalledWith("/api/test", expect.objectContaining({}));
  });

  it("appends query params", async () => {
    mockFetch.mockResolvedValue(okResponse([]));
    await api.get("/api/test", { page: 1, name: "foo" });
    expect(mockFetch).toHaveBeenCalledWith("/api/test?page=1&name=foo", expect.anything());
  });

  it("skips undefined/null/empty params", async () => {
    mockFetch.mockResolvedValue(okResponse([]));
    await api.get("/api/test", { page: 1, name: undefined, extra: null, empty: "" });
    expect(mockFetch).toHaveBeenCalledWith("/api/test?page=1", expect.anything());
  });
});

describe("api.post", () => {
  it("makes POST request with JSON body", async () => {
    mockFetch.mockResolvedValue(okResponse({ created: true }));
    const result = await api.post("/api/test", { name: "x" });
    expect(result).toEqual({ created: true });
    expect(mockFetch).toHaveBeenCalledWith("/api/test", {
      method: "POST",
      body: JSON.stringify({ name: "x" }),
      headers: { "Content-Type": "application/json" },
    });
  });
});

describe("api.put", () => {
  it("makes PUT request with JSON body", async () => {
    mockFetch.mockResolvedValue(okResponse({ updated: true }));
    const result = await api.put("/api/test/1", { name: "y" });
    expect(result).toEqual({ updated: true });
    expect(mockFetch).toHaveBeenCalledWith("/api/test/1", {
      method: "PUT",
      body: JSON.stringify({ name: "y" }),
      headers: { "Content-Type": "application/json" },
    });
  });
});

describe("api.patch", () => {
  it("makes PATCH request with JSON body", async () => {
    mockFetch.mockResolvedValue(okResponse({ patched: true }));
    const result = await api.patch("/api/test/1", { status: "active" });
    expect(result).toEqual({ patched: true });
    expect(mockFetch).toHaveBeenCalledWith("/api/test/1", {
      method: "PATCH",
      body: JSON.stringify({ status: "active" }),
      headers: { "Content-Type": "application/json" },
    });
  });
});

describe("api.del", () => {
  it("makes DELETE request and returns undefined on 204", async () => {
    mockFetch.mockResolvedValue(noContentResponse());
    const result = await api.del<undefined>("/api/test/1");
    expect(result).toBeUndefined();
    expect(mockFetch).toHaveBeenCalledWith("/api/test/1", {
      method: "DELETE",
      headers: { "Content-Type": "application/json" },
    });
  });
});

describe("api.upload", () => {
  it("makes POST with FormData", async () => {
    mockFetch.mockResolvedValue(okResponse({ upload_id: "u1" }));
    const file = new File(["a,b,c\n1,2,3"], "test.csv", { type: "text/csv" });
    const result = await api.upload("/api/uploads", file);
    expect(result).toEqual({ upload_id: "u1" });
    const callArgs = mockFetch.mock.calls[0];
    expect(callArgs[0]).toBe("/api/uploads");
    expect(callArgs[1].method).toBe("POST");
    expect(callArgs[1].body instanceof FormData).toBe(true);
  });

  it("throws ApiError on upload error", async () => {
    mockFetch.mockResolvedValue(new Response(JSON.stringify({ detail: "Upload rejected" }), { status: 422 }));
    await expect(api.upload("/api/uploads", new File(["a"], "test.csv"))).rejects.toThrow("Upload rejected");
  });
});

describe("api.download", () => {
  it("creates anchor and clicks it", () => {
    const click = vi.fn();
    const createElement = vi.spyOn(document, "createElement").mockReturnValue({
      href: "",
      download: "",
      click,
    } as unknown as HTMLAnchorElement);

    api.download("/api/generate/file.csv");
    expect(createElement).toHaveBeenCalledWith("a");
    expect(click).toHaveBeenCalled();
    createElement.mockRestore();
  });
});

describe("ApiError", () => {
  it("throws ApiError on 404", async () => {
    mockFetch.mockResolvedValue(errorResponse(404, "Not found"));
    try {
      await api.get("/api/missing");
      expect.unreachable();
    } catch (e) {
      expect(e instanceof ApiError).toBe(true);
      expect((e as ApiError).message).toBe("Not found");
    }
  });

  it("throws ApiError with HTTP status on error with no body", async () => {
    mockFetch.mockResolvedValue(errorResponse(500));
    await expect(api.get("/api/error")).rejects.toThrow("HTTP 500");
  });

  it("ApiError has status property", async () => {
    mockFetch.mockResolvedValue(errorResponse(403));
    try {
      await api.get("/api/forbidden");
    } catch (e) {
      expect(e instanceof ApiError).toBe(true);
      expect((e as ApiError).status).toBe(403);
    }
  });
});
