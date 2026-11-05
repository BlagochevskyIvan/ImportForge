"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { describeError, listSupplierConfigs, saveSupplierConfig, type CsvColumn, type CsvConfig, type ImportConfig } from "@/lib/api";

const blankColumn = (): CsvColumn => ({ source: "", target: "", type: "text", required: false, trim: true, min_value: null, max_value: null });
const defaultConfig: CsvConfig = { schema_version: 2, delimiter: ",", encoding: "utf-8", columns: [blankColumn()] };

export default function SupplierConfigForm({ supplierId, initialConfig, onReadyChange }: {
  supplierId: number;
  initialConfig: ImportConfig | null;
  onReadyChange: (config: ImportConfig | null) => void;
}) {
  const [saved, setSaved] = useState(initialConfig);
  const [versions, setVersions] = useState<ImportConfig[]>(initialConfig ? [initialConfig] : []);
  const [config, setConfig] = useState(initialConfig?.config_data || defaultConfig);
  const [name, setName] = useState(initialConfig?.name || "Основная");
  const [busy, setBusy] = useState(false);
  const [dirty, setDirty] = useState(!initialConfig);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  useEffect(() => {
    let active = true;
    listSupplierConfigs(supplierId).then((items) => { if (active) setVersions(items); })
      .catch((cause) => { if (active) setError(describeError(cause)); });
    return () => { active = false; };
  }, [supplierId]);

  function apply(item: ImportConfig) {
    setSaved(item); setConfig(item.config_data); setName(item.name);
    setDirty(false); setError(null); setSuccess(null); onReadyChange(item);
  }

  function edited() {
    setDirty(true); setError(null); setSuccess(null); onReadyChange(null);
  }

  function updateColumn(index: number, changes: Partial<CsvColumn>) {
    setConfig({ ...config, columns: config.columns.map((column, i) => i === index ? { ...column, ...changes } : column) });
    edited();
  }

  async function loadJson(file: File) {
    setBusy(true); setError(null);
    try {
      if (file.size > 64 * 1024) throw new Error("JSON-конфиг должен быть не больше 64 КиБ.");
      const parsed = JSON.parse((await file.text()).replace(/^\uFEFF/, ""));
      const value = parsed.config_data ?? parsed;
      if (!Array.isArray(value.columns) || !value.columns.length || value.columns.length > 200 ||
          value.columns.some((column: unknown) => !column || typeof column !== "object" ||
            !("source" in column) || !("target" in column) || typeof column.source !== "string" || typeof column.target !== "string")) {
        throw new Error("Ожидается конфиг со списком columns от 1 до 200 колонок.");
      }
      setConfig({ ...defaultConfig, ...value, columns: value.columns.map((column: Partial<CsvColumn>) => ({ ...blankColumn(), ...column })) });
      if (typeof parsed.name === "string") setName(parsed.name);
      edited(); setSuccess("JSON загружен. Сохраните конфигурацию для запуска.");
    } catch (cause) { setError(cause instanceof SyntaxError ? "Не удалось прочитать JSON." : describeError(cause)); }
    finally { setBusy(false); if (fileInput.current) fileInput.current.value = ""; }
  }

  function downloadSaved() {
    if (!saved) return;
    const url = URL.createObjectURL(new Blob([JSON.stringify({ name: saved.name, config_data: saved.config_data }, null, 2)], { type: "application/json" }));
    const link = document.createElement("a"); link.href = url; link.download = `supplier-${supplierId}-config-${saved.id}.json`; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (busy) return;
    setBusy(true); setError(null); setSuccess(null);
    try {
      const result = await saveSupplierConfig(supplierId, config, name);
      apply(result);
      setVersions((items) => [result, ...items.filter((item) => item.id !== result.id)]);
      setSuccess("Конфигурация сохранена и выбрана для запуска. Предыдущие версии доступны в списке.");
    } catch (cause) { setError(describeError(cause)); }
    finally { setBusy(false); }
  }

  return <section className="card" aria-labelledby="config-title">
    <p className="eyebrow">Настройки обработки</p><h2 id="config-title">Конфигурации CSV</h2>
    <p className="small-text">Выберите сохранённую версию или задайте свои колонки и правила. Порядок колонок ниже определяет порядок в результате.</p>
    <p className="hint" role="status">{dirty ? "Есть несохранённые настройки. Сохраните их перед запуском." : `Для запуска выбрана конфигурация «${saved?.name}», версия #${saved?.id}.`}</p>
    {error && <p className="notice error" role="alert">{error}</p>}
    {success && <p className="notice success" role="status">{success}</p>}
    <form onSubmit={save} aria-busy={busy}><fieldset className="form" disabled={busy}>
      <legend className="sr-only">Конфигурация CSV</legend>
      <label className="field">Сохранённая версия
        <select value={dirty ? "custom" : String(saved?.id ?? "custom")} onChange={(event) => {
          const item = versions.find((version) => String(version.id) === event.target.value);
          if (item) apply(item);
          else { setConfig({ ...defaultConfig, columns: [blankColumn()] }); setName("Новая конфигурация"); edited(); }
        }}>
          <option value="custom">Новая / изменённая конфигурация</option>
          {versions.map((item) => <option key={item.id} value={item.id}>{item.name} · #{item.id}</option>)}
        </select>
      </label>
      <label className="field">Название конфигурации<input required maxLength={200} value={name} onChange={(event) => { setName(event.target.value); edited(); }} /></label>
      <div className="actions">
        <input ref={fileInput} className="sr-only" type="file" accept=".json,application/json" aria-label="JSON-конфиг" onChange={(event) => { const file = event.target.files?.[0]; if (file) void loadJson(file); }} />
        <button className="button secondary small" type="button" onClick={() => fileInput.current?.click()}>Загрузить JSON</button>
        {saved && <button className="button secondary small" type="button" onClick={downloadSaved}>Скачать сохранённый JSON</button>}
        {saved && dirty && <button className="button secondary small" type="button" onClick={() => apply(saved)}>Отменить изменения</button>}
      </div>
      <div className="config-options">
        <label className="field">Разделитель<select value={config.delimiter} onChange={(event) => { setConfig({ ...config, delimiter: event.target.value }); edited(); }}>
          <option value=",">Запятая (,)</option><option value=";">Точка с запятой (;)</option><option value={"\t"}>Табуляция</option><option value="|">Вертикальная черта (|)</option>
          {![",", ";", "\t", "|"].includes(config.delimiter) && <option value={config.delimiter}>Свой: {config.delimiter}</option>}
        </select></label>
        <label className="field">Кодировка<select value={config.encoding} onChange={(event) => { setConfig({ ...config, encoding: event.target.value as CsvConfig["encoding"] }); edited(); }}>
          <option value="utf-8">UTF-8</option><option value="utf-8-sig">UTF-8 с BOM</option><option value="cp1251">Windows-1251</option>
        </select></label>
      </div>
      {config.columns.map((column, index) => <fieldset key={index} className="form">
        <legend>Колонка {index + 1}</legend>
        <label className="field">Название в исходном CSV<input required maxLength={200} value={column.source} onChange={(event) => updateColumn(index, { source: event.target.value })} /></label>
        <label className="field">Название в результате<input required maxLength={200} value={column.target} onChange={(event) => updateColumn(index, { target: event.target.value })} /></label>
        <label className="field">Тип<select value={column.type} onChange={(event) => updateColumn(index, { type: event.target.value as CsvColumn["type"], min_value: null, max_value: null })}>
          <option value="text">Текст</option><option value="integer">Целое число</option><option value="decimal">Десятичное число</option>
        </select></label>
        <label><input type="checkbox" checked={column.required} onChange={(event) => updateColumn(index, { required: event.target.checked })} /> Обязательное значение</label>
        <label><input type="checkbox" checked={column.trim} onChange={(event) => updateColumn(index, { trim: event.target.checked })} /> Убирать пробелы по краям</label>
        {column.type !== "text" && <div className="config-options">
          <label className="field">Минимум<input inputMode="decimal" value={column.min_value ?? ""} onChange={(event) => updateColumn(index, { min_value: event.target.value || null })} /></label>
          <label className="field">Максимум<input inputMode="decimal" value={column.max_value ?? ""} onChange={(event) => updateColumn(index, { max_value: event.target.value || null })} /></label>
        </div>}
        <div className="actions">
          <button className="button secondary small" type="button" disabled={index === 0} onClick={() => {
            const columns = [...config.columns]; [columns[index - 1], columns[index]] = [columns[index], columns[index - 1]];
            setConfig({ ...config, columns }); edited();
          }}>Выше</button>
          <button className="button secondary small" type="button" disabled={config.columns.length === 1} onClick={() => { setConfig({ ...config, columns: config.columns.filter((_, i) => i !== index) }); edited(); }}>Удалить колонку</button>
        </div>
      </fieldset>)}
      <button className="button secondary small" type="button" disabled={config.columns.length >= 200} onClick={() => { setConfig({ ...config, columns: [...config.columns, blankColumn()] }); edited(); }}>Добавить колонку</button>
      <button className="button" type="submit">{busy ? "Сохраняем…" : "Сохранить конфигурацию"}</button>
    </fieldset></form>
  </section>;
}
