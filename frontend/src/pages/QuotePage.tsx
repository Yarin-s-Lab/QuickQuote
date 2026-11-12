import { useEffect, useState, type FormEvent } from "react";
import { ApiError, getProducts, previewQuote } from "../api/client";
import {
  partiesSchema,
  type InputValue,
  type Parties,
  type PreviewResponse,
  type Product,
  type ProductCode,
} from "../api/types";
import { CoverageList } from "../components/CoverageList";
import { PartiesFields, type PartiesErrors } from "../components/PartiesFields";
import { PremiumPreview } from "../components/PremiumPreview";
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
        <button type="submit" disabled={loading}>
          {loading ? "מחשב…" : "חשב פרמיה"}
        </button>
        {submitError && (
          <p role="alert" className="error">
            {submitError}
          </p>
        )}
      </form>
      {preview && <PremiumPreview preview={preview} stale={stale} />}
    </main>
  );
}
