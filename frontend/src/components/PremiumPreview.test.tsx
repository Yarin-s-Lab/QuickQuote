import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { PREVIEW } from "../test-fixtures";
import { formatFactor, formatILS } from "../format";
import { PremiumPreview } from "./PremiumPreview";

describe("formatting", () => {
  it.each([
    ["6975", "6,975 ₪"],
    ["1234", "1,234 ₪"],
    ["2000.00", "2,000 ₪"],
    ["1700.5", "1,700.5 ₪"],
    ["-100.000", "-100 ₪"],
  ])("formatILS(%s) = %s", (input, expected) => {
    expect(formatILS(input)).toBe(expected);
  });

  it("formats factors", () => {
    expect(formatFactor("1.50")).toBe("×1.5");
  });
});

describe("PremiumPreview", () => {
  it("shows the premium from the API, isolated with <bdi>", () => {
    render(<PremiumPreview preview={PREVIEW} stale={false} />);
    const premium = screen.getByTestId("premium");
    expect(premium).toHaveTextContent("6,975 ₪");
    expect(premium.tagName).toBe("BDI");
  });

  it("lists every breakdown line and factor", () => {
    render(<PremiumPreview preview={PREVIEW} stale={false} />);
    for (const line of PREVIEW.breakdown) {
      expect(screen.getByRole("rowheader", { name: line.label_he })).toBeInTheDocument();
    }
    expect(screen.getByText("×1.5")).toBeInTheDocument();
    expect(screen.getByText("3,325 ₪")).toBeInTheDocument();
  });

  it("flags minimum premium and stale data", () => {
    render(<PremiumPreview preview={{ ...PREVIEW, minimum_applied: true }} stale />);
    expect(screen.getByText("הוחלה פרמיה מינימלית.")).toBeInTheDocument();
    expect(screen.getByText(/הנתונים השתנו/)).toBeInTheDocument();
  });
});
