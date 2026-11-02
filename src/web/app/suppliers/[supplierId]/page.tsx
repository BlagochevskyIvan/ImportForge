import type { Metadata } from "next";
import { notFound } from "next/navigation";
import SupplierDetail from "@/components/SupplierDetail";

export const metadata: Metadata = { title: "Поставщик", robots: { index: false, follow: false } };

export default async function SupplierPage({ params }: { params: Promise<{ supplierId: string }> }) {
  const { supplierId } = await params;
  const id = Number(supplierId);
  if (!/^\d+$/.test(supplierId) || !Number.isSafeInteger(id) || id <= 0) notFound();
  return <main id="main" className="container dashboard"><SupplierDetail supplierId={id} /></main>;
}
