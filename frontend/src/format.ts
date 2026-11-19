// Display formatting only — no premium calculation happens in the frontend.

const amountFormat = new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 });

/** "1234.5" -> "1,234.5 ₪". The value comes from the API as a decimal string. */
export function formatILS(amount: string): string {
  return `${amountFormat.format(Number(amount))} ₪`;
}

/**
 * Direction for a <bdi> around a short value. A run with no letters (amounts, phone
 * numbers, "+150 ₪", "17–90") would inherit the page's RTL and flip signs/ranges,
 * so it is forced LTR. Text with Hebrew letters keeps automatic direction.
 */
export function bidiDir(text: string): "ltr" | undefined {
  return /[\u0590-\u05FF]/.test(text) ? undefined : "ltr";
}

const dateFormat = new Intl.DateTimeFormat("en-GB", {
  timeZone: "Asia/Jerusalem",
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
});

/** ISO timestamp -> "DD/MM/YYYY" in Israel time (same as the PDF). */
export function formatDate(iso: string): string {
  return dateFormat.format(new Date(iso));
}

/** "1.50" -> "×1.5" */
export function formatFactor(value: string): string {
  return `×${Number(value)}`;
}
