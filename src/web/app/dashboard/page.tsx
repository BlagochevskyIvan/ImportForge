import type { Metadata } from "next";
import Dashboard from "@/components/Dashboard";

export const metadata: Metadata = { title: "Личный кабинет", robots: { index: false, follow: false } };

export default function DashboardPage() {
  return <main id="main" className="container dashboard"><Dashboard /></main>;
}
