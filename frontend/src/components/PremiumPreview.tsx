import type { PreviewResponse } from "../api/types";
import { formatFactor, formatILS } from "../format";

interface Props {
  preview: PreviewResponse;
  stale: boolean;
}

export function PremiumPreview({ preview, stale }: Props) {
  return (
    <section className="card preview" aria-live="polite" aria-label="תצוגה מקדימה">
      <h2>
        פרמיה שנתית: <bdi data-testid="premium">{formatILS(preview.premium)}</bdi>
      </h2>
      {stale && <p className="stale">הנתונים השתנו — לחצו "חשב פרמיה" לעדכון.</p>}
      {preview.minimum_applied && <p className="note">הוחלה פרמיה מינימלית.</p>}

      <table>
        <caption>פירוט החישוב</caption>
        <tbody>
          {preview.breakdown.map((line) => (
            <tr key={line.code}>
              <th scope="row">{line.label_he}</th>
              <td>
                <bdi>{formatILS(line.amount)}</bdi>
              </td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr>
            <th scope="row">סה"כ לפני עיגול</th>
            <td>
              <bdi>{formatILS(preview.premium_before_rounding)}</bdi>
            </td>
          </tr>
        </tfoot>
      </table>

      <h3>פקטורים</h3>
      <ul className="factors">
        {preview.factors.map((factor) => (
          <li key={factor.code}>
            {factor.label_he}: <bdi>{formatFactor(factor.value)}</bdi>
          </li>
        ))}
      </ul>
      <p className="disclaimer">תצוגה מקדימה בלבד — הצעה לדוגמה, לא מחייבת.</p>
    </section>
  );
}
