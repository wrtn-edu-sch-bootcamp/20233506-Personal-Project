import type { ListingAnalysisRequest, AnalysisReport } from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "";
const BACKEND_DIRECT = process.env.NEXT_PUBLIC_BACKEND_URL ?? API_BASE;

class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });

  if (!res.ok) {
    const body = await res.text().catch(() => "Unknown error");
    throw new ApiError(res.status, body);
  }

  return res.json() as Promise<T>;
}

export async function analyzeListing(
  data: ListingAnalysisRequest
): Promise<AnalysisReport> {
  return request<AnalysisReport>("/api/analyze", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export interface ScrapedListing {
  address: string;
  building_name: string;
  deposit: number | null;
  monthly_rent: number | null;
  area_sqm: number | null;
  floor: string;
  listing_text: string;
  listing_type: string;
  property_type: string;
  source: string;
}

export async function scrapeListing(url: string): Promise<ScrapedListing> {
  return request<ScrapedListing>("/api/scrape-listing", {
    method: "POST",
    body: JSON.stringify({ url }),
  });
}

export interface RegistryFileResult {
  owner: string | null;
  mortgage: number | null;
  seizure: boolean;
  trust: boolean;
  raw_text: string;
  risk_factors: string[];
}

export async function analyzeRegistryFile(file: File): Promise<RegistryFileResult> {
  const form = new FormData();
  form.append("file", file);

  const base = BACKEND_DIRECT || API_BASE;
  const res = await fetch(`${base}/api/analyze/registry/file`, {
    method: "POST",
    body: form,
  });

  if (!res.ok) {
    const body = await res.text().catch(() => "Unknown error");
    throw new ApiError(res.status, body);
  }

  return res.json() as Promise<RegistryFileResult>;
}

export async function healthCheck(): Promise<{ status: string }> {
  return request("/api/health");
}
