"use client";

import { useState, type FormEvent } from "react";
import { createSupplier, describeError, type Supplier } from "@/lib/api";

interface SupplierFormProps {
  onCreated: (supplier: Supplier) => void;
  onCancel: () => void;
}

export default function SupplierForm({ onCreated, onCancel }: SupplierFormProps) {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    setError(null);
    const normalizedName = name.trim();
    if (!normalizedName || Array.from(normalizedName).length > 200 || !email.trim()) {
      setError("Введите название (1–200 символов) и контактный email."); return;
    }
    setBusy(true);
    try {
      const supplier = await createSupplier({ name: normalizedName, contact_email: email.trim() });
      onCreated(supplier);
    } catch (cause) { setError(describeError(cause)); }
    finally { setBusy(false); }
  }

  return <section className="card supplier-form" id="supplier-form" aria-labelledby="supplier-form-title">
    <h3 id="supplier-form-title">Новый поставщик</h3>
    <p className="small-text">Укажите название компании и email для связи.</p>
    {error && <p className="notice error" role="alert">{error}</p>}
    <form className="form" onSubmit={submit} aria-busy={busy}>
      <label className="field">Название поставщика
        <input name="name" required maxLength={200} value={name} onChange={(event) => setName(event.target.value)} disabled={busy} placeholder="Например, Север Трейд" autoFocus />
      </label>
      <label className="field">Контактный email
        <input name="contact_email" type="email" required maxLength={320} value={email} onChange={(event) => setEmail(event.target.value)} disabled={busy} placeholder="supply@company.ru" />
      </label>
      <div className="actions"><button className="button" type="submit" disabled={busy}>{busy ? "Создаём…" : "Сохранить поставщика"}</button><button className="button secondary" type="button" disabled={busy} onClick={onCancel}>Отмена</button></div>
      {busy && <span role="status" className="hint">Ожидаем ответ сервера…</span>}
    </form>
  </section>;
}
