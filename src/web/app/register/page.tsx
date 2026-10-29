import type { Metadata } from "next";
import AuthForm from "@/components/AuthForm";

export const metadata: Metadata = { title: "Регистрация" };

export default function RegisterPage() {
  return <main id="main" className="container auth-layout">
    <section className="auth-aside"><p className="eyebrow"><span className="dot" /> Первый шаг</p><h1>Начните с порядка.</h1><p className="lead">Создайте аккаунт, добавьте поставщиков и соберите контакты в одном месте.</p><p className="aside-note">У каждого пользователя — собственный список поставщиков.</p></section>
    <AuthForm mode="register" />
  </main>;
}
