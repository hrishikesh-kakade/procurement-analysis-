export type Role = "admin" | "procurement_manager" | "approver" | "requester" | "viewer";

export interface Page<T = any> {
  items: T[];
  total: number;
  page: number;
  limit: number;
  pages: number;
}

export class ApiError extends Error {
  status: number;
  code: string;
  details?: { field: string; message: string }[];
  constructor(status: number, code: string, message: string, details?: any) {
    super(message);
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

const BASE = "/api/v1";
let token: string | null = localStorage.getItem("token");
let onUnauthorized: () => void = () => {};

export const getToken = () => token;
export function setToken(value: string | null) {
  token = value;
  if (value) localStorage.setItem("token", value);
  else localStorage.removeItem("token");
}
export function setUnauthorizedHandler(handler: () => void) {
  onUnauthorized = handler;
}

interface RequestOptions {
  method?: string;
  body?: any;
  form?: URLSearchParams | FormData;
  params?: Record<string, any>;
  blob?: boolean;
}

async function request<T = any>(path: string, options: RequestOptions = {}): Promise<T> {
  const url = new URL(BASE + path, window.location.origin);
  Object.entries(options.params ?? {}).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") url.searchParams.set(key, String(value));
  });
  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;
  let body: any = options.form;
  if (options.body !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(options.body);
  }
  const response = await fetch(url.toString(), { method: options.method ?? "GET", headers, body });

  if (!response.ok) {
    let payload: any = null;
    try {
      payload = await response.json();
    } catch {
      /* non-JSON error body */
    }
    if (response.status === 401 && path !== "/auth/login") onUnauthorized();
    const error = payload?.error;
    throw new ApiError(response.status, error?.code ?? "error", error?.message ?? response.statusText, error?.details);
  }
  if (response.status === 204) return undefined as T;
  if (options.blob) return (await response.blob()) as any;
  return response.json();
}

export const api = {
  get: <T = any>(path: string, params?: Record<string, any>) => request<T>(path, { params }),
  post: <T = any>(path: string, body?: any) => request<T>(path, { method: "POST", body: body ?? {} }),
  put: <T = any>(path: string, body?: any) => request<T>(path, { method: "PUT", body }),
  patch: <T = any>(path: string, body?: any) => request<T>(path, { method: "PATCH", body }),
  del: <T = any>(path: string) => request<T>(path, { method: "DELETE" }),
  upload: <T = any>(path: string, form: FormData) => request<T>(path, { method: "POST", form }),
  download: (path: string) => request<Blob>(path, { blob: true }),
  login: (email: string, password: string) =>
    request<{ access_token: string }>("/auth/login", {
      method: "POST",
      form: new URLSearchParams({ username: email, password }),
    }),
};

export function formatError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.details?.length) return error.details.map((d) => `${d.field || "request"}: ${d.message}`).join("; ");
    return error.message;
  }
  return error instanceof Error ? error.message : "Something went wrong";
}
