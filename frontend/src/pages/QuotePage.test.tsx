import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { CREATED, PREVIEW, PRODUCTS } from "../test-fixtures";
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

  it("blocks quote creation until agent and client details are valid", async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(json(200, PRODUCTS));
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    render(<QuotePage />);

    await user.click(await screen.findByRole("button", { name: "צור הצעה" }));

    expect(screen.getByRole("alert")).toHaveTextContent("יש להשלים את פרטי הסוכן והלקוח");
    expect(screen.getByText("יש להזין שם סוכן")).toBeInTheDocument();
    expect(screen.getByText("יש להזין שם לקוח")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(1); // only GET /products
  });

  it("creates a quote and shows its number and validity", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(json(200, PRODUCTS))
      .mockResolvedValueOnce(json(201, CREATED));
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    render(<QuotePage />);

    await user.type(await screen.findByLabelText("שם הסוכן"), "דנה כהן");
    await user.type(screen.getByLabelText("שם הלקוח"), "ישראל ישראלי");
    await user.type(screen.getByLabelText("גיל הנהג"), "23");
    await user.type(screen.getByLabelText("שווי הרכב (₪)"), "100000");
    await user.click(screen.getByRole("button", { name: "צור הצעה" }));

    const number = await screen.findByTestId("quote-number");
    expect(number).toHaveTextContent("Q-2026-000001");
    expect(number).toHaveAttribute("dir", "ltr");
    // 22:30 UTC on 19/12 is already 20/12 in Israel, same rule as the PDF.
    expect(screen.getByTestId("valid-until")).toHaveTextContent("20/12/2026");
    const link = screen.getByRole("link", { name: "הורדת PDF" });
    expect(link).toHaveAttribute("href", CREATED.download_url);
    expect(link).toHaveAttribute("rel", "noreferrer");

    const [url, init] = fetchMock.mock.calls[1];
    expect(url).toBe("/api/quotes");
    expect(JSON.parse(init.body)).toEqual({
      product: "car",
      inputs: { driver_age: 23, car_value: 100000, coverage_type: "comprehensive" },
      coverages: [],
      agent_name: "דנה כהן",
      client_full_name: "ישראל ישראלי",
      client_phone: "",
      client_email: "",
    });
  });

  it("shows a backend error when creation fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(json(200, PRODUCTS))
        .mockResolvedValueOnce(
          json(503, { error: { code: "pdf_unavailable", message_he: "יצירת PDF אינה זמינה בשרת זה" } }),
        ),
    );
    const user = userEvent.setup();
    render(<QuotePage />);

    await user.type(await screen.findByLabelText("שם הסוכן"), "דנה");
    await user.type(screen.getByLabelText("שם הלקוח"), "ישראל");
    await user.click(screen.getByRole("button", { name: "צור הצעה" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("יצירת PDF אינה זמינה בשרת זה");
  });

  it("renders right-to-left content", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValueOnce(json(200, PRODUCTS)));
    render(<QuotePage />);
    expect(await screen.findByRole("heading", { name: "הצעת מחיר לביטוח" })).toBeInTheDocument();
  });
});
