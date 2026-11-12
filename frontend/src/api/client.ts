import type { ZodType } from "zod";
import {
  apiErrorSchema,
  previewResponseSchema,
  productsResponseSchema,
  type PreviewRequest,
  type PreviewResponse,
  type ProductsResponse,
} from "./types";

const API_BASE = `${import.meta.env.VITE_API_BASE ?? ""}/api`;

export class ApiError extends Error {
  readonly code: string;

  constructor(code: string, messageHe: string) {
    super(messageHe);
    this.name = "ApiError";
    this.code = code;
  }
}

async function request<T>(path: string, schema: ZodType<T>, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, init);
  } catch {
    throw new ApiError("network_error", "לא ניתן להתחבר לשרת");
  }

  const body: unknown = await response.json().catch(() => null);

  if (!response.ok) {
    const parsed = apiErrorSchema.safeParse(body);
    if (parsed.success) {
      throw new ApiError(parsed.data.error.code, parsed.data.error.message_he);
    }
    throw new ApiError("http_error", "שגיאה לא צפויה מהשרת");
  }

  const parsed = schema.safeParse(body);
  if (!parsed.success) {
    throw new ApiError("invalid_response", "תגובה לא תקינה מהשרת");
  }
  return parsed.data;
}

export function getProducts(): Promise<ProductsResponse> {
  return request("/products", productsResponseSchema);
}

export function previewQuote(payload: PreviewRequest): Promise<PreviewResponse> {
  return request("/quotes/preview", previewResponseSchema, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}
