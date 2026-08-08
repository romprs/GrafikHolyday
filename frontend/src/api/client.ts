const DEV_USER_STORAGE_KEY = "dev_user_id";

export interface ApiErrorBody {
  code: string;
  message_ru: string;
  params: Record<string, unknown>;
}

export class ApiError extends Error {
  code: string;
  params: Record<string, unknown>;

  constructor(body: ApiErrorBody) {
    super(body.message_ru);
    this.code = body.code;
    this.params = body.params;
  }
}

export function getDevUserId(): string | null {
  return localStorage.getItem(DEV_USER_STORAGE_KEY);
}

export function setDevUserId(id: string | null): void {
  if (id) localStorage.setItem(DEV_USER_STORAGE_KEY, id);
  else localStorage.removeItem(DEV_USER_STORAGE_KEY);
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const devUserId = getDevUserId();
  const headers = new Headers(init?.headers);
  headers.set("Content-Type", "application/json");
  if (devUserId) headers.set("X-Dev-User-Id", devUserId);

  const res = await fetch(`/api${path}`, { ...init, headers });
  if (!res.ok) {
    const body = (await res.json()) as ApiErrorBody;
    throw new ApiError(body);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}
