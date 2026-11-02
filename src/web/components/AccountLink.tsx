"use client";

import Link from "next/link";
import { useAuth } from "@/hooks/useAuth";

export default function AccountLink() {
  const { user } = useAuth();
  return <Link className="button secondary small" href={user ? "/dashboard" : "/login"}>{user ? "Личный кабинет" : "Войти"}</Link>;
}
