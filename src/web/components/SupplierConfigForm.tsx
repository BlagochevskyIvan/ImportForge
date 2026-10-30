"use client";

import { useRef, useState, type FormEvent } from "react";
import { describeError, saveSupplierConfig, type CsvConfig, type ImportConfig } from "@/lib/api";

const defaultConfig: CsvConfig = {
  delimiter: ",", encoding: "utf-8", column_mapping: { sku: "sku", name: "name", price: "price" },
};
const targets = ["sku", "name", "price"] as const;
const targetLabels = { sku: "Артикул (sku)", name: "Название (name)", price: "Цена (price)" };

function sourceFor(config: CsvConfig, target: typeof targets[number]) {
  return Object.entries(config.column_mapping).find(([, value]) => value === target)?.[0] || "";
}

function readConfig(value: unknown): CsvConfig {
  if (value && typeof value === "object" && "config_data" in value) value = value.config_data;
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("Ожидается JSON-объект конфига.");
  const data = value as Record<string, unknown>;
  if (Object.keys(data).some((key) => !["delimiter", "encoding", "column_mapping"].includes(key))) {
    throw new Error("Допустимы только delimiter, encoding и column_mapping.");
  }
  const delimiter = data.delimiter === undefined ? "," : data.delimiter;
  const encoding = data.encoding === undefined ? "utf-8" : data.encoding;
  if (typeof delimiter !== "string" || Array.from(delimiter).length !== 1 || /[\n\r\0"]/.test(delimiter)) {
    throw new Error("Разделитель должен быть одним символом, кроме переноса строки, NUL и кавычки.");
  }
  if (encoding !== "utf-8" && encoding !== "utf-8-sig" && encoding !== "cp1251") {
    throw new Error("Выберите кодировку UTF-8, UTF-8 с BOM или Windows-1251.");
  }
  if (!data.column_mapping || typeof data.column_mapping !== "object" || Array.isArray(data.column_mapping)) {
    throw new Error("Укажите соответствие колонок в column_mapping.");
  }
  const entries = Object.entries(data.column_mapping);
  if (entries.length !== 3 || targets.some((target) => entries.filter(([, value]) => value === target).length !== 1)) {
    throw new Error("Сопоставьте ровно три колонки: sku, name и price, каждую один раз.");
  }
  const names = entries.map(([name]) => name.trim());
  if (names.some((name) => !name || Array.from(name).length > 200) || new Set(names).size !== 3) {
    throw new Error("Названия трёх исходных колонок должны различаться и содержать от 1 до 200 символов.");
  }
  return {
    delimiter, encoding,
    column_mapping: Object.fromEntries(entries.map(([name, target]) => [name.trim(), target])) as CsvConfig["column_mapping"],
  };
}

export default function SupplierConfigForm({ supplierId, initialConfig, onReadyChange }: {
  supplierId: number;
  initialConfig: ImportConfig | null;
  onReadyChange: (ready: boolean) => void;
}) {
  const [saved, setSaved] = useState(initialConfig);
  const [selection, setSelection] = useState(initialConfig ? "saved" : "comma");
  const [config, setConfig] = useState(initialConfig?.config_data || defaultConfig);
  const [sources, setSources] = useState(() => targets.map((target) => sourceFor(config, target)));
  const [busy, setBusy] = useState(false);
  const [dirty, setDirty] = useState(!initialConfig);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  function apply(next: CsvConfig, option: string, ready = false) {
    setConfig(next);
    setSources(targets.map((target) => sourceFor(next, target)));
    setSelection(option);
    setDirty(!ready);
    setError(null);
    setSuccess(null);
    onReadyChange(ready);
  }

  function edited() {
    setSelection("custom");
    setDirty(true);
    setError(null);
    setSuccess(null);
    onReadyChange(false);
  }

  async function loadJson(file: File) {
    setError(null);
    setSuccess(null);
    setBusy(true);
    try {
      if (file.size > 64 * 1024) throw new Error("JSON-конфиг должен быть не больше 64 КиБ.");
      const parsed = JSON.parse((await file.text()).replace(/^\uFEFF/, ""));
      apply(readConfig(parsed), "custom");
      setSuccess(`Конфиг из «${file.name}» выбран. Сохраните его для загрузки CSV.`);
    } catch (cause) {
      setError(cause instanceof SyntaxError ? "Не удалось прочитать JSON. Проверьте формат файла." : describeError(cause));
    } finally {
      if (fileInput.current) fileInput.current.value = "";
      setBusy(false);
    }
  }

  function downloadSaved() {
    if (!saved) return;
    const blob = new Blob([JSON.stringify({ config_data: saved.config_data }, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `supplier-${supplierId}-config.json`;
    link.click();
    // Let the browser start the download before releasing the object URL.
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    setError(null);
    setSuccess(null);
    setBusy(true);
    try {
      if (new Set(sources.map((name) => name.trim())).size !== 3) {
        throw new Error("Для артикула, названия и цены укажите три разные колонки CSV.");
      }
      const next = readConfig({ ...config, column_mapping: Object.fromEntries(sources.map((name, index) => [name, targets[index]])) });
      const result = await saveSupplierConfig(supplierId, next);
      setSaved(result);
      apply(result.config_data, "saved", true);
      setSuccess("Конфиг сохранён. Теперь можно загрузить CSV.");
    } catch (cause) { setError(describeError(cause)); }
    finally { setBusy(false); }
  }

  return <section className="card" aria-labelledby="config-title">
    <p className="eyebrow">Шаг 1</p><h2 id="config-title">Конфиг CSV</h2>
    <p className="small-text">Выберите сохранённый конфиг, шаблон или JSON-файл. У поставщика один текущий конфиг.</p>
    <p className="hint" role="status">{dirty
      ? "Настройки не сохранены. Сохраните их перед загрузкой CSV."
      : "Используется сохранённый конфиг поставщика."}</p>
    {error && <p className="notice error" role="alert">{error}</p>}
    {success && <p className="notice success" role="status">{success}</p>}
    <form onSubmit={save} aria-busy={busy}>
      <fieldset className="form" disabled={busy}>
        <legend className="sr-only">Настройки конфига CSV</legend>
        <label className="field">Выбор конфига
          <select value={selection} onChange={(event) => {
            const option = event.target.value;
            if (option === "saved" && saved) apply(saved.config_data, option, true);
            else apply({ ...defaultConfig, delimiter: option === "semicolon" ? ";" : option === "tab" ? "\t" : "," }, option);
          }}>
            {saved && <option value="saved">Сохранённый конфиг поставщика</option>}
            <option value="comma">CSV: запятая, UTF-8</option>
            <option value="semicolon">CSV: точка с запятой, UTF-8</option>
            <option value="tab">CSV: табуляция, UTF-8</option>
            {selection === "custom" && <option value="custom">Свои настройки / JSON-файл</option>}
          </select>
        </label>
        <div className="actions">
          <input ref={fileInput} className="sr-only" id="config-file" type="file" accept=".json,application/json" aria-label="JSON-конфиг" tabIndex={-1} onChange={(event) => { const file = event.target.files?.[0]; if (file) void loadJson(file); }} />
          <button className="button secondary small" type="button" onClick={() => fileInput.current?.click()}>Выбрать JSON-конфиг</button>
          {saved && <button className="button secondary small" type="button" onClick={downloadSaved}>Скачать сохранённый JSON</button>}
          {saved && dirty && <button className="button secondary small" type="button" onClick={() => apply(saved.config_data, "saved", true)}>Отменить изменения</button>}
        </div>
        <div className="config-options">
          <label className="field">Разделитель
            <select value={config.delimiter} onChange={(event) => { setConfig({ ...config, delimiter: event.target.value }); edited(); }}>
              <option value=",">Запятая (,)</option><option value=";">Точка с запятой (;)</option><option value={"\t"}>Табуляция</option><option value="|">Вертикальная черта (|)</option>
              {![",", ";", "\t", "|"].includes(config.delimiter) && <option value={config.delimiter}>Свой: {config.delimiter}</option>}
            </select>
          </label>
          <label className="field">Кодировка
            <select value={config.encoding} onChange={(event) => { setConfig({ ...config, encoding: event.target.value as CsvConfig["encoding"] }); edited(); }}>
              <option value="utf-8">UTF-8</option><option value="utf-8-sig">UTF-8 с BOM</option><option value="cp1251">Windows-1251</option>
            </select>
          </label>
        </div>
        <p className="hint">Введите точные названия колонок из первой строки CSV.</p>
        {targets.map((target, index) => <label className="field" key={target}>{targetLabels[target]}
          <input required maxLength={200} name={`source_${target}`} value={sources[index]} onChange={(event) => { setSources(sources.map((source, i) => i === index ? event.target.value : source)); edited(); }} />
        </label>)}
        <button className="button" type="submit">{busy ? "Сохраняем…" : "Сохранить конфиг"}</button>
      </fieldset>
    </form>
  </section>;
}
