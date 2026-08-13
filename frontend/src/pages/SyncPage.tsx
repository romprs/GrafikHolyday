import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { ApiError } from "../api/client";
import { importOrgDirectoryFile, listSyncRuns, triggerSync } from "../api/orgLoad";

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
      <p style={{ color: "#888", fontSize: "0.9em" }}>
        Источник и реквизиты — на вкладке «Интеграции». Пока он выключен или URL не задан,
        используется тестовая фикстура вместо реального источника.
      </p>
      <button onClick={handleTrigger} disabled={triggering}>
        Запустить синхронизацию
      </button>

      <div
        style={{
          marginTop: 16,
          padding: 16,
          border: "1px solid #ddd",
          borderRadius: 6,
          maxWidth: 560,
        }}
      >
        <h4 style={{ marginTop: 0 }}>Загрузить из файла</h4>
        <p style={{ fontSize: "0.85em", color: "#888" }}>
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
        <button
          onClick={handleImport}
          disabled={importing || (!departmentsFile && !employeesFile)}
        >
          Загрузить
        </button>
        {importError && <p style={{ color: "crimson" }}>{importError}</p>}
      </div>

      <table style={{ borderCollapse: "collapse", width: "100%", marginTop: 16 }}>
        <thead>
          <tr>
            <th style={{ textAlign: "left" }}>Начало</th>
            <th style={{ textAlign: "left" }}>Статус</th>
            <th style={{ textAlign: "left" }}>Оргюниты</th>
            <th style={{ textAlign: "left" }}>Сотрудники</th>
            <th style={{ textAlign: "left" }}>Ошибка</th>
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
              <td style={{ color: "crimson", maxWidth: 420, wordBreak: "break-word" }}>
                {r.error_message}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
