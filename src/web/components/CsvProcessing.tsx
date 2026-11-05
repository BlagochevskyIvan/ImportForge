"use client";

import { useEffect, useState } from "react";
import { describeError, downloadCsv, listFiles, listRuns, processFile, type ImportRun, type SourceFile } from "@/lib/api";

const PAGE_SIZE = 10;
const statusLabels: Record<SourceFile["status"], string> = {
  uploaded: "Готов к обработке", processing: "Обрабатывается", completed: "Обработан", failed: "Ошибка обработки",
  queued: "Ожидает обработки", retry_wait: "Ожидает повторной попытки",
};

export default function CsvProcessing({ supplierId, revision, configId }: { supplierId: number; revision: number; configId: number | null }) {
  const [files, setFiles] = useState<SourceFile[]>([]);
  const [offset, setOffset] = useState(0);
  const [refresh, setRefresh] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [processing, setProcessing] = useState<string | null>(null);
  const [downloading, setDownloading] = useState<string | null>(null);
  const [history, setHistory] = useState<Record<string, ImportRun[]>>({});
  const hasProcessing = files.some((file) => ["queued", "processing", "retry_wait"].includes(file.status));

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
      const result = await processFile(file.id, configId);
      setFiles((records) => records.map((record) => record.id === result.id ? result : record));
      setHistory((items) => { const next = { ...items }; delete next[file.id]; return next; });
    } catch (cause) { setError(describeError(cause)); }
    finally { setProcessing(null); setRefresh((value) => value + 1); }
  }

  async function download(file: SourceFile, kind: "source" | "result" | "errors", runId?: string) {
    if (downloading) return;
    setDownloading(`${file.id}:${kind}`);
    setError(null);
    try { await downloadCsv(file, kind, runId); }
    catch (cause) { setError(describeError(cause)); }
    finally { setDownloading(null); }
  }

  async function showHistory(file: SourceFile) {
    try { setHistory((items) => ({ ...items, [file.id]: [] }));
      const runs = await listRuns(file.id);
      setHistory((items) => ({ ...items, [file.id]: runs }));
    } catch (cause) { setError(describeError(cause)); }
  }

  function page(next: number) {
    setLoading(true);
    setOffset(next);
  }

  return <section className="card processing-section" aria-labelledby="processing-title">
    <div className="section-head"><div><p className="eyebrow">Шаг 3</p><h2 id="processing-title">Обработка CSV</h2></div>
      <button className="button secondary small" type="button" onClick={() => setRefresh((value) => value + 1)} disabled={loading}>Обновить</button>
    </div>
    <p className="small-text">Каждый запуск сохраняет выбранную конфигурацию и собственный результат. Колонки определяются настройками. Ошибки записей доступны отдельным CSV.</p>
    {!configId && <p className="hint">Выберите сохранённую конфигурацию в форме выше для нового запуска.</p>}
    {error && <p className="notice error" role="alert">{error}</p>}
    {loading ? <p role="status">Загружаем файлы…</p> : !files.length ? <p className="muted">Загрузите CSV, чтобы начать обработку.</p> : <div className="processing-list">
      {files.slice(0, PAGE_SIZE).map((file) => <article className="processing-file" key={file.id} aria-busy={file.status === "processing"}>
        <div className="section-head"><strong>{file.filename}</strong><span className={`badge${file.status === "failed" ? " inactive" : ""}`}>{statusLabels[file.status]}</span></div>
        <p className="hint">ID: {file.id}</p>
        {file.latest_run && <p className="hint">Последний запуск: {file.latest_run.config_name} · {file.latest_run.id}</p>}
        {file.status === "processing" && <p role="status" className="small-text">Читаем CSV и формируем результат…</p>}
        {file.processing_result?.error && <p className="notice error" role="alert">{file.processing_result.error}</p>}
        {file.status === "completed" && file.processing_result && <>
          <dl className="processing-stats"><div><dt>Всего записей</dt><dd>{file.processing_result.total_rows}</dd></div><div><dt>Успешно</dt><dd>{file.processing_result.successful_rows}</dd></div><div><dt>С ошибками</dt><dd>{file.processing_result.failed_rows}</dd></div></dl>
          {file.processing_result.failed_rows > 0 && <p className="small-text">Некорректные записи пропущены. Причины и исходные значения доступны в отчёте ошибок.</p>}
        </>}
        <div className="actions">
          {!["queued", "processing", "retry_wait"].includes(file.status) && <button className="button small" type="button" disabled={Boolean(processing) || !configId} onClick={() => void process(file)}>{file.latest_run ? "Новый запуск" : "Обработать"}</button>}
          <button className="button secondary small" type="button" onClick={() => void showHistory(file)}>История запусков</button>
          <button className="button secondary small" type="button" disabled={Boolean(downloading)} onClick={() => void download(file, "source")}>Исходник</button>
          {file.status === "completed" && <>
            <button className="button small" type="button" disabled={Boolean(downloading)} onClick={() => void download(file, "result")}>Скачать результат</button>
            <button className="button secondary small" type="button" disabled={Boolean(downloading)} onClick={() => void download(file, "errors")}>Отчёт ошибок</button>
          </>}
        </div>
        {history[file.id]?.map((run) => <div key={run.id} className="hint">
          <p>{run.config_name} · {new Date(run.created_at).toLocaleString("ru-RU")} · {statusLabels[run.status]}</p>
          {run.error_message && <p>{run.error_message}</p>}
          {run.status === "completed" && <div className="actions">
            <button className="button secondary small" type="button" disabled={Boolean(downloading)} onClick={() => void download(file, "result", run.id)}>Результат запуска</button>
            <button className="button secondary small" type="button" disabled={Boolean(downloading)} onClick={() => void download(file, "errors", run.id)}>Ошибки запуска</button>
          </div>}
        </div>)}
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
