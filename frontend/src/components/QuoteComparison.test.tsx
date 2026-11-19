import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { CreateQuoteResponse } from "../api/types";
import { QuoteComparison } from "./QuoteComparison";

const LABELS = { car: "ביטוח רכב", apartment: "ביטוח דירה" };

function quote(n: number, product: "car" | "apartment", premium = "1000"): CreateQuoteResponse {
  return {
    quote_number: `Q-2026-00000${n}`,
    product,
    premium,
    issued_at: "2026-11-19T08:30:00Z",
    valid_until: "2026-12-19T08:30:00Z",
    download_url: `/api/quotes/download/${String(n).repeat(43)}`,
  };
}

function pdfResponse(filename = "compare-Q-2026-000001-Q-2026-000003.pdf") {
  return new Response("%PDF-1.7", {
    status: 200,
    headers: {
      "Content-Type": "application/pdf",
      "Content-Disposition": `attachment; filename="${filename}"`,
    },
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("QuoteComparison", () => {
  it("is hidden with fewer than two quotes of the same product", () => {
    const { container, rerender } = render(<QuoteComparison quotes={[]} productLabels={LABELS} />);
    expect(container).toBeEmptyDOMElement();
    rerender(<QuoteComparison quotes={[quote(1, "car")]} productLabels={LABELS} />);
    expect(container).toBeEmptyDOMElement();
    rerender(
      <QuoteComparison quotes={[quote(1, "car"), quote(2, "apartment")]} productLabels={LABELS} />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("appears with two quotes of the same product", () => {
    render(<QuoteComparison quotes={[quote(1, "car"), quote(2, "car")]} productLabels={LABELS} />);
    expect(screen.getByRole("heading", { name: "השוואת הצעות" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "הורד השוואה" })).toBeDisabled();
  });

  it("disables quotes of another product and products with no pair", async () => {
    const user = userEvent.setup();
    const quotes = [quote(1, "car"), quote(2, "apartment"), quote(3, "car")];
    render(<QuoteComparison quotes={quotes} productLabels={LABELS} />);

    // A lone apartment has nothing to pair with.
    expect(screen.getByLabelText("הצעה Q-2026-000002")).toBeDisabled();
    await user.click(screen.getByLabelText("הצעה Q-2026-000001"));
    expect(screen.getByLabelText("הצעה Q-2026-000002")).toBeDisabled();
    expect(screen.getByLabelText("הצעה Q-2026-000003")).toBeEnabled();
  });

  it("allows at most two selections", async () => {
    const user = userEvent.setup();
    const quotes = [quote(1, "car"), quote(2, "car"), quote(3, "car")];
    render(<QuoteComparison quotes={quotes} productLabels={LABELS} />);

    await user.click(screen.getByLabelText("הצעה Q-2026-000001"));
    await user.click(screen.getByLabelText("הצעה Q-2026-000002"));
    expect(screen.getByLabelText("הצעה Q-2026-000003")).toBeDisabled();
    expect(screen.getByRole("button", { name: "הורד השוואה" })).toBeEnabled();

    // Unselecting frees a slot again.
    await user.click(screen.getByLabelText("הצעה Q-2026-000002"));
    expect(screen.getByLabelText("הצעה Q-2026-000003")).toBeEnabled();
  });

  it("posts the two tokens in the body, in selection order, and saves the PDF", async () => {
    const user = userEvent.setup();
    const fetchMock = vi.fn().mockResolvedValue(pdfResponse());
    vi.stubGlobal("fetch", fetchMock);
    const saveFile = vi.fn();
    const quotes = [quote(1, "car"), quote(2, "apartment"), quote(3, "car")];
    render(<QuoteComparison quotes={quotes} productLabels={LABELS} saveFile={saveFile} />);

    await user.click(screen.getByLabelText("הצעה Q-2026-000003")); // picked first = quote A
    await user.click(screen.getByLabelText("הצעה Q-2026-000001"));
    expect(screen.getByText("הצעה א'")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "הורד השוואה" }));

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/quotes/compare");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body)).toEqual({ tokens: ["3".repeat(43), "1".repeat(43)] });
    expect(url).not.toContain("3".repeat(43)); // tokens never in the URL
    await vi.waitFor(() => expect(saveFile).toHaveBeenCalledTimes(1));
    const [blob, filename] = saveFile.mock.calls[0];
    expect(blob).toBeInstanceOf(Blob);
    expect(filename).toBe("compare-Q-2026-000001-Q-2026-000003.pdf");
  });

  it("shows the server's Hebrew error", async () => {
    const user = userEvent.setup();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            error: { code: "quote_expired", message_he: "תוקף ההצעה פג ולא ניתן להוריד אותה" },
          }),
          { status: 410, headers: { "Content-Type": "application/json" } },
        ),
      ),
    );
    const saveFile = vi.fn();
    render(
      <QuoteComparison
        quotes={[quote(1, "car"), quote(2, "car")]}
        productLabels={LABELS}
        saveFile={saveFile}
      />,
    );
    await user.click(screen.getByLabelText("הצעה Q-2026-000001"));
    await user.click(screen.getByLabelText("הצעה Q-2026-000002"));
    await user.click(screen.getByRole("button", { name: "הורד השוואה" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("תוקף ההצעה פג");
    expect(saveFile).not.toHaveBeenCalled();
  });
});
