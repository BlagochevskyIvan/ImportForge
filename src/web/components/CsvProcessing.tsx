"use client";

import { useEffect, useState } from "react";
import { describeError, downloadCsv, listFiles, processFile, type SourceFile } from "@/lib/api";

const PAGE_SIZE = 10;
const statusLabels: Record<SourceFile["status"], string> = {
  uploaded: "Готов к обработке", processing: "Обрабатывается", completed: "Обработан", failed: "Ошибка обработки",
};

export default function CsvProcessing({ supplierId, revision }: { supplierId: number; revision: number }) {
  const [files, setFiles] = useState<SourceFile[]>([]);
  const [offset, setOffset] = useState(0);
  const [refresh, setRefresh] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [processing, setProcessing] = useState<string | null>(null);
  const [downloading, setDownloading] = useState<string | null>(null);
  const hasProcessing = files.some((file) => file.status === "processing");

  useEffect(() => {
    let active = true;
    listFiles(supplierId, offset, PAGE_SIZE + 1).then((records) => {
      if (active) { setFiles(records); setError(null); }
    }).catch((cause) => { if (active) setError(describeError(cause)); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [supplierId, offset, revision, refresh]);

  useEffect(() => {
    if (!hasProcessing) return;
    const timer = setInterval(() => setRefresh((value) => value + 1), 3000);
    return () => clearInterval(timer);
  }, [hasProcessing]);

  async function process(file: SourceFile) {
    if (processing) return;
    setProcessing(file.id);
    setError(null);
    setFiles((records) => records.map((record) => record.id === file.id ? { ...record, status: "processing" } : record));
    try {
      const result = await processFile(file.id);
      setFiles((records) => records.map((record) => record.id === result.id ? result : record));
    } catch (cause) { setError(describeError(cause)); }
    finally { setProcessing(null); setRefresh((value) => value + 1); }
  }

  async function download(file: SourceFile, kind: "source" | "result" | "errors") {
    if (downloading) return;
    setDownloading(`${file.id}:${kind}`);
    setError(null);
    try { await downloadCsv(file, kind); }
    catch (cause) { setError(describeError(cause)); }
    finally { setDownloading(null); }
  }

  function page(next: number) {
    setLoading(true);
    setOffset(next);
  }

  return <section className="card processing-section" aria-labelledby="processing-title">
    <div className="section-head"><div><p className="eyebrow">Шаг 3</p><h2 id="processing-title">Обработка CSV</h2></div>
      <button className="button secondary small" type="button" onClick={() => setRefresh((value) => value + 1)} disabled={loading}>Обновить</button>
    </div>
    <p className="small-text">Каждый файл использует настройки, сохранённые при его загрузке. Результат содержит колонки sku, name, price; ошибки записей сохраняются отдельным CSV.</p>
    {error && <p className="notice error" role="alert">{error}</p>}
    {loading ? <p role="status">Загружаем файлы…</p> : !files.length ? <p className="muted">Загрузите CSV, чтобы начать обработку.</p> : <div className="processing-list">
      {files.slice(0, PAGE_SIZE).map((file) => <article className="processing-file" key={file.id} aria-busy={file.status === "processing"}>
        <div className="section-head"><strong>{file.filename}</strong><span className={`badge${file.status === "failed" ? " inactive" : ""}`}>{statusLabels[file.status]}</span></div>
        <p className="hint">ID: {file.id}</p>
        {file.status === "processing" && <p role="status" className="small-text">Читаем CSV и формируем результат…</p>}
        {file.processing_result?.error && <p className="notice error" role="alert">{file.processing_result.error}</p>}
        {file.status === "completed" && file.processing_result && <>
          <dl className="processing-stats"><div><dt>Всего записей</dt><dd>{file.processing_result.total_rows}</dd></div><div><dt>Успешно</dt><dd>{file.processing_result.successful_rows}</dd></div><div><dt>С ошибками</dt><dd>{file.processing_result.failed_rows}</dd></div></dl>
          {file.processing_result.failed_rows > 0 && <p className="small-text">Некорректные записи пропущены. Причины и исходные значения доступны в отчёте ошибок.</p>}
        </>}
        <div className="actions">
          {(file.status === "uploaded" || file.status === "failed") && <button className="button small" type="button" disabled={Boolean(processing)} onClick={() => void process(file)}>{file.status === "failed" ? "Повторить обработку" : "Обработать"}</button>}
          <button className="button secondary small" type="button" disabled={Boolean(downloading)} onClick={() => void download(file, "source")}>Исходник</button>
          {file.status === "completed" && <>
            <button className="button small" type="button" disabled={Boolean(downloading)} onClick={() => void download(file, "result")}>Скачать результат</button>
            <button className="button secondary small" type="button" disabled={Boolean(downloading)} onClick={() => void download(file, "errors")}>Отчёт ошибок</button>
          </>}
        </div>
        {downloading?.startsWith(`${file.id}:`) && <p className="hint" role="status">Скачиваем файл…</p>}
      </article>)}
    </div>}
    {(offset > 0 || files.length > PAGE_SIZE) && <nav className="pagination" aria-label="Страницы файлов">
      <button className="button secondary small" type="button" disabled={loading || offset === 0} onClick={() => page(Math.max(0, offset - PAGE_SIZE))}>← Назад</button>
      <span>Страница {Math.floor(offset / PAGE_SIZE) + 1}</span>
      <button className="button secondary small" type="button" disabled={loading || files.length <= PAGE_SIZE} onClick={() => page(offset + PAGE_SIZE)}>Далее →</button>
    </nav>}
  </section>;
}
