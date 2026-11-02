import Link from "next/link";
import AccountLink from "@/components/AccountLink";

export default function Header() {
  return <header className="header container">
    <Link className="brand" href="/" aria-label="ImportForge — главная"><span className="brand-icon" aria-hidden="true">↳</span> ImportForge</Link>
    <nav className="nav" aria-label="Главная навигация"><Link href="/dashboard">Поставщики</Link><AccountLink /></nav>
  </header>;
}
