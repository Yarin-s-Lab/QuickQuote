import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { PREVIEW } from "../test-fixtures";
import { bidiDir, formatFactor, formatILS } from "../format";
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

  it.each([
    ["+150 ₪", "ltr"],
    ["17–90", "ltr"],
    ["-100 ₪", "ltr"],
    ["0.05% משווי המבנה", undefined],
  ])("bidiDir(%s) = %s", (text, expected) => {
    expect(bidiDir(text)).toBe(expected);
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

  it("forces LTR on every amount so a negative sign never flips", () => {
    const preview = {
      ...PREVIEW,
      breakdown: [...PREVIEW.breakdown, { code: "x", label_he: "הנחה", amount: "-100.000" }],
    };
    render(<PremiumPreview preview={preview} stale={false} />);
    const negative = screen.getByText("-100 ₪");
    expect(negative.tagName).toBe("BDI");
    expect(negative).toHaveAttribute("dir", "ltr");
    expect(screen.getByTestId("premium")).toHaveAttribute("dir", "ltr");
    expect(screen.getByText("×1.5")).toHaveAttribute("dir", "ltr");
  });

  it("flags minimum premium and stale data", () => {
    render(<PremiumPreview preview={{ ...PREVIEW, minimum_applied: true }} stale />);
    expect(screen.getByText("הוחלה פרמיה מינימלית.")).toBeInTheDocument();
    expect(screen.getByText(/הנתונים השתנו/)).toBeInTheDocument();
  });
});
