"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useAuth } from "@/hooks/useAuth";
import { describeError, listSuppliers, type Supplier, type User } from "@/lib/api";
import SupplierForm from "@/components/SupplierForm";
import SupplierList from "@/components/SupplierList";

const PAGE_SIZE = 20;

function Workspace({ user }: { user: User }) {
  const auth = useAuth();
  const router = useRouter();
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [logoutError, setLogoutError] = useState<string | null>(null);
  const [loggingOut, setLoggingOut] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [success, setSuccess] = useState<string | null>(null);
  const [offset, setOffset] = useState(0);
  const [revision, setRevision] = useState(0);

  useEffect(() => {
    let active = true;
    // One extra row tells us whether a next page exists, without a new API endpoint.
    listSuppliers(offset, PAGE_SIZE + 1).then((items) => {
      if (active) setSuppliers(items);
    }).catch((cause) => { if (active) setError(describeError(cause)); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [offset, revision]);

  function reload(nextOffset = offset) {
    setLoading(true);
    setError(null);
    setOffset(nextOffset);
    setRevision((value) => value + 1);
  }

  function created(supplier: Supplier) {
    setShowForm(false);
    setSuccess(`Поставщик «${supplier.name}» создан.`);
    reload(0);
  }

  async function signOut() {
    if (loggingOut) return;
    setLoggingOut(true);
    setLogoutError(null);
    try { await auth.logout(); router.replace("/login"); }
    catch (cause) { setLogoutError(describeError(cause)); }
    finally { setLoggingOut(false); }
  }

  return <>
    <div className="dashboard-title"><div><p className="eyebrow"><span className="dot" /> Личный кабинет</p><h1>Здравствуйте, {user.username}.</h1><p className="muted">Ваши поставщики и контакты в одном месте.</p></div><button className="button secondary small" type="button" onClick={signOut} disabled={loggingOut}>{loggingOut ? "Выходим…" : "Выйти"}</button></div>
    {logoutError && <p className="notice error" role="alert">Выход не подтверждён: {logoutError}</p>}
    <section aria-labelledby="suppliers-title">
      <div className="section-head"><h2 id="suppliers-title">Поставщики</h2><div className="actions"><button className="button secondary small" type="button" onClick={() => reload()} disabled={loading}>Обновить список</button><button className="button small" type="button" onClick={() => { setShowForm(true); setSuccess(null); }} disabled={showForm} aria-expanded={showForm} aria-controls="supplier-form">+ Создать поставщика</button></div></div>
      {success && <p role="status" className="notice success">{success}</p>}
      {showForm && <SupplierForm onCreated={created} onCancel={() => setShowForm(false)} />}
      {loading ? <p role="status">Загружаем поставщиков…</p> : error ? <div className="notice error" role="alert">{error} <button className="button secondary small" type="button" onClick={() => reload()}>Повторить</button></div> : <>
        <SupplierList suppliers={suppliers.slice(0, PAGE_SIZE)} />
        <nav className="pagination" aria-label="Страницы поставщиков"><button className="button secondary small" type="button" disabled={offset === 0} onClick={() => reload(Math.max(0, offset - PAGE_SIZE))}>← Назад</button><span>Страница {Math.floor(offset / PAGE_SIZE) + 1}</span><button className="button secondary small" type="button" disabled={suppliers.length <= PAGE_SIZE} onClick={() => reload(offset + PAGE_SIZE)}>Далее →</button></nav>
      </>}
    </section>
  </>;
}

export default function Dashboard() {
  const { user, loading, error, retry } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !user && !error) router.replace("/login");
  }, [loading, user, error, router]);

  if (loading) return <div className="session" role="status">Проверяем сессию…</div>;
  if (error) return <div className="session"><p className="notice error" role="alert">{error}</p><button className="button" type="button" onClick={() => void retry()}>Повторить проверку</button></div>;
  if (!user) return <div className="session" role="status">Переходим ко входу…</div>;
  return <Workspace key={user.id} user={user} />;
}
