"use client";

import { useRef, useState, type FormEvent } from "react";
import { describeError, uploadCsv, type SourceFile } from "@/lib/api";

const MAX_FILE_SIZE = 20 * 1024 * 1024;

export default function CsvUpload({ supplierId, configReady }: { supplierId: number; configReady: boolean }) {
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [uploaded, setUploaded] = useState<SourceFile | null>(null);
  const input = useRef<HTMLInputElement>(null);

  function choose(next: File | null) {
    setError(null);
    setUploaded(null);
    setFile(null);
    if (!next) return;
    if (!next.name.toLowerCase().endsWith(".csv")) setError("Выберите файл с расширением .csv.");
    else if (next.name.length > 255) setError("Имя файла должно содержать не больше 255 символов.");
    else if (!next.size) setError("Выбранный файл пуст.");
    else if (next.size > MAX_FILE_SIZE) setError("Размер CSV не должен превышать 20 МиБ.");
    else { setFile(next); return; }
    if (input.current) input.current.value = "";
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy || !file || !configReady) return;
    setBusy(true);
    setError(null);
    setUploaded(null);
    try {
      const result = await uploadCsv(supplierId, file);
      setUploaded(result);
      setFile(null);
      if (input.current) input.current.value = "";
    } catch (cause) { setError(describeError(cause)); }
    finally { setBusy(false); }
  }

  return <section className="card" aria-labelledby="csv-title">
    <p className="eyebrow">Шаг 2</p><h2 id="csv-title">Загрузка CSV</h2>
    <p className="small-text">CSV до 20 МиБ с заголовками в первой строке. Файл сохранится у выбранного поставщика вместе с копией конфига.</p>
    {!configReady && <p className="notice" role="status">Сначала сохраните конфиг или выберите сохранённый вариант.</p>}
    {error && <p className="notice error" role="alert">{error}</p>}
    {uploaded && <div className="notice success" role="status"><strong>Файл «{uploaded.filename}» загружен.</strong><div>ID: {uploaded.id}</div><div>Статус: загружен. Обработка ещё не запускалась.</div></div>}
    <form className="form" onSubmit={submit} aria-busy={busy}>
      <label className="field">CSV-файл
        <input ref={input} type="file" name="file" accept=".csv,text/csv" disabled={busy} onChange={(event) => choose(event.target.files?.[0] || null)} />
      </label>
      {file && <p className="selected-file">{file.name} <span className="hint">({(file.size / 1024).toFixed(1)} КиБ)</span></p>}
      <div className="actions">
        <button className="button" type="submit" disabled={busy || !file || !configReady}>{busy ? "Загружаем…" : "Загрузить CSV"}</button>
        <button className="button secondary" type="button" disabled={busy || !file} onClick={() => { if (input.current) input.current.value = ""; choose(null); }}>Очистить</button>
      </div>
      {busy && <span className="hint" role="status">Отправляем файл. Дождитесь подтверждения сервера.</span>}
    </form>
  </section>;
}
