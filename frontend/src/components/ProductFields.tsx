import type { ProductField } from "../api/types";

export type FieldValues = Record<string, string | boolean>;

interface Props {
  fields: ProductField[];
  values: FieldValues;
  onChange: (name: string, value: string | boolean) => void;
}

function rangeHint(field: ProductField): string | null {
  if (field.min === null || field.max === null) return null;
  const fmt = (n: number) => n.toLocaleString("en-US");
  return `${fmt(field.min)}–${fmt(field.max)}`;
}

export function ProductFields({ fields, values, onChange }: Props) {
  return (
    <fieldset className="card">
      <legend>נתוני המוצר</legend>
      <div className="grid">
        {fields.map((field) => {
          const id = `field-${field.name}`;
          const value = values[field.name];

          if (field.type === "boolean") {
            return (
              <label key={field.name} className="choice" htmlFor={id}>
                <input
                  id={id}
                  type="checkbox"
                  checked={value === true}
                  onChange={(e) => onChange(field.name, e.target.checked)}
                />
                {field.label_he}
              </label>
            );
          }

          if (field.type === "enum") {
            return (
              <div key={field.name} className="field">
                <label htmlFor={id}>{field.label_he}</label>
                <select
                  id={id}
                  value={String(value ?? "")}
                  onChange={(e) => onChange(field.name, e.target.value)}
                >
                  {field.options?.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label_he}
                    </option>
                  ))}
                </select>
              </div>
            );
          }

          const hint = rangeHint(field);
          return (
            <div key={field.name} className="field">
              <label htmlFor={id}>{field.label_he}</label>
              <input
                id={id}
                type="number"
                inputMode="numeric"
                dir="ltr"
                step={1}
                min={field.min ?? undefined}
                max={field.max ?? undefined}
                required={field.required}
                value={String(value ?? "")}
                onChange={(e) => onChange(field.name, e.target.value)}
              />
              {hint && (
                <small className="hint">
                  טווח: <bdi>{hint}</bdi>
                </small>
              )}
            </div>
          );
        })}
      </div>
    </fieldset>
  );
}
