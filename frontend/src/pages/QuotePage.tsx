import { useEffect, useState, type FormEvent } from "react";
import { ApiError, createQuote, getProducts, previewQuote } from "../api/client";
import {
  partiesSchema,
  type CreateQuoteResponse,
  type InputValue,
  type Parties,
  type PreviewResponse,
  type Product,
  type ProductCode,
} from "../api/types";
import { CoverageList } from "../components/CoverageList";
import { PartiesFields, type PartiesErrors } from "../components/PartiesFields";
import { PremiumPreview } from "../components/PremiumPreview";
import { QuoteCreated } from "../components/QuoteCreated";
import { ProductFields, type FieldValues } from "../components/ProductFields";
import { ProductSelector } from "../components/ProductSelector";

const EMPTY_PARTIES: Parties = {
  agent_name: "",
  client_full_name: "",
  client_phone: "",
  client_email: "",
};

function initialValues(product: Product): FieldValues {
  const values: FieldValues = {};
  for (const field of product.fields) {
    if (field.type === "boolean") values[field.name] = false;
    else if (field.type === "enum") values[field.name] = field.options?.[0]?.value ?? "";
    else values[field.name] = "";
  }
  return values;
}

/** Turn form strings into JSON values. The backend validates everything. */
function toInputs(product: Product, values: FieldValues): Record<string, InputValue> {
  const inputs: Record<string, InputValue> = {};
  for (const field of product.fields) {
    const raw = values[field.name];
    if (field.type === "integer" || field.type === "money") {
      const text = String(raw).trim();
      if (text === "") continue; // backend reports the missing field
      const num = Number(text);
      inputs[field.name] = Number.isFinite(num) ? num : text;
    } else {
      inputs[field.name] = raw;
    }
  }
  return inputs;
}

function partiesErrors(values: Parties): PartiesErrors {
  const result = partiesSchema.safeParse(values);
  if (result.success) return {};
  const errors: PartiesErrors = {};
  for (const issue of result.error.issues) {
    const key = issue.path[0] as keyof Parties;
    errors[key] ??= issue.message;
  }
  return errors;
}

export function QuotePage() {
  const [products, setProducts] = useState<Product[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [productCode, setProductCode] = useState<ProductCode>("car");
  const [values, setValues] = useState<FieldValues>({});
  const [coverages, setCoverages] = useState<string[]>([]);
  const [parties, setParties] = useState<Parties>(EMPTY_PARTIES);
  const [touched, setTouched] = useState<Partial<Record<keyof Parties, boolean>>>({});
  const [preview, setPreview] = useState<PreviewResponse | null>(null);
  const [stale, setStale] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [creating, setCreating] = useState(false);
  const [created, setCreated] = useState<CreateQuoteResponse | null>(null);
  const [createError, setCreateError] = useState<string | null>(null);

  useEffect(() => {
    getProducts()
      .then((data) => {
        setProducts(data.products);
        const first = data.products[0];
        if (first) {
          setProductCode(first.code);
          setValues(initialValues(first));
        }
      })
      .catch((err: unknown) => {
        setLoadError(err instanceof ApiError ? err.message : "שגיאה בטעינת המוצרים");
      });
  }, []);

  if (loadError) return <p role="alert" className="error">{loadError}</p>;
  if (!products) return <p>טוען…</p>;

  const product = products.find((p) => p.code === productCode) ?? products[0];
  const allErrors = partiesErrors(parties);
  const visibleErrors: PartiesErrors = Object.fromEntries(
    Object.entries(allErrors).filter(([key]) => touched[key as keyof Parties]),
  );

  function selectProduct(code: ProductCode) {
    const next = products?.find((p) => p.code === code);
    if (!next) return;
    setProductCode(code);
    setValues(initialValues(next));
    setCoverages([]);
    setPreview(null);
    setSubmitError(null);
    setCreateError(null);
  }

  function markStale() {
    if (preview) setStale(true);
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setSubmitError(null);
    try {
      const result = await previewQuote({
        product: product.code,
        inputs: toInputs(product, values),
        coverages,
      });
      setPreview(result);
      setStale(false);
    } catch (err) {
      setSubmitError(err instanceof ApiError ? err.message : "שגיאה לא צפויה");
    } finally {
      setLoading(false);
    }
  }

  async function onCreate() {
    setCreateError(null);
    if (Object.keys(allErrors).length > 0) {
      // Show every party error, not only the fields the user already visited.
      setTouched({
        agent_name: true,
        client_full_name: true,
        client_phone: true,
        client_email: true,
      });
      setCreateError("יש להשלים את פרטי הסוכן והלקוח לפני יצירת ההצעה");
      return;
    }
    setCreating(true);
    try {
      const result = await createQuote({
        product: product.code,
        inputs: toInputs(product, values),
        coverages,
        ...parties,
      });
      setCreated(result);
    } catch (err) {
      setCreateError(err instanceof ApiError ? err.message : "שגיאה לא צפויה");
    } finally {
      setCreating(false);
    }
  }

  return (
    <main className="page">
      <h1>הצעת מחיר לביטוח</h1>
      <form onSubmit={onSubmit} noValidate>
        <PartiesFields
          values={parties}
          errors={visibleErrors}
          onChange={(name, value) => setParties((prev) => ({ ...prev, [name]: value }))}
          onBlur={(name) => setTouched((prev) => ({ ...prev, [name]: true }))}
        />
        <ProductSelector products={products} value={product.code} onChange={selectProduct} />
        <ProductFields
          fields={product.fields}
          values={values}
          onChange={(name, value) => {
            setValues((prev) => ({ ...prev, [name]: value }));
            markStale();
          }}
        />
        <CoverageList
          coverages={product.coverages}
          selected={coverages}
          onToggle={(code) => {
            setCoverages((prev) =>
              prev.includes(code) ? prev.filter((c) => c !== code) : [...prev, code],
            );
            markStale();
          }}
        />
        <div className="actions">
          <button type="submit" disabled={loading || creating}>
            {loading ? "מחשב…" : "חשב פרמיה"}
          </button>
          <button
            type="button"
            className="primary"
            onClick={onCreate}
            disabled={loading || creating}
          >
            {creating ? "יוצר הצעה…" : "צור הצעה"}
          </button>
        </div>
        {submitError && (
          <p role="alert" className="error">
            {submitError}
          </p>
        )}
        {createError && (
          <p role="alert" className="error">
            {createError}
          </p>
        )}
      </form>
      {created && <QuoteCreated quote={created} />}
      {preview && <PremiumPreview preview={preview} stale={stale} />}
    </main>
  );
}
