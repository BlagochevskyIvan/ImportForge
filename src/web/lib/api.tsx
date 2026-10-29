"use client";

export interface User {
  id: number;
  username: string;
  email: string;
  is_active: boolean;
  created_at: string;
}

export interface Credentials { email: string; password: string }
export interface Registration extends Credentials { username: string }
export interface SupplierInput { name: string; contact_email: string }
export interface Supplier extends SupplierInput { id: number; user_id: number; is_active: boolean }
interface TokenResponse { access_token: string; token_type: "bearer" }

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = "ApiError";
  }
}

const messages: Record<string, string> = {
  "Invalid email or password": "Неверный email или пароль.",
  "Account is inactive": "Аккаунт отключён.",
  "Username or email already exists": "Такое имя пользователя или email уже заняты.",
  "Invalid or expired refresh token": "Сессия завершилась. Войдите снова.",
  "Invalid authentication credentials": "Войдите в аккаунт для продолжения.",
  "Untrusted authentication origin": "Адрес фронтенда отсутствует в AUTH_ALLOWED_ORIGINS бэкенда.",
};
const fieldNames: Record<string, string> = {
  username: "Имя пользователя", email: "Email", password: "Пароль",
  name: "Название", contact_email: "Контактный email",
};

function errorMessage(body: unknown, status: number): string {
  const detail = body && typeof body === "object" && "detail" in body ? body.detail : null;
  if (typeof detail === "string") return messages[detail] || detail;
  if (Array.isArray(detail)) {
    return detail.map((item) => {
      const field = Array.isArray(item.loc) ? String(item.loc.at(-1)) : "Данные";
      return `${fieldNames[field] || field}: ${String(item.msg || "проверьте значение")}`;
    }).join(". ");
  }
  return status >= 500
    ? "Сервис временно недоступен. Попробуйте ещё раз позже."
    : `Не удалось выполнить запрос (HTTP ${status}).`;
}

async function request<T,>(path: string, options: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/api${path}`, {
      ...options,
      credentials: "same-origin",
      cache: "no-store",
      signal: AbortSignal.timeout(15000),
      headers: { "Content-Type": "application/json", ...options.headers },
    });
  } catch {
    throw new ApiError(0, "Нет связи с сервером или время ожидания истекло. Проверьте подключение и повторите запрос.");
  }
  if (response.status === 204) return undefined as T;
  const body: unknown = await response.json().catch(() => null);
  if (!response.ok) throw new ApiError(response.status, errorMessage(body, response.status));
  if (body === null) throw new ApiError(502, "Сервер вернул неожиданный ответ.");
  return body as T;
}

// Client-only module: this variable belongs to one tab, never a shared server process.
let accessToken: string | null = null;
let refreshPromise: Promise<string> | null = null;
let restorePromise: Promise<User> | null = null;
export const SESSION_ENDED = "importforge:session-ended";
export const SESSION_CHANNEL = "importforge:session";
export const SESSION_SOURCE = Math.random().toString(36).slice(2);

function broadcastSession(type: "login" | "logout") {
  if (typeof BroadcastChannel === "undefined") return;
  const channel = new BroadcastChannel(SESSION_CHANNEL);
  channel.postMessage({ type, source: SESSION_SOURCE });
  channel.close();
}

export function clearSession() {
  accessToken = null;
  window.dispatchEvent(new Event(SESSION_ENDED));
}

// The backend rotates a single-use refresh cookie. Serialize auth mutations across
// tabs with Web Locks; share one pending refresh inside this tab.
async function authLock<T,>(action: () => Promise<T>): Promise<T> {
  if (navigator.locks) return navigator.locks.request("importforge:auth", action);
  return action();
}

function refreshAccess(): Promise<string> {
  if (!refreshPromise) {
    refreshPromise = authLock(async () => {
      const result = await request<TokenResponse>("/users/auth/refresh", { method: "POST" });
      accessToken = result.access_token;
      return accessToken;
    }).catch((error: unknown) => {
      if (error instanceof ApiError && error.status === 401) clearSession();
      throw error;
    }).finally(() => { refreshPromise = null; });
  }
  return refreshPromise;
}

export async function authenticatedRequest<T,>(path: string, options: RequestInit = {}): Promise<T> {
  const token = accessToken || await refreshAccess();
  const send = (value: string) => request<T>(path, {
    ...options, headers: { ...options.headers, Authorization: `Bearer ${value}` },
  });
  try {
    return await send(token);
  } catch (error) {
    if (!(error instanceof ApiError) || error.status !== 401) throw error;
    const replacement = accessToken && accessToken !== token ? accessToken : await refreshAccess();
    try { return await send(replacement); }
    catch (retryError) {
      if (retryError instanceof ApiError && retryError.status === 401) clearSession();
      throw retryError;
    }
  }
}

export function restoreSession(): Promise<User> {
  if (!restorePromise) {
    restorePromise = (async () => {
      if (!accessToken) await refreshAccess();
      return authenticatedRequest<User>("/users/me");
    })().finally(() => { restorePromise = null; });
  }
  return restorePromise;
}

export function login(data: Credentials): Promise<User> {
  return authLock(async () => {
    const result = await request<TokenResponse>("/users/auth/login", {
      method: "POST", body: JSON.stringify(data),
    });
    accessToken = result.access_token;
    const profile = await request<User>("/users/me", { headers: { Authorization: `Bearer ${accessToken}` } });
    broadcastSession("login");
    return profile;
  });
}

export function register(data: Registration) {
  return request<User>("/users/auth/register", { method: "POST", body: JSON.stringify(data) });
}

export async function logout() {
  await authLock(() => request<void>("/users/auth/logout", { method: "POST" }));
  clearSession();
  broadcastSession("logout");
}

export function listSuppliers(offset: number, limit: number) {
  return authenticatedRequest<Supplier[]>(`/suppliers?offset=${offset}&limit=${limit}`);
}

export function createSupplier(data: SupplierInput) {
  return authenticatedRequest<Supplier>("/suppliers", { method: "POST", body: JSON.stringify(data) });
}

export function describeError(error: unknown): string {
  return error instanceof Error ? error.message : "Произошла ошибка. Попробуйте ещё раз.";
}

export function passwordError(value: string): string | null {
  const length = Array.from(value).length;
  if (length < 8 || length > 72) return "Пароль должен содержать от 8 до 72 символов.";
  if (new TextEncoder().encode(value).length > 72) return "Пароль должен занимать не более 72 байт UTF-8: кириллица и emoji занимают несколько байт.";
  return null;
}
