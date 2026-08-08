import { useQuery } from "@tanstack/react-query";
import { listAuditLog } from "../api/admin";

function formatState(state: Record<string, unknown>): string {
  return Object.entries(state)
    .map(([k, v]) => `${k}: ${v}`)
    .join(", ");
}

export function AuditLogPage() {
  const { data: entries } = useQuery({ queryKey: ["audit-log"], queryFn: listAuditLog });

  return (
    <div>
      <h3>Журнал изменений</h3>
      <table style={{ borderCollapse: "collapse", width: "100%" }}>
        <thead>
          <tr>
            <th style={{ textAlign: "left" }}>Когда</th>
            <th style={{ textAlign: "left" }}>Действие</th>
            <th style={{ textAlign: "left" }}>Причина</th>
            <th style={{ textAlign: "left" }}>Было</th>
            <th style={{ textAlign: "left" }}>Стало</th>
          </tr>
        </thead>
        <tbody>
          {entries?.map((e) => (
            <tr key={e.id}>
              <td>{new Date(e.created_at).toLocaleString("ru-RU")}</td>
              <td>{e.action}</td>
              <td>{e.reason}</td>
              <td>{formatState(e.before_state)}</td>
              <td>{formatState(e.after_state)}</td>
            </tr>
          ))}
          {entries?.length === 0 && (
            <tr>
              <td colSpan={5}>Изменений пока нет.</td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
