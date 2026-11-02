import type { Metadata } from "next";
import AuthForm from "@/components/AuthForm";

export const metadata: Metadata = { title: "Вход" };

export default async function LoginPage({ searchParams }: { searchParams: Promise<{ registered?: string }> }) {
  const { registered } = await searchParams;
  return <main id="main" className="container auth-layout">
    <section className="auth-aside"><p className="eyebrow"><span className="dot" /> С возвращением</p><h1>Ваше рабочее пространство.</h1><p className="lead">Поставщики, контакты и статусы — продолжите с того места, где остановились.</p><p className="aside-note">Войдите с email, который указали при регистрации.</p></section>
    <AuthForm mode="login" registrationComplete={registered === "1"} />
  </main>;
}
