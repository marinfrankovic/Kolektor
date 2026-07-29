import type { Language } from "../i18n/dictionaries";

export type Kind = "coin" | "banknote" | "token" | "set" | "other";
export type ItemStatus =
  | "owned"
  | "wish"
  | "ordered"
  | "duplicate"
  | "for_sale"
  | "sold"
  | "missing";
export type ImageRole =
  | "obverse"
  | "reverse"
  | "face"
  | "back"
  | "edge"
  | "watermark"
  | "detail"
  | "certificate"
  | "other";
export type AuthMode = "password" | "open";

export type User = {
  id: string;
  email: string;
  display_name: string | null;
  language: Language;
  must_change_password: boolean;
};

export type SetupStatus = {
  setup_required: boolean;
  auth_mode: AuthMode;
  languages: Language[];
  default_language: Language;
};

export type PublicConfig = {
  languages: Language[];
  default_language: Language;
  ocr_enabled: boolean;
  autocrop: boolean;
  autoenhance: boolean;
  max_upload_mb: number;
  tls_terminated: boolean;
};

export type Suggestion = {
  field: string;
  value: string | number;
  confidence: number;
  source: string;
};

export type ItemImage = {
  id: string;
  role: ImageRole;
  sort: number;
  status: "pending" | "processing" | "ready" | "failed";
  width: number | null;
  height: number | null;
  phash: string | null;
  transform: Record<string, unknown>;
  detection: Record<string, unknown>;
  suggestions: Suggestion[];
  error: string | null;
  created_at: string;
};

export type Coin = Record<string, string | number | null>;
export type Banknote = Record<string, string | number | boolean | null>;
export type MoneyEvent = Record<string, string | null>;
export type CatalogRef = { id?: number; catalog: string; number: string };

export type Item = {
  id: string;
  kind: Kind;
  title: string;
  status: ItemStatus;
  quantity: number;
  country_code: string | null;
  map_country_code: string | null;
  issuing_entity: string | null;
  region: string | null;
  period: string | null;
  ruler: string | null;
  denomination_value: string | null;
  denomination_text: string | null;
  currency_unit: string | null;
  year: number | null;
  year_text: string | null;
  year_on_item: string | null;
  series: string | null;
  subject: string | null;
  grade_scale: string | null;
  grade_value: string | null;
  grader: string | null;
  cert_number: string | null;
  rarity: string | null;
  condition_note: string | null;
  storage: string | null;
  slot: string | null;
  barcode: string | null;
  notes: string | null;
  features: string | null;
  tags: string[];
  extra: Record<string, unknown>;
  completeness: number;
  warnings: string[];
  coin: Coin | null;
  banknote: Banknote | null;
  acquisition: MoneyEvent | null;
  disposal: MoneyEvent | null;
  catalog_refs: CatalogRef[];
  images: ItemImage[];
};

export type ItemRow = {
  id: string;
  kind: Kind;
  title: string;
  status: ItemStatus;
  quantity: number;
  country_code: string | null;
  map_country_code: string | null;
  issuing_entity: string | null;
  denomination_text: string | null;
  denomination_value: string | null;
  currency_unit: string | null;
  year: number | null;
  grade_value: string | null;
  completeness: number;
  thumb_image_id: string | null;
  updated_at: string;
};

export type ItemPage = { rows: ItemRow[]; total: number; page: number; page_size: number };

export type MapCountryStat = {
  code2: string;
  numeric3: string;
  name: string;
  continent: string | null;
  coins: number;
  banknotes: number;
  other: number;
  total: number;
};

export type MapStats = {
  countries: MapCountryStat[];
  covered: number;
  sovereign_total: number;
  by_continent: Record<string, number>;
};

export type CollectionStats = {
  items: number;
  pieces: number;
  coins: number;
  banknotes: number;
  countries: number;
  images: number;
  year_min: number | null;
  year_max: number | null;
  spend_by_currency: Record<string, string>;
  average_completeness: number;
};

export type Country = {
  code2: string;
  code3: string;
  numeric3: string;
  name: string;
  continent: string | null;
};

export class ApiError extends Error {
  status: number;
  detail: unknown;

  constructor(status: number, detail: unknown) {
    super(typeof detail === "string" ? detail : `Request failed (${status})`);
    this.status = status;
    this.detail = detail;
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(path, {
    credentials: "same-origin",
    ...init,
    headers: {
      ...(init.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
      ...(init.headers ?? {}),
    },
  });

  if (response.status === 204) return undefined as T;

  const text = await response.text();
  const payload = text ? JSON.parse(text) : null;

  if (!response.ok) {
    throw new ApiError(response.status, payload?.detail ?? payload);
  }
  return payload as T;
}

export const api = {
  setupStatus: () => request<SetupStatus>("/api/auth/setup"),
  completeSetup: (body: {
    auth_mode: AuthMode;
    language: Language;
    email?: string;
    password?: string;
  }) => request<User>("/api/auth/setup", { method: "POST", body: JSON.stringify(body) }),
  changeAuthMode: (body: { auth_mode: AuthMode; email?: string; password?: string }) =>
    request<SetupStatus>("/api/auth/mode", { method: "POST", body: JSON.stringify(body) }),

  config: () => request<PublicConfig>("/api/config"),
  login: (email: string, password: string) =>
    request<User>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  logout: () => request<void>("/api/auth/logout", { method: "POST" }),
  me: () => request<User>("/api/auth/me"),
  updateMe: (body: { display_name?: string | null; language?: Language }) =>
    request<User>("/api/auth/me", { method: "PATCH", body: JSON.stringify(body) }),
  changePassword: (current_password: string, new_password: string) =>
    request<void>("/api/auth/password", {
      method: "POST",
      body: JSON.stringify({ current_password, new_password }),
    }),

  listItems: (params: Record<string, string | number | undefined>) => {
    const query = new URLSearchParams();
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined && value !== "") query.set(key, String(value));
    }
    return request<ItemPage>(`/api/items?${query.toString()}`);
  },
  getItem: (id: string) => request<Item>(`/api/items/${id}`),
  createItem: (body: Record<string, unknown>) =>
    request<Item>("/api/items", { method: "POST", body: JSON.stringify(body) }),
  updateItem: (id: string, body: Record<string, unknown>) =>
    request<Item>(`/api/items/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  deleteItem: (id: string) => request<void>(`/api/items/${id}`, { method: "DELETE" }),

  uploadImage: (itemId: string, role: ImageRole, file: File | Blob, filename = "photo.jpg") => {
    const form = new FormData();
    form.set("item_id", itemId);
    form.set("role", role);
    form.set("file", file, filename);
    return request<ItemImage>("/api/images", { method: "POST", body: form });
  },
  updateImage: (id: string, body: { role?: ImageRole; sort?: number }) =>
    request<ItemImage>(`/api/images/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  importImage: (itemId: string, role: ImageRole, url: string) =>
    request<ItemImage>("/api/images/from-url", {
      method: "POST",
      body: JSON.stringify({ item_id: itemId, role, url }),
    }),
  reprocessImage: (id: string, body: Record<string, unknown> = {}) =>
    request<ItemImage>(`/api/images/${id}/reprocess`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  deleteImage: (id: string) => request<void>(`/api/images/${id}`, { method: "DELETE" }),
  imageUrl: (id: string, variant: "thumb" | "preview" | "display" | "original" = "preview") =>
    `/api/images/${id}/${variant}`,

  mapStats: () => request<MapStats>("/api/stats/map"),
  summary: () => request<CollectionStats>("/api/stats/summary"),
  countries: (used = false) =>
    request<Country[]>(`/api/reference/countries${used ? "?used=true" : ""}`),
};
