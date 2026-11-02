import type { Metadata } from "next";
import Header from "@/components/Header";
import Styles from "@/components/Styles";
import { AuthProvider } from "@/hooks/useAuth";

export const metadata: Metadata = {
  title: { default: "ImportForge — поставщики и данные", template: "%s | ImportForge" },
  description: "Управляйте поставщиками в едином рабочем пространстве ImportForge.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="ru" data-scroll-behavior="smooth">
      <head><Styles /></head>
      <body>
        <a className="skip" href="#main">Перейти к содержимому</a>
        <AuthProvider><Header />{children}</AuthProvider>
        <footer className="footer container"><span>ImportForge</span><span>Данные начинаются с порядка.</span></footer>
      </body>
    </html>
  );
}
