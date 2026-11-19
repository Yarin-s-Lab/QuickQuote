import type { CreateQuoteResponse } from "../api/types";
import { formatDate, formatILS } from "../format";

interface Props {
  quote: CreateQuoteResponse;
}

export function QuoteCreated({ quote }: Props) {
  return (
    <section className="card created" role="status" aria-label="ההצעה נוצרה">
      <h2>
        ההצעה נוצרה: <bdi dir="ltr" data-testid="quote-number">{quote.quote_number}</bdi>
      </h2>
      <dl>
        <dt>פרמיה שנתית</dt>
        <dd>
          <bdi dir="ltr">{formatILS(quote.premium)}</bdi>
        </dd>
        <dt>תאריך הנפקה</dt>
        <dd>
          <bdi dir="ltr">{formatDate(quote.issued_at)}</bdi>
        </dd>
        <dt>בתוקף עד</dt>
        <dd>
          <bdi dir="ltr" data-testid="valid-until">
            {formatDate(quote.valid_until)}
          </bdi>
        </dd>
      </dl>
      {quote.download_url ? (
        <a href={quote.download_url}>הורדת PDF</a>
      ) : (
        <p className="note">קובץ ה-PDF נוצר ונשמר. קישור להורדה יתווסף בהמשך.</p>
      )}
    </section>
  );
}
