import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { ApiError } from "../api/client";
import { clearSyncRuns, importOrgDirectoryFile, listSyncRuns, triggerSync } from "../api/orgLoad";

const statusLabelRu: Record<string, string> = {
  running: "Выполняется",
  success: "Успешно",
  failed: "Ошибка",
  partial: "Частично",
};

export function SyncPage() {
  const queryClient = useQueryClient();
  const [triggering, setTriggering] = useState(false);
  const [departmentsFile, setDepartmentsFile] = useState<File | null>(null);
  const [employeesFile, setEmployeesFile] = useState<File | null>(null);
  const [importing, setImporting] = useState(false);
  const [importError, setImportError] = useState<string | null>(null);
  const { data: runs } = useQuery({ queryKey: ["sync-runs"], queryFn: listSyncRuns });
  const [clearing, setClearing] = useState(false);

  async function handleClearHistory() {
    if (!window.confirm("Удалить всю историю прогонов синхронизации оргструктуры? Действие необратимо.")) {
      return;
    }
    setClearing(true);
    try {
      await clearSyncRuns();
      queryClient.invalidateQueries({ queryKey: ["sync-runs"] });
    } finally {
      setClearing(false);
    }
  }

  async function handleTrigger() {
    setTriggering(true);
    try {
      await triggerSync();
      queryClient.invalidateQueries({ queryKey: ["sync-runs"] });
      queryClient.invalidateQueries({ queryKey: ["org-units"] });
    } finally {
      setTriggering(false);
    }
  }

  async function handleImport() {
    if (!departmentsFile && !employeesFile) return;
    setImportError(null);
    setImporting(true);
    try {
      const input: { departments?: string; employees?: string } = {};
      if (departmentsFile) input.departments = await departmentsFile.text();
      if (employeesFile) input.employees = await employeesFile.text();
      await importOrgDirectoryFile(input);
      setDepartmentsFile(null);
      setEmployeesFile(null);
      queryClient.invalidateQueries({ queryKey: ["sync-runs"] });
      queryClient.invalidateQueries({ queryKey: ["org-units"] });
    } catch (err) {
      setImportError(err instanceof ApiError ? err.message : "Не удалось загрузить файл");
    } finally {
      setImporting(false);
    }
  }

  return (
    <div>
      <h3>Синхронизация оргструктуры</h3>
      <p className="hint">
        Источник и реквизиты — на вкладке «Интеграции». Пока он выключен или URL не задан,
        используется тестовая фикстура вместо реального источника.
      </p>
      <button className="btn-primary" onClick={handleTrigger} disabled={triggering}>
        {triggering ? "Выполняется…" : "Запустить синхронизацию"}
      </button>
      {triggering && (
        <p className="hint" style={{ marginTop: 6 }}>
          Идёт обход подразделений и сотрудников — на большом штате может занять минуту и больше,
          не закрывайте страницу.
        </p>
      )}

      <div className="panel" style={{ marginTop: 16, maxWidth: 560 }}>
        <h4>Загрузить из файла</h4>
        <p className="hint">
          Файлы — сырой ответ источника (JSON с полем "value"): GetDepartments() и/или
          GetEmployeers(). Можно загрузить один файл или оба сразу — записи из файла обновят те
          же подразделения/сотрудников, что и обычная синхронизация по URL.
        </p>
        <label style={{ display: "block", marginBottom: 8 }}>
          <span style={{ display: "inline-block", width: 220 }}>Файл GetDepartments():</span>
          <input
            type="file"
            accept=".json,.txt,application/json,text/plain"
            onChange={(e) => setDepartmentsFile(e.target.files?.[0] ?? null)}
            disabled={importing}
          />
        </label>
        <label style={{ display: "block", marginBottom: 8 }}>
          <span style={{ display: "inline-block", width: 220 }}>Файл GetEmployeers():</span>
          <input
            type="file"
            accept=".json,.txt,application/json,text/plain"
            onChange={(e) => setEmployeesFile(e.target.files?.[0] ?? null)}
            disabled={importing}
          />
        </label>
        <button className="btn-outline" onClick={handleImport} disabled={importing || (!departmentsFile && !employeesFile)}>
          Загрузить
        </button>
        {importError && <p className="error-text">{importError}</p>}
      </div>

      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 16 }}>
        <h4 style={{ margin: 0 }}>История прогонов</h4>
        <button className="btn-ghost" onClick={handleClearHistory} disabled={clearing || !runs?.length}>
          {clearing ? "Удаление…" : "Очистить историю"}
        </button>
      </div>
      <div className="panel" style={{ marginTop: 8 }}>
        <table className="t">
          <thead>
            <tr>
              <th>Начало</th>
              <th>Статус</th>
              <th>Оргюниты</th>
              <th>Сотрудники</th>
              <th>Ошибка</th>
            </tr>
          </thead>
          <tbody>
            {runs?.map((r) => (
              <tr key={r.id}>
                <td>{new Date(r.started_at).toLocaleString("ru-RU")}</td>
                <td>{statusLabelRu[r.status] ?? r.status}</td>
                <td>
                  {r.summary.org_units &&
                    `создано ${r.summary.org_units.created}, обновлено ${r.summary.org_units.updated}, без изменений ${r.summary.org_units.unchanged}`}
                </td>
                <td>
                  {r.summary.users &&
                    `создано ${r.summary.users.created}, обновлено ${r.summary.users.updated}, без изменений ${r.summary.users.unchanged}`}
                </td>
                <td className="error-text" style={{ maxWidth: 420, wordBreak: "break-word" }}>
                  {r.error_message}
                </td>
              </tr>
            ))}
            {(!runs || runs.length === 0) && (
              <tr>
                <td colSpan={5} className="empty">
                  Синхронизация ещё не запускалась.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
