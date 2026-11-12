import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { PREVIEW, PRODUCTS } from "../test-fixtures";
import { QuotePage } from "./QuotePage";

function json(status: number, body: unknown) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("QuotePage", () => {
  it("builds the form from /api/products and shows the preview from the API", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(json(200, PRODUCTS))
      .mockResolvedValueOnce(json(200, PREVIEW));
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    render(<QuotePage />);

    await user.type(await screen.findByLabelText("גיל הנהג"), "23");
    await user.type(screen.getByLabelText("שווי הרכב (₪)"), "100000");
    await user.click(screen.getByLabelText(/גרירה/));
    await user.click(screen.getByRole("button", { name: "חשב פרמיה" }));

    expect(await screen.findByTestId("premium")).toHaveTextContent("6,975 ₪");
    const [url, init] = fetchMock.mock.calls[1];
    expect(url).toBe("/api/quotes/preview");
    expect(JSON.parse(init.body)).toEqual({
      product: "car",
      inputs: { driver_age: 23, car_value: 100000, coverage_type: "comprehensive" },
      coverages: ["towing"],
    });
  });

  it("switches product and shows that product's fields", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValueOnce(json(200, PRODUCTS)));
    const user = userEvent.setup();
    render(<QuotePage />);

    await user.click(await screen.findByLabelText("ביטוח דירה"));
    expect(screen.getByLabelText("קומה")).toBeInTheDocument();
    expect(screen.getByLabelText("יש אזעקה")).toBeInTheDocument();
    expect(screen.queryByLabelText("גיל הנהג")).not.toBeInTheDocument();
  });

  it("shows the backend validation message in Hebrew", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(json(200, PRODUCTS))
        .mockResolvedValueOnce(
          json(422, { error: { code: "validation_error", message_he: "גיל הנהג: שדה חובה" } }),
        ),
    );
    const user = userEvent.setup();
    render(<QuotePage />);

    await user.click(await screen.findByRole("button", { name: "חשב פרמיה" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("גיל הנהג: שדה חובה");
  });

  it("validates agent and client fields on blur", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValueOnce(json(200, PRODUCTS)));
    const user = userEvent.setup();
    render(<QuotePage />);

    await user.click(await screen.findByLabelText("שם הסוכן"));
    await user.tab();
    expect(screen.getByText("יש להזין שם סוכן")).toBeInTheDocument();
  });

  it("renders right-to-left content", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValueOnce(json(200, PRODUCTS)));
    render(<QuotePage />);
    expect(await screen.findByRole("heading", { name: "הצעת מחיר לביטוח" })).toBeInTheDocument();
  });
});
