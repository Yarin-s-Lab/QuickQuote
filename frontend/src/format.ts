// Display formatting only — no premium calculation happens in the frontend.

const amountFormat = new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 });

/** "1234.5" -> "1,234.5 ₪". The value comes from the API as a decimal string. */
export function formatILS(amount: string): string {
  return `${amountFormat.format(Number(amount))} ₪`;
}

/** "1.50" -> "×1.5" */
export function formatFactor(value: string): string {
  return `×${Number(value)}`;
}
