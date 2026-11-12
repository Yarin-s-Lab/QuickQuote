import type { Product, ProductCode } from "../api/types";

interface Props {
  products: Product[];
  value: ProductCode;
  onChange: (code: ProductCode) => void;
}

export function ProductSelector({ products, value, onChange }: Props) {
  return (
    <fieldset className="card">
      <legend>מוצר</legend>
      <div className="choices">
        {products.map((product) => (
          <label key={product.code} className="choice">
            <input
              type="radio"
              name="product"
              value={product.code}
              checked={value === product.code}
              onChange={() => onChange(product.code)}
            />
            {product.label_he}
          </label>
        ))}
      </div>
    </fieldset>
  );
}
