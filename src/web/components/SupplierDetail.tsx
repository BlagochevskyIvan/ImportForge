"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import CsvUpload from "@/components/CsvUpload";
import SupplierConfigForm from "@/components/SupplierConfigForm";
import { useAuth } from "@/hooks/useAuth";
import { describeError, getSupplier, getSupplierConfig, type ImportConfig, type Supplier } from "@/lib/api";

function SupplierWorkspace({ supplierId }: { supplierId: number }) {
  const [data, setData] = useState<{ supplier: Supplier; config: ImportConfig | null } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [revision, setRevision] = useState(0);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let active = true;
    Promise.all([getSupplier(supplierId), getSupplierConfig(supplierId)])
      .then(([supplier, config]) => {
        if (!active) return;
        setData({ supplier, config });
        setReady(Boolean(config));
      })
      .catch((cause) => { if (active) setError(describeError(cause)); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [supplierId, revision]);

  if (loading) return <p className="session" role="status">Загружаем поставщика и конфиг…</p>;
  if (error) return <div className="session"><p className="notice error" role="alert">{error}</p><button className="button" type="button" onClick={() => { setError(null); setLoading(true); setRevision((value) => value + 1); }}>Повторить</button></div>;
  if (!data) return null;
  return <>
    <div className="dashboard-title"><div><p className="eyebrow"><span className="dot" /> Поставщик · ID {data.supplier.id}</p><h1>{data.supplier.name}</h1><p className="muted">{data.supplier.contact_email}</p></div><span className={`badge${data.supplier.is_active ? "" : " inactive"}`}>{data.supplier.is_active ? "Активен" : "Неактивен"}</span></div>
    <div className="supplier-workspace">
      <SupplierConfigForm supplierId={supplierId} initialConfig={data.config} onReadyChange={setReady} />
      <CsvUpload supplierId={supplierId} configReady={ready} />
    </div>
  </>;
}

export default function SupplierDetail({ supplierId }: { supplierId: number }) {
  const { user, loading, error, retry } = useAuth();
  const router = useRouter();
  useEffect(() => {
    if (!loading && !user && !error) router.replace("/login");
  }, [loading, user, error, router]);

  return <>
    <Link className="back-link" href="/dashboard">← Все поставщики</Link>
    {loading ? <p className="session" role="status">Проверяем сессию…</p>
      : error ? <div className="session"><p className="notice error" role="alert">{error}</p><button className="button" type="button" onClick={() => void retry()}>Повторить проверку</button></div>
      : !user ? <p className="session" role="status">Переходим ко входу…</p>
      : <SupplierWorkspace key={`${user.id}:${supplierId}`} supplierId={supplierId} />}
  </>;
}
