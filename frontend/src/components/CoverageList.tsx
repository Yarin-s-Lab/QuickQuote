import type { Coverage } from "../api/types";

interface Props {
  coverages: Coverage[];
  selected: string[];
  onToggle: (code: string) => void;
}

export function CoverageList({ coverages, selected, onToggle }: Props) {
  return (
    <fieldset className="card">
      <legend>כיסויים נוספים</legend>
      <div className="choices">
        {coverages.map((coverage) => (
          <label key={coverage.code} className="choice">
            <input
              type="checkbox"
              checked={selected.includes(coverage.code)}
              onChange={() => onToggle(coverage.code)}
            />
            {coverage.label_he}{" "}
            <small className="hint">
              (<bdi>{coverage.price_rule_he}</bdi>)
            </small>
          </label>
        ))}
      </div>
    </fieldset>
  );
}
