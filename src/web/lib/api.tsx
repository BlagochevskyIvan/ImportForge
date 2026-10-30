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
export interface CsvConfig {
  delimiter: string;
  encoding: "utf-8" | "utf-8-sig" | "cp1251";
  column_mapping: Record<string, "sku" | "name" | "price">;
}
export interface ImportConfig { id: number; supplier_id: number; config_data: CsvConfig }
export interface SourceFile { id: string; supplier_id: number; filename: string; status: "uploaded" }
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
  "Supplier not found": "Поставщик не найден или недоступен.",
  "Save supplier configuration before uploading": "Сначала сохраните конфиг поставщика.",
  "Expected a CSV file": "Выберите файл с расширением .csv.",
  "File is too large": "Размер CSV не должен превышать 20 МиБ.",
  "File is empty": "Выбранный файл пуст.",
  "Filename is too long": "Имя файла должно содержать не больше 255 символов.",
  "File storage unavailable": "Хранилище файлов недоступно. Повторите загрузку позже.",
  "File storage is not configured": "Хранилище файлов ещё не настроено на сервере.",
  "Failed to save file metadata": "Не удалось сохранить сведения о файле. Повторите загрузку.",
};
const fieldNames: Record<string, string> = {
  username: "Имя пользователя", email: "Email", password: "Пароль",
  name: "Название", contact_email: "Контактный email",
  delimiter: "Разделитель", encoding: "Кодировка", column_mapping: "Соответствие колонок",
  supplier_id: "Поставщик", file: "Файл",
};
const validationMessages: Record<string, string> = {
  "Value error, Map sku, name and price exactly once each": "Укажите три разные колонки для sku, name и price, каждую ровно один раз.",
  "Value error, Delimiter cannot be a newline, NUL or quote": "Разделитель не может быть переносом строки, NUL или кавычкой.",
  "Extra inputs are not permitted": "Неизвестный параметр.",
};

function errorMessage(body: unknown, status: number): string {
  const detail = body && typeof body === "object" && "detail" in body ? body.detail : null;
  if (typeof detail === "string") return messages[detail] || detail;
  if (Array.isArray(detail)) {
    return detail.map((item) => {
      const field = Array.isArray(item.loc) ? String(item.loc.at(-1)) : "Данные";
      const message = String(item.msg || "проверьте значение");
      return `${fieldNames[field] || field}: ${validationMessages[message] || message}`;
    }).join(". ");
  }
  return status >= 500
    ? "Сервис временно недоступен. Попробуйте ещё раз позже."
    : `Не удалось выполнить запрос (HTTP ${status}).`;
}

async function request<T,>(path: string, options: RequestInit = {}): Promise<T> {
  let response: Response;
  const multipart = options.body instanceof FormData;
  const headers = new Headers(options.headers);
  if (options.body && !multipart && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  try {
    response = await fetch(`/api${path}`, {
      ...options,
      credentials: "same-origin",
      cache: "no-store",
      signal: options.signal ?? AbortSignal.timeout(multipart ? 120000 : 15000),
      headers,
    });
  } catch {
    throw new ApiError(0, "Нет связи с сервером или время ожидания истекло. Проверьте подключение и повторите запрос.");
  }
  if (response.status === 204) return undefined as T;
  let body: unknown;
  try { body = await response.json(); }
  catch { throw new ApiError(response.status >= 400 ? response.status : 502, "Сервер вернул неожиданный ответ."); }
  if (!response.ok) throw new ApiError(response.status, errorMessage(body, response.status));
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
  const send = (value: string) => {
    const headers = new Headers(options.headers);
    headers.set("Authorization", `Bearer ${value}`);
    return request<T>(path, { ...options, headers });
  };
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

export function getSupplier(id: number) {
  return authenticatedRequest<Supplier>(`/suppliers/${id}`);
}

export function getSupplierConfig(id: number) {
  return authenticatedRequest<ImportConfig | null>(`/suppliers/${id}/config`);
}

export function saveSupplierConfig(id: number, config: CsvConfig) {
  return authenticatedRequest<ImportConfig>(`/suppliers/${id}/config`, {
    method: "PUT", body: JSON.stringify({ config_data: config }),
  });
}

export function uploadCsv(supplierId: number, file: File) {
  const body = new FormData();
  body.set("supplier_id", String(supplierId));
  body.set("file", file);
  return authenticatedRequest<SourceFile>("/imports", { method: "POST", body });
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
