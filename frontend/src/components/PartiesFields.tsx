import { MAX_TEXT, type Parties } from "../api/types";

export type PartiesErrors = Partial<Record<keyof Parties, string>>;

interface Props {
  values: Parties;
  errors: PartiesErrors;
  onChange: (name: keyof Parties, value: string) => void;
  onBlur: (name: keyof Parties) => void;
}

const FIELDS: { name: keyof Parties; label: string; type: string; dir?: "ltr" }[] = [
  { name: "agent_name", label: "שם הסוכן", type: "text" },
  { name: "client_full_name", label: "שם הלקוח", type: "text" },
  { name: "client_phone", label: "טלפון (רשות)", type: "tel", dir: "ltr" },
  { name: "client_email", label: "דוא\"ל (רשות)", type: "email", dir: "ltr" },
];

/** Agent and client details. Validated here; sent to the backend from level 2. */
export function PartiesFields({ values, errors, onChange, onBlur }: Props) {
  return (
    <fieldset className="card">
      <legend>פרטי סוכן ולקוח</legend>
      <div className="grid">
        {FIELDS.map((field) => {
          const id = `party-${field.name}`;
          const error = errors[field.name];
          return (
            <div key={field.name} className="field">
              <label htmlFor={id}>{field.label}</label>
              <input
                id={id}
                type={field.type}
                dir={field.dir}
                maxLength={MAX_TEXT}
                value={values[field.name]}
                aria-invalid={error ? true : undefined}
                aria-describedby={error ? `${id}-error` : undefined}
                onChange={(e) => onChange(field.name, e.target.value)}
                onBlur={() => onBlur(field.name)}
              />
              {error && (
                <small id={`${id}-error`} className="field-error">
                  {error}
                </small>
              )}
            </div>
          );
        })}
      </div>
    </fieldset>
  );
}
