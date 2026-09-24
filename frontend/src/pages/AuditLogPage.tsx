import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { clearAuditLog, listAuditLog } from "../api/admin";
import { apiFetch } from "../api/client";
import type { LeaveRequestStatus, OrgUnitEmployeeOut, OrgUnitOut } from "../api/types";
import { statusLabel } from "./statusLabel";

const entityTypeLabelRu: Record<string, string> = {
  org_unit: "Подразделение",
  user: "Сотрудник",
  leave_delegation: "Делегирование",
};

// Ключи полей в "Было"/"Стало" — это имена полей моделей на бэкенде
// (см. audit_service.log в user_admin_service.py, org_unit_service.py,
// delegation_service.py, approval_service.py) и без перевода выглядели
// как английские названия прямо в журнале.
const fieldLabelRu: Record<string, string> = {
  email: "email",
  full_name: "ФИО",
  org_unit_id: "подразделение",
  has_benefits: "льготы",
  is_active: "активен",
  hire_date: "дата приёма",
  termination_date: "дата увольнения",
  employee_code: "таб. номер",
  name: "название",
  unit_kind: "тип",
  parent_id: "родительское подразделение",
  head_user_id: "руководитель",
  date_from: "начало периода",
  date_to: "конец периода",
  status: "статус",
  bonus_requested: "выплата ЕСВ",
  is_approver: "право согласования",
  delegate_user_id: "делегат",
  scope: "область",
  role: "роль",
};

function actionLabelRu(action: string): string {
  const labels: Record<string, string> = {
    create: "создание",
    update: "изменение",
    deactivate: "деактивация",
    reactivate: "восстановление",
    grant: "выдача",
    revoke: "отзыв",
    role_grant: "выдача роли",
    role_revoke: "отзыв роли",
  };
  return labels[action] ?? action;
}

export function AuditLogPage() {
  const queryClient = useQueryClient();
  const { data: entries } = useQuery({ queryKey: ["audit-log"], queryFn: listAuditLog });
  const { data: orgUnits } = useQuery({
    queryKey: ["org-units"],
    queryFn: () => apiFetch<OrgUnitOut[]>("/org-units"),
  });
  const { data: employees } = useQuery({
    queryKey: ["org-unit-employees"],
    queryFn: () => apiFetch<OrgUnitEmployeeOut[]>("/org-units/employees"),
  });

  // Раньше в "Было"/"Стало" сырые UUID (org_unit_id, head_user_id и т.п.)
  // ничего не говорили HR — теперь подставляем имя, если id из диапазона
  // подразделений/сотрудников (id самой строки в этих отображениях не
  // используется, только их id для распознавания значений внутри диффов).
  const idToName = useMemo(() => {
    const map = new Map<string, string>();
    for (const u of orgUnits ?? []) map.set(u.id, u.name);
    for (const e of employees ?? []) map.set(e.id, e.full_name);
    return map;
  }, [orgUnits, employees]);

  function resolveValue(key: string, v: unknown): string {
    if (v === null || v === undefined) return "—";
    if (typeof v === "boolean") return v ? "да" : "нет";
    if (key === "status" && typeof v === "string") return statusLabel(v as LeaveRequestStatus);
    if (typeof v === "string" && idToName.has(v)) return idToName.get(v)!;
    if (typeof v === "object") {
      const obj = v as Record<string, unknown>;
      if ("before" in obj || "after" in obj) {
        return `${resolveValue(key, obj.before)} → ${resolveValue(key, obj.after)}`;
      }
    }
    return String(v);
  }

  function formatState(state: Record<string, unknown>): string {
    return Object.entries(state)
      .map(([k, v]) => `${fieldLabelRu[k] ?? k}: ${resolveValue(k, v)}`)
      .join("; ");
  }

  const [search, setSearch] = useState("");
  const [entityTypeFilter, setEntityTypeFilter] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [clearing, setClearing] = useState(false);

  const entityTypes = useMemo(
    () => Array.from(new Set((entries ?? []).map((e) => e.entity_type))).sort(),
    [entries],
  );

  const filteredEntries = useMemo(() => {
    const query = search.trim().toLowerCase();
    return (entries ?? []).filter((e) => {
      if (entityTypeFilter && e.entity_type !== entityTypeFilter) return false;
      const day = e.created_at.slice(0, 10);
      if (dateFrom && day < dateFrom) return false;
      if (dateTo && day > dateTo) return false;
      if (query) {
        const haystack = `${e.performed_by_name} ${e.action} ${e.reason}`.toLowerCase();
        if (!haystack.includes(query)) return false;
      }
      return true;
    });
  }, [entries, search, entityTypeFilter, dateFrom, dateTo]);

  async function handleClear() {
    const range =
      dateFrom || dateTo
        ? `за период ${dateFrom || "…"} — ${dateTo || "…"}`
        : "целиком (весь журнал)";
    if (!window.confirm(`Очистить журнал изменений ${range}? Действие необратимо.`)) return;
    setClearing(true);
    try {
      await clearAuditLog({ date_from: dateFrom || undefined, date_to: dateTo || undefined });
      queryClient.invalidateQueries({ queryKey: ["audit-log"] });
    } finally {
      setClearing(false);
    }
  }

  return (
    <div>
      <h3>Журнал изменений</h3>

      <div className="toolbar">
        <input
          type="text"
          placeholder="Поиск: кто/действие/причина"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{ width: 220 }}
        />
        <select value={entityTypeFilter} onChange={(e) => setEntityTypeFilter(e.target.value)}>
          <option value="">Все сущности</option>
          {entityTypes.map((t) => (
            <option key={t} value={t}>
              {entityTypeLabelRu[t] ?? t}
            </option>
          ))}
        </select>
        <label style={{ display: "flex", alignItems: "center", gap: 4 }}>
          с <input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
        </label>
        <label style={{ display: "flex", alignItems: "center", gap: 4 }}>
          по <input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
        </label>
        <span className="hint">
          Показано {filteredEntries.length} из {entries?.length ?? 0}
        </span>
        <button className="btn-ghost" onClick={handleClear} disabled={clearing || !entries?.length} style={{ marginLeft: "auto" }}>
          {clearing ? "Очистка…" : dateFrom || dateTo ? "Очистить за период" : "Очистить журнал"}
        </button>
      </div>

      <div className="panel">
        <table className="t">
          <thead>
            <tr>
              <th>Когда</th>
              <th>Кто</th>
              <th>Сущность</th>
              <th>Действие</th>
              <th>Причина</th>
              <th>Было</th>
              <th>Стало</th>
            </tr>
          </thead>
          <tbody>
            {filteredEntries.map((e) => (
              <tr key={e.id}>
                <td>{new Date(e.created_at).toLocaleString("ru-RU")}</td>
                <td>{e.performed_by_name}</td>
                <td>
                  {entityTypeLabelRu[e.entity_type] ?? e.entity_type}
                  {idToName.has(e.entity_id) ? `: ${idToName.get(e.entity_id)}` : ""}
                </td>
                <td>{actionLabelRu(e.action)}</td>
                <td>{e.reason}</td>
                <td>{formatState(e.before_state)}</td>
                <td>{formatState(e.after_state)}</td>
              </tr>
            ))}
            {filteredEntries.length === 0 && (
              <tr>
                <td colSpan={7} className="empty">
                  {entries?.length ? "Ничего не найдено по фильтру." : "Изменений пока нет."}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
