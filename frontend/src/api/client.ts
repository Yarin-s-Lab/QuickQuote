import type { ZodType } from "zod";
import {
  apiErrorSchema,
  type CompareRequest,
  createQuoteResponseSchema,
  type CreateQuoteRequest,
  type CreateQuoteResponse,
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

async function send(path: string, init?: RequestInit): Promise<Response> {
  try {
    return await fetch(`${API_BASE}${path}`, init);
  } catch {
    throw new ApiError("network_error", "לא ניתן להתחבר לשרת");
  }
}

/** Turn a non-2xx response into an ApiError carrying the server's Hebrew message. */
async function errorFrom(response: Response): Promise<ApiError> {
  const body: unknown = await response.json().catch(() => null);
  const parsed = apiErrorSchema.safeParse(body);
  if (parsed.success) {
    return new ApiError(parsed.data.error.code, parsed.data.error.message_he);
  }
  return new ApiError("http_error", "שגיאה לא צפויה מהשרת");
}

async function request<T>(path: string, schema: ZodType<T>, init?: RequestInit): Promise<T> {
  const response = await send(path, init);
  if (!response.ok) {
    throw await errorFrom(response);
  }
  const body: unknown = await response.json().catch(() => null);

  const parsed = schema.safeParse(body);
  if (!parsed.success) {
    throw new ApiError("invalid_response", "תגובה לא תקינה מהשרת");
  }
  return parsed.data;
}

export function getProducts(): Promise<ProductsResponse> {
  return request("/products", productsResponseSchema);
}

export function createQuote(payload: CreateQuoteRequest): Promise<CreateQuoteResponse> {
  return request("/quotes", createQuoteResponseSchema, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function previewQuote(payload: PreviewRequest): Promise<PreviewResponse> {
  return request("/quotes/preview", previewResponseSchema, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export interface ComparisonFile {
  blob: Blob;
  filename: string;
}

/**
 * POST /api/quotes/compare. The tokens go in the body (never the URL) and the server
 * answers with the PDF itself; it is not stored on the server.
 */
export async function compareQuotes(tokens: [string, string]): Promise<ComparisonFile> {
  const payload: CompareRequest = { tokens };
  const response = await send("/quotes/compare", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw await errorFrom(response);
  }
  if (!(response.headers.get("Content-Type") ?? "").startsWith("application/pdf")) {
    throw new ApiError("invalid_response", "תגובה לא תקינה מהשרת");
  }
  const disposition = response.headers.get("Content-Disposition") ?? "";
  const match = /filename="(compare-Q-\d{4}-\d{6}-Q-\d{4}-\d{6}\.pdf)"/.exec(disposition);
  return { blob: await response.blob(), filename: match?.[1] ?? "compare.pdf" };
}
