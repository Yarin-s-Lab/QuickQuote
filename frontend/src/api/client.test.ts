import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, compareQuotes, createQuote, getProducts, previewQuote } from "./client";
import { CREATED, PREVIEW, PRODUCTS } from "../test-fixtures";

function mockFetch(status: number, body: unknown) {
  const fn = vi.fn().mockResolvedValue(
    new Response(typeof body === "string" ? body : JSON.stringify(body), {
      status,
      headers: { "Content-Type": "application/json" },
    }),
  );
  vi.stubGlobal("fetch", fn);
  return fn;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("api client", () => {
  it("loads and validates products", async () => {
    const fetchMock = mockFetch(200, PRODUCTS);
    const data = await getProducts();
    expect(fetchMock).toHaveBeenCalledWith("/api/products", undefined);
    expect(data.products.map((p) => p.code)).toEqual(["car", "apartment"]);
  });

  it("posts the preview request as JSON", async () => {
    const fetchMock = mockFetch(200, PREVIEW);
    const payload = { product: "car" as const, inputs: { driver_age: 30 }, coverages: ["glass"] };
    const data = await previewQuote(payload);

    expect(data.premium).toBe("6975");
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/quotes/preview");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body)).toEqual(payload);
  });

  it("creates a quote with agent and client details", async () => {
    const fetchMock = mockFetch(201, CREATED);
    const payload = {
      product: "car" as const,
      inputs: { driver_age: 30 },
      coverages: [],
      agent_name: "דנה",
      client_full_name: "ישראל",
      client_phone: "",
      client_email: "",
    };
    const data = await createQuote(payload);
    expect(data.quote_number).toBe("Q-2026-000001");
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/quotes");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body)).toEqual(payload);
  });

  it.each([
    ["path traversal", "/api/quotes/download/../../etc/passwd"],
    ["other host", "https://evil.example/x.pdf"],
    ["short token", "/api/quotes/download/abc"],
  ])("rejects a download_url that is not a same-origin token link (%s)", async (_, url) => {
    mockFetch(201, { ...CREATED, download_url: url });
    await expect(
      createQuote({
        product: "car",
        inputs: {},
        coverages: [],
        agent_name: "a",
        client_full_name: "b",
        client_phone: "",
        client_email: "",
      }),
    ).rejects.toMatchObject({ code: "invalid_response" });
  });

  it("rejects a malformed quote number from the server", async () => {
    mockFetch(201, { ...CREATED, quote_number: "../../x" });
    await expect(
      createQuote({
        product: "car",
        inputs: {},
        coverages: [],
        agent_name: "a",
        client_full_name: "b",
        client_phone: "",
        client_email: "",
      }),
    ).rejects.toMatchObject({ code: "invalid_response" });
  });

  it("compareQuotes returns the PDF blob and the server's filename", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response("%PDF-1.7", {
        status: 200,
        headers: {
          "Content-Type": "application/pdf",
          "Content-Disposition": 'attachment; filename="compare-Q-2026-000001-Q-2026-000002.pdf"',
        },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const file = await compareQuotes(["a".repeat(43), "b".repeat(43)]);
    expect(file.filename).toBe("compare-Q-2026-000001-Q-2026-000002.pdf");
    expect(await file.blob.text()).toBe("%PDF-1.7");
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({
      tokens: ["a".repeat(43), "b".repeat(43)],
    });
  });

  it("compareQuotes ignores an unexpected filename from the server", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response("%PDF", {
          headers: {
            "Content-Type": "application/pdf",
            "Content-Disposition": 'attachment; filename="../../evil.exe"',
          },
        }),
      ),
    );
    expect((await compareQuotes(["a", "b"])).filename).toBe("compare.pdf");
  });

  it("compareQuotes rejects a non-PDF success response", async () => {
    mockFetch(200, { not: "a pdf" });
    await expect(compareQuotes(["a", "b"])).rejects.toMatchObject({ code: "invalid_response" });
  });

  it("compareQuotes surfaces 422/404/410 messages", async () => {
    mockFetch(422, { error: { code: "validation_error", message_he: "ניתן להשוות רק הצעות של אותו מוצר" } });
    await expect(compareQuotes(["a", "b"])).rejects.toMatchObject({
      code: "validation_error",
      message: "ניתן להשוות רק הצעות של אותו מוצר",
    });
  });

  it("surfaces the Hebrew message from the error envelope", async () => {
    mockFetch(422, { error: { code: "validation_error", message_he: "גיל הנהג: הערך חייב להיות לפחות 17" } });
    await expect(previewQuote({ product: "car", inputs: {}, coverages: [] })).rejects.toMatchObject({
      code: "validation_error",
      message: "גיל הנהג: הערך חייב להיות לפחות 17",
    });
  });

  it("handles a non-JSON error body", async () => {
    mockFetch(500, "<html>oops</html>");
    await expect(getProducts()).rejects.toMatchObject({ code: "http_error" });
  });

  it("rejects a response that does not match the contract", async () => {
    mockFetch(200, { ...PREVIEW, premium: 6975 });
    await expect(
      previewQuote({ product: "car", inputs: {}, coverages: [] }),
    ).rejects.toMatchObject({ code: "invalid_response" });
  });

  it("reports network failures in Hebrew", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    const error = await getProducts().catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).message).toBe("לא ניתן להתחבר לשרת");
  });
});
