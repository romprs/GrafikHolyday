const DEV_USER_STORAGE_KEY = "dev_user_id";
const ADMIN_FALLBACK_EMAIL_KEY = "admin_fallback_email";
const ADMIN_FALLBACK_PASSWORD_KEY = "admin_fallback_password";

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

export interface AdminFallbackCreds {
  email: string;
  password: string;
}

// Аварийный вход hr_admin — независим от dev/Kerberos (см. backend
// app/auth/admin_fallback.py). Держим в sessionStorage, а не localStorage,
// как dev_user_id: это настоящий пароль, а не просто выбор тестового
// пользователя, не должен переживать закрытие вкладки на общем компьютере.
export function getAdminFallbackCreds(): AdminFallbackCreds | null {
  const email = sessionStorage.getItem(ADMIN_FALLBACK_EMAIL_KEY);
  const password = sessionStorage.getItem(ADMIN_FALLBACK_PASSWORD_KEY);
  return email && password ? { email, password } : null;
}

export function setAdminFallbackCreds(creds: AdminFallbackCreds | null): void {
  if (creds) {
    sessionStorage.setItem(ADMIN_FALLBACK_EMAIL_KEY, creds.email);
    sessionStorage.setItem(ADMIN_FALLBACK_PASSWORD_KEY, creds.password);
  } else {
    sessionStorage.removeItem(ADMIN_FALLBACK_EMAIL_KEY);
    sessionStorage.removeItem(ADMIN_FALLBACK_PASSWORD_KEY);
  }
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const devUserId = getDevUserId();
  const fallbackCreds = getAdminFallbackCreds();
  const headers = new Headers(init?.headers);
  headers.set("Content-Type", "application/json");
  if (fallbackCreds) {
    headers.set("X-Admin-Fallback-Email", fallbackCreds.email);
    headers.set("X-Admin-Fallback-Password", fallbackCreds.password);
  } else if (devUserId) {
    headers.set("X-Dev-User-Id", devUserId);
  }

  const res = await fetch(`/api${path}`, { ...init, headers });
  if (!res.ok) {
    const body = (await res.json()) as ApiErrorBody;
    throw new ApiError(body);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}
