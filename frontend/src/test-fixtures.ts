// Shapes copied from real backend responses (GET /api/products, POST /api/quotes/preview).
import type { CreateQuoteResponse, PreviewResponse, ProductsResponse } from "./api/types";

export const PRODUCTS: ProductsResponse = {
  min_premium: "500",
  products: [
    {
      code: "car",
      label_he: "ביטוח רכב",
      fields: [
        { name: "driver_age", label_he: "גיל הנהג", type: "integer", required: true, min: 17, max: 90, options: null },
        { name: "car_value", label_he: "שווי הרכב (₪)", type: "money", required: true, min: 10000, max: 1000000, options: null },
        {
          name: "coverage_type",
          label_he: "סוג כיסוי",
          type: "enum",
          required: true,
          min: null,
          max: null,
          options: [
            { value: "comprehensive", label_he: "מקיף" },
            { value: "third_party", label_he: "צד ג'" },
          ],
        },
      ],
      coverages: [
        { code: "towing", label_he: "גרירה", price_rule_he: "+150 ₪" },
        { code: "glass", label_he: "שמשות", price_rule_he: "+200 ₪" },
      ],
    },
    {
      code: "apartment",
      label_he: "ביטוח דירה",
      fields: [
        { name: "floor", label_he: "קומה", type: "integer", required: true, min: 0, max: 60, options: null },
        { name: "has_alarm", label_he: "יש אזעקה", type: "boolean", required: true, min: null, max: null, options: null },
      ],
      coverages: [{ code: "jewelry", label_he: "תכשיטים", price_rule_he: "+300 ₪" }],
    },
  ],
};

export const CREATED: CreateQuoteResponse = {
  quote_number: "Q-2026-000001",
  product: "car",
  premium: "6975",
  issued_at: "2026-11-19T22:30:00Z",
  valid_until: "2026-12-19T22:30:00Z",
  download_url: "/api/quotes/download/" + "T".repeat(43),
};

export const PREVIEW: PreviewResponse = {
  product: "car",
  currency: "ILS",
  premium: "6975",
  premium_before_rounding: "6975.00",
  minimum_applied: false,
  breakdown: [
    { code: "base", label_he: "פרמיית בסיס (מקיף)", amount: "1500" },
    { code: "value_part", label_he: "רכיב שווי הרכב (2%)", amount: "2000.00" },
    { code: "factors_adjustment", label_he: "התאמה לפי פקטורים", amount: "3325.0000" },
    { code: "towing", label_he: "גרירה", amount: "150" },
  ],
  factors: [
    { code: "age_factor", label_he: "פקטור גיל", value: "1.5" },
    { code: "license_factor", label_he: "פקטור ותק", value: "1.3" },
    { code: "claims_factor", label_he: "פקטור תביעות", value: "1.00" },
  ],
};
