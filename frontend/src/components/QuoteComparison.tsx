import { useState } from "react";
import { ApiError, compareQuotes } from "../api/client";
import { tokenFromDownloadUrl, type CreateQuoteResponse, type ProductCode } from "../api/types";
import { formatILS } from "../format";

interface Props {
  /** Quotes created in this session (component state only, never persisted). */
  quotes: CreateQuoteResponse[];
  productLabels: Record<string, string>;
  /** Injected for tests; saves the PDF in the browser by default. */
  saveFile?: (blob: Blob, filename: string) => void;
}

function saveWithLink(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.rel = "noreferrer";
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function countByProduct(quotes: CreateQuoteResponse[]): Map<ProductCode, number> {
  const counts = new Map<ProductCode, number>();
  for (const q of quotes) counts.set(q.product, (counts.get(q.product) ?? 0) + 1);
  return counts;
}

/**
 * Pick two quotes of the same product and download a side-by-side PDF.
 * Shown only when at least two quotes share a product. The first quote picked is
 * quote A (right column in the RTL document).
 */
export function QuoteComparison({ quotes, productLabels, saveFile = saveWithLink }: Props) {
  const [selected, setSelected] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const counts = countByProduct(quotes);
  if (![...counts.values()].some((n) => n >= 2)) return null;

  const byNumber = new Map(quotes.map((q) => [q.quote_number, q]));
  const selectedProduct = selected.length ? byNumber.get(selected[0])?.product : undefined;

  function isSelectable(q: CreateQuoteResponse): boolean {
    if (selected.includes(q.quote_number)) return true;
    if ((counts.get(q.product) ?? 0) < 2) return false; // nothing to pair it with
    if (selectedProduct && q.product !== selectedProduct) return false;
    return selected.length < 2;
  }

  function toggle(number: string) {
    setError(null);
    setSelected((prev) =>
      prev.includes(number) ? prev.filter((n) => n !== number) : [...prev, number].slice(0, 2),
    );
  }

  async function download() {
    const [a, b] = selected.map((n) => byNumber.get(n));
    if (!a || !b) return;
    setBusy(true);
    setError(null);
    try {
      const file = await compareQuotes([
        tokenFromDownloadUrl(a.download_url),
        tokenFromDownloadUrl(b.download_url),
      ]);
      saveFile(file.blob, file.filename);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "שגיאה לא צפויה");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="card comparison" aria-labelledby="comparison-title">
      <h2 id="comparison-title">השוואת הצעות</h2>
      <p className="hint">בחרו שתי הצעות של אותו מוצר. ההצעה הראשונה שנבחרה תופיע מימין.</p>
      <ul className="comparison-list">
        {quotes.map((q) => {
          const order = selected.indexOf(q.quote_number);
          return (
            <li key={q.quote_number}>
              <label className="choice">
                <input
                  type="checkbox"
                  checked={order >= 0}
                  disabled={!isSelectable(q) || busy}
                  onChange={() => toggle(q.quote_number)}
                  aria-label={`הצעה ${q.quote_number}`}
                />
                <bdi dir="ltr">{q.quote_number}</bdi> · {productLabels[q.product] ?? q.product} ·{" "}
                <bdi dir="ltr">{formatILS(q.premium)}</bdi>
                {order >= 0 && <span className="pick">{order === 0 ? "הצעה א'" : "הצעה ב'"}</span>}
              </label>
            </li>
          );
        })}
      </ul>
      <button type="button" className="primary" onClick={download} disabled={selected.length !== 2 || busy}>
        {busy ? "מכין השוואה…" : "הורד השוואה"}
      </button>
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
    </section>
  );
}
