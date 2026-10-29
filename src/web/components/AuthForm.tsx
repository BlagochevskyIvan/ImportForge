"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";
import { describeError, passwordError, register } from "@/lib/api";
import { useAuth } from "@/hooks/useAuth";

export default function AuthForm({ mode, registrationComplete = false }: { mode: "login" | "register"; registrationComplete?: boolean }) {
  const isRegister = mode === "register";
  const router = useRouter();
  const auth = useAuth();
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (auth.user) router.replace("/dashboard");
  }, [auth.user, router]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    setError(null);
    const normalizedEmail = email.trim().toLowerCase();
    const normalizedName = username.trim();
    if (!normalizedEmail || !password || (isRegister && !normalizedName)) {
      setError("Заполните все поля."); return;
    }
    if (isRegister && (Array.from(normalizedName).length < 3 || Array.from(normalizedName).length > 64)) {
      setError("Имя пользователя должно содержать от 3 до 64 символов."); return;
    }
    const invalidPassword = passwordError(password);
    if (invalidPassword) { setError(invalidPassword); return; }
    setBusy(true);
    try {
      if (isRegister) {
        await register({ username: normalizedName, email: normalizedEmail, password });
        setPassword("");
        router.replace("/login?registered=1");
      } else {
        await auth.login({ email: normalizedEmail, password });
        router.replace("/dashboard");
      }
    } catch (cause) { setError(describeError(cause)); }
    finally { setBusy(false); }
  }

  return <div className="card">
    <h2>{isRegister ? "Создать аккаунт" : "Вход в аккаунт"}</h2>
    <p className="small-text">{isRegister ? "Начните с личного рабочего пространства." : "Продолжите работу с вашими поставщиками."}</p>
    {registrationComplete && <p role="status" className="notice success">Аккаунт создан. Теперь войдите с вашим email и паролем.</p>}
    {auth.error && <div role="alert" className="notice error">{auth.error} <button className="button secondary small" type="button" onClick={() => void auth.retry()} disabled={auth.loading}>Повторить проверку сессии</button></div>}
    {error && <p role="alert" className="notice error">{error}</p>}
    <form className="form" onSubmit={submit} aria-busy={busy}>
      {isRegister && <label className="field">Имя пользователя
        <input name="username" autoComplete="username" required minLength={3} maxLength={64} value={username} onChange={(event) => setUsername(event.target.value)} disabled={busy || auth.loading} />
        <span className="hint">От 3 до 64 символов</span>
      </label>}
      <label className="field">Email
        <input name="email" type="email" autoComplete={isRegister ? "email" : "username"} required maxLength={320} value={email} onChange={(event) => setEmail(event.target.value)} disabled={busy || auth.loading} placeholder="you@company.ru" />
      </label>
      <label className="field">Пароль
        <input name="password" type="password" autoComplete={isRegister ? "new-password" : "current-password"} required minLength={8} maxLength={72} value={password} onChange={(event) => setPassword(event.target.value)} disabled={busy || auth.loading} aria-describedby="password-hint" />
        <span className="hint" id="password-hint">От 8 до 72 символов, максимум 72 байта UTF-8</span>
      </label>
      <button className="button" type="submit" disabled={busy || auth.loading || Boolean(auth.user)}>{auth.loading ? "Проверяем сессию…" : busy ? "Отправляем…" : isRegister ? "Зарегистрироваться" : "Войти"}</button>
      {busy && <span role="status" className="hint">Ожидаем ответ сервера…</span>}
    </form>
    <p className="form-footer">{isRegister ? "Уже есть аккаунт? " : "Впервые здесь? "}<Link href={isRegister ? "/login" : "/register"}>{isRegister ? "Войти" : "Зарегистрироваться"}</Link></p>
  </div>;
}
