import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { listSyncRuns, triggerSync } from "../api/orgLoad";

const statusLabelRu: Record<string, string> = {
  running: "Выполняется",
  success: "Успешно",
  failed: "Ошибка",
  partial: "Частично",
};

export function SyncPage() {
  const queryClient = useQueryClient();
  const [triggering, setTriggering] = useState(false);
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

      <table style={{ borderCollapse: "collapse", width: "100%", marginTop: 16 }}>
        <thead>
          <tr>
            <th style={{ textAlign: "left" }}>Начало</th>
            <th style={{ textAlign: "left" }}>Статус</th>
            <th style={{ textAlign: "left" }}>Оргюниты</th>
            <th style={{ textAlign: "left" }}>Сотрудники</th>
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
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
