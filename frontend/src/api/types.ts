// Contract with the backend (SPEC section 5). Keep in sync with backend/app/api/schemas.py.
import { z } from "zod";

/** Decimal values travel as strings so no precision is lost. */
const decimalString = z.string().regex(/^-?\d+(\.\d+)?$/);

export const productCodeSchema = z.enum(["car", "apartment"]);
export type ProductCode = z.infer<typeof productCodeSchema>;

export const productFieldSchema = z.object({
  name: z.string(),
  label_he: z.string(),
  type: z.enum(["integer", "money", "boolean", "enum"]),
  required: z.boolean(),
  min: z.number().nullable(),
  max: z.number().nullable(),
  options: z.array(z.object({ value: z.string(), label_he: z.string() })).nullable(),
});
export type ProductField = z.infer<typeof productFieldSchema>;

export const coverageSchema = z.object({
  code: z.string(),
  label_he: z.string(),
  price_rule_he: z.string(),
});
export type Coverage = z.infer<typeof coverageSchema>;

export const productSchema = z.object({
  code: productCodeSchema,
  label_he: z.string(),
  fields: z.array(productFieldSchema),
  coverages: z.array(coverageSchema),
});
export type Product = z.infer<typeof productSchema>;

export const productsResponseSchema = z.object({
  min_premium: decimalString,
  products: z.array(productSchema),
});
export type ProductsResponse = z.infer<typeof productsResponseSchema>;

export type InputValue = number | string | boolean;

export interface PreviewRequest {
  product: ProductCode;
  inputs: Record<string, InputValue>;
  coverages: string[];
}

export const previewResponseSchema = z.object({
  product: productCodeSchema,
  currency: z.literal("ILS"),
  premium: decimalString,
  premium_before_rounding: decimalString,
  minimum_applied: z.boolean(),
  breakdown: z.array(z.object({ code: z.string(), label_he: z.string(), amount: decimalString })),
  factors: z.array(z.object({ code: z.string(), label_he: z.string(), value: decimalString })),
});
export type PreviewResponse = z.infer<typeof previewResponseSchema>;

export const apiErrorSchema = z.object({
  error: z.object({ code: z.string(), message_he: z.string() }),
});

/** Agent and client details. Collected now, sent to the backend from level 2 (POST /quotes). */
export const MAX_TEXT = 100;
export const partiesSchema = z.object({
  agent_name: z
    .string()
    .trim()
    .min(1, "יש להזין שם סוכן")
    .max(MAX_TEXT, `עד ${MAX_TEXT} תווים`),
  client_full_name: z
    .string()
    .trim()
    .min(1, "יש להזין שם לקוח")
    .max(MAX_TEXT, `עד ${MAX_TEXT} תווים`),
  client_phone: z
    .string()
    .trim()
    .max(MAX_TEXT, `עד ${MAX_TEXT} תווים`)
    .regex(/^(\+?\d[\d -]{6,18}\d)?$/, "מספר טלפון לא תקין"),
  client_email: z
    .union([z.literal(""), z.string().trim().email("כתובת דוא\"ל לא תקינה")])
    .refine((v) => v.length <= MAX_TEXT, `עד ${MAX_TEXT} תווים`),
});
export type Parties = z.infer<typeof partiesSchema>;
